"""No fabricated CJ Notino feed, price, stock, image rights or clicks."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx
from scripts.check_dufynd_cj_notino_feed import (
    CJ_GRAPHQL,
    build_feed_query,
    check_notino_feeds,
    parse_feed_response,
)

NOW = datetime(2026, 10, 24, 9, tzinfo=UTC)
ADVERTISER = "1234567"
PUBLISHER = "7654321"


def example_response(*, advertiser: str = ADVERTISER) -> dict:
    return {
        "data": {
            "productFeeds": {
                "totalCount": 1,
                "count": 1,
                "resultList": [
                    {
                        "adId": "9999999",
                        "advertiserId": advertiser,
                        "feedName": "Notino DE product feed",
                        "productCount": 100,
                        "lastUpdated": (NOW - timedelta(hours=1)).isoformat(),
                        "currency": "EUR",
                        "sourceFeedType": "GOOGLE",
                    }
                ],
            }
        }
    }


def test_no_token_or_ids_means_zero_network_requests() -> None:
    calls = []

    def forbidden(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise AssertionError("request not authorized")

    result = check_notino_feeds(
        token="",
        company_id=PUBLISHER,
        notino_advertiser_id=ADVERTISER,
        transport=httpx.MockTransport(forbidden),
    )
    assert result["status"] == "CJ_CREDENTIALS_OR_COMPANY_IDS_NOT_CONFIGURED"
    assert result["network_requests"] == 0
    assert result["current_sku_prices_verified"] == 0
    assert not calls


def test_official_graphql_one_scoped_request_is_inventory_only() -> None:
    observed = []

    def mock(request: httpx.Request) -> httpx.Response:
        observed.append(request)
        query = json.loads(request.content)["query"]
        assert request.method == "POST"
        assert str(request.url) == CJ_GRAPHQL
        assert f'companyId: "{PUBLISHER}"' in query
        assert f'partnerIds: ["{ADVERTISER}"]' in query
        assert request.headers["Authorization"] == "Bearer synthetic-test-token"
        return httpx.Response(200, json=example_response())

    result = check_notino_feeds(
        token="synthetic-test-token",
        company_id=PUBLISHER,
        notino_advertiser_id=ADVERTISER,
        transport=httpx.MockTransport(mock),
        now=NOW,
    )
    assert result["status"] == "CJ_FEED_CANDIDATES_VISIBLE_NEED_SKU_EVIDENCE"
    assert result["network_requests"] == len(observed) == 1
    assert len(result["feeds"]) == 1
    assert result["feeds"][0]["feed_metadata_within_72h"] is True
    assert result["current_sku_prices_verified"] == 0
    assert result["offer_activation_authorized"] is False
    assert result["image_rights_authorized"] is False
    assert "synthetic-test-token" not in json.dumps(result)


def test_scope_conflict_or_graphql_error_cannot_certify_any_feed() -> None:
    wrong = parse_feed_response(
        example_response(advertiser="2222222"),
        notino_advertiser_id=ADVERTISER,
        checked_at=NOW,
    )
    assert wrong["status"] == "CJ_ADVERTISER_SCOPE_MISMATCH"
    assert wrong["feeds"] == []
    error = parse_feed_response(
        {"errors": [{"message": "Forbidden"}]},
        notino_advertiser_id=ADVERTISER,
        checked_at=NOW,
    )
    assert error["feeds"] == []


def test_empty_feed_and_old_metadata_do_not_make_current_offers() -> None:
    payload = {"data": {"productFeeds": {"totalCount": 0, "count": 0, "resultList": []}}}
    empty = parse_feed_response(payload, notino_advertiser_id=ADVERTISER, checked_at=NOW)
    assert empty["status"] == "CJ_NO_FEED_FOR_SCOPED_ADVERTISER"
    old = example_response()
    old["data"]["productFeeds"]["resultList"][0]["lastUpdated"] = (
        NOW - timedelta(days=30)
    ).isoformat()
    report = parse_feed_response(old, notino_advertiser_id=ADVERTISER, checked_at=NOW)
    assert report["feeds"][0]["feed_metadata_within_72h"] is False


def test_invalid_company_ids_and_invalid_feed_identity_are_rejected() -> None:
    for invalid in ("", "1) { products", "-9", "foo", "0"):
        try:
            build_feed_query(PUBLISHER, invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe CJ advertiser company ID was accepted")
    feed = example_response()
    feed["data"]["productFeeds"]["resultList"][0]["adId"] = None
    report = parse_feed_response(feed, notino_advertiser_id=ADVERTISER, checked_at=NOW)
    assert report["status"] == "CJ_FEED_ID_MISSING_OR_DUPLICATE"


def test_authorization_error_and_rate_limit_never_trigger_retry() -> None:
    for response_status, expected in [
        (401, "CJ_AUTHORIZATION_NOT_CONFIRMED"),
        (429, "CJ_RATE_LIMITED_NO_RETRY"),
    ]:
        calls = []

        def mock(
            request: httpx.Request,
            *,
            _calls: list = calls,
            _status: int = response_status,
        ) -> httpx.Response:
            _calls.append(request)
            return httpx.Response(_status, text="private details")

        result = check_notino_feeds(
            token="synthetic-test-token",
            company_id=PUBLISHER,
            notino_advertiser_id=ADVERTISER,
            transport=httpx.MockTransport(mock),
            now=NOW,
        )
        assert result["status"] == expected
        assert result["feeds"] == []
        assert result["network_requests"] == len(calls) == 1
        assert "private details" not in json.dumps(result)


def test_incomplete_cj_inventory_must_not_be_read_as_no_feed() -> None:
    partial = example_response()
    partial["data"]["productFeeds"]["totalCount"] = 2
    result = parse_feed_response(partial, notino_advertiser_id=ADVERTISER, checked_at=NOW)
    assert result["status"] == "CJ_FEED_INVENTORY_INCOMPLETE"
    assert result["feeds"] == []

    invalid = example_response()
    invalid["data"]["productFeeds"]["count"] = 2
    result = parse_feed_response(invalid, notino_advertiser_id=ADVERTISER, checked_at=NOW)
    assert result["status"] == "CJ_FEED_COUNTS_UNTRUSTWORTHY"
    assert result["feeds"] == []

    result = parse_feed_response(
        example_response(),
        notino_advertiser_id=ADVERTISER,
        checked_at=NOW.replace(tzinfo=None),
    )
    assert result["status"] == "CJ_REFERENCE_CLOCK_INVALID"
    assert result["feeds"] == []


def test_feed_visibility_never_grants_an_affiliate_relationship() -> None:
    result = parse_feed_response(
        example_response(), notino_advertiser_id=ADVERTISER, checked_at=NOW
    )
    assert result["feeds"][0]["publisher_partnership_verified"] is False
