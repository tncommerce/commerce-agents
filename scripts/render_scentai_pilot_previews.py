from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Workflow trigger marker: batch01
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "examples/retail/data"
PUBLIC_DIR = ROOT / "examples/retail/storefront-web/public"
OUTPUT_DIR = PUBLIC_DIR / "social/pilots/batch01"

PILOT_MANIFEST = DATA_DIR / "scentai_pilot_batch_01.json"
PRODUCTS_FILE = DATA_DIR / "scentai_products.json"

WIDTH = 1080
HEIGHT = 1920
FPS = 30

GROUND = "#f4f6fa"
CARD = "#ffffff"
INK = "#1e2c4f"
INK_2 = "#3b4763"
INK_SOFT = "#5a6679"
ACCENT = "#d97f5f"
ACCENT_STRONG = "#c4643f"
ACCENT_SOFT = "#f9e8e0"

FONT_CANDIDATES = [
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
]
FONT_BOLD_CANDIDATES = [
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
]

SCENE_PRODUCTS_BATCH01: dict[str, list[list[str]]] = {
    "original_vs_alt_imagination_01": [
        [
            "SC-LV-IMAGINATION-100",
            "SC-ARABIYAT-MARWA-EDP-100",
            "SC-BUJAIRAMI-HECTIC-100",
        ],
        ["SC-LV-IMAGINATION-100"],
        ["SC-ARABIYAT-MARWA-EDP-100", "SC-BUJAIRAMI-HECTIC-100"],
        ["SC-ARABIYAT-MARWA-EDP-100", "SC-BUJAIRAMI-HECTIC-100"],
        [
            "SC-LV-IMAGINATION-100",
            "SC-ARABIYAT-MARWA-EDP-100",
            "SC-BUJAIRAMI-HECTIC-100",
        ],
    ],
    "not_every_dupe_clone_01": [
        ["SC-PDM-ALTHAIR-125", "SC-FRENCH-AVENUE-LIQUID-BRUN-100"],
        ["SC-PDM-ALTHAIR-125", "SC-FRENCH-AVENUE-LIQUID-BRUN-100"],
        ["SC-LV-IMAGINATION-100", "SC-ARABIYAT-MARWA-EDP-100"],
        ["SC-CREED-AVENTUS-100", "SC-MONTBLANC-EXPLORER-100"],
        [
            "SC-PDM-ALTHAIR-125",
            "SC-ARABIYAT-MARWA-EDP-100",
            "SC-MONTBLANC-EXPLORER-100",
        ],
    ],
    "budget_three_under_50_01": [
        [
            "SC-AL-WATANIAH-KAYAAN-CLASSIC-100",
            "SC-FRENCH-AVENUE-LIQUID-BRUN-100",
            "SC-AFNAN-TURATHI-BLUE-90",
        ],
        ["SC-AL-WATANIAH-KAYAAN-CLASSIC-100"],
        ["SC-FRENCH-AVENUE-LIQUID-BRUN-100"],
        ["SC-AFNAN-TURATHI-BLUE-90"],
        [
            "SC-AL-WATANIAH-KAYAAN-CLASSIC-100",
            "SC-FRENCH-AVENUE-LIQUID-BRUN-100",
            "SC-AFNAN-TURATHI-BLUE-90",
        ],
    ],
    "bois_imperial_explained_01": [
        ["SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100"],
        ["SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100"],
        ["SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100"],
        ["SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100"],
    ],
    "top3_office_01": [
        [
            "SC-PRADA-LHOMME-100",
            "SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100",
            "SC-CHANEL-BLEU-DE-CHANEL-EDP-100",
        ],
        ["SC-PRADA-LHOMME-100"],
        ["SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100"],
        ["SC-CHANEL-BLEU-DE-CHANEL-EDP-100"],
        [
            "SC-PRADA-LHOMME-100",
            "SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100",
            "SC-CHANEL-BLEU-DE-CHANEL-EDP-100",
        ],
    ],
}

