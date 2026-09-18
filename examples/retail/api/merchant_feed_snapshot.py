from __future__ import annotations

import hashlib
from pathlib import Path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def changed_snapshot_files(
    *,
    feed_path: Path,
    expected_feed_sha256: str,
    mappings_path: Path,
    expected_mappings_sha256: str,
) -> list[str]:
    changed: list[str] = []

    if file_sha256(feed_path) != expected_feed_sha256:
        changed.append("feed")

    if (
        file_sha256(mappings_path)
        != expected_mappings_sha256
    ):
        changed.append("mappings")

    return changed
