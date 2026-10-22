"""Image generation client for the chatgpt2api proxy (OpenAI-compatible)."""
import base64
import io
import json
import os
import sys
import time

import requests

BASE = "https://chatgpt2api.handraw-style.com/v1"
KEY = "Abc123!!!!"
MODEL = os.environ.get("IMG_MODEL", "gpt-image-2")


def _dump(resp):
    try:
        return resp.json()
    except Exception:
        return {"_raw": resp.text[:2000]}


def generate(prompt, out_path, model=MODEL, size="1024x1536", quality="high", ref=None):
    """ref: local path (or list of paths) to reference image(s) sent via /images/edits)."""
    headers = {"Authorization": f"Bearer {KEY}"}
    if ref:
        refs = [ref] if isinstance(ref, str) else list(ref)
        files = []
        for i, path in enumerate(refs):
            blob = open(path, "rb").read()
            files.append(("image", (f"ref{i}.png", io.BytesIO(blob), "image/png")))
        data = {"model": model, "prompt": prompt, "size": size, "quality": quality,
                "n": "1", "response_format": "b64_json"}
        r = requests.post(f"{BASE}/images/edits", headers=headers, files=files, data=data, timeout=600)
    else:
        data = {"model": model, "prompt": prompt, "size": size, "quality": quality,
                "n": "1", "response_format": "b64_json"}
        r = requests.post(f"{BASE}/images/generations", headers=headers, json=data, timeout=600)

    if r.status_code != 200:
        print("HTTP", r.status_code, r.text[:1500], file=sys.stderr)
        return None
    j = _dump(r)
    items = j.get("data") or []
    if not items:
        print("no data:", json.dumps(j, ensure_ascii=False)[:1500], file=sys.stderr)
        return None
    item = items[0]
    if item.get("b64_json"):
        blob = base64.b64decode(item["b64_json"])
    elif item.get("url"):
        blob = requests.get(item["url"], timeout=300).content
    else:
        print("unexpected payload:", json.dumps(item)[:800], file=sys.stderr)
        return None
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(blob)
    print("saved", out_path, len(blob), "bytes")
    return out_path


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ref")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--size", default="1024x1536")
    ap.add_argument("--quality", default="high")
    a = ap.parse_args()
    t = time.time()
    p = generate(a.prompt, a.out, model=a.model, size=a.size, quality=a.quality, ref=a.ref)
    print("elapsed", round(time.time() - t, 1), "s")
    sys.exit(0 if p else 1)
