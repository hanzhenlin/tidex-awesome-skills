"""ASCII 'eyes' for images: no vision needed. Prints structure + color-class maps."""
import sys
import numpy as np
from PIL import Image, ImageFilter


def load(path, cols=44):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    rows = max(1, round(cols * h / w / 2.0))
    small = im.resize((cols, rows), Image.LANCZOS)
    return im, np.asarray(small).astype(np.float32)


LUMA = " .:-=+*#%@"


def luma_map(a, cols):
    l = (0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]) / 255.0
    idx = np.clip((l * (len(LUMA) - 1)).astype(int), 0, len(LUMA) - 1)
    return ["".join(LUMA[i] for i in row) for row in idx], l


def color_map(a):
    r, g, b = a[..., 0] / 255.0, a[..., 1] / 255.0, a[..., 2] / 255.0
    mx = np.max(a, axis=-1) / 255.0
    mn = np.min(a, axis=-1) / 255.0
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    v = mx
    ch = np.full(a.shape[:2], "K", dtype="<U1")
    warm = (r > b + 0.06)
    cool = (b >= r + 0.02)
    ch[(v < 0.16)] = " "
    ch[(v >= 0.16) & (v < 0.34) & (sat < 0.25)] = "."
    ch[(v >= 0.16) & (sat >= 0.25) & warm] = "O"
    ch[(v >= 0.16) & (sat >= 0.25) & cool] = "B"
    ch[(v >= 0.16) & (sat >= 0.25) & (~warm) & (~cool)] = "G"
    ch[(v >= 0.55) & (sat < 0.22)] = "o"
    ch[(v >= 0.72) & (sat < 0.30)] = "@"
    ch[(v >= 0.72) & (sat >= 0.30) & warm] = "W"
    return ch


def stats(im):
    a = np.asarray(im).astype(np.float32) / 255.0
    lum = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    sat = a.max(-1) - a.min(-1)
    edges = np.asarray(im.convert("L").filter(ImageFilter.FIND_EDGES)).astype(np.float32)
    edge_row = (edges > 40).mean(axis=1)
    # rows that look like dense text bands: many short horizontal strokes
    band = (edge_row > 0.28).sum() / len(edge_row)
    return {
        "size": im.size,
        "mean_lum": round(float(lum.mean()), 3),
        "mean_sat": round(float(sat.mean()), 3),
        "dark_frac": round(float((lum < 0.12).mean()), 3),
        "bright_frac": round(float((lum > 0.75).mean()), 3),
        "edge_density": round(float((edges > 40).mean()), 4),
        "textlike_band_frac": round(float(band), 3),
    }


if __name__ == "__main__":
    cols = int(sys.argv[2]) if len(sys.argv) > 2 else 44
    for path in sys.argv[1].split(","):
        im, a = load(path, cols)
        lm, _ = luma_map(a, cols)
        cm = color_map(a)
        print("=" * 70)
        print(path, stats(im))
        print("--- luminance ---")
        for row in lm:
            print(row)
        print("--- color class (B=blue O=orange o=cream @=white W=warm-bright G=green .=mid K=dark) ---")
        for row in cm:
            print("".join(row))
