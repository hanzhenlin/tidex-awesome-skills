#!/usr/bin/env python3
"""Build derived style JSON and an offline number-searchable gallery."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SKILL = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "styles_200_reorganized.md"
STYLE_JSON = SKILL / "references" / "styles.json"
GALLERY = SKILL / "gallery" / "index.html"
ROW = re.compile(r"^\|\s*(\d{3})\s*·\s*([^|]+)\|\s*([^|]+)\|\s*(.*)\|\s*$")
HEADING = re.compile(r"^##\s+([A-H])\s+(.+)$")
IMAGE = re.compile(r"^([A-H])_(\d{3})(?:-(\d{3}))?\.webp$")
REMOTE_VERSION_URL = "https://raw.githubusercontent.com/yang0/handraw-style/master/skills/handdraw-style-prompter/references/version.json"
VERSION_FILE = SKILL / "references" / "version.json"
UPDATE_COMMAND = "请更新skill https://github.com/yang0/handraw-style"


def load_version() -> str:
    if VERSION_FILE.exists():
        try:
            data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
            return str(data.get("version", "1.0.0"))
        except Exception:
            pass
    return "1.0.0"


def parse_styles() -> list[dict[str, str]]:
    group = ""
    items: list[dict[str, str]] = []
    for line in SOURCE.read_text(encoding="utf-8").splitlines():
        heading = HEADING.match(line)
        if heading:
            group = f"{heading.group(1)} {heading.group(2)}"
            continue
        match = ROW.match(line)
        if match:
            number, reference, generation_name, traits = (part.strip() for part in match.groups())
            items.append({"number": number, "group": group, "reference": reference,
                          "generation_name": generation_name, "traits": traits})
    return items


def contact_sheets() -> list[dict[str, str]]:
    sheets = []
    for path in sorted((ROOT / "images").glob("*.webp")):
        match = IMAGE.match(path.name)
        if match:
            group = match.group(1)
            start = match.group(2)
            end = match.group(3) or start
            sheets.append({"group": group, "start": start, "end": end,
                           "path": f"../../../images/{path.name}"})
    return sheets


def individual_image_path(number: str) -> str:
    value = int(number)
    start = ((value - 1) // 200) * 200 + 1
    end = start + 199
    return f"../../../images/individual/{start:03}-{end:03}/{number}.webp"


def gallery_html(styles: list[dict[str, str]], sheets: list[dict[str, str]]) -> str:
    total_count = len(styles)
    max_num = f"{total_count:03}"
    style_cards = "\n".join(
        f'<article class="style" data-number="{s["number"]}" data-group="{s["group"][0]}" '
        f'data-image-src="{individual_image_path(s["number"])}"><b>#{s["number"]}</b> '
        f'<span>{html.escape(s["generation_name"])}</span><small>{html.escape(s["reference"])}</small>'
        f'<p>{html.escape(s["traits"])}</p></article>' for s in styles)
    
    sheet_card_list = []
    for s in sheets:
        if s["start"] == s["end"]:
            label = f'{s["group"]} · #{s["start"]}'
            aria = f'放大查看 {s["group"]} #{s["start"]}'
            alt = f'Style {s["start"]}'
            caption = f'{s["group"]} · #{s["start"]} · <span class="zoom-text" data-i18n="clickEnlarge">点击放大</span>'
            badge = f'#{s["start"]}'
        else:
            label = f'{s["group"]} · #{s["start"]}–#{s["end"]}'
            aria = f'放大查看 {s["group"]} #{s["start"]} 到 #{s["end"]}'
            alt = f'Styles {s["start"]} to {s["end"]}'
            caption = f'{s["group"]} · #{s["start"]}–#{s["end"]} · <span class="zoom-text" data-i18n="clickEnlarge">点击放大</span>'
            badge = f'#{s["start"]}–#{s["end"]}'
        
        sheet_card_list.append(
            f'<figure data-group="{s["group"]}"><span class="sheet-badge">{badge}</span><button class="sheet" type="button" data-src="{s["path"]}" '
            f'data-label="{label}" aria-label="{aria}">'
            f'<img src="{s["path"]}" alt="{alt}"></button>'
            f'<figcaption>{caption}</figcaption></figure>'
        )
    sheet_cards = "\n".join(sheet_card_list)
    version = load_version()

    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>手绘风格编号画廊</title><style>
body{{margin:0;background:#f7f5f0;color:#24211e;font:16px/1.5 system-ui,"Microsoft YaHei",sans-serif}} main{{max-width:1440px;margin:auto;padding:18px 30px 30px}} h1{{margin:0}} .lead{{color:#665f57}} input{{width:min(520px,100%);box-sizing:border-box;padding:12px;border:1px solid #bdb5aa;border-radius:10px;font-size:16px}} .update-status{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:14px 0 18px;padding:9px 12px;border-left:3px solid #8b8177;background:#ece8e2;color:#514a43;font-size:14px}} .update-status strong{{color:#24211e}} .update-status.is-update{{border-color:#b74227;background:#fff0eb;color:#7f3022}} .update-status.is-local-newer{{border-color:#39726a;background:#eaf5f1;color:#25534d}} .update-status button{{border:1px solid currentColor;border-radius:6px;background:transparent;color:inherit;padding:4px 8px;font:inherit;cursor:pointer}} .update-status button:hover{{background:#ffffff80}} .sheets{{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:18px;margin:24px 0 36px}} figure{{position:relative;margin:0;background:#fff;padding:10px;border-radius:12px;box-shadow:0 1px 5px #0002}} .sheet-badge{{position:absolute;top:16px;left:16px;background:rgba(36,33,30,0.85);color:#fff;padding:3px 8px;border-radius:6px;font-size:12px;font-weight:700;letter-spacing:0.5px;pointer-events:none;z-index:2;box-shadow:0 1px 3px rgba(0,0,0,0.3)}} .sheet{{display:block;width:100%;padding:0;border:0;background:transparent;cursor:zoom-in}} .sheet:focus-visible{{outline:3px solid #d67d4d;outline-offset:4px;border-radius:8px}} img{{display:block;width:100%;border-radius:7px}} figcaption{{padding:8px 2px 0;font-weight:700}} .styles{{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:10px}} .style{{background:#fff;border-radius:10px;padding:12px;border-left:4px solid #d67d4d}} .style b{{font-variant-numeric:tabular-nums}} .style small{{display:block;color:#71685e;margin-top:2px}} .style p{{margin:7px 0 0;font-size:14px;color:#4b4540}} dialog{{width:min(94vw,1300px);max-width:none;padding:12px;border:0;border-radius:14px;background:#171513;color:#fff;box-shadow:0 20px 70px #0008}} dialog::backdrop{{background:#000b}} dialog img{{max-height:82vh;object-fit:contain}} .close{{float:right;border:0;border-radius:7px;padding:7px 10px;background:#fff;color:#24211e;cursor:pointer;font:inherit}} .dialog-label{{margin:8px 0 0;clear:both}} .dialog-tip{{margin:6px 0 0;font-size:12px;color:#a8a199;text-align:center}} [hidden]{{display:none!important}}</style></head>
<body><style>.site-nav{{position:sticky;top:0;z-index:100;display:flex;align-items:center;gap:10px;margin:0;padding:12px 30px;border-bottom:1px solid #ded8cf;background:#fffdf9}} .site-nav a{{border:1px solid #9e9185;border-radius:8px;background:#fff;color:#403a34;padding:7px 13px;text-decoration:none;font-weight:800;line-height:1.2;transition:background .15s,color .15s,border-color .15s}} .site-nav a:hover{{border-color:#b74227;background:#fff0eb;color:#9f351f}} .site-nav a[aria-current="page"]{{border-color:#b74227;background:#b74227;color:#fff;box-shadow:0 1px 3px #b7422744}} .nav-right{{margin-left:auto;display:flex;align-items:center;gap:8px}} .nav-ext{{display:inline-flex;align-items:center;font-weight:700}} .nav-btn{{border:1px solid #9e9185;border-radius:8px;background:#fff;color:#403a34;padding:7px 13px;font:inherit;font-weight:700;line-height:1.2;cursor:pointer;transition:background .15s,color .15s,border-color .15s}} .nav-btn:hover{{border-color:#b74227;background:#fff0eb;color:#9f351f}} .nav-btn:focus-visible,.site-nav a:focus-visible{{outline:3px solid #d67d4d;outline-offset:3px}} .prompt-examples{{display:flex;align-items:center;flex-wrap:wrap;gap:10px 18px;margin:16px 0 20px}} .prompt-examples h2{{margin:0;color:#665f57;font-size:14px;font-weight:600}} .prompt-example{{display:flex;align-items:center;gap:8px;min-width:0}} .prompt-label{{color:#71685e;font-size:13px;white-space:nowrap}} .prompt-value{{padding:5px 8px;border:1px solid #d9d2c8;border-radius:6px;background:#fffdf9;color:#24211e;font:13px/1.4 ui-monospace,SFMono-Regular,Consolas,"Liberation Mono",monospace;white-space:nowrap}} @media(max-width:760px){{.site-nav{{padding:10px 20px;flex-wrap:wrap;gap:8px}} .nav-right{{width:100%;justify-content:flex-start;gap:6px;margin-left:0}} .site-nav a,.nav-btn{{padding:6px 10px;font-size:13px}} .prompt-examples{{align-items:flex-start;flex-direction:column;gap:8px}} .prompt-example{{flex-wrap:wrap}} .prompt-value{{white-space:normal}}}}</style><nav class="site-nav" aria-label="画廊导航"><a href="index.html" aria-current="page" data-i18n="stylesNav">风格画廊</a><a href="layouts.html" data-i18n="layoutsNav">图型画廊</a><a href="colors.html" data-i18n="colorsNav">色彩画廊</a><a href="tutorials.html" data-i18n="tutorialsNav">实操教程</a><div class="nav-right"><a class="nav-ext" href="https://github.com/yang0/handraw-style" target="_blank" rel="noopener noreferrer" title="GitHub 仓库"><svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" style="vertical-align:-2px;margin-right:4px" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>GitHub</a><a class="nav-ext" href="https://x.com/yang02010" target="_blank" rel="noopener noreferrer" title="X (Twitter) @yang02010"><svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" style="vertical-align:-2px;margin-right:4px" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>X (@yang02010)</a><button class="nav-btn" id="wechat-btn" type="button" data-i18n="wechatBtn">💬 交流群 / 作者微信</button><button class="nav-btn" id="lang-btn" type="button" aria-label="Switch Language">🌐 EN / 中</button></div></nav><main data-local-version="{version}" data-remote-version-url="{REMOTE_VERSION_URL}"><h1 data-i18n="title">手绘风格编号画廊</h1><section class="prompt-examples" aria-labelledby="prompt-examples-title"><h2 id="prompt-examples-title" data-i18n="promptTitle">提示词案例</h2><div class="prompt-example"><span class="prompt-label" data-i18n="ex1Label">1 · 出图</span><code class="prompt-value" data-i18n="ex1Code">风格：001，主题：吃冰淇淋的小姑娘</code></div><div class="prompt-example"><span class="prompt-label" data-i18n="ex2Label">2 · 切换图文模式</span><code class="prompt-value" data-i18n="ex2Code">切换为图文模式</code></div><div class="prompt-example"><span class="prompt-label" data-i18n="ex3Label">3 · 海报提示词</span><code class="prompt-value" data-i18n="ex3Code">请帮我出海报提示词， 主题：秋分</code></div></section><section id="update-status" class="update-status" role="status" aria-live="polite" hidden></section>
<h2 data-i18n="sheetsTitle">风格拼图</h2><section class="sheets">{sheet_cards}</section><h2 data-i18n="stylesTitle">风格索引（{total_count}）</h2><section class="styles" id="styles">{style_cards}</section></main>
<dialog id="preview" aria-labelledby="dialog-label"><button class="close" type="button" aria-label="关闭放大预览" data-i18n="closeBtn">关闭 ×</button><img id="preview-image" alt=""><p class="dialog-label" id="dialog-label"></p><p class="dialog-tip" data-i18n="dialogTip">图片出于展示目的做了压缩，AI出的图字迹是很清晰的</p></dialog>
<dialog id="wechat-modal" aria-labelledby="wechat-title" style="width:min(90vw,360px);padding:20px;border:0;border-radius:14px;background:#1e1b18;color:#fff;box-shadow:0 20px 70px #000a;text-align:center"><button class="close" type="button" aria-label="关闭" style="position:absolute;top:12px;right:12px;border:0;border-radius:7px;padding:5px 9px;background:#fff;color:#24211e;cursor:pointer;font:inherit">关闭 ×</button><h3 id="wechat-title" style="margin:4px 0 14px;font-size:17px;color:#fff" data-i18n="wechatTitle">💬 交流群 / 作者微信</h3><img id="wechat-img" src="https://raw.githubusercontent.com/yang0/handraw-style/master/images/wechat_community.jpg" onerror="this.onerror=null;this.src='../../../images/wechat_personal_fallback.jpg';const s=document.getElementById('wechat-status');if(s)s.textContent='（已切换为本地备用二维码）';" alt="微信二维码" style="display:block;width:100%;max-width:260px;margin:0 auto;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,0.3)"><p style="margin:14px 0 4px;font-size:14px;color:#eee" data-i18n="wechatSub">微信扫一扫加我为朋友</p><p style="margin:0 0 4px;font-size:13px;color:#d67d4d;font-weight:600" data-i18n="wechatNote">备注【手绘】拉你进群</p><p id="wechat-status" style="margin:4px 0 0;font-size:12px;color:#999"></p><div style="margin-top:14px;padding-top:12px;border-top:1px solid #332f2b;display:flex;justify-content:center;gap:16px;font-size:13px"><a href="https://github.com/yang0/handraw-style" target="_blank" rel="noopener noreferrer" style="color:#d67d4d;text-decoration:none;font-weight:600">GitHub 仓库 ↗</a><a href="https://x.com/yang02010" target="_blank" rel="noopener noreferrer" style="color:#d67d4d;text-decoration:none;font-weight:600">X @yang02010 ↗</a></div></dialog>
<script>
const cards=[...document.querySelectorAll('.style')],dialog=document.querySelector('#preview'),preview=document.querySelector('#preview-image'),label=document.querySelector('#dialog-label'),gallery=document.querySelector('main'),updateStatus=document.querySelector('#update-status'),localVersion=gallery.dataset.localVersion||'1.0.0',remoteVersionUrl=gallery.dataset.remoteVersionUrl,updateCommand='{UPDATE_COMMAND}',wechatBtn=document.querySelector('#wechat-btn'),wechatModal=document.querySelector('#wechat-modal'),langBtn=document.querySelector('#lang-btn');
const I18N = {{
  zh: {{
    pageTitle: "手绘风格编号画廊",
    title: "手绘风格编号画廊",
    stylesNav: "风格画廊",
    layoutsNav: "图型画廊",
    colorsNav: "色彩画廊",
    tutorialsNav: "实操教程",
    wechatBtn: "💬 交流群 / 作者微信",
    promptTitle: "提示词案例",
    ex1Label: "1 · 出图",
    ex1Code: "风格：001，主题：吃冰淇淋的小姑娘",
    ex2Label: "2 · 切换图文模式",
    ex2Code: "切换为图文模式",
    ex3Label: "3 · 海报提示词",
    ex3Code: "请帮我出海报提示词， 主题：秋分",
    sheetsTitle: "风格拼图",
    stylesTitle: "风格索引（" + cards.length + "）",
    clickEnlarge: "点击放大",
    closeBtn: "关闭 ×",
    dialogTip: "图片出于展示目的做了压缩，AI出的图字迹是很清晰的",
    wechatTitle: "💬 交流群 / 作者微信",
    wechatSub: "微信扫一扫加我为朋友",
    wechatNote: "备注【手绘】拉你进群",
    langBtn: "🌐 English",
    updateHeading: "发现风格库更新",
    updateMsg: "请复制更新指令，然后丢给 Codex 进行更新。",
    updateCopyBtn: "复制更新指令",
    updateCopied: "已复制",
    updateCopyFailed: "复制失败，请手动复制"
  }},
  en: {{
    pageTitle: "Hand-drawn Style Gallery",
    title: "Hand-drawn Style Gallery",
    stylesNav: "Styles",
    layoutsNav: "Layouts",
    colorsNav: "Colors",
    tutorialsNav: "Tutorials",
    wechatBtn: "💬 Community / WeChat",
    promptTitle: "Prompt Examples",
    ex1Label: "1 · Generate",
    ex1Code: "Style: 001, Theme: Little girl eating ice cream",
    ex2Label: "2 · Graphic-Text Mode",
    ex2Code: "Switch to graphic-text mode",
    ex3Label: "3 · Poster Prompt",
    ex3Code: "Please generate a poster prompt for me, Theme: Autumn Equinox",
    sheetsTitle: "Contact Sheets",
    stylesTitle: "Style Index (" + cards.length + ")",
    clickEnlarge: "Click to enlarge",
    closeBtn: "Close ×",
    dialogTip: "Images are compressed for display; AI outputs are sharp and clear.",
    wechatTitle: "💬 Community / WeChat",
    wechatSub: "Scan QR code on WeChat to connect",
    wechatNote: "Note 'handdraw' to join group",
    langBtn: "🌐 中文",
    updateHeading: "Style Library Update Available",
    updateMsg: "Copy update command and send to Codex to update.",
    updateCopyBtn: "Copy Update Command",
    updateCopied: "Copied",
    updateCopyFailed: "Failed to copy, please copy manually"
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
    if (I18N[lang] && I18N[lang][key]) {{
      el.textContent = I18N[lang][key];
    }}
  }});
  if (langBtn) langBtn.textContent = I18N[lang].langBtn;
}}
if (langBtn) {{
  langBtn.addEventListener('click', () => {{
    applyLang(currentLang === 'zh' ? 'en' : 'zh');
  }});
}}
applyLang(currentLang);
if(wechatBtn&&wechatModal){{wechatBtn.addEventListener('click',()=>wechatModal.showModal());wechatModal.querySelector('.close').addEventListener('click',()=>wechatModal.close());wechatModal.addEventListener('click',event=>{{if(event.target===wechatModal)wechatModal.close()}});}}
function openPreview(button){{preview.src=button.dataset.src;preview.alt=button.querySelector('img').alt;label.textContent=button.dataset.label||'';dialog.showModal();}}
document.querySelectorAll('.sheet').forEach(button=>button.addEventListener('click',()=>openPreview(button)));
dialog.querySelector('.close').addEventListener('click',()=>dialog.close());
dialog.addEventListener('click',event=>{{if(event.target===dialog)dialog.close()}});
function showUpdateStatus(remoteVer){{const t = I18N[currentLang] || I18N.zh;updateStatus.hidden=false;updateStatus.className='update-status is-update';updateStatus.replaceChildren();const heading=document.createElement('strong'),message=document.createElement('span'),copyButton=document.createElement('button');heading.textContent=t.updateHeading+(remoteVer?' (v'+remoteVer+')':'');message.textContent=t.updateMsg;copyButton.type='button';copyButton.textContent=t.updateCopyBtn;copyButton.addEventListener('click',async()=>{{try{{await navigator.clipboard.writeText(updateCommand);copyButton.textContent=t.updateCopied;}}catch{{copyButton.textContent=t.updateCopyFailed;}}}});updateStatus.append(heading,message,copyButton);}}
function isNewerVersion(remote,local){{const clean=s=>String(s).replace(/^v/i,''),r=clean(remote).split('.').map(n=>parseInt(n,10)||0),l=clean(local).split('.').map(n=>parseInt(n,10)||0);for(let i=0;i<Math.max(r.length,l.length);i++){{const rv=r[i]||0,lv=l[i]||0;if(rv>lv)return true;if(rv<lv)return false;}}return false;}}
async function checkRepositoryUpdate(){{try{{const response=await fetch(remoteVersionUrl);if(!response.ok)throw new Error('Remote version is unavailable');const data=await response.json();const remoteVer=typeof data==='object'&&data!==null?(data.version||''):String(data);if(remoteVer&&isNewerVersion(remoteVer,localVersion))showUpdateStatus(remoteVer);}}catch{{}}}}
checkRepositoryUpdate();
</script></body></html>'''


def main() -> None:
    styles = parse_styles()
    sheets = contact_sheets()
    numbers = [item["number"] for item in styles]
    expected = [f"{number:03}" for number in range(1, len(styles) + 1)]
    if numbers != expected:
        raise SystemExit(f"Style source must contain exactly continuous 001–{len(styles):03} entries.")
    STYLE_JSON.parent.mkdir(parents=True, exist_ok=True)
    GALLERY.parent.mkdir(parents=True, exist_ok=True)
    STYLE_JSON.write_text(json.dumps(styles, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    GALLERY.write_text(gallery_html(styles, sheets), encoding="utf-8")
    print(f"Built {len(styles)} styles and {len(sheets)} contact sheets.")
    try:
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        from build_markdown_galleries import build_styles_md
        build_styles_md()
    except Exception as exc:
        print(f"Notice: build_styles_md skipped: {exc}")


if __name__ == "__main__":
    main()
