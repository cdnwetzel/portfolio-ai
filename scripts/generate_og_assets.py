#!/usr/bin/env python3
"""Generate PNG social-share assets from first principles using Pillow.

Run from repo root:
    .venv-assets/bin/python scripts/generate_og_assets.py
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

PUBLIC = Path("frontend/public")
PUBLIC.mkdir(parents=True, exist_ok=True)


def load_font(size):
    """Try a few system sans-serif fonts in order of preference."""
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def draw_gradient(draw, size, color_top, color_bottom):
    for y in range(size[1]):
        ratio = y / size[1]
        r = int(color_top[0] * (1 - ratio) + color_bottom[0] * ratio)
        g = int(color_top[1] * (1 - ratio) + color_bottom[1] * ratio)
        b = int(color_top[2] * (1 - ratio) + color_bottom[2] * ratio)
        draw.line([(0, y), (size[0], y)], fill=(r, g, b))


def generate_apple_touch_icon():
    size = (180, 180)
    img = Image.new("RGB", size, color="#0f172a")
    draw = ImageDraw.Draw(img)
    font = load_font(80)
    text = "CW"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size[0] - text_w) // 2
    y = (size[1] - text_h) // 2 - 6
    draw.text((x, y), text, font=font, fill="#60a5fa")
    img.save(PUBLIC / "apple-touch-icon.png")
    print("Generated apple-touch-icon.png")


def generate_og_image():
    size = (1200, 630)
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)
    draw_gradient(draw, size, (15, 23, 42), (30, 41, 59))

    # Border
    draw.rounded_rectangle([60, 60, 1140, 570], radius=24, outline="#334155", width=2)

    font_name = load_font(72)
    font_title = load_font(40)
    font_body = load_font(32)
    font_mono = load_font(20)

    draw.text((120, 200), "Chris Wetzel", font=font_name, fill="#f8fafc")
    draw.text((120, 290), "Infrastructure & AI Engineer", font=font_title, fill="#60a5fa")
    draw.text((120, 390), "Ask my AI anything — grounded in 26 years of", font=font_body, fill="#94a3b8")
    draw.text((120, 435), "documented infrastructure work, running on owned hardware.", font=font_body, fill="#94a3b8")
    draw.text((120, 540), "Qwen 14B · vLLM · Qdrant · 2× RTX A4500 · Gentoo", font=font_mono, fill="#64748b")

    img.save(PUBLIC / "og-image.png")
    print("Generated og-image.png")


def generate_favicon_png():
    size = (64, 64)
    img = Image.new("RGB", size, color="#0f172a")
    draw = ImageDraw.Draw(img)
    font = load_font(32)
    text = "CW"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size[0] - text_w) // 2
    y = (size[1] - text_h) // 2 - 2
    draw.text((x, y), text, font=font, fill="#60a5fa")
    img.save(PUBLIC / "favicon.png")
    print("Generated favicon.png")


if __name__ == "__main__":
    generate_apple_touch_icon()
    generate_og_image()
    generate_favicon_png()
