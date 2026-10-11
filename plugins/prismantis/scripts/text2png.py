"""Render monospace text (stdin) to a PNG: text2png.py OUT.png [BG_HEX] [FG_HEX]."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

FONTS = ["CascadiaMono.ttf", "consola.ttf", "DejaVuSansMono.ttf", "Menlo.ttc", "cour.ttf"]


def load_font(size):
    for name in FONTS:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main():
    out = Path(sys.argv[1])
    bg = sys.argv[2] if len(sys.argv) > 2 else "#1e1e2e"
    fg = sys.argv[3] if len(sys.argv) > 3 else "#cdd6f4"
    text = sys.stdin.buffer.read().decode("utf-8").rstrip("\n")
    lines = text.split("\n")
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    font = load_font(28)
    asc, desc = font.getmetrics()
    line_h = asc + desc + 4
    char_w = font.getlength("M")
    pad = 32
    w = int(max(len(l) for l in lines) * char_w + pad * 2)
    h = int(len(lines) * line_h + pad * 2)
    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((pad, pad + i * line_h), line, font=font, fill=fg)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(out)


main()
