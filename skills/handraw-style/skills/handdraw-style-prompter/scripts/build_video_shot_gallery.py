"""Seven shot cards, same catalog as the CLI, clean image-and-spec reference.
Unified with handdraw-style gallery design system (index.html, layouts.html, colors.html).
No video samples or reels embedded; lightweight and clean.
"""
from pathlib import Path
import json, hashlib, html as html_lib

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'skills/handraw-video-producer/catalog/shots.json').is_file())
GALLERY = ROOT / 'skills/handdraw-style-prompter/gallery'

def main():
    data = json.loads((ROOT / 'skills/handraw-video-producer/catalog/shots.json').read_text(encoding='utf-8'))
    dest = GALLERY / 'video-shot-previews'
    dest.mkdir(exist_ok=True)

    for item in data['items']:
        gif_path = dest / (item['id'] + '.gif')
        png_path = dest / (item['id'] + '.png')
        if gif_path.is_file():
            poster_path = gif_path
            ext = '.gif'
        elif png_path.is_file():
            poster_path = png_path
            ext = '.png'
        else:
            raise FileNotFoundError('缺少随包截图：' + str(png_path) + '；画廊不会下载或读取案例视频。')

        sha = hashlib.sha256(poster_path.read_bytes()).hexdigest()[:12]
        item['image'] = 'video-shot-previews/' + item['id'] + ext + '?v=' + sha
        item['renderers'] = (['剪映', '浏览器'] if item.get('output_routes', {}).get('jianying') == 'native_config_required' else ['浏览器'])

    # Pre-render cards HTML: number in front of title, no card action buttons, entire card clickable
    cards_html_parts = []
    for item in data['items']:
        card_html = f'''      <article class="card" data-id="{item['id']}" data-open="{item['id']}">
        <div class="card-frame">
          <img src="{item['image']}" alt="{item['id']} {html_lib.escape(item['name'])}" loading="lazy">
          <span class="card-id-badge">{item['id']}</span>
        </div>
        <div class="card-body">
          <h3 class="card-title">{item['id']} {html_lib.escape(item['name'])}</h3>
          <p class="card-desc">{html_lib.escape(item['description'])}</p>
          <span class="badge-renderers">渲染方式：{'、'.join(item['renderers'])}</span>
        </div>
      </article>'''
        cards_html_parts.append(card_html)
    cards_rendered_html = '\n'.join(cards_html_parts)

    html = f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>视频类型 · 手绘视频</title>
<style>
:root {{
  color: #24211e;
  background: #f7f5f0;
  font: 16px/1.5 system-ui, "Microsoft YaHei", sans-serif;
  --accent: #b74227;
  --accent-hover: #9f351f;
  --accent-light: #fbeee8;
  --border: #e3ded6;
  --text-main: #24211e;
  --text-muted: #5e574f;
  --text-dim: #7f766c;
  --tag-bg: #ece6dc;
}}

* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: #f7f5f0;
  color: var(--text-main);
  -webkit-font-smoothing: antialiased;
}}

/* Header & Navigation */
.sticky-header {{
  position: sticky;
  top: 0;
  z-index: 100;
}}
.site-nav {{
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 30px;
  margin: 0;
  border-bottom: 1px solid #ded8cf;
  background: #fffdf9;
}}
.site-nav a {{
  border: 1px solid #9e9185;
  color: #403a34;
  background: #fff;
  text-decoration: none;
  font-weight: 800;
  line-height: 1.2;
  padding: 7px 13px;
  border-radius: 8px;
  transition: background .15s, color .15s, border-color .15s;
}}
.site-nav a:hover {{
  border-color: #b74227;
  color: #9f351f;
  background: #fff0eb;
}}
.site-nav a[aria-current="page"] {{
  border-color: #b74227;
  color: #fff;
  background: #b74227;
  box-shadow: 0 1px 3px #b7422744;
}}
.nav-right {{
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
}}
.nav-ext {{ display: inline-flex; align-items: center; font-weight: 700; }}
.nav-btn {{
  border: 1px solid #9e9185;
  border-radius: 8px;
  background: #fff;
  color: #403a34;
  padding: 7px 13px;
  font: inherit;
  font-weight: 700;
  line-height: 1.2;
  cursor: pointer;
  transition: background .15s, color .15s, border-color .15s;
}}
.nav-btn:hover {{
  border-color: #b74227;
  background: #fff0eb;
  color: #9f351f;
}}
.nav-btn:focus-visible, .site-nav a:focus-visible {{
  outline: 3px solid #d67d4d;
  outline-offset: 3px;
}}

