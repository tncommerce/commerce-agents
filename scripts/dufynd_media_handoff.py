"""Byte-preserving private MP4 handoff for existing publisher path inputs.

No network, transcoding, approval, public hosting or provider call. The creating
host materializes an authorized Library/Drive source before invoking this helper.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import tempfile
from pathlib import Path

MAX_BYTES = 300_000_000


def _open_regular(path: Path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise ValueError("regular_media_file_required")
    return os.fdopen(fd, "rb")


def stage_private_media(source: Path, directory: Path, sha256: str) -> dict:
    """Install once by digest; concurrent copies converge without overwriting.

    This is local staging, not durable Library storage or a public publisher URL.
    A caller must continue to use the existing media audit and Owner GO gates.
    """
    if not re.fullmatch(r"[a-f0-9]{64}", sha256):
        raise ValueError("valid_sha256_required")
    if source.suffix.lower() != ".mp4":
        raise ValueError("mp4_source_required")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.getuid():
        raise ValueError("private_owned_directory_required")
    directory = directory.resolve()
    target = directory / f"{sha256}.mp4"
    temporary = None
    try:
        with (
            _open_regular(source) as stream,
            tempfile.NamedTemporaryFile(dir=directory, delete=False) as output,
        ):
            temporary = Path(output.name)
            digest, size = hashlib.sha256(), 0
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError("media_too_large")
                digest.update(chunk)
                output.write(chunk)
            if not size or digest.hexdigest() != sha256:
                raise ValueError("source_sha256_mismatch")
            output.flush()
            os.fsync(output.fileno())
            os.fchmod(output.fileno(), 0o400)
        try:
            os.link(temporary, target)
            reused = False
        except FileExistsError:
            reused = True
        with _open_regular(target) as installed:
            info = os.fstat(installed.fileno())
            if stat.S_IMODE(info.st_mode) != 0o400 or info.st_uid != os.getuid():
                raise ValueError("handoff_permissions_invalid")
            if (
                info.st_size != size
                or hashlib.file_digest(installed, "sha256").hexdigest() != sha256
            ):
                raise ValueError("existing_handoff_sha256_mismatch")
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return {
            "path": str(target),
            "sha256": sha256,
            "bytes": size,
            "reused": reused,
            "private": True,
            "publication_authorized": False,
        }
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    try:
        result = stage_private_media(args.source, args.directory, args.sha256)
    except (OSError, ValueError) as error:
        # Never echo source path/OS details into CI logs.
        print(json.dumps({"passed": False, "error_type": type(error).__name__}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
