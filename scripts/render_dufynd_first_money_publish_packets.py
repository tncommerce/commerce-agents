from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
PACKET_PATH = ROOT / "examples/retail/data/dufynd_first_money_publish_packets_20261004.json"
PRODUCTS_PATH = ROOT / "examples/retail/data/scentai_products.json"
PUBLIC_DIR = ROOT / "examples/retail/storefront-web/public"
OUTPUT_ROOT = PUBLIC_DIR / "social/first-money"

IG_SIZE = (1080, 1350)
TT_SIZE = (1080, 1920)

FONT_REGULAR = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
FONT_CONDENSED = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf")
FONT_SERIF = Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf")

BLOCKED_RENDER_MARKERS = (
    "PILOT ",
    "VISUAL PREVIEW",
    "FINAL MIT VOICEOVER",
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    selected_font: ImageFont.FreeTypeFont,
    max_width: int,
) -> str:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            bbox = draw.textbbox((0, 0), candidate, font=selected_font)
            if bbox[2] - bbox[0] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return "\n".join(lines)


def fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    path: Path,
    max_size: int,
    min_size: int,
    max_width: int,
    max_height: int,
) -> tuple[ImageFont.FreeTypeFont, str]:
    for size in range(max_size, min_size - 1, -2):
        selected = font(path, size)
        wrapped = wrap_text(draw, text, selected, max_width)
        bbox = draw.multiline_textbbox(
            (0, 0),
            wrapped,
            font=selected,
            spacing=max(6, size // 8),
        )
        if bbox[2] - bbox[0] <= max_width and bbox[3] - bbox[1] <= max_height:
            return selected, wrapped
    selected = font(path, min_size)
    return selected, wrap_text(draw, text, selected, max_width)


def rounded_panel(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    *,
    fill: tuple[int, int, int, int],
    radius: int = 34,
    shadow: bool = True,
) -> None:
    if shadow:
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        x1, y1, x2, y2 = box
        draw.rounded_rectangle(
            (x1 + 8, y1 + 14, x2 + 8, y2 + 14),
            radius=radius,
            fill=(0, 0, 0, 48),
        )
        layer = layer.filter(ImageFilter.GaussianBlur(18))
        canvas.alpha_composite(layer)
    ImageDraw.Draw(canvas).rounded_rectangle(box, radius=radius, fill=fill)


def product_image(products_by_id: dict[str, dict], product_id: str) -> Image.Image:
    product = products_by_id[product_id]
    image_url = str(product.get("image_url") or "")
    if not image_url.startswith("/"):
        raise ValueError(f"{product_id}: image_url must be local")
    path = PUBLIC_DIR / image_url.lstrip("/")
    if not path.is_file():
        raise FileNotFoundError(f"{product_id}: missing image {path}")
    return Image.open(path).convert("RGB")


def paste_contained(
    canvas: Image.Image,
    source: Image.Image,
    box: tuple[int, int, int, int],
    *,
    panel_fill: tuple[int, int, int, int],
) -> None:
    x1, y1, x2, y2 = box
    rounded_panel(canvas, box, fill=panel_fill, radius=36, shadow=True)
    inner = (x2 - x1 - 44, y2 - y1 - 44)
    fitted = ImageOps.contain(source.convert("RGBA"), inner, Image.Resampling.LANCZOS)
    px = x1 + (x2 - x1 - fitted.width) // 2
    py = y1 + (y2 - y1 - fitted.height) // 2
    canvas.alpha_composite(fitted, (px, py))


def add_brand(canvas: Image.Image, *, light: bool) -> None:
    draw = ImageDraw.Draw(canvas)
    color = (245, 245, 248) if light else (22, 26, 37)
    draw.text((68, 62), "DUFYND", font=font(FONT_BOLD, 32), fill=color)


def draw_text_block(
    canvas: Image.Image,
    *,
    kicker: str,
    title: str,
    body: str,
    light: bool,
    top: int,
    max_width: int,
    title_font: Path,
) -> int:
    draw = ImageDraw.Draw(canvas)
    ink = (248, 248, 250) if light else (20, 25, 35)
    muted = (210, 210, 220) if light else (86, 92, 105)
    accent = (220, 153, 91) if not light else (214, 132, 255)

    draw.text((70, top), kicker.upper(), font=font(FONT_BOLD, 24), fill=accent)
    title_y = top + 54
    title_selected, wrapped_title = fit_font(
        draw,
        title,
        title_font,
        76,
        48,
        max_width,
        300,
    )
    spacing = max(8, title_selected.size // 9)
    draw.multiline_text(
        (70, title_y),
        wrapped_title,
        font=title_selected,
        fill=ink,
        spacing=spacing,
    )
    title_box = draw.multiline_textbbox(
        (70, title_y),
        wrapped_title,
        font=title_selected,
        spacing=spacing,
    )
    body_y = title_box[3] + 30
    body_selected, wrapped_body = fit_font(
        draw,
        body,
        FONT_REGULAR,
        34,
        28,
        max_width,
        120,
    )
    draw.multiline_text(
        (70, body_y),
        wrapped_body,
        font=body_selected,
        fill=muted,
        spacing=8,
    )
    body_box = draw.multiline_textbbox(
        (70, body_y),
        wrapped_body,
        font=body_selected,
        spacing=8,
    )
    return body_box[3]


def gift_background(size: tuple[int, int]) -> Image.Image:
    width, height = size
    canvas = Image.new("RGBA", size, (244, 239, 232, 255))
    draw = ImageDraw.Draw(canvas)
    for y in range(height):
        t = y / max(1, height - 1)
        shade = int(246 - 12 * t)
        draw.line((0, y, width, y), fill=(shade, shade - 4, shade - 10, 255))
    draw.ellipse(
        (width - 360, -120, width + 120, 360),
        fill=(220, 153, 91, 34),
    )
    draw.ellipse(
        (-180, height - 330, 260, height + 110),
        fill=(43, 54, 78, 22),
    )
    return canvas


def date_background(
    size: tuple[int, int],
    products_by_id: dict[str, dict],
    product_ids: list[str],
) -> Image.Image:
    width, height = size
    if product_ids:
        source = product_image(products_by_id, product_ids[0])
        source = ImageOps.fit(source, size, method=Image.Resampling.LANCZOS)
        source = source.filter(ImageFilter.GaussianBlur(34)).convert("RGBA")
    else:
        source = Image.new("RGBA", size, (16, 13, 25, 255))

    overlay = Image.new("RGBA", size, (8, 8, 16, 190))
    source.alpha_composite(overlay)

    draw = ImageDraw.Draw(source)
    for y in range(height):
        alpha = int(35 + 125 * (y / max(1, height - 1)))
        draw.line((0, y, width, y), fill=(10, 8, 18, alpha))
    draw.ellipse(
        (-180, height // 2 - 180, 420, height // 2 + 420),
        fill=(132, 66, 190, 36),
    )
    return source


def render_gift_slide(
    piece: dict,
    slide: dict,
    *,
    platform: str,
    products_by_id: dict[str, dict],
) -> Image.Image:
    size = IG_SIZE if platform == "instagram" else TT_SIZE
    width, height = size
    canvas = gift_background(size)
    add_brand(canvas, light=False)

    text_bottom = draw_text_block(
        canvas,
        kicker=slide["kicker"],
        title=slide["title"],
        body=slide["body"],
        light=False,
        top=130 if platform == "instagram" else 170,
        max_width=width - 140,
        title_font=FONT_SERIF,
    )

    product_ids = list(slide.get("product_ids") or [])
    if len(product_ids) == 1:
        top = max(text_bottom + 48, 560 if platform == "instagram" else 760)
        bottom = height - (150 if platform == "instagram" else 210)
        box = (150, top, width - 150, bottom)
        paste_contained(
            canvas,
            product_image(products_by_id, product_ids[0]),
            box,
            panel_fill=(255, 255, 255, 235),
        )
        label = slide.get("product_label")
        if label:
            ImageDraw.Draw(canvas).text(
                (170, bottom - 74),
                str(label),
                font=font(FONT_BOLD, 28),
                fill=(33, 40, 57),
            )
    elif product_ids:
        top = max(text_bottom + 54, 610 if platform == "instagram" else 860)
        bottom = height - (155 if platform == "instagram" else 230)
        gap = 24
        card_w = (width - 140 - gap * 2) // 3
        for index, product_id in enumerate(product_ids[:3]):
            x1 = 70 + index * (card_w + gap)
            x2 = x1 + card_w
            paste_contained(
                canvas,
                product_image(products_by_id, product_id),
                (x1, top, x2, bottom),
                panel_fill=(255, 255, 255, 232),
            )

    footer = slide.get("instagram_footer" if platform == "instagram" else "tiktok_footer")
    if footer:
        draw = ImageDraw.Draw(canvas)
        draw.text(
            (70, height - (92 if platform == "instagram" else 132)),
            str(footer),
            font=font(FONT_BOLD, 26),
            fill=(37, 44, 61),
        )
    return canvas.convert("RGB")


def render_date_slide(
    piece: dict,
    slide: dict,
    *,
    platform: str,
    products_by_id: dict[str, dict],
) -> Image.Image:
    size = IG_SIZE if platform == "instagram" else TT_SIZE
    width, height = size
    product_ids = list(slide.get("product_ids") or [])
    canvas = date_background(size, products_by_id, product_ids)
    add_brand(canvas, light=True)

    draw = ImageDraw.Draw(canvas)
    if 2 <= int(slide["n"]) <= 4:
        numeral = str(int(slide["n"]) - 1)
        draw.text(
            (width - 330, 85 if platform == "instagram" else 120),
            numeral,
            font=font(FONT_CONDENSED, 230 if platform == "instagram" else 280),
            fill=(255, 255, 255, 26),
        )

    text_bottom = draw_text_block(
        canvas,
        kicker=slide["kicker"],
        title=slide["title"],
        body=slide["body"],
        light=True,
        top=135 if platform == "instagram" else 185,
        max_width=width - 140,
        title_font=FONT_CONDENSED,
    )

    if len(product_ids) == 1:
        top = max(text_bottom + 40, 560 if platform == "instagram" else 790)
        bottom = height - (145 if platform == "instagram" else 220)
        rounded_panel(
            canvas,
            (120, top, width - 120, bottom),
            fill=(255, 255, 255, 30),
            radius=48,
            shadow=True,
        )
        source = product_image(products_by_id, product_ids[0])
        source = ImageOps.contain(
            source.convert("RGBA"),
            (width - 300, bottom - top - 120),
            Image.Resampling.LANCZOS,
        )
        px = (width - source.width) // 2
        py = top + (bottom - top - source.height) // 2
        canvas.alpha_composite(source, (px, py))
        label = slide.get("product_label")
        if label:
            draw.text(
                (145, bottom - 72),
                str(label),
                font=font(FONT_BOLD, 27),
                fill=(246, 246, 250),
            )
    elif product_ids:
        top = max(text_bottom + 52, 620 if platform == "instagram" else 900)
        bottom = height - (150 if platform == "instagram" else 240)
        gap = 22
        card_w = (width - 132 - gap * 2) // 3
        for index, product_id in enumerate(product_ids[:3]):
            x1 = 66 + index * (card_w + gap)
            x2 = x1 + card_w
            paste_contained(
                canvas,
                product_image(products_by_id, product_id),
                (x1, top, x2, bottom),
                panel_fill=(255, 255, 255, 34),
            )

    footer = slide.get("instagram_footer" if platform == "instagram" else "tiktok_footer")
    if footer:
        draw.text(
            (70, height - (90 if platform == "instagram" else 132)),
            str(footer),
            font=font(FONT_BOLD, 26),
            fill=(245, 245, 250),
        )
    return canvas.convert("RGB")


def render_slide(
    piece: dict,
    slide: dict,
    *,
    platform: str,
    products_by_id: dict[str, dict],
) -> Image.Image:
    if piece["theme"] == "gift_editorial":
        return render_gift_slide(
            piece,
            slide,
            platform=platform,
            products_by_id=products_by_id,
        )
    if piece["theme"] == "date_night_dark":
        return render_date_slide(
            piece,
            slide,
            platform=platform,
            products_by_id=products_by_id,
        )
    raise ValueError(f"Unsupported theme: {piece['theme']}")


def render_tiktok_video(slides: list[Path], durations: list[float], output: Path) -> None:
    concat_path = output.with_suffix(".concat.txt")
    lines: list[str] = []
    for path, duration in zip(slides, durations, strict=True):
        escaped = str(path.resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
        lines.append(f"duration {duration:.3f}")
    escaped_last = str(slides[-1].resolve()).replace("'", "'\\''")
    lines.append(f"file '{escaped_last}'")
    concat_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-vf",
            "fps=30,format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-movflags",
            "+faststart",
            str(output),
        ],
        check=True,
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_packet(packet: dict) -> None:
    protected = set(packet.get("protected_content_ids") or [])
    piece_ids = {piece["content_id"] for piece in packet.get("pieces", [])}
    collision = protected & piece_ids
    if collision:
        raise ValueError(f"Protected content collision: {sorted(collision)}")
    if packet.get("constraints", {}).get("publishing_authorized") is not False:
        raise ValueError("Publishing must remain unauthorized in the publish packet")
    if packet.get("constraints", {}).get("existing_repo_assets_only") is not True:
        raise ValueError("Existing-assets-only constraint is required")

    for piece in packet.get("pieces", []):
        if piece.get("state") != "READY_FOR_OWNER_PUBLISH_GO":
            raise ValueError(f"{piece['content_id']}: invalid state")
        if piece.get("tracking", {}).get("tiktok") is not None:
            raise ValueError(f"{piece['content_id']}: TikTok tracking link must be null")
        renderable_text = json.dumps(
            {
                "hook": piece.get("hook"),
                "slides": piece.get("slides"),
                "caption": piece.get("caption"),
                "cta": piece.get("cta"),
            },
            ensure_ascii=False,
        ).upper()
        for marker in BLOCKED_RENDER_MARKERS:
            if marker in renderable_text:
                raise ValueError(f"{piece['content_id']}: blocked legacy marker {marker}")


def render_all(packet: dict, products_by_id: dict[str, dict]) -> None:
    validate_packet(packet)
    for piece in packet["pieces"]:
        piece_root = OUTPUT_ROOT / piece["content_id"]
        ig_root = piece_root / "instagram"
        tt_root = piece_root / "tiktok"
        ig_root.mkdir(parents=True, exist_ok=True)
        tt_root.mkdir(parents=True, exist_ok=True)

        ig_files: list[Path] = []
        tt_files: list[Path] = []
        durations: list[float] = []

        for slide in piece["slides"]:
            n = int(slide["n"])
            ig_path = ig_root / f"slide-{n:02d}.jpg"
            tt_path = tt_root / f"slide-{n:02d}.jpg"
            render_slide(
                piece,
                slide,
                platform="instagram",
                products_by_id=products_by_id,
            ).save(ig_path, quality=94, optimize=True)
            render_slide(
                piece,
                slide,
                platform="tiktok",
                products_by_id=products_by_id,
            ).save(tt_path, quality=94, optimize=True)
            ig_files.append(ig_path)
            tt_files.append(tt_path)
            durations.append(float(slide["duration_seconds_tiktok"]))

        video_path = tt_root / f"{piece['content_id']}.mp4"
        render_tiktok_video(tt_files, durations, video_path)

        manifest = {
            "content_id": piece["content_id"],
            "experiment_id": piece["experiment_id"],
            "state": "READY_FOR_OWNER_PUBLISH_GO",
            "publish_action_taken": False,
            "existing_assets_only": True,
            "instagram": [
                {
                    "path": str(path.relative_to(ROOT)),
                    "sha256": sha256(path),
                    "size": list(IG_SIZE),
                }
                for path in ig_files
            ],
            "tiktok_slides": [
                {
                    "path": str(path.relative_to(ROOT)),
                    "sha256": sha256(path),
                    "size": list(TT_SIZE),
                }
                for path in tt_files
            ],
            "tiktok_video": {
                "path": str(video_path.relative_to(ROOT)),
                "sha256": sha256(video_path),
                "duration_seconds": sum(durations),
                "audio": False,
            },
            "automated_quality_gates": {
                "no_legacy_preview_markers": True,
                "correct_platform_dimensions": True,
                "protected_one_million_untouched": True,
                "tiktok_fake_link_cta_absent": True,
                "publish_not_performed": True,
            },
        }
        (piece_root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def check_outputs(packet: dict) -> None:
    validate_packet(packet)
    for piece in packet["pieces"]:
        piece_root = OUTPUT_ROOT / piece["content_id"]
        manifest_path = piece_root / "manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(manifest_path)
        manifest = load_json(manifest_path)
        if manifest.get("publish_action_taken") is not False:
            raise ValueError(f"{piece['content_id']}: publish action must be false")
        for platform, expected_size in (
            ("instagram", IG_SIZE),
            ("tiktok", TT_SIZE),
        ):
            root = piece_root / platform
            for slide in piece["slides"]:
                path = root / f"slide-{int(slide['n']):02d}.jpg"
                if not path.is_file():
                    raise FileNotFoundError(path)
                with Image.open(path) as image:
                    if image.size != expected_size:
                        raise ValueError(f"{path}: size {image.size} != {expected_size}")
        video_path = piece_root / "tiktok" / f"{piece['content_id']}.mp4"
        if not video_path.is_file() or video_path.stat().st_size <= 0:
            raise FileNotFoundError(video_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render no-spend DUFYND First Money pieces 2 and 3."
    )
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    packet = load_json(PACKET_PATH)
    products_payload = load_json(PRODUCTS_PATH)
    products_by_id = {
        product["product_id"]: product for product in products_payload.get("products", [])
    }

    if args.check_only:
        check_outputs(packet)
        print("DUFYND First Money publish packet check passed")
        return 0

    render_all(packet, products_by_id)
    check_outputs(packet)
    print("Rendered DUFYND First Money pieces 2 and 3; no publishing performed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