SCENE_PRODUCTS_BATCH02: dict[str, list[list[str]]] = {
    "dupe_battle_imagination_01": [
        [
            "SC-ARABIYAT-MARWA-EDP-100",
            "SC-BUJAIRAMI-HECTIC-100",
            "SC-ARABIYAT-MARWA-EXTRAIT-60",
        ],
        ["SC-ARABIYAT-MARWA-EDP-100"],
        ["SC-BUJAIRAMI-HECTIC-100"],
        ["SC-ARABIYAT-MARWA-EXTRAIT-60"],
        [
            "SC-ARABIYAT-MARWA-EDP-100",
            "SC-BUJAIRAMI-HECTIC-100",
            "SC-ARABIYAT-MARWA-EXTRAIT-60",
        ],
    ],
    "layton_alternatives_01": [
        [
            "SC-PDM-LAYTON-125",
            "SC-AL-HARAMAIN-DETOUR-NOIR-100",
            "SC-ORIENTICA-ROYAL-BLEU-80",
        ],
        [
            "SC-PDM-LAYTON-125",
            "SC-AL-HARAMAIN-DETOUR-NOIR-100",
            "SC-ORIENTICA-ROYAL-BLEU-80",
        ],
        ["SC-PDM-LAYTON-125", "SC-AL-HARAMAIN-DETOUR-NOIR-100"],
        ["SC-PDM-LAYTON-125", "SC-ORIENTICA-ROYAL-BLEU-80"],
        [
            "SC-PDM-LAYTON-125",
            "SC-AL-HARAMAIN-DETOUR-NOIR-100",
            "SC-ORIENTICA-ROYAL-BLEU-80",
        ],
    ],
    "althair_liquid_brun_01": [
        ["SC-PDM-ALTHAIR-125", "SC-FRENCH-AVENUE-LIQUID-BRUN-100"],
        ["SC-PDM-ALTHAIR-125", "SC-FRENCH-AVENUE-LIQUID-BRUN-100"],
        ["SC-PDM-ALTHAIR-125", "SC-FRENCH-AVENUE-LIQUID-BRUN-100"],
        ["SC-PDM-ALTHAIR-125", "SC-FRENCH-AVENUE-LIQUID-BRUN-100"],
        ["SC-PDM-ALTHAIR-125", "SC-FRENCH-AVENUE-LIQUID-BRUN-100"],
    ],
    "top3_date_01": [
        [
            "SC-ARMANI-SWY-INTENSELY-100",
            "SC-DIOR-HOMME-INTENSE-100",
            "SC-VALENTINO-BORN-IN-ROMA-INTENSE-100",
        ],
        ["SC-ARMANI-SWY-INTENSELY-100"],
        ["SC-DIOR-HOMME-INTENSE-100"],
        ["SC-VALENTINO-BORN-IN-ROMA-INTENSE-100"],
        [
            "SC-ARMANI-SWY-INTENSELY-100",
            "SC-DIOR-HOMME-INTENSE-100",
            "SC-VALENTINO-BORN-IN-ROMA-INTENSE-100",
        ],
    ],
    "top3_fresh_01": [
        [
            "SC-LV-IMAGINATION-100",
            "SC-BVLGARI-TYGAR-125",
            "SC-AFNAN-TURATHI-BLUE-90",
        ],
        ["SC-LV-IMAGINATION-100"],
        ["SC-BVLGARI-TYGAR-125"],
        ["SC-AFNAN-TURATHI-BLUE-90"],
        [
            "SC-LV-IMAGINATION-100",
            "SC-BVLGARI-TYGAR-125",
            "SC-AFNAN-TURATHI-BLUE-90",
        ],
    ],
}


