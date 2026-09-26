#!/usr/bin/env python3
"""Build the offline interactive prompt assembler and tutorials gallery page."""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[3]
GALLERY = SKILL / "gallery" / "tutorials.html"
STYLES_JSON = SKILL / "references" / "styles.json"
LAYOUTS_JSON = SKILL / "references" / "layouts.json"
COLORS_JSON = SKILL / "references" / "colors.json"

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
from build_color_gallery import CATEGORIES as COLOR_CATEGORIES

TUTORIALS = [
    {
        "id": "poster-mindset",
        "summary_zh": "手绘 skill 里面的信息图类型不够用怎么办？可以把信息图当做海报来设计，你只要告知 skill 你要呈现的信息和使用场景，剩下的一切就交给 skill 来处理就好。",
        "summary_en": "What if preset infographic types aren't enough? Treat infographics as posters. Just provide your info and scenario, and let the skill handle the rest.",
        "prompt_zh": "做一张《山系露营轻量化装包》海报，把装备按睡眠系统（帐篷/睡袋）、烹饪系统（炉头/钛杯）、照明系统（马灯）分类，标注总重量控制在 8kg 内，户外手绘工装风。",
        "prompt_en": "Design an Ultralight Mountain Camping Packing Guide poster categorizing sleeping, cooking, and lighting gear, marked under 8kg, in vintage outdoor workwear silkscreen style.",
    },
    {
        "id": "modes-rule",
        "summary_zh": "想为图片自动添加排版文字？输入提示词：切换为图文模式。AI 会自动在画风笔触与文字版式之间建立呼吸感，让文字原生参与构图，图文一体。",
        "summary_en": "Want to automatically add layout text to your image? Enter: Switch to graphic-text mode. AI will create breathing space between linework and typography, letting text integrate natively into the composition.",
        "prompt_zh": "切换到图文模式",
        "prompt_en": "Switch to graphic-text mode",
    },
]

COPY_ICON_SVG = (
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>'
    '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>'
    '</svg>'
)


