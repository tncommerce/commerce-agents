from __future__ import annotations

import io
import json
import ssl
import subprocess
import sys
import warnings
from email.message import Message
from types import SimpleNamespace
from urllib.parse import urlencode
from urllib.response import addinfourl

import pytest
from scripts import dufynd_gmail_owner_reauthorize as helper

ORIGIN = "https://dufynd-private-observer-example-ew.a.run.app"
CLIENT_ID = "1234567890-example.apps.googleusercontent.com"
OWNER_KEY = "local-owner-key-for-offline-tests-only-0123456789"
STATE = "s" * 43
CHALLENGE = "c" * 43
MAILBOX = "owner@example.test"


def authorization_url(**changes):
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": ORIGIN + "/oauth/gmail/callback",
        "response_type": "code",
        "scope": helper.GMAIL_SCOPE,
        "access_type": "offline",
        "include_granted_scopes": "false",
        "prompt": "consent select_account",
        "login_hint": MAILBOX,
        "state": STATE,
        "code_challenge": CHALLENGE,
        "code_challenge_method": "S256",
    }
    params.update(changes)
    return helper.GOOGLE_AUTH_ENDPOINT + "?" + urlencode(params)


@pytest.fixture
def transport(monkeypatch):
    calls = []
    reads = []
    response = SimpleNamespace(
        code=200,
        body=json.dumps({"authorization_url": authorization_url()}).encode(),
        content_type="application/json",
        location=None,
        url=None,
        error=None,
    )

    class BoundedStream(io.BytesIO):
        def read(self, size=-1):
            reads.append(size)
            assert 0 <= size <= helper.MAX_RESPONSE_BYTES + 1
            return super().read(size)

    def https_open(handler, request):
        # The real urllib opener, error processor and redirect handler remain in
        # use. Only the HTTPS network boundary is replaced by a controlled stub.
        calls.append(
            {
                "request": request,
                "url": request.full_url,
                "method": request.get_method(),
                "data": request.data,
                "headers": dict(request.header_items()),
                "proxy": request.has_proxy(),
                "timeout": request.timeout,
                "context": handler._context,
            }
        )
        if response.error is not None:
            raise response.error
        headers = Message()
        headers["Content-Type"] = response.content_type
        if response.location:
            headers["Location"] = response.location
        result = addinfourl(
            BoundedStream(response.body), headers, response.url or request.full_url, response.code
        )
        result.msg = "controlled test response"
        return result

    monkeypatch.setattr(helper.HTTPSHandler, "https_open", https_open)
    return SimpleNamespace(calls=calls, reads=reads, response=response)


@pytest.fixture
def local_owner(monkeypatch):
    opened = []
    answers = iter(["ja", "ja"])
    monkeypatch.setattr(helper.sys.stdin, "isatty", lambda: True)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("BROWSER", raising=False)
    monkeypatch.delenv("SSLKEYLOGFILE", raising=False)
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    monkeypatch.setattr(helper.getpass, "getpass", lambda _prompt: OWNER_KEY)
    monkeypatch.setattr(
        helper,
        "graphical_browser",
        lambda: SimpleNamespace(open=lambda url, **kwargs: opened.append((url, kwargs)) or True),
    )
    return opened


def cli_args():
    return ["--broker-origin", ORIGIN, "--client-id", CLIENT_ID]


def assert_no_private_output(capsys):
    output = capsys.readouterr()
    for value in (OWNER_KEY, STATE, CHALLENGE, MAILBOX, authorization_url()):
        assert value not in output.out + output.err
    assert "Traceback" not in output.err
    return output


def test_real_broker_start_contract_is_accepted():
    from private_broker.runtime import OAuth

    config = SimpleNamespace(
        callback_logging_ready=True,
        client_id=CLIENT_ID,
        callback=ORIGIN + "/oauth/gmail/callback",
        mailbox=MAILBOX,
    )
    vault = SimpleNamespace(get=lambda _key: ({}, None), cas=lambda *_args: True)
    payload = OAuth(config, vault, None).start()
    assert helper.validate_authorization_url(payload["authorization_url"], ORIGIN, CLIENT_ID)


