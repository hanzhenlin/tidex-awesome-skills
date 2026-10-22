"""Vision reviewer: asks the chatgpt2api proxy to describe / judge an image and prints text."""
import base64
import json
import os
import sys

import requests

BASE = "https://chatgpt2api.handraw-style.com/v1"
KEY = "Abc123!!!!"


def ask(image_paths, instruction, model="auto", max_tokens=1200):
    content = []
    for p in image_paths:
        b = base64.b64encode(open(p, "rb").read()).decode()
        content.append({"type": "text", "text": instruction})
        content.append({"type": "image_url", "image_url": {"url": "data:image/png;base64," + b}})
    data = {"model": model, "messages": [{"role": "user", "content": content}],
            "max_tokens": max_tokens}
    r = requests.post(f"{BASE}/chat/completions", headers={"Authorization": f"Bearer {KEY}"},
                      json=data, timeout=600)
    if r.status_code != 200:
        return f"HTTP {r.status_code}: {r.text[:600]}"
    j = r.json()
    return j["choices"][0]["message"]["content"]


PLATE_QA = """你是严格的美术审片人。用中文回答，控制在 400 字以内，分点回答：
1) 画面主体是什么？出现在画面的哪个位置（用九宫格描述）？
2) 是否存在任何文字/字母/招牌字/水印？有的话原样写出。
3) 整体色调与光线（冷暖分布、主色）。
4) 人物或动物的造型特征（毛色、体型、衣着），用于和另一张图比对一致性。
5) 这张图是否适合做竖屏短片底图（构图留白是否够放字幕）。
不要臆测，只描述你真实看到的。"""

MATCH_QA = """这两张图是同一部短片的连续镜头。请用中文回答，300 字以内：
1) 两图中的「猫」在毛色、花纹、体型、眼睛颜色上是否一致？不一致就指出差异。
2) 两图中的「小男孩」在发型、雨衣颜色、眼镜、身高比例上是否一致？不一致就指出。
3) 两图的巷子、贩卖机、光线氛围是否统一？
4) 给出结论：一致性 合格 / 需要重做（说明原因）。
不要臆测，只描述你真实看到的。"""

if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "plate":
        for p in sys.argv[2].split(","):
            print("=" * 60)
            print(p)
            print(ask([p], PLATE_QA))
    elif mode == "match":
        a, b = sys.argv[2].split(",")
        print(ask([a, b], MATCH_QA))
    elif mode == "ask":
        print(ask(sys.argv[3].split(","), sys.argv[2]))