SCENE_PRODUCTS_BATCH03: dict[str, list[list[str]]] = {
    "tygar_vibrato_value_01": [
        [
            "SC-BVLGARI-TYGAR-125",
            "SC-SOSPIRO-VIBRATO-100",
            "SC-AFNAN-TURATHI-BLUE-90",
        ],
        ["SC-BVLGARI-TYGAR-125", "SC-SOSPIRO-VIBRATO-100"],
        ["SC-AFNAN-TURATHI-BLUE-90"],
        ["SC-MAISON-ASRAR-REGENT-100"],
        [
            "SC-BVLGARI-TYGAR-125",
            "SC-SOSPIRO-VIBRATO-100",
            "SC-AFNAN-TURATHI-BLUE-90",
        ],
    ],
    "naxos_value_01": [
        [
            "SC-XERJOFF-NAXOS-100",
            "SC-NUSUK-ATEEQ-100",
            "SC-RAYHAAN-ITALIA-100",
        ],
        ["SC-XERJOFF-NAXOS-100"],
        ["SC-NUSUK-ATEEQ-100"],
        ["SC-RAYHAAN-ITALIA-100"],
        [
            "SC-XERJOFF-NAXOS-100",
            "SC-NUSUK-ATEEQ-100",
            "SC-RAYHAAN-ITALIA-100",
        ],
    ],
    "dior_homme_intense_alt_01": [
        [
            "SC-DIOR-HOMME-INTENSE-100",
            "SC-AL-WATANIAH-KAYAAN-CLASSIC-100",
        ],
        [
            "SC-DIOR-HOMME-INTENSE-100",
            "SC-AL-WATANIAH-KAYAAN-CLASSIC-100",
        ],
        [
            "SC-DIOR-HOMME-INTENSE-100",
            "SC-AL-WATANIAH-KAYAAN-CLASSIC-100",
        ],
        [
            "SC-DIOR-HOMME-INTENSE-100",
            "SC-AL-WATANIAH-KAYAAN-CLASSIC-100",
        ],
        [
            "SC-DIOR-HOMME-INTENSE-100",
            "SC-AL-WATANIAH-KAYAAN-CLASSIC-100",
        ],
    ],
    "signature_vs_safe_01": [
        [
            "SC-DIOR-SAUVAGE-EDP-100",
            "SC-PRADA-LHOMME-100",
            "SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100",
        ],
        ["SC-DIOR-SAUVAGE-EDP-100"],
        ["SC-PRADA-LHOMME-100"],
        ["SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100"],
        [
            "SC-DIOR-SAUVAGE-EDP-100",
            "SC-PRADA-LHOMME-100",
            "SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100",
        ],
    ],
    "gift_for_him_safe_to_bold_01": [
        [
            "SC-CHANEL-BLEU-DE-CHANEL-EDP-100",
            "SC-PRADA-LHOMME-100",
            "SC-XERJOFF-NAXOS-100",
        ],
        ["SC-CHANEL-BLEU-DE-CHANEL-EDP-100"],
        ["SC-PRADA-LHOMME-100"],
        ["SC-XERJOFF-NAXOS-100"],
        [
            "SC-CHANEL-BLEU-DE-CHANEL-EDP-100",
            "SC-PRADA-LHOMME-100",
            "SC-XERJOFF-NAXOS-100",
        ],
    ],
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def font_path(candidates: list[Path]) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("No supported system font found")


REGULAR_FONT = font_path(FONT_CANDIDATES)
BOLD_FONT = font_path(FONT_BOLD_CANDIDATES)


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(
        str(BOLD_FONT if bold else REGULAR_FONT),
        size=size,
    )


def hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def rounded_rect(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    radius: int,
    fill: str,
    shadow: bool = False,
) -> None:
    draw = ImageDraw.Draw(canvas)
    if shadow:
        shadow_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(shadow_layer)
        x1, y1, x2, y2 = box
        sdraw.rounded_rectangle(
            (x1 + 8, y1 + 14, x2 + 8, y2 + 14),
            radius=radius,
            fill=(30, 44, 79, 35),
        )
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(18))
        canvas.alpha_composite(shadow_layer)

    draw.rounded_rectangle(box, radius=radius, fill=fill)


def fit_image(
    image: Image.Image,
    target_w: int,
    target_h: int,
) -> Image.Image:
    source = image.convert("RGBA")
    source.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
    return source


def wrap_to_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    selected_font: ImageFont.FreeTypeFont,
    max_width: int,
) -> str:
    words = text.split()
    if not words:
        return ""

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = current + " " + word
        box = draw.textbbox((0, 0), candidate, font=selected_font)
        if box[2] - box[0] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return "\n".join(lines)


def product_label(product: dict) -> str:
    brand = str(product.get("brand") or "").strip()
    name = str(product.get("name") or "").strip()
    if name.casefold().startswith(brand.casefold()):
        return name
    return f"{brand} {name}".strip()


