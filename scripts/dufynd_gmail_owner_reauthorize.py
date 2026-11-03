#!/usr/bin/env python3
"""Start one Gmail renewal from the owner's local, interactive desktop.

Standard library only. The owner key is read with hidden terminal input; it is
never accepted as an argument, loaded from an environment/file or printed. This
client opens a validated Google consent URL only after a second local confirmation.
It does not perform consent, inspect the callback, poll, retry or deploy anything.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import ssl
import subprocess
import sys
import time
import warnings
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.metadata"
GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
START_PATH = "/owner/oauth/gmail/start"
MAX_RESPONSE_BYTES = 16_384
REQUEST_TIMEOUT_SECONDS = 15
LAUNCH_WAIT_SECONDS = 5
OPEN_DEADLINE_SECONDS = 570  # Broker state lasts 600 seconds; leave a small margin.

MESSAGES = {
    "invalid_configuration": "Broker-Origin oder öffentliche Client-ID ist ungültig.",
    "local_terminal_required": "Bitte in einem privaten lokalen Terminal am eigenen Desktop starten.",
    "hidden_input_required": "Verdeckte Schlüsseleingabe ist hier nicht verfügbar; Abbruch.",
    "invalid_owner_key": "Der verdeckt eingegebene Owner-Key hat kein gültiges Format.",
    "browser_unavailable": "Ein unterstützter lokaler grafischer Browser ist nicht verfügbar.",
    "browser_override": "BROWSER-Umgebungsüberschreibung entfernen und lokal erneut starten.",
    "tls_keylogging": "TLS-Keylogging ist konfiguriert; SSLKEYLOGFILE vor dem lokalen Start entfernen.",
    "redirect_blocked": "Der Broker antwortete mit einer Weiterleitung; sie wurde blockiert.",
    "owner_start_rejected": "Der Broker hat den privaten Start abgelehnt; keine Wiederholung erfolgt.",
    "start_failed": "Der private Start ist fehlgeschlagen; Antwortdetails werden nicht ausgegeben.",
    "invalid_response": "Die Broker-Antwort entspricht nicht dem erlaubten Google-Consent-Vertrag.",
    "session_expired": "Die vorbereitete Sitzung ist zu alt; kein Browser wurde geöffnet.",
    "browser_failed": "Der lokale Browser konnte nicht geöffnet werden; der Link bleibt privat.",
    "cancelled": "Abgebrochen. Es erfolgt keine automatische Wiederholung.",
}


class OwnerFlowError(Exception):
    """Only a fixed, non-sensitive reason may leave the local flow."""


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse normally echoes unknown arguments, including an accidentally
        # supplied secret. Reject them without reflecting any supplied value.
        self.print_usage(sys.stderr)
        self.exit(2, "Ungültige Argumente. Owner-Keys gehören nur in die verdeckte Eingabe.\n")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        fp.close()
        raise OwnerFlowError("redirect_blocked")


def validate_configuration(origin: str, client_id: str) -> None:
    """Accept the existing service's HTTPS origin, never a path or proxy URL."""
    try:
        parsed = urlsplit(origin)
        host = parsed.hostname or ""
        if (
            not origin.isascii()
            or any(ord(char) <= 32 or ord(char) == 127 for char in origin)
            or len(origin) > 512
            or parsed.scheme != "https"
            or parsed.netloc != host
            or origin != "https://" + host
            or parsed.path
            or parsed.query
            or parsed.fragment
            or not host.startswith("dufynd-private-observer-")
            or not host.endswith(".run.app")
            or not re.fullmatch(r"[a-z0-9]+(?:[-.][a-z0-9]+)*", host)
            or len(client_id) > 256
            or not re.fullmatch(r"[A-Za-z0-9_-]+\.apps\.googleusercontent\.com", client_id)
        ):
            raise ValueError
    except (TypeError, ValueError):
        raise OwnerFlowError("invalid_configuration") from None


