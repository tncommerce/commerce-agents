from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from scripts.render_scentai_model3d_review_html import (
    DEFAULT_CANDIDATES,
    DEFAULT_PUBLIC_ROOT,
    load_json,
    render_html,
    review_candidates,
)
from scripts.scentai_model3d_guard import public_model_path

DEFAULT_OUTPUT_DIR = Path("dufynd-model3d-review")


def build_review_bundle(
    candidates_payload: dict,
    *,
    public_root: Path,
    output_dir: Path,
) -> dict:
    reviewed = review_candidates(candidates_payload, public_root)
    output_dir.mkdir(parents=True, exist_ok=True)

    for candidate in reviewed:
        model_url = str(candidate["model_url"])
        source = public_model_path(public_root, model_url)
        destination = output_dir / model_url.removeprefix("/")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)

    index = render_html(reviewed, relative_model_paths=True)
    (output_dir / "index.html").write_text(index, encoding="utf-8")

    manifest = {
        "version": 1,
        "status": "review_only_not_live",
        "candidate_count": len(reviewed),
        "candidates": reviewed,
    }
    (output_dir / "review-candidates.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "README.txt").write_text(
        "DUFYND TRUE 3D REVIEW ONLY\n"
        "\n"
        "This bundle cannot approve or publish a model.\n"
        "Extract the artifact, open a terminal in this directory, and run:\n"
        "  python -m http.server 8000\n"
        "Then open http://127.0.0.1:8000/ in a browser.\n"
        "Final geometry and visual approval remains human-only.\n",
        encoding="utf-8",
    )

    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a portable review-only DUFYND true-3D model artifact."
    )
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--public-root", type=Path, default=DEFAULT_PUBLIC_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    try:
        manifest = build_review_bundle(
            load_json(args.candidates),
            public_root=args.public_root,
            output_dir=args.output_dir,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    print(
        "DUFYND 3D review bundle | "
        f"candidates={manifest['candidate_count']} | output={args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