def image_for_product(product: dict) -> Image.Image:
    image_url = str(product.get("image_url") or "")
    if not image_url.startswith("/"):
        raise ValueError(f"{product.get('product_id')}: expected local image_url")
    path = PUBLIC_DIR / image_url.lstrip("/")
    if not path.exists():
        raise FileNotFoundError(f"{product.get('product_id')}: missing image {path}")
    return Image.open(path).convert("RGBA")


def draw_brand_header(
    canvas: Image.Image,
    pilot_number: int,
) -> None:
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(
        (64, 60, 430, 132),
        radius=28,
        fill=INK,
    )
    draw.text(
        (92, 79),
        "DUFYND",
        font=font(38, bold=True),
        fill="white",
    )
    draw.text(
        (290, 87),
        f"PILOT {pilot_number:02d}",
        font=font(25, bold=True),
        fill=ACCENT_SOFT,
    )


def draw_footer(canvas: Image.Image) -> None:
    draw = ImageDraw.Draw(canvas)
    draw.line(
        (64, HEIGHT - 118, WIDTH - 64, HEIGHT - 118),
        fill=hex_rgb(INK) + (35,),
        width=2,
    )
    draw.text(
        (64, HEIGHT - 92),
        "VISUAL PREVIEW · FINAL MIT VOICEOVER + MUSIK",
        font=font(24, bold=True),
        fill=INK_SOFT,
    )


def draw_overlay(
    canvas: Image.Image,
    text: str,
) -> None:
    draw = ImageDraw.Draw(canvas)
    selected_font = font(72, bold=True)
    wrapped = wrap_to_width(
        draw,
        text.upper(),
        selected_font,
        WIDTH - 160,
    )
    bbox = draw.multiline_textbbox(
        (0, 0),
        wrapped,
        font=selected_font,
        spacing=10,
    )
    text_h = bbox[3] - bbox[1]
    y = 185

    draw.multiline_text(
        (80, y),
        wrapped,
        font=selected_font,
        fill=INK,
        spacing=10,
    )
    draw.rounded_rectangle(
        (80, y + text_h + 28, 250, y + text_h + 40),
        radius=6,
        fill=ACCENT,
    )


def product_card(
    canvas: Image.Image,
    product: dict,
    box: tuple[int, int, int, int],
) -> None:
    x1, y1, x2, y2 = box
    rounded_rect(canvas, box, 36, CARD, shadow=True)

    inner_w = x2 - x1 - 50
    inner_h = y2 - y1 - 160
    source = image_for_product(product)
    fitted = fit_image(source, inner_w, inner_h)

    px = x1 + (x2 - x1 - fitted.width) // 2
    py = y1 + 26 + (inner_h - fitted.height) // 2
    canvas.alpha_composite(fitted, (px, py))

    draw = ImageDraw.Draw(canvas)
    label_font = font(29, bold=True)
    label = wrap_to_width(
        draw,
        product_label(product),
        label_font,
        x2 - x1 - 50,
    )
    draw.multiline_text(
        (x1 + 25, y2 - 116),
        label,
        font=label_font,
        fill=INK_2,
        spacing=4,
        anchor=None,
    )


def card_layout(count: int) -> list[tuple[int, int, int, int]]:
    top = 650
    bottom = 1720

    if count <= 1:
        return [(170, top, 910, bottom)]
    if count == 2:
        return [
            (70, top, 520, bottom),
            (560, top, 1010, bottom),
        ]

    card_w = 300
    gap = 30
    start_x = (WIDTH - (card_w * 3 + gap * 2)) // 2
    return [
        (
            start_x + index * (card_w + gap),
            top + 120,
            start_x + index * (card_w + gap) + card_w,
            bottom - 120,
        )
        for index in range(3)
    ]


def render_scene(
    *,
    pilot: dict,
    scene_index: int,
    scene: dict,
    products_by_id: dict[str, dict],
    scene_products: dict[str, list[list[str]]],
    output_path: Path,
) -> None:
    canvas = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        hex_rgb(GROUND) + (255,),
    )

    draw_brand_header(canvas, int(pilot["pilot"]))
    draw_overlay(canvas, str(scene.get("overlay") or ""))

    product_ids = scene_products[pilot["content_id"]][scene_index]
    products = [products_by_id[product_id] for product_id in product_ids]
    boxes = card_layout(len(products))

    for product, box in zip(products, boxes, strict=True):
        product_card(canvas, product, box)

    draw_footer(canvas)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output_path, quality=94)