def check_private_environment() -> None:
    # create_default_context() and some browsers inherit this logging setting.
    # Reject it before hidden input and again at the transport/launch boundaries.
    if "SSLKEYLOGFILE" in os.environ:
        raise OwnerFlowError("tls_keylogging")
    if os.environ.get("BROWSER"):
        raise OwnerFlowError("browser_override")


class LocalBrowser:
    """Native desktop launcher with no inherited input or diagnostic output."""

    def __init__(self, command: str | None):
        self.command = command

    def open(self, url: str, *, new=2, autoraise=True) -> bool:
        del new, autoraise  # The owner's native browser controls its tab/window choice.
        check_private_environment()
        if self.command is None:
            # Use Windows' native URL association, not a shell command. No owner
            # key is passed to the operating-system launcher.
            os.startfile(url, "open")
            return True
        process = subprocess.Popen(
            [self.command, url],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            close_fds=True,
            start_new_session=True,
        )
        try:
            return process.wait(timeout=LAUNCH_WAIT_SECONDS) == 0
        except subprocess.TimeoutExpired:
            # Some desktop launchers remain attached to a running browser. A
            # launch request is all this client can attest; never print the URL.
            return True


def graphical_browser():
    """Select a fixed OS launcher, never PATH/BROWSER or a terminal browser."""
    check_private_environment()
    if sys.platform == "win32":
        if not hasattr(os, "startfile"):
            raise OwnerFlowError("browser_unavailable")
        return LocalBrowser(None)
    elif sys.platform == "darwin":
        command = "/usr/bin/open"
    elif sys.platform.startswith("linux") and (
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    ):
        command = "/usr/bin/xdg-open"
    else:
        raise OwnerFlowError("browser_unavailable")
    if not os.path.isfile(command) or not os.access(command, os.X_OK):
        raise OwnerFlowError("browser_unavailable")
    return LocalBrowser(command)


def validate_owner_key(key: str) -> None:
    if not isinstance(key, str) or not 32 <= len(key) <= 512:
        raise OwnerFlowError("invalid_owner_key")
    if any(not 33 <= ord(char) <= 126 for char in key):
        raise OwnerFlowError("invalid_owner_key")


def hidden_owner_key() -> str:
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        try:
            key = getpass.getpass("Privater Owner-Key (Eingabe bleibt unsichtbar): ")
        except getpass.GetPassWarning:
            raise OwnerFlowError("hidden_input_required") from None
    validate_owner_key(key)
    return key


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise OwnerFlowError("invalid_response")
        result[key] = value
    return result


def validate_authorization_url(url: object, origin: str, client_id: str) -> str:
    if (
        not isinstance(url, str)
        or len(url) > 8_192
        or not url.isascii()
        or any(ord(char) <= 32 or ord(char) == 127 for char in url)
        or "#" in url
        or re.search(r"%(?![0-9A-Fa-f]{2})", url)
    ):
        raise OwnerFlowError("invalid_response")
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "accounts.google.com"
            or parsed.path != "/o/oauth2/v2/auth"
            or parsed.fragment
        ):
            raise ValueError
        params = unique_object(parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True))
    except ValueError:
        raise OwnerFlowError("invalid_response") from None
    fixed = {
        "client_id": client_id,
        "redirect_uri": origin + "/oauth/gmail/callback",
        "response_type": "code",
        "scope": GMAIL_SCOPE,
        "access_type": "offline",
        "include_granted_scopes": "false",
        "prompt": "consent select_account",
        "code_challenge_method": "S256",
    }
    if (
        set(params) != set(fixed) | {"state", "code_challenge", "login_hint"}
        or any(params.get(key) != value for key, value in fixed.items())
        or not re.fullmatch(r"[A-Za-z0-9_-]{43}", params.get("state", ""))
        or not re.fullmatch(r"[A-Za-z0-9_-]{43}", params.get("code_challenge", ""))
        or not re.fullmatch(
            r"[^\s@\x00-\x1f\x7f]{1,128}@[^\s@\x00-\x1f\x7f]{1,128}", params.get("login_hint", "")
        )
    ):
        raise OwnerFlowError("invalid_response")
    return url


