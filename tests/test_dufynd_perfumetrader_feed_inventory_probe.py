from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import probe_dufynd_perfumetrader_feed_inventory as probe

KEY = "fixture-secret/never-log"
HEADER = "Advertiser ID,Advertiser Name,Primary Region,Membership Status,Feed ID,Feed Name,Language,Last Imported,URL\n"
TARGET = "11672,Perfumetrader,DE,Joined,99999,Default,German,2026-10-30 09:00:00,https://datafeed.api.productserve.com/datafeed/download/apikey/fixture-secret%2Fnever-log/fid/99999/format/csv/\n"
OTHER = "31081,top Parfümerie,DE,Joined,91379,Default,German,2026-10-30 09:00:00,https://example.invalid/not-requested\n"


class InventoryProbeTests(unittest.TestCase):
    def test_only_target_inventory_and_one_identity_bound_list_read(self):
        with patch.object(
            probe, "_read_url", return_value=(HEADER + OTHER + TARGET).encode()
        ) as read:
            report = probe.probe_inventory(KEY)
        read.assert_called_once_with(
            "https://productdata.awin.com/datafeed/list/apikey/fixture-secret%2Fnever-log",
            max_bytes=probe.DEFAULT_LIST_MAX_BYTES,
            expected_list_api_key=KEY,
        )
        self.assertEqual(report["status"], "FEEDS_LISTED_REVIEW_ONLY")
        self.assertEqual(report["feed_count"], 1)
        self.assertEqual(report["feeds"][0]["advertiser_id"], "11672")
        self.assertEqual(report["feeds"][0]["feed_id"], "99999")
        self.assertTrue(report["feeds"][0]["joined"])
        self.assertFalse(report["product_feed_downloaded"])
        self.assertFalse(report["image_publication_allowed"])
        output = json.dumps(report)
        self.assertNotIn("31081", output)
        self.assertNotIn("https://", output)
        self.assertNotIn("fixture-secret", output)

    def test_successful_empty_inventory_is_not_claimed_as_http_failure(self):
        with patch.object(probe, "_read_url", return_value=(HEADER + OTHER).encode()) as read:
            report = probe.probe_inventory(KEY)
        self.assertEqual(report["status"], "NO_FEEDS_LISTED_FOR_ADVERTISER")
        self.assertEqual(report["feeds"], [])
        self.assertEqual(report["feed_count"], 0)
        self.assertEqual(read.call_count, 1)

    def test_missing_key_produces_safe_machine_readable_blocker_without_request(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(probe, "_read_url") as read,
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            status = probe.main()
        read.assert_not_called()
        self.assertEqual(status, 2)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "BLOCKED_CREDENTIAL_MISSING")
        self.assertEqual(stderr.getvalue(), "")

    def test_request_failure_never_prints_exception_or_credential(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            patch.dict("os.environ", {probe.KEY_ENV: KEY}, clear=True),
            patch.object(
                probe, "_read_url", side_effect=RuntimeError("https://example.invalid/" + KEY)
            ),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            status = probe.main()
        self.assertEqual(status, 2)
        self.assertEqual(
            json.loads(stdout.getvalue())["status"], "BLOCKED_INVENTORY_READ_OR_PARSE_FAILED"
        )
        self.assertNotIn(KEY, stdout.getvalue() + stderr.getvalue())
        self.assertNotIn("https://", stdout.getvalue() + stderr.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_reflected_key_or_url_in_metadata_is_redacted(self):
        row = TARGET.replace("Perfumetrader", KEY).replace(
            "Default", "https://example.invalid/feed"
        )
        with patch.object(probe, "_read_url", return_value=(HEADER + row).encode()):
            report = probe.probe_inventory(KEY)
        self.assertEqual(report["feeds"][0]["advertiser_name"], "[redacted]")
        self.assertEqual(report["feeds"][0]["feed_name"], "[redacted]")
        self.assertNotIn(KEY, json.dumps(report))

    def test_readable_error_document_cannot_claim_advertiser_has_no_feeds(self):
        for payload in (b"error\nAccess denied\n", HEADER.encode()):
            stdout = io.StringIO()
            with self.subTest(payload=payload):
                with (
                    patch.dict("os.environ", {probe.KEY_ENV: KEY}, clear=True),
                    patch.object(probe, "_read_url", return_value=payload),
                    contextlib.redirect_stdout(stdout),
                ):
                    status = probe.main()
                self.assertEqual(status, 2)
                self.assertEqual(
                    json.loads(stdout.getvalue())["status"],
                    "BLOCKED_INVENTORY_READ_OR_PARSE_FAILED",
                )

    def test_non_active_membership_cannot_become_an_approval(self):
        with patch.object(
            probe,
            "_read_url",
            return_value=(HEADER + TARGET.replace(",Joined,", ",Pending,")).encode(),
        ):
            report = probe.probe_inventory(KEY)
        self.assertEqual(report["status"], "FEEDS_LISTED_NO_ACTIVE_MEMBERSHIP")
        self.assertFalse(report["feeds"][0]["joined"])
        self.assertFalse(report["image_publication_allowed"])

    def test_workflow_probe_is_manual_branch_scoped_and_dependency_free(self):
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github/workflows/dufynd-awin-feed-revalidation.yml"
        ).read_text()
        branch = "refs/heads/work/dufynd-image-sources-followup-20261030"
        self.assertIn("if: ${{ github.ref != '" + branch + "' }}", workflow)
        job = workflow.split("  probe-perfumetrader-inventory:\n", 1)[1]
        self.assertIn(
            "github.event_name == 'workflow_dispatch' && github.ref == '" + branch + "'", job
        )
        self.assertIn("timeout-minutes: 5", job)
        self.assertIn("persist-credentials: false", job)
        self.assertIn("python3 scripts/probe_dufynd_perfumetrader_feed_inventory.py", job)
        for forbidden in (
            "pip install",
            "setup-python",
            "upload-artifact",
            "actions/cache",
            "write-all",
            "contents: write",
        ):
            self.assertNotIn(forbidden, job)


if __name__ == "__main__":
    unittest.main()