def parse_duration(value: str) -> float:
    start_raw, end_raw = value.split("-", maxsplit=1)
    start = float(start_raw)
    end = float(end_raw)
    if end <= start:
        raise ValueError(f"Invalid scene timing: {value}")
    return end - start


def render_video(
    *,
    frame_paths: list[Path],
    durations: list[float],
    output_path: Path,
) -> None:
    if len(frame_paths) != len(durations):
        raise ValueError("frame_paths and durations must match")

    concat_path = output_path.with_suffix(".concat.txt")
    lines: list[str] = []
    for frame_path, duration in zip(frame_paths, durations, strict=True):
        escaped = str(frame_path.resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
        lines.append(f"duration {duration:.3f}")

    escaped_last = str(frame_paths[-1].resolve()).replace("'", "'\\''")
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
            f"fps={FPS},format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "24",
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Render DUFYND pilot visual preview MP4 files.")
    parser.add_argument(
        "--batch",
        choices=("batch01", "batch02", "batch03"),
        default="batch01",
    )
    args = parser.parse_args()

    if args.batch == "batch03":
        pilot_manifest = DATA_DIR / "scentai_pilot_batch_03.json"
        output_dir = PUBLIC_DIR / "social/pilots/batch03"
        scene_products = SCENE_PRODUCTS_BATCH03
    elif args.batch == "batch02":
        pilot_manifest = DATA_DIR / "scentai_pilot_batch_02.json"
        output_dir = PUBLIC_DIR / "social/pilots/batch02"
        scene_products = SCENE_PRODUCTS_BATCH02
    else:
        pilot_manifest = DATA_DIR / "scentai_pilot_batch_01.json"
        output_dir = PUBLIC_DIR / "social/pilots/batch01"
        scene_products = SCENE_PRODUCTS_BATCH01

    manifest = load_json(pilot_manifest)
    products_payload = load_json(PRODUCTS_FILE)
    products_by_id = {
        product["product_id"]: product for product in products_payload.get("products", [])
    }

    output_dir.mkdir(parents=True, exist_ok=True)

    index_rows: list[dict] = []
    for pilot in manifest.get("pilots", []):
        content_id = str(pilot["content_id"])
        scenes = pilot.get("scenes", [])
        expected = scene_products.get(content_id)
        if expected is None or len(expected) != len(scenes):
            raise ValueError(f"{content_id}: scene-product mapping is missing or incomplete")

        pilot_dir = output_dir / content_id
        pilot_dir.mkdir(parents=True, exist_ok=True)

        frame_paths: list[Path] = []
        durations: list[float] = []
        for index, scene in enumerate(scenes):
            frame_path = pilot_dir / f"scene-{index + 1:02d}.jpg"
            render_scene(
                pilot=pilot,
                scene_index=index,
                scene=scene,
                products_by_id=products_by_id,
                scene_products=scene_products,
                output_path=frame_path,
            )
            frame_paths.append(frame_path)
            durations.append(parse_duration(str(scene["seconds"])))

        cover_path = output_dir / f"{content_id}-cover.jpg"
        Image.open(frame_paths[0]).save(cover_path, quality=95)

        video_path = output_dir / f"{content_id}-preview.mp4"
        render_video(
            frame_paths=frame_paths,
            durations=durations,
            output_path=video_path,
        )

        index_rows.append(
            {
                "content_id": content_id,
                "cover": "/" + str(cover_path.relative_to(PUBLIC_DIR)).replace("\\", "/"),
                "preview": "/" + str(video_path.relative_to(PUBLIC_DIR)).replace("\\", "/"),
                "duration_seconds": sum(durations),
                "audio": False,
                "status": "visual_preview",
            }
        )

    index_path = output_dir / "index.json"
    index_path.write_text(
        json.dumps(
            {
                "version": 1,
                "batch": args.batch,
                "generated_from": pilot_manifest.name,
                "previews": index_rows,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Rendered {len(index_rows)} DUFYND {args.batch} visual previews -> {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
