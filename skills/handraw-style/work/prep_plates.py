"""Crop plates to 9:16, grade them to one palette, and write them into claude-motion/public."""
import os
import sys

from PIL import Image, ImageEnhance

SRC = "plates"
DST = "../claude-motion/public/plates"
W, H = 1080, 1920


def grade(im):
    """One look for every plate: cool the shadows, warm the highlights, lift a little."""
    im = ImageEnhance.Color(im).enhance(1.06)
    im = ImageEnhance.Contrast(im).enhance(1.05)
    im = ImageEnhance.Brightness(im).enhance(1.02)
    # duotone-ish shadow tint toward prussian blue, highlight tint toward persimmon
    r, g, b = im.split()
    r = r.point(lambda v: min(255, int(v * 1.02 + 6)))
    g = g.point(lambda v: min(255, int(v * 0.99 + 3)))
    b = b.point(lambda v: min(255, int(v * 1.03 + 14)))
    return Image.merge("RGB", (r, g, b))


def prep(path, out):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    target_ratio = W / H
    crop_w = min(w, int(h * target_ratio))
    if crop_w < w:
        left = (w - crop_w) // 2
        im = im.crop((left, 0, left + crop_w, h))
    im = im.resize((W, H), Image.LANCZOS)
    im = grade(im)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    im.save(out, "PNG", optimize=True)
    print("prepped", out, im.size)


if __name__ == "__main__":
    names = sys.argv[1:] or ["p1_alley", "p2_arrival", "p3_button", "p4_drop", "p5_together"]
    for n in names:
        src = os.path.join(SRC, f"{n}.png")
        if os.path.exists(src):
            prep(src, os.path.join(DST, f"{n}.png"))
        else:
            print("missing", src)