/* Main Wrap */
main {{
  max-width: 1360px;
  margin: 0 auto;
  padding: 24px 30px 48px;
}}

/* Titles & Lead */
.gallery-title-bar {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
  margin: 0 0 4px;
}}
.gallery-title-bar h1 {{
  margin: 0;
  font-size: 26px;
  font-weight: 800;
  color: var(--text-main);
  line-height: 1.2;
}}
.lead {{
  margin: 8px 0 24px;
  color: var(--text-muted);
  font-size: 14.5px;
  line-height: 1.6;
}}

/* Gallery Grid */
.gallery {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 22px;
  align-items: stretch;
}}
@media (max-width: 1100px) {{
  .gallery {{ grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }}
}}
@media (max-width: 680px) {{
  .gallery {{ grid-template-columns: 1fr; gap: 16px; }}
}}

/* Card System */
.card {{
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  border-radius: 12px;
  background: #fff;
  border: 1px solid var(--border);
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  overflow: hidden;
  transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
  text-align: left;
  cursor: pointer;
}}
.card:hover {{
  transform: translateY(-3px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.09);
  border-color: #d1c7ba;
}}

/* Card Frame (16:9) */
.card-frame {{
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: #ede8e1;
  overflow: hidden;
  border-bottom: 1px solid var(--border);
}}
.card-frame img {{
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform .25s ease;
}}
.card:hover .card-frame img {{
  transform: scale(1.02);
}}
.card-id-badge {{
  position: absolute;
  top: 10px;
  left: 10px;
  background: var(--accent);
  color: #fff;
  font: 12px/1 ui-monospace, SFMono-Regular, Consolas, monospace;
  font-weight: 800;
  padding: 4px 8px;
  border-radius: 5px;
  box-shadow: 0 2px 6px rgba(0,0,0,0.3);
  letter-spacing: 0.5px;
  z-index: 2;
}}

/* Card Body */
.card-body {{
  padding: 16px 18px 18px;
  display: flex;
  flex-direction: column;
  flex: 1;
}}
.card-title {{
  margin: 0 0 6px;
  font-size: 18px;
  font-weight: 800;
  color: var(--text-main);
  line-height: 1.3;
}}
.card-desc {{
  font-size: 13.5px;
  color: var(--text-muted);
  margin: 0 0 10px;
  line-height: 1.55;
  flex: 1;
}}
.badge-renderers {{
  font-size: 12.5px;
  font-weight: 700;
  color: var(--text-dim);
  background: var(--tag-bg);
  padding: 4px 9px;
  border-radius: 6px;
  width: fit-content;
}}