def test_exact_one_post_and_local_browser_only(transport, local_owner, capsys, monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://must-not-receive-owner-key.example.test:8080")
    monkeypatch.setenv("http_proxy", "http://must-not-receive-owner-key.example.test:8080")
    assert helper.main(cli_args()) == 0
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["url"] == ORIGIN + helper.START_PATH
    assert call["method"] == "POST" and call["data"] == b""
    assert call["headers"]["Authorization"] == "Bearer " + OWNER_KEY
    assert call["proxy"] is False
    assert call["timeout"] == helper.REQUEST_TIMEOUT_SECONDS
    assert call["context"].check_hostname is True
    assert call["context"].verify_mode == ssl.CERT_REQUIRED
    assert call["context"].keylog_filename is None
    assert call["request"].get_header("Authorization") is None
    assert transport.reads == [helper.MAX_RESPONSE_BYTES + 1]
    assert local_owner == [(authorization_url(), {"new": 2, "autoraise": True})]
    output = assert_no_private_output(capsys)
    assert "Google-Öffnung angefordert" in output.out
    assert (
        "Anmeldung bestätigt" in output.out
    )  # conditional callback instruction, no claim of success


@pytest.mark.parametrize("code", [301, 302, 303, 307, 308])
@pytest.mark.parametrize("target", ["https://attacker.example.test/steal", ORIGIN + "/other"])
def test_redirect_never_forwards_authorization(code, target, transport, local_owner, capsys):
    transport.response.code = code
    transport.response.location = target
    transport.response.body = (OWNER_KEY + STATE).encode()
    assert helper.main(cli_args()) == 1
    assert len(transport.calls) == 1
    assert transport.calls[0]["url"] == ORIGIN + helper.START_PATH
    assert local_owner == []
    output = assert_no_private_output(capsys)
    assert "Weiterleitung" in output.err


@pytest.mark.parametrize("code", [401, 403, 429, 500, 503])
def test_http_failure_is_redacted_without_retry(code, transport, local_owner, capsys):
    transport.response.code = code
    transport.response.body = (OWNER_KEY + STATE).encode()
    assert helper.main(cli_args()) == 1
    assert len(transport.calls) == 1
    assert transport.reads == []
    assert local_owner == []
    assert_no_private_output(capsys)


def test_transport_exception_never_echoes_secret_or_retries(transport, local_owner, capsys):
    transport.response.error = OSError("transport included " + OWNER_KEY + authorization_url())
    assert helper.main(cli_args()) == 1
    assert len(transport.calls) == 1
    assert local_owner == []
    assert_no_private_output(capsys)


@pytest.mark.parametrize(
    "body",
    [
        b"x" * (helper.MAX_RESPONSE_BYTES + 1),
        b"{not json}",
        b"[]",
        b'{"authorization_url":null}',
        b'{"authorization_url":"one","authorization_url":"two"}',
        json.dumps({"authorization_url": authorization_url(), "access_token": OWNER_KEY}).encode(),
    ],
)
def test_bad_or_oversized_response_never_opens_browser(body, transport, local_owner, capsys):
    transport.response.body = body
    assert helper.main(cli_args()) == 1
    assert len(transport.calls) == 1
    assert transport.reads == [helper.MAX_RESPONSE_BYTES + 1]
    assert local_owner == []
    assert_no_private_output(capsys)


@pytest.mark.parametrize("field,value", [("content_type", "text/html"), ("url", ORIGIN + "/other")])
def test_response_origin_and_type_fail_closed(field, value, transport, local_owner, capsys):
    setattr(transport.response, field, value)
    assert helper.main(cli_args()) == 1
    assert transport.reads == []
    assert local_owner == []
    assert_no_private_output(capsys)


@pytest.mark.parametrize(
    "change",
    [
        {"client_id": "different.apps.googleusercontent.com"},
        {"redirect_uri": "https://attacker.example.test/oauth/gmail/callback"},
        {"redirect_uri": ORIGIN + "/oauth/gmail/callback/"},
        {"scope": "https://www.googleapis.com/auth/gmail.readonly"},
        {"scope": helper.GMAIL_SCOPE + " openid"},
        {"response_type": "token"},
        {"access_type": "online"},
        {"include_granted_scopes": "true"},
        {"prompt": "none"},
        {"code_challenge_method": "plain"},
        {"code_challenge": "short"},
        {"state": "short"},
        {"login_hint": "not-an-address"},
        {"unregistered_parameter": "value"},
    ],
)
def test_oauth_contract_mismatch_is_rejected(change):
    with pytest.raises(helper.OwnerFlowError, match="invalid_response"):
        helper.validate_authorization_url(authorization_url(**change), ORIGIN, CLIENT_ID)


@pytest.mark.parametrize(
    "bad_url",
    [
        authorization_url().replace("https:", "http:", 1),
        authorization_url().replace("accounts.google.com", "accounts.google.com.attacker.test"),
        authorization_url().replace("accounts.google.com", "user@accounts.google.com"),
        authorization_url().replace("accounts.google.com", "accounts.google.com:443"),
        authorization_url().replace("/o/oauth2/v2/auth", "/o/oauth2/v2/auth/"),
        authorization_url() + "&state=" + STATE,
        authorization_url() + "&%73cope=" + helper.GMAIL_SCOPE,
        authorization_url() + "#fragment",
        authorization_url() + "#",
        authorization_url() + "&bad=%zz",
        "\n" + authorization_url(),
        "javascript:alert(1)",
    ],
)
def test_oauth_destination_and_encoding_rejected(bad_url):
    with pytest.raises(helper.OwnerFlowError, match="invalid_response"):
        helper.validate_authorization_url(bad_url, ORIGIN, CLIENT_ID)


@pytest.mark.parametrize(
    "origin",
    [
        ORIGIN.replace("https:", "http:"),
        ORIGIN + "/",
        ORIGIN + "?",
        ORIGIN + "#",
        ORIGIN + "?token=wrong",
        ORIGIN + ":443",
        ORIGIN.replace("https://", "https://user@"),
        "https://127.0.0.1",
        "https://localhost",
        "https://attacker.example.test",
        "https://other-service.run.app",
        "https://dufynd-private-observer-good.run.app.attacker.test",
        "\n" + ORIGIN,
        ORIGIN.replace(".run.app", ".run.app."),
    ],
)
def test_bad_origin_has_no_secret_prompt_or_network(origin, monkeypatch, transport, capsys):
    monkeypatch.setattr(helper.getpass, "getpass", lambda _prompt: pytest.fail("secret prompt"))
    assert helper.main(["--broker-origin", origin, "--client-id", CLIENT_ID]) == 1
    assert transport.calls == []
    assert_no_private_output(capsys)


@pytest.mark.parametrize(
    "key", ["short", OWNER_KEY + "\n", OWNER_KEY + "\rInjected: value", "x" * 513]
)
def test_invalid_key_rejected_before_transport(key, transport):
    with pytest.raises(helper.OwnerFlowError, match="invalid_owner_key"):
        helper.start_once(ORIGIN, CLIENT_ID, key)
    assert transport.calls == []


def test_unknown_secret_cli_argument_is_not_reflected(capsys, transport):
    with pytest.raises(SystemExit) as exc:
        helper.main(cli_args() + ["--owner-key", OWNER_KEY])
    assert exc.value.code == 2
    assert transport.calls == []
    assert_no_private_output(capsys)


def test_noninteractive_terminal_rejected_before_secret(monkeypatch, transport, capsys):
    monkeypatch.setattr(helper.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(helper.getpass, "getpass", lambda _prompt: pytest.fail("secret prompt"))
    assert helper.main(cli_args()) == 1
    assert transport.calls == []
    assert_no_private_output(capsys)


def test_getpass_echo_fallback_is_an_error(monkeypatch, local_owner, transport, capsys):
    def unsafe_getpass(_prompt):
        warnings.warn("unavailable", helper.getpass.GetPassWarning, stacklevel=1)
        pytest.fail("echoing fallback must never read the key")

    monkeypatch.setattr(helper.getpass, "getpass", unsafe_getpass)
    assert helper.main(cli_args()) == 1
    assert transport.calls == []
    assert_no_private_output(capsys)


@pytest.mark.parametrize("answers,post_count", [(["nein"], 0), (["ja", "nein"], 1)])
def test_both_owner_confirmations_are_respected(
    answers, post_count, monkeypatch, local_owner, transport, capsys
):
    values = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _prompt: next(values))
    assert helper.main(cli_args()) == 1
    assert len(transport.calls) == post_count
    assert local_owner == []
    assert_no_private_output(capsys)


def test_expired_session_not_opened_or_retried(monkeypatch, local_owner, transport, capsys):
    moments = iter([0, helper.OPEN_DEADLINE_SECONDS])
    monkeypatch.setattr(helper.time, "monotonic", lambda: next(moments))
    assert helper.main(cli_args()) == 1
    assert len(transport.calls) == 1
    assert local_owner == []
    assert_no_private_output(capsys)


def test_browser_failure_does_not_print_url(monkeypatch, local_owner, transport, capsys):
    def fail_open(url, **_kwargs):
        raise RuntimeError(url + OWNER_KEY)

    monkeypatch.setattr(helper, "graphical_browser", lambda: SimpleNamespace(open=fail_open))
    assert helper.main(cli_args()) == 1
    assert len(transport.calls) == 1
    assert_no_private_output(capsys)


def test_browser_override_is_never_executed(monkeypatch):
    monkeypatch.setenv("BROWSER", "echo %s")
    monkeypatch.setattr(
        helper.subprocess, "Popen", lambda *_a, **_k: pytest.fail("browser override")
    )
    with pytest.raises(helper.OwnerFlowError, match="browser_override"):
        helper.graphical_browser()


def test_windows_uses_explicit_native_browser(monkeypatch):
    monkeypatch.delenv("BROWSER", raising=False)
    monkeypatch.delenv("SSLKEYLOGFILE", raising=False)
    monkeypatch.setattr(helper.sys, "platform", "win32")
    calls = []
    monkeypatch.setattr(helper.os, "startfile", lambda *args: calls.append(args), raising=False)
    monkeypatch.setattr(
        helper.subprocess, "Popen", lambda *_a, **_k: pytest.fail("shell execution")
    )
    assert helper.graphical_browser().open(authorization_url()) is True
    assert calls == [(authorization_url(), "open")]


def test_headless_session_never_falls_back_to_terminal_browser(monkeypatch):
    for name in ("BROWSER", "DISPLAY", "WAYLAND_DISPLAY", "SSLKEYLOGFILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(helper.sys, "platform", "linux")
    monkeypatch.setattr(
        helper.subprocess, "Popen", lambda *_a, **_k: pytest.fail("terminal browser")
    )
    with pytest.raises(helper.OwnerFlowError, match="browser_unavailable"):
        helper.graphical_browser()


@pytest.mark.parametrize("empty_setting", [False, True])
def test_tls_keylogging_blocks_before_hidden_input_or_file_creation(
    empty_setting, tmp_path, monkeypatch, local_owner, transport, capsys
):
    keylog = tmp_path / "tls-session-keys.log"
    monkeypatch.setenv("SSLKEYLOGFILE", "" if empty_setting else str(keylog))
    monkeypatch.setattr(helper.getpass, "getpass", lambda _prompt: pytest.fail("secret prompt"))
    assert helper.main(cli_args()) == 1
    assert transport.calls == []
    assert local_owner == []
    assert not keylog.exists()
    output = assert_no_private_output(capsys)
    assert str(keylog) not in output.out + output.err
    assert "TLS-Keylogging" in output.err


def test_tls_keylogging_also_blocks_direct_transport_without_touching_file(
    tmp_path, monkeypatch, transport
):
    keylog = tmp_path / "existing-diagnostic.log"
    keylog.write_text("unchanged marker", encoding="utf-8")
    monkeypatch.setenv("SSLKEYLOGFILE", str(keylog))
    with pytest.raises(helper.OwnerFlowError, match="tls_keylogging"):
        helper.start_once(ORIGIN, CLIENT_ID, OWNER_KEY)
    assert transport.calls == []
    assert keylog.read_text(encoding="utf-8") == "unchanged marker"


def test_tls_keylogging_enabled_after_prompt_still_prevents_send(
    tmp_path, monkeypatch, local_owner, transport, capsys
):
    keylog = tmp_path / "late-diagnostic.log"

    def enter_key(_prompt):
        monkeypatch.setenv("SSLKEYLOGFILE", str(keylog))
        return OWNER_KEY

    monkeypatch.setattr(helper.getpass, "getpass", enter_key)
    assert helper.main(cli_args()) == 1
    assert transport.calls == []
    assert local_owner == []
    assert not keylog.exists()
    assert_no_private_output(capsys)


def test_tls_context_does_not_use_environment_aware_default_factory(monkeypatch, transport):
    monkeypatch.delenv("SSLKEYLOGFILE", raising=False)
    monkeypatch.delenv("BROWSER", raising=False)
    monkeypatch.setattr(
        helper.ssl, "create_default_context", lambda: pytest.fail("environment-aware TLS factory")
    )
    assert helper.start_once(ORIGIN, CLIENT_ID, OWNER_KEY) == authorization_url()
    context = transport.calls[0]["context"]
    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.keylog_filename is None
    assert context.cert_store_stats()["x509_ca"] > 0


def test_tls_keylogging_blocks_browser_if_enabled_after_post(tmp_path, monkeypatch):
    keylog = tmp_path / "browser-diagnostic.log"
    monkeypatch.setenv("SSLKEYLOGFILE", str(keylog))
    monkeypatch.setattr(helper.subprocess, "Popen", lambda *_a, **_k: pytest.fail("browser launch"))
    with pytest.raises(helper.OwnerFlowError, match="tls_keylogging"):
        helper.LocalBrowser("/usr/bin/xdg-open").open(authorization_url())
    assert not keylog.exists()


@pytest.mark.parametrize(
    "platform,command", [("linux", "/usr/bin/xdg-open"), ("darwin", "/usr/bin/open")]
)
@pytest.mark.parametrize("exit_status", [0, 23])
def test_native_launchers_cannot_echo_oauth_url_or_read_terminal(
    platform, command, exit_status, tmp_path, monkeypatch, capfd
):
    # Exercise actual subprocess stdio inheritance. The OS launcher executable
    # alone is substituted with a hostile child that writes its URL to both fds.
    # No browser, network, credential or genuine OAuth session is involved.
    executable = sys.executable
    child = tmp_path / "hostile_desktop_launcher.py"
    child.write_text(
        "import sys\n"
        "assert sys.stdin.read() == ''\n"
        "print(sys.argv[1], flush=True)\n"
        "print(sys.argv[1], file=sys.stderr, flush=True)\n"
        f"raise SystemExit({exit_status})\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("BROWSER", raising=False)
    monkeypatch.delenv("SSLKEYLOGFILE", raising=False)
    monkeypatch.setenv("DISPLAY", ":offline-test")
    monkeypatch.setattr(helper.sys, "platform", platform)
    original_isfile = helper.os.path.isfile
    original_access = helper.os.access
    monkeypatch.setattr(
        helper.os.path, "isfile", lambda path: path == command or original_isfile(path)
    )
    monkeypatch.setattr(
        helper.os, "access", lambda path, mode: path == command or original_access(path, mode)
    )
    real_popen = subprocess.Popen
    launches = []

    def controlled_launcher(args, **kwargs):
        launches.append((args, kwargs))
        assert args == [command, authorization_url()]
        return real_popen([executable, str(child), args[1]], **kwargs)

    monkeypatch.setattr(helper.subprocess, "Popen", controlled_launcher)
    assert helper.graphical_browser().open(authorization_url()) is (exit_status == 0)
    assert len(launches) == 1
    kwargs = launches[0][1]
    assert kwargs["stdin"] == kwargs["stdout"] == kwargs["stderr"] == subprocess.DEVNULL
    assert kwargs["shell"] is False
    assert kwargs["close_fds"] is True
    output = capfd.readouterr()
    assert output.out == output.err == ""