def individual_image_path(number: str) -> str:
    value = int(number)
    start = ((value - 1) // 200) * 200 + 1
    end = start + 199
    return f"../../../images/individual/{start:03}-{end:03}/{number}.webp"


def build_html() -> str:
    styles_raw = json.loads(STYLES_JSON.read_text(encoding="utf-8")) if STYLES_JSON.exists() else []
    layouts_raw = json.loads(LAYOUTS_JSON.read_text(encoding="utf-8")) if LAYOUTS_JSON.exists() else []
    colors_raw = json.loads(COLORS_JSON.read_text(encoding="utf-8")) if COLORS_JSON.exists() else []

    styles_data = [
        {
            "id": s["number"],
            "name": s["generation_name"],
            "ref": s["reference"],
            "group": s["group"][:1],
            "img": individual_image_path(s["number"]),
        }
        for s in styles_raw
    ]

    layouts_data = [
        {
            "id": l["id"],
            "name": l["name"],
            "name_en": l.get("name_en", l["name"]),
            "cat": l.get("category", "social-card"),
            "img": l["image"],
        }
        for l in layouts_raw
    ]

    colors_data = [
        {
            "id": c["id"],
            "name": c["name_zh"],
            "name_en": c["name_en"],
            "cat": c.get("category", "all"),
            "cat_zh": c.get("category_zh", ""),
            "cat_en": c.get("category_en", ""),
            "img": c["image"],
        }
        for c in colors_raw
    ]

    styles_json_str = json.dumps(styles_data, ensure_ascii=False, separators=(",", ":"))
    layouts_json_str = json.dumps(layouts_data, ensure_ascii=False, separators=(",", ":"))
    colors_json_str = json.dumps(colors_data, ensure_ascii=False, separators=(",", ":"))
    color_categories_data = [{"id": cid, "zh": czh, "en": cen} for cid, czh, cen in COLOR_CATEGORIES]
    color_categories_json_str = json.dumps(color_categories_data, ensure_ascii=False, separators=(",", ":"))

    cards = []
    for item in TUTORIALS:
        card_html = (
            f'<article class="tutorial-card">'
            f'<p class="card-summary" data-zh="{html.escape(item["summary_zh"])}" data-en="{html.escape(item["summary_en"])}">{html.escape(item["summary_zh"])}</p>'
            f'<div class="formula-box">'
            f'<button class="copy-btn" type="button" title="复制提示词" aria-label="复制提示词" data-prompt="{html.escape(item["prompt_zh"], quote=True)}">{COPY_ICON_SVG}</button>'
            f'<span class="formula-label" data-i18n="formulaLabel">示例提示词：</span>'
            f'<code class="formula-text" data-zh="{html.escape(item["prompt_zh"])}" data-en="{html.escape(item["prompt_en"])}">{html.escape(item["prompt_zh"])}</code>'
            f'</div>'
            f'</article>'
        )
        cards.append(card_html)
    cards_str = "\n".join(cards)

    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>手绘 Skill 提示词拼装器</title><style>
:root{{color:#24211e;background:#f7f5f0;font:16px/1.5 system-ui,"Microsoft YaHei",sans-serif}}
body{{margin:0}}
main{{max-width:1240px;margin:auto;padding:24px 30px 50px}}
.sticky-header{{position:sticky;top:0;z-index:100}}
.site-nav{{display:flex;align-items:center;gap:10px;margin:0;padding:12px 30px;border-bottom:1px solid #ded8cf;background:#fffdf9}}
.site-nav a{{border:1px solid #9e9185;border-radius:8px;background:#fff;color:#403a34;padding:7px 13px;text-decoration:none;font-weight:800;line-height:1.2;transition:background .15s,color .15s,border-color .15s}}
.site-nav a:hover{{border-color:#b74227;background:#fff0eb;color:#9f351f}}
.site-nav a[aria-current="page"]{{border-color:#b74227;background:#b74227;color:#fff;box-shadow:0 1px 3px #b7422744}}
.nav-right{{margin-left:auto;display:flex;align-items:center;gap:8px}}
.nav-ext{{display:inline-flex;align-items:center;font-weight:700}}
.nav-btn{{border:1px solid #9e9185;border-radius:8px;background:#fff;color:#403a34;padding:7px 13px;font:inherit;font-weight:700;line-height:1.2;cursor:pointer;transition:background .15s,color .15s,border-color .15s}}
.nav-btn:hover{{border-color:#b74227;background:#fff0eb;color:#9f351f}}
.nav-btn:focus-visible,.site-nav a:focus-visible{{outline:3px solid #d67d4d;outline-offset:3px}}

/* Assembler Studio */
.assembler-section{{margin-bottom:36px}}
.assembler-box{{background:#fff;border:1px solid #dcd5ca;border-radius:16px;padding:24px 26px;box-shadow:0 3px 12px rgba(0,0,0,0.04)}}
.assembler-header{{display:flex;align-items:baseline;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:18px;border-bottom:1px solid #eee8df;padding-bottom:14px}}
.assembler-title-wrap{{display:flex;align-items:center;gap:10px}}
.assembler-title{{margin:0;font-size:22px;font-weight:800;color:#24211e}}
.assembler-sub{{margin:0;font-size:13.5px;color:#786f65}}

/* Mode Radiobox */
.mode-row{{display:flex;align-items:center;gap:12px;margin-bottom:18px;flex-wrap:wrap}}
.mode-label{{font-size:14px;font-weight:750;color:#3b352f}}
.mode-group{{display:inline-flex;align-items:center;gap:4px;background:#eee8df;padding:3px;border-radius:8px;border:1px solid #dcd5ca}}
.mode-btn{{border:1px solid transparent;background:transparent;color:#514a43;font:inherit;font-size:13px;font-weight:750;padding:5px 14px;border-radius:6px;cursor:pointer;line-height:1.3;transition:all .15s}}
.mode-btn:hover{{color:#b74227;background:#ffffffa0}}
.mode-btn.is-active{{background:#b74227;color:#fff;border-color:#b74227;box-shadow:0 1px 3px rgba(183,66,39,0.3)}}

/* Form Fields */
.form-section{{display:flex;flex-direction:column;gap:12px;margin-bottom:20px}}
.form-group{{display:flex;flex-direction:column;gap:5px}}
.form-label{{font-size:13.5px;font-weight:700;color:#3b352f;display:flex;align-items:center;gap:4px}}
.form-label .req{{color:#b74227}}
.text-input{{width:100%;box-sizing:border-box;border:1px solid #c9c1b6;border-radius:8px;padding:9px 12px;font:inherit;font-size:14px;background:#fffdfa;color:#24211e;transition:border-color .15s,box-shadow .15s}}
.text-input:focus{{outline:none;border-color:#b74227;box-shadow:0 0 0 3px rgba(183,66,39,0.15)}}
.text-area{{min-height:58px;line-height:1.5;resize:vertical;font-family:inherit;overflow-y:auto}}
.extra-fields-grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
.extra-fields-grid[hidden]{{display:none!important}}

/* Slots Grid */
.slots-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:18px}}
.slot-card{{border:1px solid #ded8cf;border-radius:12px;background:#faf8f5;padding:12px 14px;display:flex;flex-direction:column;gap:8px;transition:border-color .15s,box-shadow .15s}}
.slot-card.has-value{{background:#fff;border-color:#b74227;box-shadow:0 2px 8px rgba(183,66,39,0.08)}}
.slot-header{{display:flex;align-items:center;justify-content:space-between;font-size:13px;font-weight:750;color:#514a43}}
.slot-title{{display:flex;align-items:center;gap:5px}}
.slot-optional{{font-size:11px;font-weight:600;color:#8c8276;background:#eee8df;padding:1px 5px;border-radius:3px}}
.slot-trigger{{width:100%;min-height:92px;border:2px dashed #c9c1b6;border-radius:8px;background:#fffdfa;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;cursor:pointer;color:#786f65;font:inherit;font-size:13px;font-weight:650;transition:all .15s}}
.slot-trigger:hover{{border-color:#b74227;color:#b74227;background:#fff8f5}}
.slot-filled{{display:flex;align-items:center;gap:10px;min-height:92px;box-sizing:border-box;background:#fff;border-radius:8px}}
.slot-img-wrap{{width:72px;height:72px;border-radius:6px;overflow:hidden;flex-shrink:0;background:#eee;border:1px solid #dcd5ca}}
.slot-img-wrap img{{width:100%;height:100%;object-fit:cover;display:block}}
.slot-meta{{display:flex;flex-direction:column;gap:3px;flex:1;min-width:0}}
.slot-code{{font-size:12px;font-weight:800;color:#b74227}}
.slot-name{{font-size:13px;font-weight:700;color:#24211e;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.slot-actions{{display:flex;flex-direction:column;gap:5px;flex-shrink:0;align-items:flex-end}}
.btn-change{{border:1px solid #c9c1b6;background:#fff;color:#514a43;border-radius:5px;padding:3px 7px;font:inherit;font-size:11.5px;font-weight:700;cursor:pointer;line-height:1.2;transition:all .15s}}
.btn-change:hover{{border-color:#b74227;color:#b74227;background:#fff8f5}}
.btn-clear{{border:0;background:transparent;color:#8c8276;font-size:16px;line-height:1;cursor:pointer;padding:2px 4px;border-radius:4px;transition:all .15s}}
.btn-clear:hover{{color:#b74227;background:#fff0eb}}

/* Toolbar */
.assembler-toolbar{{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:16px;flex-wrap:wrap}}
.toolbar-left{{display:flex;align-items:center;gap:10px}}
.btn-tool{{border:1px solid #c9c1b6;border-radius:7px;background:#fff;color:#403a34;padding:6px 12px;font:inherit;font-size:13px;font-weight:700;cursor:pointer;display:inline-flex;align-items:center;gap:6px;transition:all .15s}}
.btn-tool:hover{{border-color:#b74227;color:#b74227;background:#fff8f5}}
.btn-tool:focus-visible{{outline:2px solid #d67d4d;outline-offset:1px}}

/* Output Panel */
.output-box{{background:#f8f6f0;border-left:4px solid #b74227;border-radius:0 12px 12px 0;padding:16px 20px;border:1px solid #ded8cf;border-left-width:4px}}
.output-header{{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:8px;flex-wrap:wrap}}
.output-title{{font-size:14px;font-weight:800;color:#b74227}}
.copy-main-btn{{border:0;border-radius:6px;background:#b74227;color:#fff;padding:6px 14px;font:inherit;font-size:13px;font-weight:750;cursor:pointer;display:inline-flex;align-items:center;gap:6px;transition:background .15s,box-shadow .15s}}
.copy-main-btn:hover{{background:#cf4f33}}
.copy-main-btn.copied{{background:#2a854a}}
.assembled-text{{margin:0;font:14px/1.6 ui-monospace,SFMono-Regular,Consolas,"Liberation Mono",monospace;color:#24211e;white-space:pre-wrap;word-break:break-word;background:#fff;border:1px solid #e5dfd5;border-radius:6px;padding:10px 14px}}

/* Modal Picker */
dialog.picker-modal{{width:min(94vw,860px);max-height:86vh;padding:20px;border:0;border-radius:14px;background:#fff;color:#24211e;box-shadow:0 20px 60px rgba(0,0,0,0.2);box-sizing:border-box}}
dialog::backdrop{{background:#000a}}
.modal-header{{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}}
.modal-title{{margin:0;font-size:17px;font-weight:800;color:#24211e}}
.modal-close-btn{{border:0;border-radius:6px;background:#ece7df;color:#514a43;padding:5px 9px;font:inherit;font-size:13px;font-weight:700;cursor:pointer;transition:all .15s}}
.modal-close-btn:hover{{background:#b74227;color:#fff}}
.modal-nav{{display:flex;gap:6px;align-items:center;overflow-x:auto;-webkit-overflow-scrolling:touch;padding-bottom:8px;margin-bottom:10px}}
.modal-filter-btn{{border:1px solid #c9c1b6;background:#fff;color:#514a43;border-radius:6px;padding:4px 10px;font:inherit;font-size:12.5px;font-weight:700;white-space:nowrap;cursor:pointer;transition:all .15s}}
.modal-filter-btn:hover{{border-color:#b74227;color:#b74227;background:#fff8f5}}
.modal-filter-btn.is-active{{background:#b74227;color:#fff;border-color:#b74227}}
.modal-search-wrap{{margin-bottom:14px}}
.modal-search{{width:100%;box-sizing:border-box;border:1px solid #c9c1b6;border-radius:7px;padding:8px 12px;font:inherit;font-size:13.5px}}
.modal-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(115px,1fr));gap:10px;max-height:54vh;overflow-y:auto;padding-right:4px}}
.picker-card{{display:flex;flex-direction:column;box-sizing:border-box;padding:0;border:1px solid #ded8cf;border-radius:8px;background:#fff;cursor:pointer;overflow:hidden;text-align:left;transition:transform .15s,box-shadow .15s,border-color .15s}}
.picker-card:hover{{transform:translateY(-2px);border-color:#b74227;box-shadow:0 4px 12px rgba(0,0,0,0.1)}}
.picker-card.is-selected{{border-color:#b74227;box-shadow:0 0 0 2px #b74227}}
.picker-card-img{{width:100%;aspect-ratio:1/1;object-fit:cover;object-position:top;display:block;background:#eee}}
.picker-card-info{{padding:5px 6px;background:#fffdfa;display:flex;flex-direction:column;gap:1px}}
.picker-card-id{{font-size:10.5px;font-weight:800;color:#b74227}}
.picker-card-name{{font-size:11px;font-weight:700;color:#24211e;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;line-height:1.2}}

/* Retained Guides */
.guides-section{{margin-top:20px}}
.guides-title{{font-size:18px;font-weight:800;color:#24211e;margin:0 0 14px;display:flex;align-items:center;gap:6px}}
.tutorials-list{{display:flex;flex-direction:column;gap:16px}}
.tutorial-card{{border:1px solid #ded8cf;border-radius:14px;background:#fff;padding:18px 22px;box-shadow:0 2px 8px rgba(0,0,0,0.04);transition:transform .15s,box-shadow .15s}}
.tutorial-card:hover{{box-shadow:0 5px 16px rgba(0,0,0,0.07)}}
.card-summary{{margin:0 0 10px;font-size:14.5px;color:#2e2a25;line-height:1.6;font-weight:500}}
.formula-box{{display:flex;align-items:baseline;flex-wrap:wrap;gap:6px 8px;padding:10px 14px;background:#f8f6f0;border-left:4px solid #b74227;border-radius:0 8px 8px 0;margin:0}}
.formula-label{{font-size:13px;font-weight:750;color:#b74227;white-space:nowrap;user-select:none}}
.formula-text{{font-size:13.5px;font-weight:600;color:#332e29;word-break:break-word;flex:1 1 auto}}
.copy-btn{{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;padding:0;border:1px solid #c9c1b6;border-radius:5px;background:#fff;color:#b74227;cursor:pointer;transition:all .15s;flex-shrink:0;align-self:center}}
.copy-btn:hover{{border-color:#b74227;background:#fff0eb;color:#9f351f}}
.copy-btn.copied{{border-color:#2a854a;background:#2a854a;color:#fff}}
[hidden]{{display:none!important}}

@media(max-width:860px){{
  .slots-grid{{grid-template-columns:1fr}}
  .extra-fields-grid{{grid-template-columns:1fr}}
}}
@media(max-width:760px){{
  main{{padding:16px 18px 40px}}
  .site-nav{{padding:10px 16px;flex-wrap:wrap;gap:8px}}
  .nav-right{{width:100%;justify-content:flex-start;gap:6px;margin-left:0}}
  .site-nav a,.nav-btn{{padding:6px 10px;font-size:13px}}
  .assembler-box{{padding:16px 18px}}
  .modal-grid{{grid-template-columns:repeat(auto-fill,minmax(95px,1fr))}}
}}
</style></head><body>
<header class="sticky-header">
<nav class="site-nav" aria-label="画廊导航"><a href="index.html" data-i18n="stylesNav">风格画廊</a><a href="layouts.html" data-i18n="layoutsNav">图型画廊</a><a href="colors.html" data-i18n="colorsNav">色彩画廊</a><a href="tutorials.html" aria-current="page" data-i18n="tutorialsNav">提示词</a><div class="nav-right"><a class="nav-ext" href="https://github.com/yang0/handraw-style" target="_blank" rel="noopener noreferrer" title="GitHub 仓库"><svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" style="vertical-align:-2px;margin-right:4px" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>GitHub</a><a class="nav-ext" href="https://x.com/yang02010" target="_blank" rel="noopener noreferrer" title="X (Twitter) @yang02010"><svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" style="vertical-align:-2px;margin-right:4px" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>X (@yang02010)</a><button class="nav-btn" id="wechat-btn" type="button" data-i18n="wechatBtn">💬 创作变现交流群</button><button class="nav-btn" id="lang-btn" type="button" aria-label="Switch Language">🌐 EN / 中</button></div></nav>
</header>
<main>
<!-- Prompt Assembler Studio -->
<section class="assembler-section">
  <div class="assembler-box">
    <div class="assembler-header">
      <div class="assembler-title-wrap">
        <h1 class="assembler-title" data-i18n="assemblerTitle">🛠️ 提示词拼装器</h1>
      </div>
      <p class="assembler-sub" data-i18n="assemblerSub">交互式点选图型、风格与色彩，实时拼装出图指令。</p>
    </div>

    <!-- Mode Radiobox -->
    <div class="mode-row">
      <span class="mode-label" data-i18n="modeLabel">出图模式：</span>
      <div class="mode-group" role="radiogroup" aria-label="出图模式">
        <button type="button" class="mode-btn is-active" data-mode="pure" data-i18n="modePure">纯图</button>
        <button type="button" class="mode-btn" data-mode="graphic-text" data-i18n="modeGraphicText">图文</button>
        <button type="button" class="mode-btn" data-mode="poster" data-i18n="modePoster">海报</button>
      </div>
    </div>

    <!-- Form Input Fields -->
    <div class="form-section">
      <div class="form-group">
        <label for="input-theme" class="form-label">
          <span data-i18n="themeLabel">主题：</span>
          <span class="req">*</span>
        </label>
        <textarea id="input-theme" class="text-input text-area" rows="2" placeholder="输入画面主题，例如：秋天的第一杯奶茶 / 窗台晒太阳的猫咪..."></textarea>
      </div>

      <!-- Extra fields for poster mode only -->
      <div class="extra-fields-grid" id="poster-extra-fields" hidden>
        <div class="form-group">
          <label for="input-audience" class="form-label" data-i18n="audienceLabel">受众：</label>
          <input type="text" id="input-audience" class="text-input" placeholder="例如：年轻都市白领 / 露营爱好者 / 亲子家庭...">
        </div>
        <div class="form-group">
          <label for="input-channel" class="form-label" data-i18n="channelLabel">海报投放渠道：</label>
          <input type="text" id="input-channel" class="text-input" placeholder="例如：小红书 / 微信公众号封面 / 线下门店立牌...">
        </div>
      </div>
    </div>

    <!-- 3-in-1 Slot Pickers -->
    <div class="slots-grid">
      <!-- Layout Slot -->
      <div class="slot-card" id="slot-layout">
        <div class="slot-header">
          <span class="slot-title">📐 <span data-i18n="slotLayout">图型</span></span>
          <span class="slot-optional" data-i18n="optional">可选 (120)</span>
        </div>
        <button type="button" class="slot-trigger" data-picker="layout">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg>
          <span data-i18n="pickLayoutText">按图选择图型</span>
        </button>
        <div class="slot-filled" hidden>
          <div class="slot-img-wrap"><img src="" alt=""></div>
          <div class="slot-meta">
            <span class="slot-code"></span>
            <span class="slot-name"></span>
          </div>
          <div class="slot-actions">
            <button type="button" class="btn-change" data-picker="layout" data-i18n="changeBtn">更换</button>
            <button type="button" class="btn-clear" data-clear="layout" title="清除选择" aria-label="清除选择">×</button>
          </div>
        </div>
      </div>

      <!-- Style Slot -->
      <div class="slot-card" id="slot-style">
        <div class="slot-header">
          <span class="slot-title">🎨 <span data-i18n="slotStyle">风格</span></span>
          <span class="slot-optional" data-i18n="optional">可选 (278)</span>
        </div>
        <button type="button" class="slot-trigger" data-picker="style">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="10"/><path d="M12 2a4.5 4.5 0 0 0 0 9 4.5 4.5 0 0 1 0 9 10 10 0 0 1 0-18z"/></svg>
          <span data-i18n="pickStyleText">按图选择风格</span>
        </button>
        <div class="slot-filled" hidden>
          <div class="slot-img-wrap"><img src="" alt=""></div>
          <div class="slot-meta">
            <span class="slot-code"></span>
            <span class="slot-name"></span>
          </div>
          <div class="slot-actions">
            <button type="button" class="btn-change" data-picker="style" data-i18n="changeBtn">更换</button>
            <button type="button" class="btn-clear" data-clear="style" title="清除选择" aria-label="清除选择">×</button>
          </div>
        </div>
      </div>

      <!-- Theme Color Slot -->
      <div class="slot-card" id="slot-color">
        <div class="slot-header">
          <span class="slot-title">🌈 <span data-i18n="slotColor">主题色</span></span>
          <span class="slot-optional" data-i18n="optional">可选 (36)</span>
        </div>
        <button type="button" class="slot-trigger" data-picker="color">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 15h18"/></svg>
          <span data-i18n="pickColorText">按图选择色彩</span>
        </button>
        <div class="slot-filled" hidden>
          <div class="slot-img-wrap"><img src="" alt=""></div>
          <div class="slot-meta">
            <span class="slot-code"></span>
            <span class="slot-name"></span>
          </div>
          <div class="slot-actions">
            <button type="button" class="btn-change" data-picker="color" data-i18n="changeBtn">更换</button>
            <button type="button" class="btn-clear" data-clear="color" title="清除选择" aria-label="清除选择">×</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Action Toolbar -->
    <div class="assembler-toolbar">
      <div class="toolbar-left">
        <button type="button" id="btn-gacha" class="btn-tool" title="随机抽选图型、风格与色彩">
          <span>🎲</span>
          <span data-i18n="gachaBtn">智能随机抽卡</span>
        </button>
        <button type="button" id="btn-reset" class="btn-tool" title="清空全部已选">
          <span>🧹</span>
          <span data-i18n="resetBtn">一键清空</span>
        </button>
      </div>
    </div>

    <!-- Prompt Output Box -->
    <div class="output-box">
      <div class="output-header">
        <span class="output-title" data-i18n="outputTitle">📋 拼装生成的出图指令：</span>
        <button type="button" id="btn-copy-assembled" class="copy-main-btn">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
          <span id="copy-btn-text" data-i18n="copyPromptBtn">复制出图指令</span>
        </button>
      </div>
      <pre class="assembled-text" id="assembled-text"></pre>
    </div>
  </div>
</section>

<!-- Retained Guides -->
<section class="guides-section">
  <h2 class="guides-title" data-i18n="guidesTitle">📖 实战思维与技巧说明</h2>
  <div class="tutorials-list" id="tutorials-list">{cards_str}</div>
</section>
</main>

<!-- Reusable Visual Picker Dialog -->
<dialog id="picker-dialog" class="picker-modal" aria-labelledby="picker-title">
  <div class="modal-header">
    <h3 id="picker-title" class="modal-title">选择</h3>
    <button type="button" class="modal-close-btn close" aria-label="关闭">关闭 ×</button>
  </div>
  <div class="modal-nav" id="picker-filters"></div>
  <div class="modal-search-wrap">
    <input type="search" id="picker-search" class="modal-search" placeholder="输入编号或名称过滤...">
  </div>
  <div class="modal-grid" id="picker-grid"></div>
</dialog>

<!-- WeChat QR Modal -->
<dialog id="wechat-modal" aria-labelledby="wechat-title" style="width:min(94vw,560px);padding:22px;border:0;border-radius:14px;background:#1e1b18;color:#fff;box-shadow:0 20px 70px #000a;text-align:center"><button class="close" type="button" aria-label="关闭" style="position:absolute;top:12px;right:12px;border:0;border-radius:7px;padding:5px 9px;background:#fff;color:#24211e;cursor:pointer;font:inherit">关闭 ×</button><h3 id="wechat-title" style="margin:4px 0 10px;font-size:17px;color:#fff" data-i18n="wechatTitle">💬 创作变现交流群</h3><p style="margin:0 0 4px;font-size:14px;color:#eee" data-i18n="wechatSub">请优先加群，满了的话也可以尝试加我个人微信</p><p style="margin:0 0 16px;font-size:13px;color:#d67d4d;font-weight:600" data-i18n="wechatNote">请备注：手绘</p><div style="display:flex;justify-content:center;align-items:flex-start;gap:24px;flex-wrap:wrap"><div style="flex:1 1 200px;max-width:240px;background:#fff;padding:10px;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,0.3)"><div style="color:#24211e;font-size:13px;font-weight:700;margin-bottom:6px" data-i18n="wechatGroupLabel">① 优先加入群聊</div><img src="../../../images/wechat_group.png" onerror="this.onerror=null;this.src='https://raw.githubusercontent.com/yang0/handraw-style/master/images/wechat_group.png';" alt="手绘交流群二维码" style="display:block;width:100%;height:auto;border-radius:6px"></div><div style="flex:1 1 200px;max-width:240px;background:#fff;padding:10px;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,0.3)"><div style="color:#24211e;font-size:13px;font-weight:700;margin-bottom:6px" data-i18n="wechatPersonalLabel">② 个人微信备用</div><img src="../../../images/wechat_personal.png" onerror="this.onerror=null;this.src='https://raw.githubusercontent.com/yang0/handraw-style/master/images/wechat_personal.png';" alt="旺德福个人微信二维码" style="display:block;width:100%;height:auto;border-radius:6px"></div></div><div style="margin-top:16px;padding-top:12px;border-top:1px solid #332f2b;display:flex;justify-content:center;gap:16px;font-size:13px"><a href="https://github.com/yang0/handraw-style" target="_blank" rel="noopener noreferrer" style="color:#d67d4d;text-decoration:none;font-weight:600">GitHub 仓库 ↗</a><a href="https://x.com/yang02010" target="_blank" rel="noopener noreferrer" style="color:#d67d4d;text-decoration:none;font-weight:600">X @yang02010 ↗</a></div></dialog>

<script>
const STYLES_DATA = {styles_json_str};
const LAYOUTS_DATA = {layouts_json_str};
const COLORS_DATA = {colors_json_str};
const COLOR_CATEGORIES = {color_categories_json_str};

const wechatBtn=document.querySelector('#wechat-btn'),wechatModal=document.querySelector('#wechat-modal'),langBtn=document.querySelector('#lang-btn');
const inputTheme=document.querySelector('#input-theme'),inputAudience=document.querySelector('#input-audience'),inputChannel=document.querySelector('#input-channel'),posterExtraFields=document.querySelector('#poster-extra-fields');
const assembledText=document.querySelector('#assembled-text'),btnCopyAssembled=document.querySelector('#btn-copy-assembled'),copyBtnText=document.querySelector('#copy-btn-text');
const pickerDialog=document.querySelector('#picker-dialog'),pickerTitle=document.querySelector('#picker-title'),pickerFilters=document.querySelector('#picker-filters'),pickerSearch=document.querySelector('#picker-search'),pickerGrid=document.querySelector('#picker-grid');

let currentMode = 'pure'; // 'pure' | 'graphic-text' | 'poster'
let selectedLayout = null;
let selectedStyle = null;
let selectedColor = null;
let currentPickerType = null;
let currentPickerFilter = 'all';

const I18N = {{
  zh: {{
    pageTitle: "手绘 Skill 提示词拼装器",
    stylesNav: "风格画廊",
    layoutsNav: "图型画廊",
    colorsNav: "色彩画廊",
    tutorialsNav: "提示词",
    wechatBtn: "💬 创作变现交流群",
    assemblerTitle: "🛠️ 提示词拼装器",
    assemblerSub: "交互式点选图型、风格与色彩，实时拼装出图指令。",
    modeLabel: "出图模式：",
    modePure: "纯图",
    modeGraphicText: "图文",
    modePoster: "海报",
    themeLabel: "主题：",
    audienceLabel: "受众：",
    channelLabel: "海报投放渠道：",
    themePlaceholder: "输入画面主题，例如：秋天的第一杯奶茶 / 窗台晒太阳的猫咪...",
    audiencePlaceholder: "例如：年轻都市白领 / 露营爱好者 / 亲子家庭...",
    channelPlaceholder: "例如：小红书 / 微信公众号封面 / 线下门店立牌...",
    slotLayout: "图型",
    slotStyle: "风格",
    slotColor: "主题色",
    optional: "可选",
    pickLayoutText: "按图选择图型 (120)",
    pickStyleText: "按图选择风格 (278)",
    pickColorText: "按图选择主题色 (36)",
    changeBtn: "更换",
    gachaBtn: "智能随机抽卡",
    resetBtn: "一键清空",
    outputTitle: "📋 拼装生成的出图指令：",
    copyPromptBtn: "复制出图指令",
    copied: "已复制！",
    guidesTitle: "📖 实战思维与技巧说明",
    formulaLabel: "示例提示词：",
    searchPlaceholder: "输入编号或名称过滤...",
    pickerTitleLayout: "选择图型 (120)",
    pickerTitleStyle: "选择手绘风格 (278)",
    pickerTitleColor: "选择主题色 (36)",
    filterAll: "全部",
    filterSocialCard: "社媒卡 (SC)",
    filterInfographic: "信息图 (IG)",
    filterComicStoryboard: "漫画分镜 (SB)",
    filterBlue: "经典蓝系",
    filterGreen: "清新绿系",
    filterRed: "古典红绿",
    filterPurple: "浪漫粉紫",
    filterWarm: "暖阳大地",
    filterNeutral: "中性色系",
    fallbackPrompt: "其他你帮我选择",
    themeEmptyText: "【输入主题】",
    audienceEmptyText: "【输入受众】",
    channelEmptyText: "【输入海报投放渠道】",
    wechatTitle: "💬 创作变现交流群",
    wechatSub: "请优先加群，满了的话也可以尝试加我个人微信",
    wechatNote: "请备注：手绘",
    wechatGroupLabel: "① 优先加入群聊",
    wechatPersonalLabel: "② 个人微信备用",
    langBtn: "🌐 English"
  }},
  en: {{
    pageTitle: "Prompt Assembler | Handraw Style Prompter",
    stylesNav: "Styles",
    layoutsNav: "Layouts",
    colorsNav: "Colors",
    tutorialsNav: "Prompts",
    wechatBtn: "💬 Creator Community",
    assemblerTitle: "🛠️ Prompt Assembler",
    assemblerSub: "Visually select layout, style, and color to assemble prompt commands in real time.",
    modeLabel: "Mode:",
    modePure: "Image Only",
    modeGraphicText: "Graphic-Text",
    modePoster: "Poster",
    themeLabel: "Theme:",
    audienceLabel: "Audience:",
    channelLabel: "Distribution Channel:",
    themePlaceholder: "Enter theme, e.g. Autumn milk tea / Cat sunbathing on windowsill...",
    audiencePlaceholder: "e.g. Young urban professionals / Campers / Families...",
    channelPlaceholder: "e.g. Instagram / RED / Store poster stand...",
    slotLayout: "Layout",
    slotStyle: "Style",
    slotColor: "Theme Color",
    optional: "Optional",
    pickLayoutText: "Pick Layout (120)",
    pickStyleText: "Pick Style (278)",
    pickColorText: "Pick Theme Color (36)",
    changeBtn: "Change",
    gachaBtn: "Random Gacha",
    resetBtn: "Reset All",
    outputTitle: "📋 Assembled Generation Command:",
    copyPromptBtn: "Copy Command",
    copied: "Copied!",
    guidesTitle: "📖 Practical Guides & Principles",
    formulaLabel: "Example Prompt:",
    searchPlaceholder: "Search ID or name...",
    pickerTitleLayout: "Select Layout (120)",
    pickerTitleStyle: "Select Style (278)",
    pickerTitleColor: "Select Theme Color (36)",
    filterAll: "All",
    filterSocialCard: "Social Cards (SC)",
    filterInfographic: "Infographics (IG)",
    filterComicStoryboard: "Comic Storyboards (SB)",
    filterBlue: "Classic Blue",
    filterGreen: "Fresh Green",
    filterRed: "Classic Red & Vintage",
    filterPurple: "Romantic Pink & Purple",
    filterWarm: "Warm Sun & Earth",
    filterNeutral: "Classic Neutral Tones",
    fallbackPrompt: "pick the rest for me",
    themeEmptyText: "[Enter Theme]",
    audienceEmptyText: "[Enter Audience]",
    channelEmptyText: "[Enter Channel]",
    wechatTitle: "💬 Creator Monetization Community",
    wechatSub: "Please prioritize joining the group; if full, try adding personal WeChat",
    wechatNote: "Note: handdraw",
    wechatGroupLabel: "① Join Group (Priority)",
    wechatPersonalLabel: "② Personal WeChat (Fallback)",
    langBtn: "🌐 中文"
  }}
}};

let currentLang = localStorage.getItem('handdraw_lang') || ((navigator.language && navigator.language.startsWith('zh')) ? 'zh' : 'en');

function updatePrompt() {{
  const isZh = currentLang === 'zh';
  const t = I18N[currentLang];
  const parts = [];

  // Prefix based on mode
  if (currentMode === 'poster') {{
    parts.push(isZh ? '请帮我出海报提示词' : 'Please generate a poster prompt for me');
  }} else if (currentMode === 'graphic-text') {{
    parts.push(isZh ? '图文模式' : 'Graphic-text mode');
  }}

  // Layout
  if (selectedLayout) {{
    parts.push(isZh ? `图型：${{selectedLayout.id}}` : `Layout: ${{selectedLayout.id}}`);
  }}

  // Style
  if (selectedStyle) {{
    parts.push(isZh ? `风格：${{selectedStyle.id}}` : `Style: ${{selectedStyle.id}}`);
  }}

  // Theme color
  if (selectedColor) {{
    parts.push(isZh ? `主题色：${{selectedColor.id}}` : `Theme color: ${{selectedColor.id}}`);
  }}

  // Fallback: if style OR color is missing, inject "其他你帮我选择"
  const missingStyleOrColor = !selectedStyle || !selectedColor;
  if (missingStyleOrColor) {{
    parts.push(t.fallbackPrompt);
  }}

  // Theme
  const themeVal = inputTheme.value.trim();
  const themeDisplay = themeVal || t.themeEmptyText;
  parts.push(isZh ? `主题：${{themeDisplay}}` : `Theme: ${{themeDisplay}}`);

  // Extra fields for poster mode
  if (currentMode === 'poster') {{
    const audienceVal = inputAudience.value.trim();
    const audienceDisplay = audienceVal || t.audienceEmptyText;
    parts.push(isZh ? `受众：${{audienceDisplay}}` : `Audience: ${{audienceDisplay}}`);

    const channelVal = inputChannel.value.trim();
    const channelDisplay = channelVal || t.channelEmptyText;
    parts.push(isZh ? `海报投放渠道：${{channelDisplay}}` : `Channel: ${{channelDisplay}}`);
  }}

  const delimiter = isZh ? '，' : ', ';
  assembledText.textContent = parts.join(delimiter);
}}

function updateSlotUI(type) {{
  const slotEl = document.querySelector(`#slot-${{type}}`);
  if (!slotEl) return;
  const trigger = slotEl.querySelector('.slot-trigger');
  const filled = slotEl.querySelector('.slot-filled');
  const img = filled.querySelector('img');
  const code = filled.querySelector('.slot-code');
  const name = filled.querySelector('.slot-name');

  let item = null;
  if (type === 'layout') item = selectedLayout;
  if (type === 'style') item = selectedStyle;
  if (type === 'color') item = selectedColor;

  if (item) {{
    slotEl.classList.add('has-value');
    trigger.hidden = true;
    filled.hidden = false;
    img.src = item.img;
    img.alt = item.name;
    code.textContent = item.id ? (type === 'style' ? `#${{item.id}}` : item.id) : '';
    name.textContent = currentLang === 'en' && item.name_en ? item.name_en : item.name;
  }} else {{
    slotEl.classList.remove('has-value');
    trigger.hidden = false;
    filled.hidden = true;
    img.src = '';
    code.textContent = '';
    name.textContent = '';
  }}
}}

function setMode(mode) {{
  currentMode = mode;
  document.querySelectorAll('.mode-btn').forEach(btn => {{
    btn.classList.toggle('is-active', btn.dataset.mode === mode);
  }});
  if (mode === 'poster') {{
    posterExtraFields.hidden = false;
  }} else {{
    posterExtraFields.hidden = true;
  }}
  updatePrompt();
}}

// Visual Picker Logic
function openPicker(type) {{
  currentPickerType = type;
  currentPickerFilter = 'all';
  pickerSearch.value = '';
  pickerSearch.placeholder = I18N[currentLang].searchPlaceholder;

  if (type === 'layout') {{
    pickerTitle.textContent = I18N[currentLang].pickerTitleLayout;
    renderLayoutFilters();
  }} else if (type === 'style') {{
    pickerTitle.textContent = I18N[currentLang].pickerTitleStyle;
    renderStyleFilters();
  }} else if (type === 'color') {{
    pickerTitle.textContent = I18N[currentLang].pickerTitleColor;
    renderColorFilters();
  }}
  renderPickerItems();
  pickerDialog.showModal();
}}

function renderLayoutFilters() {{
  const t = I18N[currentLang];
  const scCount = LAYOUTS_DATA.filter(x => x.cat === 'social-card').length;
  const igCount = LAYOUTS_DATA.filter(x => x.cat === 'infographic').length;
  const sbCount = LAYOUTS_DATA.filter(x => x.cat === 'comic-storyboard').length;
  pickerFilters.innerHTML = `
    <button type="button" class="modal-filter-btn is-active" data-filter="all">${{t.filterAll}} (${{LAYOUTS_DATA.length}})</button>
    <button type="button" class="modal-filter-btn" data-filter="social-card">${{t.filterSocialCard}} (${{scCount}})</button>
    <button type="button" class="modal-filter-btn" data-filter="infographic">${{t.filterInfographic}} (${{igCount}})</button>
    <button type="button" class="modal-filter-btn" data-filter="comic-storyboard">${{t.filterComicStoryboard}} (${{sbCount}})</button>
  `;
  attachFilterEvents();
}}

function renderStyleFilters() {{
  const t = I18N[currentLang];
  const groups = ['all','A','B','C','D','E','F','G','H'];
  pickerFilters.innerHTML = groups.map(g => {{
    const label = g === 'all' ? `${{t.filterAll}} (278)` : g;
    return `<button type="button" class="modal-filter-btn${{g==='all'?' is-active':''}}" data-filter="${{g}}">${{label}}</button>`;
  }}).join('');
  attachFilterEvents();
}}

function renderColorFilters() {{
  const isZh = currentLang === 'zh';
  pickerFilters.innerHTML = COLOR_CATEGORIES.map(cat => {{
    const count = cat.id === 'all' ? COLORS_DATA.length : COLORS_DATA.filter(x => x.cat === cat.id).length;
    const label = isZh ? cat.zh : cat.en;
    const isActive = currentPickerFilter === cat.id ? ' is-active' : '';
    return `<button type="button" class="modal-filter-btn${{isActive}}" data-filter="${{cat.id}}">${{label}} (${{count}})</button>`;
  }}).join('');
  attachFilterEvents();
}}

function attachFilterEvents() {{
  pickerFilters.querySelectorAll('.modal-filter-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
      pickerFilters.querySelectorAll('.modal-filter-btn').forEach(b => b.classList.remove('is-active'));
      btn.classList.add('is-active');
      currentPickerFilter = btn.dataset.filter;
      renderPickerItems();
    }});
  }});
}}

function renderPickerItems() {{
  const query = pickerSearch.value.trim().toLowerCase();
  let list = [];
  let selectedId = null;

  if (currentPickerType === 'layout') {{
    list = LAYOUTS_DATA;
    selectedId = selectedLayout ? selectedLayout.id : null;
  }} else if (currentPickerType === 'style') {{
    list = STYLES_DATA;
    selectedId = selectedStyle ? selectedStyle.id : null;
  }} else if (currentPickerType === 'color') {{
    list = COLORS_DATA;
    selectedId = selectedColor ? selectedColor.id : null;
  }}

  const filtered = list.filter(item => {{
    // Category match
    if (currentPickerType === 'layout') {{
      if (currentPickerFilter !== 'all' && item.cat !== currentPickerFilter) return false;
    }} else if (currentPickerType === 'style') {{
      if (currentPickerFilter !== 'all' && item.group !== currentPickerFilter) return false;
    }} else if (currentPickerType === 'color') {{
      if (currentPickerFilter !== 'all' && item.cat !== currentPickerFilter) return false;
    }}
    // Search match
    if (query) {{
      const idMatch = item.id.toLowerCase().includes(query);
      const nameMatch = item.name.toLowerCase().includes(query);
      const nameEnMatch = item.name_en && item.name_en.toLowerCase().includes(query);
      const refMatch = item.ref && item.ref.toLowerCase().includes(query);
      return idMatch || nameMatch || nameEnMatch || refMatch;
    }}
    return true;
  }});

  pickerGrid.innerHTML = filtered.map(item => {{
    const isSel = selectedId === item.id;
    const displayName = currentLang === 'en' && item.name_en ? item.name_en : item.name;
    const badge = currentPickerType === 'style' ? `#${{item.id}}` : item.id;
    return `
      <button type="button" class="picker-card${{isSel ? ' is-selected' : ''}}" data-id="${{item.id}}">
        <img class="picker-card-img" src="${{item.img}}" alt="${{displayName}}">
        <div class="picker-card-info">
          <span class="picker-card-id">${{badge}}</span>
          <span class="picker-card-name" title="${{displayName}}">${{displayName}}</span>
        </div>
      </button>
    `;
  }}).join('');

  pickerGrid.querySelectorAll('.picker-card').forEach(card => {{
    card.addEventListener('click', () => {{
      const id = card.dataset.id;
      const found = list.find(x => x.id === id);
      if (currentPickerType === 'layout') selectedLayout = found;
      if (currentPickerType === 'style') selectedStyle = found;
      if (currentPickerType === 'color') selectedColor = found;
      updateSlotUI(currentPickerType);
      updatePrompt();
      pickerDialog.close();
    }});
  }});
}}

pickerSearch.addEventListener('input', renderPickerItems);
pickerDialog.querySelector('.close').addEventListener('click', () => pickerDialog.close());
pickerDialog.addEventListener('click', e => {{ if (e.target === pickerDialog) pickerDialog.close(); }});

// Triggers & Clears
document.addEventListener('click', e => {{
  const trigger = e.target.closest('[data-picker]');
  if (trigger) {{
    openPicker(trigger.dataset.picker);
    return;
  }}
  const clearBtn = e.target.closest('[data-clear]');
  if (clearBtn) {{
    const type = clearBtn.dataset.clear;
    if (type === 'layout') selectedLayout = null;
    if (type === 'style') selectedStyle = null;
    if (type === 'color') selectedColor = null;
    updateSlotUI(type);
    updatePrompt();
    return;
  }}
}});

// Mode radio buttons
document.querySelectorAll('.mode-btn').forEach(btn => {{
  btn.addEventListener('click', () => setMode(btn.dataset.mode));
}});

// Inputs change
function autoResizeTheme() {{
  if (!inputTheme) return;
  inputTheme.style.height = 'auto';
  inputTheme.style.height = Math.max(inputTheme.scrollHeight, 58) + 'px';
}}

[inputAudience, inputChannel].forEach(el => {{
  el.addEventListener('input', updatePrompt);
}});
if (inputTheme) {{
  inputTheme.addEventListener('input', () => {{
    autoResizeTheme();
    updatePrompt();
  }});
}}

// Toolbar Actions: Gacha & Reset
document.querySelector('#btn-gacha').addEventListener('click', () => {{
  // Random layout
  selectedLayout = LAYOUTS_DATA[Math.floor(Math.random() * LAYOUTS_DATA.length)];
  // Random style
  selectedStyle = STYLES_DATA[Math.floor(Math.random() * STYLES_DATA.length)];
  // Random color
  selectedColor = COLORS_DATA[Math.floor(Math.random() * COLORS_DATA.length)];

  updateSlotUI('layout');
  updateSlotUI('style');
  updateSlotUI('color');
  updatePrompt();
}});

document.querySelector('#btn-reset').addEventListener('click', () => {{
  selectedLayout = null;
  selectedStyle = null;
  selectedColor = null;
  inputTheme.value = '';
  inputTheme.style.height = '';
  inputAudience.value = '';
  inputChannel.value = '';
  updateSlotUI('layout');
  updateSlotUI('style');
  updateSlotUI('color');
  setMode('pure');
}});

// Copy Assembled Prompt
btnCopyAssembled.addEventListener('click', async () => {{
  const text = assembledText.textContent;
  if (!text) return;
  try {{
    await navigator.clipboard.writeText(text);
    copyBtnText.textContent = I18N[currentLang].copied;
    btnCopyAssembled.classList.add('copied');
    setTimeout(() => {{
      copyBtnText.textContent = I18N[currentLang].copyPromptBtn;
      btnCopyAssembled.classList.remove('copied');
    }}, 1500);
  }} catch (e) {{
    const area = document.createElement('textarea');
    area.value = text;
    document.body.append(area);
    area.select();
    document.execCommand('copy');
    area.remove();
    copyBtnText.textContent = I18N[currentLang].copied;
    btnCopyAssembled.classList.add('copied');
    setTimeout(() => {{
      copyBtnText.textContent = I18N[currentLang].copyPromptBtn;
      btnCopyAssembled.classList.remove('copied');
    }}, 1500);
  }}
}});

// I18N handling
function applyLang(lang) {{
  currentLang = lang;
  localStorage.setItem('handdraw_lang', lang);
  document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
  const t = I18N[lang];
  document.title = t.pageTitle;

  document.querySelectorAll('[data-i18n]').forEach(el => {{
    const key = el.dataset.i18n;
    if (t[key]) el.textContent = t[key];
  }});

  document.querySelectorAll('[data-zh][data-en]').forEach(el => {{
    el.textContent = lang === 'zh' ? el.dataset.zh : el.dataset.en;
  }});

  inputTheme.placeholder = t.themePlaceholder;
  inputAudience.placeholder = t.audiencePlaceholder;
  inputChannel.placeholder = t.channelPlaceholder;

  document.querySelectorAll('.copy-btn').forEach(btn => {{
    const box = btn.closest('.formula-box');
    if (box) {{
      const formula = box.querySelector('.formula-text');
      if (formula) btn.dataset.prompt = formula.dataset[lang];
    }}
  }});

  if (langBtn) langBtn.textContent = t.langBtn;
  updateSlotUI('layout');
  updateSlotUI('style');
  updateSlotUI('color');
  updatePrompt();
  if (pickerDialog.open) {{
    if (currentPickerType === 'layout') {{
      pickerTitle.textContent = t.pickerTitleLayout;
      renderLayoutFilters();
    }} else if (currentPickerType === 'style') {{
      pickerTitle.textContent = t.pickerTitleStyle;
      renderStyleFilters();
    }} else if (currentPickerType === 'color') {{
      pickerTitle.textContent = t.pickerTitleColor;
      renderColorFilters();
    }}
    renderPickerItems();
  }}
}}

if (langBtn) {{
  langBtn.addEventListener('click', () => applyLang(currentLang === 'zh' ? 'en' : 'zh'));
}}
applyLang(currentLang);

// Copy for retained tutorial cards
const COPY_ICON = '{COPY_ICON_SVG}';
const CHECK_ICON = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>';

document.querySelectorAll('.formula-box').forEach(box => {{
  const btn = box.querySelector('.copy-btn');
  const label = box.querySelector('.formula-label');
  const doCopy = async () => {{
    if (!btn) return;
    const prompt = btn.dataset.prompt;
    if (!prompt) return;
    try {{
      await navigator.clipboard.writeText(prompt);
      btn.innerHTML = CHECK_ICON;
      btn.classList.add('copied');
      setTimeout(() => {{
        btn.innerHTML = COPY_ICON;
        btn.classList.remove('copied');
      }}, 1500);
    }} catch (e) {{}}
  }};
  if (btn) btn.addEventListener('click', doCopy);
  if (label) {{
    label.style.cursor = 'pointer';
    label.addEventListener('click', doCopy);
  }}
}});

if (wechatBtn && wechatModal) {{
  wechatBtn.addEventListener('click', () => wechatModal.showModal());
  wechatModal.querySelectorAll('.close').forEach(btn => btn.addEventListener('click', () => wechatModal.close()));
  wechatModal.addEventListener('click', e => {{ if (e.target === wechatModal) wechatModal.close(); }});
}}
</script></body></html>'''


def main() -> None:
    GALLERY.write_text(build_html(), encoding="utf-8")
    print(f"Built interactive tutorials & prompt assembler gallery: {GALLERY}")


if __name__ == "__main__":
    main()