/* Dark Luxury Modal */
dialog {{
  border: 0;
  border-radius: 14px;
  padding: 22px;
  background: #171513;
  color: #f5f2eb;
  max-width: min(92vw, 680px);
  width: 100%;
  box-shadow: 0 24px 80px rgba(0,0,0,0.55);
  box-sizing: border-box;
}}
dialog::backdrop {{
  background: rgba(0,0,0,0.75);
  backdrop-filter: blur(4px);
}}
.dialog-content {{
  display: flex;
  flex-direction: column;
  max-height: 86vh;
}}
.dialog-header {{
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}}
.dialog-id {{
  font: 13px ui-monospace, SFMono-Regular, Consolas, monospace;
  font-weight: 800;
  color: #fff;
  background: var(--accent);
  padding: 3px 8px;
  border-radius: 5px;
}}
.dialog-title {{
  margin: 0;
  font-size: 18px;
  font-weight: 800;
  color: #fff;
}}
.dialog-close-btn {{
  margin-left: auto;
  border: 0;
  border-radius: 7px;
  padding: 6px 12px;
  background: #332f2b;
  color: #ded8cf;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: background .15s, color .15s;
}}
.dialog-close-btn:hover {{
  background: #47423d;
  color: #fff;
}}
.dialog-img-box {{
  width: 100%;
  aspect-ratio: 16 / 9;
  max-height: 42vh;
  background: #171513;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #3d3731;
}}
.dialog-img-box img {{
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}}
.dialog-body {{
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
  padding-right: 4px;
}}
.dialog-spec-box {{
  background: #23201d;
  border: 1px solid #3d3731;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px;
  line-height: 1.55;
  color: #ded8cf;
}}
.dialog-spec-title {{
  font-weight: 750;
  color: #fff;
  margin-bottom: 4px;
  font-size: 13.5px;
  display: flex;
  align-items: center;
  gap: 6px;
}}
.dialog-actions {{
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid #2d2925;
}}
.copy, .close {{
  border: 0;
  border-radius: 7px;
  padding: 8px 15px;
  font: inherit;
  font-size: 13.5px;
  font-weight: 700;
  cursor: pointer;
  transition: background .15s, opacity .15s;
}}
.copy {{
  background: var(--accent);
  color: #fff;
}}
.copy:hover {{
  background: var(--accent-hover);
}}
.close {{
  background: #332f2b;
  color: #ded8cf;
  margin-left: auto;
}}
.close:hover {{
  background: #47423d;
  color: #fff;
}}

/* Footer */
footer {{
  margin-top: 40px;
  padding: 24px 30px;
  border-top: 1px solid var(--border);
  background: #faf7f2;
  font-size: 13px;
  color: var(--text-dim);
  line-height: 1.75;
  text-align: center;
}}

@media (max-width: 720px) {{
  main {{ padding: 16px 16px 30px; }}
  .site-nav {{ padding: 10px 20px; flex-wrap: wrap; gap: 8px; }}
  .nav-right {{ width: 100%; justify-content: flex-start; gap: 6px; margin-left: 0; }}
  .site-nav a, .nav-btn {{ padding: 6px 10px; font-size: 13px; }}
  .gallery-title-bar {{ gap: 8px; }}
}}
[hidden] {{ display: none !important; }}
</style>
</head>
<body>
<header class="sticky-header">
  <nav class="site-nav" aria-label="画廊导航">
    <a href="index.html" data-i18n="stylesNav">风格画廊</a>
    <a href="layouts.html" data-i18n="layoutsNav">图型画廊</a>
    <a href="colors.html" data-i18n="colorsNav">色彩画廊</a>
    <a href="assets.html" data-i18n="assetsNav">自建图库</a>
    <a href="video-shots.html" aria-current="page" data-i18n="videoShotsNav">视频类型</a>
    <a href="tutorials.html" data-i18n="tutorialsNav">提示词</a>
    <div class="nav-right">
      <a class="nav-ext" href="https://github.com/yang0/handraw-style" target="_blank" rel="noopener noreferrer" title="GitHub 仓库">
        <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" style="vertical-align:-2px;margin-right:4px" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>GitHub
      </a>
      <a class="nav-ext" href="https://x.com/yang02010" target="_blank" rel="noopener noreferrer" title="X (Twitter) @yang02010">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" style="vertical-align:-2px;margin-right:4px" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>X (@yang02010)
      </a>
      <button class="nav-btn" id="wechat-btn" type="button" data-i18n="wechatBtn">💬 创作变现交流群</button>
      <button class="nav-btn" id="lang-btn" type="button" aria-label="Switch Language">🌐 EN / 中</button>
    </div>
  </nav>
</header>

