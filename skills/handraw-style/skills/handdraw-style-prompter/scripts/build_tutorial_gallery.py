#!/usr/bin/env python3
"""Build the offline tutorials gallery page."""
from __future__ import annotations

import html
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
GALLERY = SKILL / "gallery" / "tutorials.html"

TUTORIALS = [
    {
        "id": "poster-mindset",
        "summary_zh": "手绘 skill 里面的信息图类型不够用怎么办？可以把信息图当做海报来设计，你只要告知 skill 你要呈现的信息和使用场景，剩下的一切就交给 skill 来处理就好。",
        "summary_en": "What if preset infographic types aren't enough? Treat infographics as posters. Just provide your info and scenario, and let the skill handle the rest.",
        "prompt_zh": "做一张《山系露营轻量化装包》海报，把装备按睡眠系统（帐篷/睡袋）、烹饪系统（炉头/钛杯）、照明系统（马灯）分类，标注总重量控制在 8kg 内，户外手绘工装风。",
        "prompt_en": "Design an Ultralight Mountain Camping Packing Guide poster categorizing sleeping, cooking, and lighting gear, marked under 8kg, in vintage outdoor workwear silkscreen style.",
    },
    {
        "id": "auto-recommend",
        "summary_zh": "这么多风格有时候懒得挑，那么可以试试抽卡：",
        "summary_en": "Too many styles to choose from? Try pulling a gacha card:",
        "prompt_zh": "帮我生成猫咪在窗台晒太阳的治愈插画提示词，你帮我选风格和主题色（可组合）",
        "prompt_en": "Generate a prompt for a healing illustration of a cat sunbathing on a windowsill, pick the style and theme color for me (can combine)",
    },
    {
        "id": "triad-method",
        "summary_zh": "精准组装法：",
        "summary_en": "Precise Assembly:",
        "prompt_zh": "图型：SC-001，风格：041，主题色：C-01，主题：秋天的第一杯奶茶",
        "prompt_en": "Layout: SC-001, Style: 041, Theme color: C-01, Theme: First milk tea of autumn",
    },
    {
        "id": "modes-rule",
        "summary_zh": "想为图片自动添加文字？输入提示词：",
        "summary_en": "Want to automatically add text to your image? Enter:",
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


def build_html() -> str:
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
<title>手绘 Skill 实操教程与进阶技巧</title><style>
:root{{color:#24211e;background:#f7f5f0;font:16px/1.5 system-ui,"Microsoft YaHei",sans-serif}} body{{margin:0}} main{{max-width:1200px;margin:auto;padding:24px 30px 40px}} .sticky-header{{position:sticky;top:0;z-index:100}} .site-nav{{display:flex;align-items:center;gap:10px;margin:0;padding:12px 30px;border-bottom:1px solid #ded8cf;background:#fffdf9}} .site-nav a{{border:1px solid #9e9185;border-radius:8px;background:#fff;color:#403a34;padding:7px 13px;text-decoration:none;font-weight:800;line-height:1.2;transition:background .15s,color .15s,border-color .15s}} .site-nav a:hover{{border-color:#b74227;background:#fff0eb;color:#9f351f}} .site-nav a[aria-current="page"]{{border-color:#b74227;background:#b74227;color:#fff;box-shadow:0 1px 3px #b7422744}} .nav-right{{margin-left:auto;display:flex;align-items:center;gap:8px}} .nav-ext{{display:inline-flex;align-items:center;font-weight:700}} .nav-btn{{border:1px solid #9e9185;border-radius:8px;background:#fff;color:#403a34;padding:7px 13px;font:inherit;font-weight:700;line-height:1.2;cursor:pointer;transition:background .15s,color .15s,border-color .15s}} .nav-btn:hover{{border-color:#b74227;background:#fff0eb;color:#9f351f}} .nav-btn:focus-visible,.site-nav a:focus-visible{{outline:3px solid #d67d4d;outline-offset:3px}} .tutorials-list{{display:flex;flex-direction:column;gap:18px}} .tutorial-card{{border:1px solid #ded8cf;border-radius:14px;background:#fff;padding:20px 24px;box-shadow:0 2px 8px rgba(0,0,0,0.04);transition:transform .15s,box-shadow .15s}} .tutorial-card:hover{{box-shadow:0 6px 20px rgba(0,0,0,0.08)}} .card-summary{{margin:0 0 12px;font-size:15px;color:#2e2a25;line-height:1.6;font-weight:500}} .formula-box{{display:flex;align-items:baseline;flex-wrap:wrap;gap:6px 8px;padding:12px 16px;background:#f8f6f0;border-left:4px solid #b74227;border-radius:0 8px 8px 0;margin:0}} .formula-label{{font-size:13.5px;font-weight:750;color:#b74227;white-space:nowrap;user-select:none}} .formula-text{{font-size:14px;font-weight:600;color:#332e29;word-break:break-word;flex:1 1 auto}} .copy-btn{{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;padding:0;border:1px solid #c9c1b6;border-radius:5px;background:#fff;color:#b74227;cursor:pointer;transition:all .15s;flex-shrink:0;align-self:center}} .copy-btn:hover{{border-color:#b74227;background:#fff0eb;color:#9f351f}} .copy-btn.copied{{border-color:#2a854a;background:#2a854a;color:#fff}} [hidden]{{display:none!important}} @media(max-width:760px){{main{{padding:16px 18px}} .site-nav{{padding:10px 16px;flex-wrap:wrap;gap:8px}} .nav-right{{width:100%;justify-content:flex-start;gap:6px;margin-left:0}} .site-nav a,.nav-btn{{padding:6px 10px;font-size:13px}} .tutorial-card{{padding:16px}} .formula-box{{padding:10px 12px;gap:6px}}}}
</style></head><body>
<header class="sticky-header">
<nav class="site-nav" aria-label="画廊导航"><a href="index.html" data-i18n="stylesNav">风格画廊</a><a href="layouts.html" data-i18n="layoutsNav">图型画廊</a><a href="colors.html" data-i18n="colorsNav">色彩画廊</a><a href="tutorials.html" aria-current="page" data-i18n="tutorialsNav">实操教程</a><div class="nav-right"><a class="nav-ext" href="https://github.com/yang0/handraw-style" target="_blank" rel="noopener noreferrer" title="GitHub 仓库"><svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" style="vertical-align:-2px;margin-right:4px" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>GitHub</a><a class="nav-ext" href="https://x.com/yang02010" target="_blank" rel="noopener noreferrer" title="X (Twitter) @yang02010"><svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" style="vertical-align:-2px;margin-right:4px" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>X (@yang02010)</a><button class="nav-btn" id="wechat-btn" type="button" data-i18n="wechatBtn">💬 交流群 / 作者微信</button><button class="nav-btn" id="lang-btn" type="button" aria-label="Switch Language">🌐 EN / 中</button></div></nav>
</header>
<main>
<section class="tutorials-list" id="tutorials-list">{cards_str}</section>
</main>
<dialog id="wechat-modal" aria-labelledby="wechat-title" style="width:min(90vw,360px);padding:20px;border:0;border-radius:14px;background:#1e1b18;color:#fff;box-shadow:0 20px 70px #000a;text-align:center"><button class="close" type="button" aria-label="关闭" style="position:absolute;top:12px;right:12px;border:0;border-radius:7px;padding:5px 9px;background:#fff;color:#24211e;cursor:pointer;font:inherit">关闭 ×</button><h3 id="wechat-title" style="margin:4px 0 14px;font-size:17px;color:#fff" data-i18n="wechatTitle">💬 交流群 / 作者微信</h3><img id="wechat-img" src="https://raw.githubusercontent.com/yang0/handraw-style/master/images/wechat_community.jpg" onerror="this.onerror=null;this.src='../../../images/wechat_personal_fallback.jpg';const s=document.getElementById('wechat-status');if(s)s.textContent='（已切换为本地备用二维码）';" alt="微信二维码" style="display:block;width:100%;max-width:260px;margin:0 auto;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,0.3)"><p style="margin:14px 0 4px;font-size:14px;color:#eee" data-i18n="wechatSub">微信扫一扫加我为朋友</p><p style="margin:0 0 4px;font-size:13px;color:#d67d4d;font-weight:600" data-i18n="wechatNote">备注【手绘】拉你进群</p><p id="wechat-status" style="margin:4px 0 0;font-size:12px;color:#999"></p><div style="margin-top:14px;padding-top:12px;border-top:1px solid #332f2b;display:flex;justify-content:center;gap:16px;font-size:13px"><a href="https://github.com/yang0/handraw-style" target="_blank" rel="noopener noreferrer" style="color:#d67d4d;text-decoration:none;font-weight:600">GitHub 仓库 ↗</a><a href="https://x.com/yang02010" target="_blank" rel="noopener noreferrer" style="color:#d67d4d;text-decoration:none;font-weight:600">X @yang02010 ↗</a></div></dialog>
<script>
const wechatBtn=document.querySelector('#wechat-btn'),wechatModal=document.querySelector('#wechat-modal'),langBtn=document.querySelector('#lang-btn');
const I18N = {{
  zh: {{
    pageTitle: "手绘 Skill 实操教程与进阶技巧",
    stylesNav: "风格画廊",
    layoutsNav: "图型画廊",
    colorsNav: "色彩画廊",
    tutorialsNav: "实操教程",
    wechatBtn: "💬 交流群 / 作者微信",
    formulaLabel: "示例提示词：",
    wechatTitle: "💬 交流群 / 作者微信",
    wechatSub: "微信扫一扫加我为朋友",
    wechatNote: "备注【手绘】拉你进群",
    langBtn: "🌐 English"
  }},
  en: {{
    pageTitle: "Tutorials & Pro Tips | Handraw Style Prompter",
    stylesNav: "Styles",
    layoutsNav: "Layouts",
    colorsNav: "Colors",
    tutorialsNav: "Tutorials",
    wechatBtn: "💬 Community / WeChat",
    formulaLabel: "Example Prompt:",
    wechatTitle: "💬 Community / WeChat",
    wechatSub: "Scan QR code on WeChat to connect",
    wechatNote: "Note 'handdraw' to join group",
    langBtn: "🌐 中文"
  }}
}};
let currentLang = localStorage.getItem('handdraw_lang') || ((navigator.language && navigator.language.startsWith('zh')) ? 'zh' : 'en');
function applyLang(lang) {{
  currentLang = lang;
  localStorage.setItem('handdraw_lang', lang);
  document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
  document.title = I18N[lang].pageTitle;
  document.querySelectorAll('[data-i18n]').forEach(el => {{
    const key = el.dataset.i18n;
    if (I18N[lang][key]) el.textContent = I18N[lang][key];
  }});
  document.querySelectorAll('[data-zh][data-en]').forEach(el => {{
    el.textContent = lang === 'zh' ? el.dataset.zh : el.dataset.en;
  }});
  document.querySelectorAll('.copy-btn').forEach(btn => {{
    const box = btn.closest('.formula-box');
    if (box) {{
      const formula = box.querySelector('.formula-text');
      if (formula) btn.dataset.prompt = formula.dataset[lang];
    }}
  }});
}}
if (langBtn) {{
  langBtn.addEventListener('click', () => applyLang(currentLang === 'zh' ? 'en' : 'zh'));
}}
applyLang(currentLang);

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
    print(f"Built tutorials gallery: {GALLERY}")


if __name__ == "__main__":
    main()
