#!/usr/bin/env python3
"""Bounded, read-only evidence of the 57 public DUFYND fragrance routes.

No merchant URL, tracking redirect, authenticated endpoint, image or API is fetched.
This probe does not assert traffic, indexing by Google, or a commission.
"""

from __future__ import annotations

import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from xml.etree import ElementTree

ORIGIN = "https://dufynd.de"
ROOT = Path(__file__).resolve().parents[1]
MAX_READ = 262_144
ROUTE = re.compile(r"/duft/[a-z0-9]+(?:-[a-z0-9]+)*")


class SameOriginRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        source = urlsplit(req.full_url)
        target = urlsplit(newurl)
        if (
            target.scheme != "https"
            or target.netloc != "dufynd.de"
            or source.path.rstrip("/") != target.path.rstrip("/")
            or target.query
            or target.fragment
        ):
            raise ValueError("Unexpected redirect outside the exact public route")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


OPENER = build_opener(SameOriginRedirect)


def fetch_public(path: str) -> tuple[str, str]:
    if path != "/sitemap.xml" and not ROUTE.fullmatch(path):
        raise ValueError("Only the sitemap and approved fragrance routes may be read")
    request = Request(
        ORIGIN + path,
        headers={
            "Accept-Encoding": "identity",
            "User-Agent": "DUFYND-Public-Release-Read/1.0 (no merchant clicks)",
        },
    )
    with OPENER.open(request, timeout=12) as response:
        final = urlsplit(response.geturl())
        if (
            final.scheme != "https"
            or final.netloc != "dufynd.de"
            or final.path.rstrip("/") != path
            or final.query
            or final.fragment
        ):
            raise ValueError("Public request ended at an unexpected URL")
        if response.status != 200:
            raise ValueError(f"Unexpected HTTP {response.status}")
        media_type = response.headers.get_content_type()
        body = response.read(MAX_READ)
        return media_type, body.decode("utf-8", errors="replace")


class Head(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.canonical: list[str] = []
        self.robots: list[str] = []
        self.inside_head = False
        self.inside_title = False
        self.closed_head = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "head":
            self.inside_head = True
        if not self.inside_head:
            return
        a = dict(attrs)
        if tag == "title":
            self.inside_title = True
        if tag == "link" and "canonical" in (a.get("rel") or "").split() and a.get("href"):
            self.canonical.append(a["href"])
        if tag == "meta" and (a.get("name") or "").lower() == "robots":
            self.robots.append(a.get("content") or "")

    def handle_data(self, data: str) -> None:
        if self.inside_head and self.inside_title:
            self.title += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.inside_title = False
        if tag == "head":
            self.inside_head = False
            self.closed_head = True


def review_paths() -> set[str]:
    data = json.loads(
        (ROOT / "examples/retail/storefront-web/lib/generated/released-profiles.json").read_text(
            encoding="utf-8"
        )
    )["profiles"]
    approvals = json.loads(
        (ROOT / "examples/retail/data/dufynd_release_authorizations.json").read_text(
            encoding="utf-8"
        )
    )["approvals"]
    if len(data) != 20 or len(approvals) != 20:
        raise ValueError("Release evidence is not exactly the approved 20-profile wave")
    approved = {
        row["product_id"]
        for row in approvals
        if row["publication_approved"] is True and row["indexing_approved"] is True
    }
    if len(approved) != 20 or approved != {row["product_id"] for row in data}:
        raise ValueError("Released profile authorization is incomplete")
    paths = {row["seo"]["public_path"] for row in data}
    if len(paths) != 20 or any(not ROUTE.fullmatch(p) for p in paths):
        raise ValueError("Release paths are not 20 unique exact perfume routes")
    return paths


def sitemap_paths(xml: str) -> set[str]:
    root = ElementTree.fromstring(xml)
    if root.tag.rsplit("}", 1)[-1] != "urlset":
        raise ValueError("Not a URL sitemap")
    perfume_paths: list[str] = []
    for el in root.iter():
        if el.tag.rsplit("}", 1)[-1] != "loc" or not el.text:
            continue
        url = urlsplit(el.text.strip())
        if url.path.startswith("/duft/"):
            if url.scheme != "https" or url.netloc != "dufynd.de":
                raise ValueError("Sitemap perfume URL has a non-canonical host")
            if url.query or url.fragment:
                raise ValueError("Sitemap perfume URL contains tracking parameters")
            path = url.path.rstrip("/")
            if not ROUTE.fullmatch(path):
                raise ValueError("Sitemap perfume route is not a clean slug")
            perfume_paths.append(path)
    if len(perfume_paths) != len(set(perfume_paths)):
        raise ValueError("Duplicate fragrance URL in sitemap")
    return set(perfume_paths)


def check_page(path: str, approved_paths: set[str]) -> str | None:
    try:
        media_type, content = fetch_public(path)
        if media_type != "text/html":
            return f"{path}: unexpected media type {media_type}"
        head = Head()
        head.feed(content)
        if not head.closed_head or not head.title.strip():
            return f"{path}: missing parsed HTML head or title"
        if len(head.canonical) != 1:
            return f"{path}: expected exactly one canonical link"
        canonical = urlsplit(urljoin(ORIGIN, head.canonical[0]))
        if (
            canonical.scheme != "https"
            or canonical.netloc != "dufynd.de"
            or canonical.path.rstrip("/") != path
            or canonical.query
            or canonical.fragment
        ):
            return f"{path}: wrong canonical"
        robots = {token.strip().lower() for entry in head.robots for token in entry.split(",")}
        if "noindex" in robots or "none" in robots:
            return f"{path}: live noindex conflicts with published sitemap"
        if path in approved_paths and "index" not in robots:
            return f"{path}: newly released wave missing explicit index directive"
        return None
    except Exception as exc:  # noqa: BLE001 - deterministic fail-closed receipt
        return f"{path}: {type(exc).__name__}: {str(exc)[:110]}"


def main() -> int:
    try:
        approved = review_paths()
        media_type, xml = fetch_public("/sitemap.xml")
        if media_type not in {"application/xml", "text/xml"}:
            raise ValueError(f"Sitemap has unexpected media type: {media_type}")
        paths = sitemap_paths(xml)
        if len(paths) != 57 or not approved.issubset(paths):
            raise ValueError(
                f"Sitemap mismatch: {len(paths)} perfume pages; "
                f"approved wave present={len(approved & paths)}/20; expected 57/20"
            )
        with ThreadPoolExecutor(max_workers=4) as pool:
            failures = sorted(
                error
                for error in pool.map(lambda path: check_page(path, approved), sorted(paths))
                if error is not None
            )
        receipt = {
            "result": "PASS" if not failures else "FAIL",
            "live_perfume_sitemap_urls": len(paths),
            "new_approved_wave_pages": len(approved),
            "html_pages_checked": len(paths),
            "failed_pages": len(failures),
            "failures": failures[:12],
            "method": "bounded read-only GET of sitemap and exact public pages; no link following",
            "source_commit": os.environ.get("GITHUB_SHA", "local"),
        }
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
        return 1 if failures else 0
    except Exception as exc:  # noqa: BLE001 - no silent partial success
        print(
            json.dumps(
                {"result": "FAIL", "reason": f"{type(exc).__name__}: {str(exc)[:160]}"},
                ensure_ascii=False,
            )
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