<main>
  <div class="gallery-title-bar">
    <h1 data-i18n="title">视频类型</h1>
  </div>
  <p class="lead" id="gallery-lead" data-i18n="lead">这里整理了 7 种经典的手绘视频类型。制作一条完整视频时非常灵活：你既可以全片只选一种类型一贯到底，也能按内容需要自由混搭多种类型（比如白板动画讲概念、长卷画轴讲历程、多图轮播讲要点）。点击卡片即可查看每种类型的素材准备要求与剪映适配说明！</p>

  <section class="gallery" id="cards">
{cards_rendered_html}
  </section>
</main>

<footer>
  先确认视频方案与渲染方式，再准备素材；全部画面素材审查通过后开始配音、动画与合成。
</footer>

<!-- Detail Dialog -->
<dialog id="detail" aria-labelledby="detailTitle">
  <div class="dialog-content">
    <div class="dialog-header">
      <span class="dialog-id" id="detailId"></span>
      <h3 class="dialog-title" id="detailTitle"></h3>
      <button class="dialog-close-btn close" type="button" aria-label="关闭">关闭 ×</button>
    </div>
    <div class="dialog-img-box">
      <img id="detailImg" alt="视频类型预览" src="">
    </div>
    <div class="dialog-body">
      <div class="dialog-spec-box">
        <div class="dialog-spec-title">📖 类型介绍</div>
        <div id="detailDescription"></div>
      </div>
      <div class="dialog-spec-box">
        <div class="dialog-spec-title">⚙️ 渲染方式</div>
        <div id="detailRenderers"></div>
      </div>
      <div class="dialog-spec-box">
        <div class="dialog-spec-title">📥 素材要求</div>
        <div id="detailInputs"></div>
      </div>
      <div class="dialog-spec-box">
        <div class="dialog-spec-title">⚙️ 支持选项</div>
        <div id="detailOptions"></div>
      </div>
    </div>
    <div class="dialog-actions">
      <button class="copy" id="detailCopyBtn" type="button">复制类型需求</button>
      <button class="close" type="button">关闭 ×</button>
    </div>
  </div>
</dialog>

<!-- WeChat Community Dialog -->
<dialog id="wechat-modal" aria-labelledby="wechat-title" style="width:min(94vw,560px);padding:22px;border:0;border-radius:14px;background:#1e1b18;color:#fff;box-shadow:0 20px 70px #000a;text-align:center">
  <button class="close" type="button" aria-label="关闭" style="position:absolute;top:12px;right:12px;border:0;border-radius:7px;padding:5px 9px;background:#fff;color:#24211e;cursor:pointer;font:inherit">关闭 ×</button>
  <h3 id="wechat-title" style="margin:4px 0 10px;font-size:17px;color:#fff" data-i18n="wechatTitle">💬 创作变现交流群</h3>
  <p style="margin:0 0 4px;font-size:14px;color:#eee" data-i18n="wechatSub">请优先加群，满了的话也可以尝试加我个人微信</p>
  <p style="margin:0 0 16px;font-size:13px;color:#d67d4d;font-weight:600" data-i18n="wechatNote">请备注：手绘</p>
  <div style="display:flex;justify-content:center;align-items:flex-start;gap:24px;flex-wrap:wrap">
    <div style="flex:1 1 200px;max-width:240px;background:#fff;padding:10px;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,0.3)">
      <div style="color:#24211e;font-size:13px;font-weight:700;margin-bottom:6px" data-i18n="wechatGroupLabel">① 优先加入群聊</div>
      <img src="../../../images/wechat_group.png" onerror="this.onerror=null;this.src='https://raw.githubusercontent.com/yang0/handraw-style/master/images/wechat_group.png';" alt="手绘交流群二维码" style="display:block;width:100%;height:auto;border-radius:6px">
    </div>
    <div style="flex:1 1 200px;max-width:240px;background:#fff;padding:10px;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,0.3)">
      <div style="color:#24211e;font-size:13px;font-weight:700;margin-bottom:6px" data-i18n="wechatPersonalLabel">② 个人微信备用</div>
      <img src="../../../images/wechat_personal.png" onerror="this.onerror=null;this.src='https://raw.githubusercontent.com/yang0/handraw-style/master/images/wechat_personal.png';" alt="旺德福个人微信二维码" style="display:block;width:100%;height:auto;border-radius:6px">
    </div>
  </div>
