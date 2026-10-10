import hashlib
from concurrent.futures import ThreadPoolExecutor

import pytest
from scripts.dufynd_media_handoff import stage_private_media


def test_concurrent_handoffs_reuse_exact_readonly_bytes(tmp_path):
    source = tmp_path / "owner.mp4"
    source.write_bytes(b"unchanged source audio and video" * 1000)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    directory = tmp_path / "private"
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: stage_private_media(source, directory, digest), range(4)))
    assert sum(not r["reused"] for r in results) == 1
    assert len(list(directory.iterdir())) == 1
    target = directory / f"{digest}.mp4"
    assert target.read_bytes() == source.read_bytes()
    assert target.stat().st_mode & 0o777 == 0o400
    assert all(r["publication_authorized"] is False for r in results)


def test_changed_source_never_replaces_valid_handoff(tmp_path):
    source = tmp_path / "owner.mp4"
    source.write_bytes(b"approved")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    directory = tmp_path / "private"
    stage_private_media(source, directory, digest)
    source.write_bytes(b"changed")
    with pytest.raises(ValueError, match="source_sha256_mismatch"):
        stage_private_media(source, directory, digest)
    assert (directory / f"{digest}.mp4").read_bytes() == b"approved"
    assert len(list(directory.iterdir())) == 1


def test_symlink_source_and_target_and_public_directory_rejected(tmp_path):
    original = tmp_path / "original.mp4"
    original.write_bytes(b"approved")
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    source = tmp_path / "link.mp4"
    source.symlink_to(original)
    with pytest.raises(OSError):
        stage_private_media(source, tmp_path / "private", digest)
    target = tmp_path / "private" / f"{digest}.mp4"
    target.symlink_to(original)
    with pytest.raises(OSError):
        stage_private_media(original, target.parent, digest)
    assert original.read_bytes() == b"approved"
    public = tmp_path / "public"
    public.mkdir(mode=0o755)
    with pytest.raises(ValueError, match="private_owned_directory"):
        stage_private_media(original, public, digest)
