from __future__ import annotations

from scripts.validate_scentai_jarvis_state_graph import (
    compare_state_graph,
)


def test_state_graph_matches_when_all_nodes_equal() -> None:
    current = {
        "mapping_queue": {"value": 1},
        "operations": {"state": "waiting"},
    }
    expected = {
        "mapping_queue": {"value": 1},
        "operations": {"state": "waiting"},
    }

    report = compare_state_graph(current, expected)

    assert report["valid"] is True
    assert report["issues"] == []
    assert report["drifted_nodes"] == []


def test_state_graph_detects_intermediate_node_drift() -> None:
    current = {
        "mapping_queue": {"value": 1},
        "image_queue": {"value": 1},
        "operations": {"state": "waiting"},
    }
    expected = {
        "mapping_queue": {"value": 1},
        "image_queue": {"value": 2},
        "operations": {"state": "waiting"},
    }

    report = compare_state_graph(current, expected)

    assert report["valid"] is False
    assert report["drifted_nodes"] == ["image_queue"]
    assert report["issues"] == [
        "drifted_state_nodes:image_queue"
    ]


def test_state_graph_detects_missing_and_extra_nodes() -> None:
    report = compare_state_graph(
        {
            "mapping_queue": {"value": 1},
            "legacy": {},
        },
        {
            "mapping_queue": {"value": 1},
            "operations": {},
        },
    )

    assert report["valid"] is False
    assert report["missing_nodes"] == ["operations"]
    assert report["extra_nodes"] == ["legacy"]
