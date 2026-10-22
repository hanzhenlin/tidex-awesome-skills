"""Plate definitions for 《深夜巷口的巨猫》 (30s healing short)."""
import concurrent.futures as cf
import os
import sys

from gen import generate

REF_STYLE = "ref_FB-030.png"          # images/individual/FB/FB-030_grid.webp, converted
OUT = "plates"

STYLE = (
    "参考作者/风格名称：なっくす（Soft Crayon & Sumi-e Cat Storybook）。"
    "核心风格特征：温润蜡笔与水墨和风绘本风、质朴手绘炭笔蜡笔颗粒肌理、"
    "巨型猫咪的翡翠绿眼与细腻毛流、微型人偶与红色印章、充满童趣温暖的日式日常绘本。"
)
COLOR = "主题色：普鲁士蓝（Prussian Blue）、柿子橙（Persimmon Orange）、象牙白（Ivory）。"
ISOLATION = (
    "所附图片仅用于参考画风。只提取参考图的风格特征，例如线条、笔触、媒介、材质、"
    "色彩倾向和整体视觉语言；不要使用、复制或延续参考图中的任何主体、人物、动物、服装、"
    "道具、动作、姿态、场景、背景、构图、布局、文字或故事。最终画面内容完全以用户的主题为准。"
)
CONSISTENCY = (
    "其中一张参考图用于保持角色与世界的一致性：同一只猫、同一条巷子、同一台贩卖机、"
    "同一套配色与光线。它只是角色与场景的延续样本，具体画面内容与构图以本次主题为准。"
)

CAT = "一只体型巨大的浅棕色虎斑猫，额头有清晰的 M 形虎斑纹，翡翠绿色圆眼睛，粉色鼻头与肉垫，蓬松长尾巴"
BOY = "一个只到猫爪子高的小男孩，穿明黄色连帽雨衣，戴圆框眼镜"

PLATES = {
    "p1_alley": (
        "深夜安静的小巷，青石板路两侧是旧砖墙，路边一台老式自动贩卖机亮着温暖的橙色灯光，"
        "玻璃柜里整齐摆着几排饮料罐；" + CAT + "蜷缩在贩卖机前的台阶上打盹，眼睛半闭，尾巴搭在台阶边缘；"
        "巷口上方是一轮淡月和深蓝色的夜空，屋檐下放着一盆小小的绿植。"
        "画面安静、温暖、充满睡意，竖构图，主体集中在中下三分之一。"
    ),
    "p2_arrival": (
        "同一条深夜小巷，同一台亮着橙色灯光的老式自动贩卖机；" + BOY + "从巷子深处走来，"
        "背着一个小的双肩包；他停下脚步，低头看着蜷缩在贩卖机台阶上打盹的" + CAT + "；"
        "猫的一只耳朵轻轻动了一下；青石板路被灯光染成暖橙色，远处是深蓝色夜色。"
        "画面安静、温暖，竖构图，小男孩在画面中下部偏左，猫在偏右。"
    ),
    "p3_button": (
        "近景特写：巨大的" + CAT + "抬起一只前爪，按在老式自动贩卖机的一个圆形按钮上，"
        "粉色的肉垫清晰可见，翡翠绿眼睛专注地盯着按钮，胡须被橙色灯光照亮；"
        "贩卖机橙色的灯光洒在猫的侧脸上；画面下方是" + BOY + "仰头看着这一切。"
        "画面温暖、有趣，竖构图。"
    ),
    "p4_drop": (
        "老式自动贩卖机下方的取货口弹开，一罐象牙白色的温热牛奶正从出口滑落；"
        "巨大的" + CAT + "伸出前爪，掌心朝上，把牛奶罐轻轻推向下方" + BOY + "伸出的双手；"
        "罐口飘出细细的热气；温暖的橙色灯光铺满画面。"
        "画面温柔、俏皮，竖构图，牛奶罐在画面中央。"
    ),
    "p5_together": (
        "深夜小巷的台阶上，" + BOY + "和" + CAT + "并排坐着；小男孩双手捧着一罐象牙白色的温热牛奶，"
        "猫的蓬松长尾巴轻轻搭在小男孩身上像一条毯子；同一轮淡月挂在巷口上方，旁边有几颗小星星；"
        "屋檐下的小绿植安静地生长着；深蓝夜空里隐约泛起一丝暖色。"
        "画面安静、温柔、治愈，竖构图，人与猫在画面中下部。"
    ),
}

NO_TEXT = "画面中不出现任何文字、字母、招牌字、字幕、水印或签名。"


def build(theme, with_consistency=False):
    parts = [STYLE, COLOR, ISOLATION]
    if with_consistency:
        parts.append(CONSISTENCY)
    parts.append("主题：" + theme)
    parts.append(NO_TEXT)
    return "\n".join(parts)


def run(keys, ref_extra=None, model="gpt-image-2", size="1024x1536", quality="high"):
    os.makedirs(OUT, exist_ok=True)
    extra = []
    if ref_extra:
        extra = [ref_extra] if isinstance(ref_extra, str) else list(ref_extra)
    with cf.ThreadPoolExecutor(max_workers=len(keys)) as ex:
        futs = {}
        for k in keys:
            prompt = build(PLATES[k], with_consistency=bool(extra))
            refs = [REF_STYLE] + extra
            futs[ex.submit(_one, k, prompt, refs, model, size, quality)] = k
        for f in cf.as_completed(futs):
            print(futs[f], "->", f.result())


def _one(key, prompt, refs, model, size, quality):
    out = f"{OUT}/{key}.png"
    if os.path.exists(out):
        print("skip existing", out)
        return out
    try:
        return generate(prompt, out, model=model, size=size, quality=quality, ref=refs)
    except Exception as e:  # noqa: BLE001
        print("err with refs", refs, e, file=sys.stderr)
    return None


if __name__ == "__main__":
    keys = sys.argv[1].split(",") if len(sys.argv) > 1 else ["p1_alley"]
    extra = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != "-" else None
    run(keys, ref_extra=extra)