</dialog>

<script>
const DATA = __DATA__;
let currentLang = localStorage.getItem('handraw_lang') || 'zh';
let activeItemId = null;

const detailDialog = document.getElementById('detail');
const detailCopyBtn = document.getElementById('detailCopyBtn');
const wechatBtn = document.getElementById('wechat-btn');
const wechatModal = document.getElementById('wechat-modal');
const langBtn = document.getElementById('lang-btn');

const I18N = {{
  zh: {{
    pageTitle: "视频类型 · 手绘视频",
    title: "视频类型",
    lead: "这里整理了 7 种经典的手绘视频类型。制作一条完整视频时非常灵活：你既可以全片只选一种类型一贯到底，也能按内容需要自由混搭多种类型（比如白板动画讲概念、长卷画轴讲历程、多图轮播讲要点）。点击卡片即可查看每种类型的素材准备要求与剪映适配说明！",
    stylesNav: "风格画廊",
    layoutsNav: "图型画廊",
    colorsNav: "色彩画廊",
    assetsNav: "自建图库",
    tutorialsNav: "提示词",
    videoShotsNav: "视频类型",
    wechatBtn: "💬 创作变现交流群",
    renderersLabel: "渲染方式：",
    copyBtn: "复制类型需求",
    copied: "已复制 ✓",
    copyFailed: "复制失败",
    closeBtn: "关闭 ×",
    langBtn: "🌐 English",
    wechatTitle: "💬 创作变现交流群",
    wechatSub: "请优先加群，满了的话也可以尝试加我个人微信",
    wechatNote: "请备注：手绘",
    wechatGroupLabel: "① 优先加入群聊",
    wechatPersonalLabel: "② 个人微信备用"
  }},
  en: {{
    pageTitle: "Video Types · Handraw Video",
    title: "Video Types",
    lead: "7 canonical hand-drawn video types. When creating a full video, you have complete flexibility: stick to a single type throughout, or freely mix and match multiple types to fit your narrative (e.g. whiteboard sketch for concepts, infinite canvas for journeys, grid gallery for highlights). Click any card for asset requirements and editing specs!",
    stylesNav: "Styles",
    layoutsNav: "Layouts",
    colorsNav: "Colors",
    assetsNav: "Custom Library",
    tutorialsNav: "Prompts",
    videoShotsNav: "Video Types",
    wechatBtn: "💬 Creator Community",
    renderersLabel: "Rendering: ",
    copyBtn: "Copy Type Spec",
    copied: "Copied! ✓",
    copyFailed: "Copy failed",
    closeBtn: "Close ×",
    langBtn: "🌐 中文",
    wechatTitle: "💬 Creator Monetization Community",
    wechatSub: "Please prioritize joining the group; if full, try personal WeChat",
    wechatNote: "Note: handdraw",
    wechatGroupLabel: "① Join Group (Priority)",
    wechatPersonalLabel: "② Personal WeChat (Fallback)"
  }}
}};

