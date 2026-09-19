from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_INPUT = Path(
    "examples/retail/data/scentai_pilot_batch_01_subtitles.json"
)
DEFAULT_OUTPUT_DIR = Path(
    "examples/retail/data/scentai_pilot_batch_01_subtitles"
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def srt_timestamp(seconds: float) -> str:
    if seconds < 0:
        raise ValueError("subtitle timestamp cannot be negative")

    total_ms = int(round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1000)

    return (
        f"{hours:02d}:{minutes:02d}:{secs:02d},"
        f"{milliseconds:03d}"
    )


def validate_item(item: dict) -> None:
    content_id = str(item.get("content_id") or "").strip()
    if not content_id:
        raise ValueError("subtitle item requires content_id")

    segments = item.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError(f"{content_id}: requires subtitle segments")

    previous_end = 0.0
    for index, segment in enumerate(segments, start=1):
        try:
            start = float(segment["start"])
            end = float(segment["end"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"{content_id}: segment {index} has invalid timing"
            ) from exc

        text = str(segment.get("text") or "").strip()
        if not text:
            raise ValueError(
                f"{content_id}: segment {index} has empty text"
            )
        if start < previous_end:
            raise ValueError(
                f"{content_id}: segment {index} overlaps the previous segment"
            )
        if end <= start:
            raise ValueError(
                f"{content_id}: segment {index} must end after it starts"
            )

        previous_end = end


def build_srt(item: dict) -> str:
    validate_item(item)

    blocks: list[str] = []
    for index, segment in enumerate(item["segments"], start=1):
        start = srt_timestamp(float(segment["start"]))
        end = srt_timestamp(float(segment["end"]))
        text = str(segment["text"]).strip()

        blocks.append(
            f"{index}\n{start} --> {end}\n{text}"
        )

    return "\n\n".join(blocks) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export SCENTAI pilot subtitle timing drafts as .srt files."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    parser.add_argument(
        "--content-id",
        action="append",
        default=[],
        help="Optional content_id filter. Repeatable.",
    )
    args = parser.parse_args()

    payload = load_json(args.input)
    items = payload.get("items", [])
    if not isinstance(items, list) or not items:
        parser.error("subtitle payload does not contain items")

    selected_ids = {
        value.strip()
        for value in args.content_id
        if value.strip()
    }
    selected = [
        item
        for item in items
        if (
            not selected_ids
            or str(item.get("content_id") or "") in selected_ids
        )
    ]

    if selected_ids:
        found = {
            str(item.get("content_id") or "")
            for item in selected
        }
        missing = sorted(selected_ids - found)
        if missing:
            parser.error(
                "Unknown content_id values: " + ", ".join(missing)
            )

    args.output_dir.mkdir(parents=True, exist_ok=True)

    for item in selected:
        content_id = str(item["content_id"])
        output_path = args.output_dir / f"{content_id}.srt"
        try:
            content = build_srt(item)
        except ValueError as exc:
            parser.error(str(exc))

        output_path.write_text(content, encoding="utf-8")
        print(f"{content_id} -> {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