def start_once(origin: str, client_id: str, owner_key: str) -> str:
    """One HTTPS POST, no proxy inheritance, redirect, retry or raw error output."""
    check_private_environment()
    validate_configuration(origin, client_id)
    validate_owner_key(owner_key)
    endpoint = origin + START_PATH
    # Do not use create_default_context(): it can set keylog_filename from
    # SSLKEYLOGFILE. Retain certificate/hostname validation and system roots.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    context.load_default_certs(ssl.Purpose.SERVER_AUTH)
    context.keylog_filename = None
    opener = build_opener(ProxyHandler({}), NoRedirect(), HTTPSHandler(context=context))
    request = Request(
        endpoint,
        data=b"",
        headers={
            "Authorization": "Bearer " + owner_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            if (
                response.status != 200
                or response.geturl() != endpoint
                or response.headers.get_content_type() != "application/json"
            ):
                raise OwnerFlowError("invalid_response")
            body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise OwnerFlowError("invalid_response")
        payload = json.loads(body.decode("utf-8"), object_pairs_hook=unique_object)
        if not isinstance(payload, dict) or set(payload) != {"authorization_url"}:
            raise OwnerFlowError("invalid_response")
        return validate_authorization_url(payload["authorization_url"], origin, client_id)
    except HTTPError as exc:
        code = exc.code
        exc.close()
        if 300 <= code < 400:
            raise OwnerFlowError("redirect_blocked") from None
        if code in {401, 403}:
            raise OwnerFlowError("owner_start_rejected") from None
        raise OwnerFlowError("start_failed") from None
    except (UnicodeError, ValueError):
        raise OwnerFlowError("invalid_response") from None
    except OwnerFlowError:
        raise
    except Exception:
        raise OwnerFlowError("start_failed") from None
    finally:
        request.remove_header("Authorization")


def main(argv=None) -> int:
    parser = SafeArgumentParser(
        description="Einmalige Gmail-Neuverknüpfung im privaten lokalen Owner-Kontext.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--broker-origin", required=True, help="Vorhandener BROKER_ORIGIN, ohne Pfad"
    )
    parser.add_argument(
        "--client-id", required=True, help="Vorhandene öffentliche GOOGLE_CLIENT_ID"
    )
    args = parser.parse_args(argv)
    try:
        check_private_environment()
        validate_configuration(args.broker_origin, args.client_id)
        if not sys.stdin.isatty() or os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
            raise OwnerFlowError("local_terminal_required")
        browser = graphical_browser()
        print("Ziel des privaten Starts: " + args.broker_origin)
        if input("Einmalige Gmail-Neuverknüpfung jetzt starten? [ja/NEIN] ").strip() != "ja":
            raise OwnerFlowError("cancelled")
        owner_key = hidden_owner_key()
        started = time.monotonic()
        try:
            authorization_url = start_once(args.broker_origin, args.client_id, owner_key)
        finally:
            del owner_key
        if input("Google-Link ist geprüft. Im lokalen Browser öffnen? [ja/NEIN] ").strip() != "ja":
            raise OwnerFlowError("cancelled")
        if time.monotonic() - started >= OPEN_DEADLINE_SECONDS:
            raise OwnerFlowError("session_expired")
        try:
            opened = browser.open(authorization_url, new=2, autoraise=True)
        except Exception:
            raise OwnerFlowError("browser_failed") from None
        if not opened:
            raise OwnerFlowError("browser_failed")
        print(
            'Google-Öffnung angefordert. Freigabe selbst abschließen; nur bei {"status":"authorized"} '
            "ist die Anmeldung bestätigt. Keine URLs, Codes oder Schlüssel teilen."
        )
        return 0
    except OwnerFlowError as exc:
        reason = exc.args[0] if exc.args else "start_failed"
        print(MESSAGES.get(reason, MESSAGES["start_failed"]), file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print(MESSAGES["cancelled"], file=sys.stderr)
        return 1
    except Exception:
        print(MESSAGES["start_failed"], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
