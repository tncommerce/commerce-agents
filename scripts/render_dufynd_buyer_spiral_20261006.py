from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "examples/retail/data/dufynd_buyer_spiral_20261006.json"
OUT = ROOT / "examples/retail/storefront-web/public/social/organic/fragrance_buyer_spiral_20261006_01"
IG = (1080, 1350)
TT = (1080, 1920)
SANS = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
COND = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf")


def font(path: Path, size: int):
    return ImageFont.truetype(str(path), size=size)


def wrap(draw, text, fnt, width):
    out = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            out.append("")
            continue
        line = words[0]
        for word in words[1:]:
            candidate = line + " " + word
            box = draw.textbbox((0, 0), candidate, font=fnt)
            if box[2] - box[0] <= width:
                line = candidate
            else:
                out.append(line)
                line = word
        out.append(line)
    return "\n".join(out)


def fit(draw, text, path, max_size, min_size, width, height):
    for size in range(max_size, min_size - 1, -2):
        fnt = font(path, size)
        value = wrap(draw, text, fnt, width)
        box = draw.multiline_textbbox((0, 0), value, font=fnt, spacing=max(8, size // 10))
        if box[2] - box[0] <= width and box[3] - box[1] <= height:
            return fnt, value
    fnt = font(path, min_size)
    return fnt, wrap(draw, text, fnt, width)


def gradient(size, top, bottom):
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    for y in range(size[1]):
        t = y / max(1, size[1] - 1)
        rgb = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        draw.line((0, y, size[0], y), fill=rgb)
    return image


def panel(draw, box, fill, radius=28, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def render(slide, size, platform):
    w, h = size
    n = int(slide["n"])
    dark = n in (1, 5)
    if dark:
        image = gradient(size, (10, 15, 31), (27, 31, 58))
        ink, muted = (248, 244, 235), (179, 187, 207)
        rail = (255, 255, 255, 40)
        ghost = (255, 255, 255, 20)
    else:
        image = gradient(size, (248, 244, 236), (230, 233, 241))
        ink, muted = (18, 23, 38), (82, 89, 105)
        rail = (23, 31, 51, 32)
        ghost = (17, 25, 44, 18)

    draw = ImageDraw.Draw(image, "RGBA")
    orange = (255, 143, 88, 255)
    violet = (160, 142, 255, 255)

    # editorial dot field
    dot = (255, 255, 255, 18) if dark else (20, 28, 48, 13)
    for yy in range(210, h - 240, 92):
        for xx in range(72, w - 72, 92):
            draw.ellipse((xx - 2, yy - 2, xx + 2, yy + 2), fill=dot)

    # brand and progress rail
    draw.text((70, 62), "DUFYND", font=font(BOLD, 31), fill=ink)
    rail_y = 150 if platform == "tiktok" else 130
    draw.line((70, rail_y, w - 70, rail_y), fill=rail, width=3)
    labels = ("01", "02", "03", "14")
    active = 3 if n == 5 else max(-1, n - 2)
    for idx, label in enumerate(labels):
        x = 70 + int((w - 140) * idx / 3)
        passed = idx <= active
        r = 11 if idx == active else 7
        fill = orange if idx == active else violet if passed else muted + (130,)
        draw.ellipse((x-r, rail_y-r, x+r, rail_y+r), fill=fill)
        draw.text((x-17, rail_y+20), label, font=font(BOLD, 17), fill=muted)

    top = 260 if platform == "tiktok" else 215
    draw.text((70, top), slide["kicker"], font=font(BOLD, 24), fill=orange)

    title_y = top + 60
    title_font, title = fit(
        draw, slide["title"], COND,
        102 if platform == "tiktok" else 84,
        54, w - 140,
        420 if platform == "tiktok" else 330
    )
    spacing = max(8, title_font.size // 10)
    draw.multiline_text((70, title_y), title, font=title_font, fill=ink, spacing=spacing)
    title_box = draw.multiline_textbbox((70, title_y), title, font=title_font, spacing=spacing)

    body_y = title_box[3] + 32
    body_font, body = fit(draw, slide["body"], SANS, 36, 27, w - 190, 135)
    draw.multiline_text((70, body_y), body, font=body_font, fill=muted, spacing=8)

    # huge ghost step + orbit motif
    step = str(slide["step"])
    ghost_font = font(COND, 300 if platform == "tiktok" else 220)
    gb = draw.textbbox((0, 0), step, font=ghost_font)
    gx = w - (gb[2] - gb[0]) - 55
    gy = h - (760 if platform == "tiktok" else 555)
    draw.text((gx, gy), step, font=ghost_font, fill=ghost)

    cx, cy = w - 110, h - (610 if platform == "tiktok" else 430)
    for radius, start, color in ((320, 210, rail), (235, 175, rail), (150, 145, violet)):
        draw.arc((cx-radius, cy-radius, cx+radius, cy+radius), start=start, end=start+240, fill=color, width=4)
    for idx, (dx, dy) in enumerate(((-280,-70),(-185,118),(-15,145),(75,-70))):
        x, y = cx + dx, cy + dy
        rr = 12 if idx == min(max(active,0),3) else 7
        draw.ellipse((x-rr,y-rr,x+rr,y+rr), fill=orange if rr == 12 else violet)

    note = slide["note"]
    note_font, note_text = fit(draw, note, BOLD, 27, 20, w - 210, 78)
    note_box = draw.textbbox((0, 0), note_text, font=note_font)
    note_y = h - (420 if platform == "tiktok" else 265)
    note_w = min(w - 140, note_box[2] - note_box[0] + 58)
    note_fill = (246, 242, 234, 238) if dark else (20, 27, 47, 235)
    note_ink = (18, 24, 40) if dark else (247, 244, 237)
    panel(draw, (70, note_y, 70 + note_w, note_y + 76), note_fill, 38)
    draw.text((99, note_y + 22), note_text, font=note_font, fill=note_ink)

    footer = slide.get("footer")
    if footer:
        fy = h - (292 if platform == "tiktok" else 158)
        draw.text((70, fy), footer, font=font(COND, 44 if platform == "tiktok" else 35), fill=orange)

    by = h - (205 if platform == "tiktok" else 70)
    draw.text((70, by), "SCENT CULTURE  /  DUFYND", font=font(BOLD, 18), fill=muted)
    draw.rectangle((w - 190, by + 7, w - 70, by + 11), fill=violet)
    return image


def sha(path):
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main():
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    if spec["constraints"]["publishing_authorized"] is not False:
        raise ValueError("Publishing gate must remain closed")
    if float(spec["constraints"]["visual_quality_floor"]) < 9.5:
        raise ValueError("Visual floor must remain 9.5")

    ig_dir, tt_dir = OUT / "instagram", OUT / "tiktok"
    ig_dir.mkdir(parents=True, exist_ok=True)
    tt_dir.mkdir(parents=True, exist_ok=True)
    durations = []
    tt_files = []

    for slide in spec["slides"]:
        n = int(slide["n"])
        ig = ig_dir / f"slide-{n:02d}.jpg"
        tt = tt_dir / f"slide-{n:02d}.jpg"
        render(slide, IG, "instagram").save(ig, quality=95, optimize=True)
        render(slide, TT, "tiktok").save(tt, quality=95, optimize=True)
        durations.append(float(slide["duration"]))
        tt_files.append(tt)

    concat = tt_dir / "slideshow.concat.txt"
    lines = []
    for p, duration in zip(tt_files, durations, strict=True):
        lines.extend([f"file '{p.resolve()}'", f"duration {duration:.3f}"])
    lines.append(f"file '{tt_files[-1].resolve()}'")
    concat.write_text("\n".join(lines) + "\n", encoding="utf-8")

    video = tt_dir / f"{spec['content_id']}.mp4"
    subprocess.run([
        "ffmpeg","-y","-f","concat","-safe","0","-i",str(concat),
        "-vf","fps=30,format=yuv420p","-c:v","libx264","-preset","medium",
        "-crf","19","-movflags","+faststart",str(video)
    ], check=True)

    manifest = {
        "content_id": spec["content_id"],
        "experiment_id": spec["experiment_id"],
        "state": "READY_FOR_OWNER_REVIEW",
        "publish_action_taken": False,
        "visual_quality_floor": 9.5,
        "instagram": [{"path":str(p.relative_to(ROOT)),"sha256":sha(p),"size":list(IG)} for p in sorted(ig_dir.glob("slide-*.jpg"))],
        "tiktok": [{"path":str(p.relative_to(ROOT)),"sha256":sha(p),"size":list(TT)} for p in sorted(tt_dir.glob("slide-*.jpg"))],
        "video": {"path":str(video.relative_to(ROOT)),"sha256":sha(video),"duration_seconds":sum(durations),"audio":False},
        "hard_gates": {"product_rights_dependency":False,"raw_tiktok_url":False,"owner_publish_approval":False,"native_preview_pending":True}
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Rendered buyer spiral; publishing not performed")


if __name__ == "__main__":
    main()