function escapeHtml(s) {{
  return String(s).replace(/[&<>"']/g, c => ({{ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }}[c]));
}}

// Build Copy Text for a single shot
function getShotPrompt(item) {{
  const isZh = currentLang === 'zh';
  if (isZh) {{
    return `视频类型：${{item.id}} ${{item.name}}\\n类型介绍：${{item.description}}\\n渲染方式：${{item.renderers.join('、')}}\\n素材要求：${{item.inputs}}\\n支持选项：${{item.options.join('；')}}\\n请为我的视频设计包含该视频类型的完整方案，等我确认后再准备素材。`;
  }} else {{
    return `Video Type: ${{item.id}} ${{item.name}}\\nDescription: ${{item.description}}\\nRendering: ${{item.renderers.join(', ')}}\\nMaterial Inputs: ${{item.inputs}}\\nOptions: ${{item.options.join('; ')}}\\nPlease design a complete video proposal including this video type before asset preparation.`;
  }}
}}

async function copyText(text, btn) {{
  try {{
    await navigator.clipboard.writeText(text);
    const orig = btn.textContent;
    btn.textContent = I18N[currentLang].copied;
    btn.classList.add('copied');
    setTimeout(() => {{
      btn.textContent = orig;
      btn.classList.remove('copied');
    }}, 1600);
  }} catch (e) {{
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    ta.remove();
    const orig = btn.textContent;
    btn.textContent = I18N[currentLang].copied;
    btn.classList.add('copied');
    setTimeout(() => {{
      btn.textContent = orig;
      btn.classList.remove('copied');
    }}, 1600);
  }}
}}

// Detail Dialog
function openDetail(id) {{
  const item = DATA.items.find(x => x.id === id);
  if (!item) return;
  activeItemId = id;
  document.getElementById('detailId').textContent = item.id;
  document.getElementById('detailTitle').textContent = item.name;

  document.getElementById('detailDescription').textContent = item.description;
  document.getElementById('detailRenderers').textContent = item.renderers.join('、');
  document.getElementById('detailInputs').textContent = item.inputs;
  document.getElementById('detailOptions').innerHTML = item.options.map(opt => `<div>• ${{escapeHtml(opt)}}</div>`).join('');

  document.getElementById('detailImg').src = item.image;
  detailDialog.showModal();
}}

detailCopyBtn.addEventListener('click', () => {{
  if (!activeItemId) return;
  const item = DATA.items.find(x => x.id === activeItemId);
  if (!item) return;
  copyText(getShotPrompt(item), detailCopyBtn);
}});

document.querySelectorAll('[data-open]').forEach(el => {{
  el.addEventListener('click', (e) => {{
    e.stopPropagation();
    const id = el.dataset.open;
    openDetail(id);
  }});
}});

document.querySelectorAll('dialog .close').forEach(btn => {{
  btn.addEventListener('click', () => {{
    const d = btn.closest('dialog');
    d.close();
  }});
}});
detailDialog.addEventListener('click', e => {{
  if (e.target === detailDialog) {{
    detailDialog.close();
  }}
}});

// WeChat Modal
if (wechatBtn && wechatModal) {{
  wechatBtn.addEventListener('click', () => wechatModal.showModal());
}}

// Language Switching
function applyLang(lang) {{
  currentLang = lang;
  localStorage.setItem('handraw_lang', lang);
  document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';

  document.querySelectorAll('[data-i18n]').forEach(el => {{
    const key = el.dataset.i18n;
    if (I18N[lang] && I18N[lang][key]) {{
      el.textContent = I18N[lang][key];
    }}
  }});

  if (langBtn) {{
    langBtn.textContent = I18N[lang].langBtn;
  }}

  document.querySelectorAll('.badge-renderers').forEach(badge => {{
    const card = badge.closest('.card');
    if (!card) return;
    const item = DATA.items.find(x => x.id === card.dataset.id);
    if (!item) return;
    const names = lang === 'zh' ? item.renderers : item.renderers.map(x => x === '剪映' ? 'Jianying' : 'Browser');
    badge.textContent = I18N[lang].renderersLabel + names.join(lang === 'zh' ? '、' : ', ');
  }});
}}

if (langBtn) {{
  langBtn.addEventListener('click', () => {{
    applyLang(currentLang === 'zh' ? 'en' : 'zh');
  }});
}}
applyLang(currentLang);
</script>
</body>
</html>'''

    frontend_items = [{
        'id': item['id'],
        'name': item['name'],
        'inputs': item['inputs'],
        'options': item.get('options', []),
        'description': item['description'],
        'renderers': item['renderers'],
        'image': item['image']
    } for item in data['items']]

    (GALLERY / 'video-shots.html').write_text(
        html.replace('__DATA__', json.dumps({'items': frontend_items}, ensure_ascii=False).replace('<', '\\u003c')),
        encoding='utf-8'
    )
    (dest / 'manifest.json').write_text(
        json.dumps({
            'catalog': 'catalog/shots.json',
            'items': frontend_items
        }, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    print('Static clean video shot gallery built successfully.')

if __name__ == '__main__':
    main()
