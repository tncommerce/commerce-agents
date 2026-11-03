"""Adversarial offline Awin Link Builder tests; no real network or affiliate clicks."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

PATH = Path(__file__).resolve().parents[1] / "scripts" / "review_dufynd_awin_linkbuilder.py"
spec = importlib.util.spec_from_file_location("review_awin", PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def fixture(**overrides):
    parameters = {
        "awinmid": "11672",
        "awinaffid": "3099222",
        "clickref": "one_million_example61_01",
        "ued": module.DESTINATION,
    }
    parameters.update(overrides)
    return "https://www.awin1.com/cread.php?" + urlencode(parameters)


class FakeResponse:
    def __init__(self, status=200, payload=None):
        self.status = status
        self.payload = payload if payload is not None else {"url": fixture()}

    def read(self, size):
        return json.dumps(self.payload).encode("utf-8")


class FakeConnection:
    def __init__(self, host, timeout):
        assert host == "api.awin.com" and timeout == 12
        self.sent = None
        self.closed = False

    def request(self, method, path, body, headers):
        self.sent = (method, path, json.loads(body), headers)

    def getresponse(self):
        return FakeResponse()

    def close(self):
        self.closed = True


class TestLinkBuilder(unittest.TestCase):
    def test_exact_request_contract(self):
        self.assertEqual(
            module.request_body(),
            {
                "advertiserId": 11672,
                "destinationUrl": module.DESTINATION,
                "parameters": {"clickref": "one_million_example61_01"},
                "shorten": False,
            },
        )

    def test_official_generated_link_identified_without_click(self):
        with patch.object(module.http.client, "HTTPSConnection", FakeConnection):
            result = module.fetch_from_awin("test-token-not-real")
        self.assertEqual(module.verify_generated_url(result["url"]), fixture())

    def test_wrong_identity_or_destination_rejected(self):
        bad = [
            fixture(awinmid="999"),
            fixture(awinaffid="333"),
            fixture(clickref="other"),
            fixture(ued="https://www.perfumetrader.de/"),
            fixture(p="https://example.com", ued=""),
            fixture().replace("www.awin1.com", "www.awin1.com.evil.test"),
            fixture().replace("https://", "http://", 1),
            fixture().replace("cread.php", "awclick.php"),
            fixture() + "#ignore",
            "https://www.awin1.com/cread.php",
            "",
        ]
        for url in bad:
            with self.subTest(url=url[:45]), self.assertRaises(module.VerificationError):
                module.verify_generated_url(url)

    def test_invalid_tokens_never_call_network(self):
        for token in ("", " ", "bad\r\ntoken"):
            with self.assertRaises(module.VerificationError):
                module.fetch_from_awin(token)

    def test_non_200_fails_closed(self):
        class Denied(FakeConnection):
            def getresponse(self):
                return FakeResponse(status=403)

        with patch.object(module.http.client, "HTTPSConnection", Denied):
            with self.assertRaises(module.VerificationError):
                module.fetch_from_awin("dummy")

    def test_private_receipt_created_once_without_stdout_url(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "receipt.json"
            result = module.write_private_receipt(p, {"url": fixture()})
            self.assertEqual(result["status"], "OFFICIAL_LINK_GENERATED_PRIVATE")
            saved = json.loads(p.read_text())
            self.assertTrue(saved["generated_url"].startswith("https://www.awin1.com/"))
            self.assertFalse(saved["production_activated"])
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(module.VerificationError):
                module.write_private_receipt(p, {"url": fixture()})

    def test_dry_run_does_not_touch_network(self):
        with patch.object(
            module.http.client,
            "HTTPSConnection",
            side_effect=AssertionError("network forbidden"),
        ):
            self.assertEqual(module.main([]), 0)


if __name__ == "__main__":
    unittest.main()
