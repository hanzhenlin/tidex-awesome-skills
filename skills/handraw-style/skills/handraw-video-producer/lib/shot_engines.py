"""Pinned independent shot engines; no audio or generation calls."""
from pathlib import Path
from types import SimpleNamespace
import base64, hashlib, importlib.util, json, os, shutil, subprocess, sys, time
from shot_catalog import ROOT
from runtime_tools import executable, browser_executable, browser_launch_options
VENDOR=ROOT/'lib/vendor'

def runtime_vendor(name):
    """Source and installed Skills share the same pinned project-local optional install."""
    own=VENDOR/name
    for parent in ROOT.parents:
        shared=parent/'skills/handraw-video-producer/lib/vendor'/name
        if shared.resolve()!=own.resolve() and (shared/'package-lock.json').is_file() and (own/'package-lock.json').is_file() and (shared/'package-lock.json').read_bytes()==(own/'package-lock.json').read_bytes():return shared
    return own

def runtime_status():
    def tool(name):
        try:return bool(executable(name))
        except RuntimeError:return False
    try:browser=bool(browser_executable())
    except RuntimeError:browser=False
    base=importlib.util.find_spec('PIL') is not None
    playwright=importlib.util.find_spec('playwright') is not None
    ffmpeg,ffprobe=tool('ffmpeg'),tool('ffprobe')
    node=bool(shutil.which('node'))
    return {'base':base,'ffmpeg':ffmpeg,'ffprobe':ffprobe,'installed_browser':browser,'node':node,
            'browser':base and playwright and browser and ffmpeg and ffprobe,
            'edge':importlib.util.find_spec('edge_tts') is not None,
            'volc':ffmpeg and (ROOT.parent/'handraw-volc-tts/scripts/volc_voice.py').is_file(),
            'remotion':node and base and playwright and browser and ffmpeg and ffprobe and (runtime_vendor('livecanvas')/'node_modules/@remotion/renderer').is_dir(),
            'simo':node and base and playwright and browser and ffmpeg and ffprobe and (runtime_vendor('simo')/'node_modules/roughjs').is_dir(),
            'srt':base and playwright and browser and ffmpeg and ffprobe and all(importlib.util.find_spec(x) for x in ('cv2','numpy'))}

def install_runtime(engine):
    """Explicit installation only. Rendering never invokes this function."""
    if engine=='volc':
        executable('ffmpeg')
        if not (ROOT.parent/'handraw-volc-tts/scripts/volc_voice.py').is_file():raise RuntimeError('缺少随包handraw-volc-tts Skill')
        return  # Voice client uses Python's standard library; no hidden package install.
    if engine in ('remotion','simo'):
        folder=runtime_vendor('livecanvas' if engine=='remotion' else 'simo')
        npm=shutil.which('npm.cmd') or shutil.which('npm')
        if not npm:raise RuntimeError('请先安装Node.js和npm')
        subprocess.run([npm,'ci','--ignore-scripts','--no-audit','--no-fund'],cwd=folder,check=True)
        subprocess.run([sys.executable,'-m','pip','install','-r',str(ROOT/'requirements-browser.txt')],check=True)
    elif engine in ('base','browser','edge','srt'):
        filename={'base':'requirements-base.txt','browser':'requirements-browser.txt','edge':'requirements-edge-tts.txt','srt':'requirements-shot-engines.txt'}[engine]
        subprocess.run([sys.executable,'-m','pip','install','-r',str(ROOT/filename)],check=True)
    else:raise ValueError('未知运行时')

def validate_config(ep,kind,cfg,n,meta,check_runtime=True):
    import composition as c
    if check_runtime and not runtime_status()[kind]:raise RuntimeError(kind+'依赖缺失；运行hvp runtime-install --engine '+kind)
    for value in cfg.get('inputs',[]):c.asset_path(ep,value)
    if kind=='remotion':
        c.entry_path(ep,cfg.get('entry'))
        if not isinstance(cfg.get('props',{}),dict):raise ValueError('Remotion props必须是对象')
    elif kind=='simo':
        if not cfg.get('scene') and not cfg.get('dsl'):raise ValueError('simo需要scene JSON或dsl入口')
        c.entry_path(ep,cfg.get('scene',cfg.get('dsl')))
        if cfg.get('scene'):
            scene=c.read(c.entry_path(ep,cfg['scene']))
            for el in scene.get('elements',[]):
                if el.get('type') not in ('rectangle','ellipse','diamond','line','arrow','text','image'):raise ValueError('simo不支持该元素：'+str(el.get('type')))
                if el.get('type') not in ('text','image') and (type(el.get('seed'))!=int or el['seed']<=0):raise ValueError('simo线条需固定正整数seed，不能随机生成笔迹')
    elif kind=='srt':
        c.image_check(ep,cfg.get('image'));c.entry_path(ep,cfg.get('annotation'))
        ann=c.read(c.entry_path(ep,cfg['annotation']))
        if not ann.get('canvas') or not ann.get('elements'):raise ValueError('SRT标注缺少canvas/elements')
        # Temporal allocation may be derived from the real narration during production.
        if 'srt' in cfg:c.entry_path(ep,cfg['srt'])
        elif 'timing_cues' not in cfg and not cfg.get('align_narration'):
            if any('reveal' not in e for e in ann['elements']):raise ValueError('无SRT时需align_narration或实际timing_cues')
        image=c.asset_path(ep,cfg['image'])
        from PIL import Image
        with Image.open(image) as im:
            if list(im.size)!=[ann['canvas']['width'],ann['canvas']['height']]:raise ValueError('标注坐标必须使用原图尺寸')
        for e in ann['elements']:
            r=e.get('region',{})
            if not all(type(r.get(k)) in (int,float) for k in ('x','y','width','height')) or r['width']<=0 or r['height']<=0 or r['x']<0 or r['y']<0 or r['x']+r['width']>ann['canvas']['width'] or r['y']+r['height']>ann['canvas']['height']:raise ValueError('标注region超出原图')

def srt_cues(path):
    import re
    def seconds(v):
        a,b,c=v.replace(',','.').split(':');return int(a)*3600+int(b)*60+float(c)
    text=Path(path).read_text(encoding='utf-8-sig');result=[]
    for block in re.split(r'\n\s*\n',text.strip()):
        lines=block.splitlines();i=next((i for i,v in enumerate(lines) if '-->' in v),None)
        if i is None:continue
        a,b=lines[i].split('-->');result.append({'start':seconds(a.strip()),'end':seconds(b.strip().split()[0]),'text':' '.join(lines[i+1:])})
    if not result or any(not q['text'] or not 0<=q['start']<q['end'] for q in result):raise ValueError('SRT缺少有效cue或时间/文本无效')
    return result

def aligned_annotation(ep,meta,shot,cfg):
    import composition as c
    ann=c.read(c.entry_path(ep,cfg['annotation']));fps=meta['fps'];n=shot['end_frame']-shot['start_frame']
    cues=cfg.get('timing_cues')
    if cfg.get('srt'):cues=srt_cues(c.entry_path(ep,cfg['srt']))
    elif cfg.get('align_narration'):
        path=Path(ep)/'work/timing.json'
        if not path.exists():raise ValueError('SRT白板等待实际配音字幕；先完成配音，不能使用估计时序')
        cues=c.read(path)['segments'];offset=shot['start_frame']/fps
        cues=[dict(q,start=q['start']-offset,end=q['end']-offset) for q in cues if q['start']>=offset and q['end']<=(shot['end_frame']/fps)+.001]
    elements=sorted(ann['elements'],key=lambda e:e['sequence'])
    if [e['sequence'] for e in elements]!=list(range(1,len(elements)+1)):raise ValueError('SRT语义分区sequence需连续从1开始')
    if cues is not None:
        for i,e in enumerate(elements):
            idx=e.get('cue_index',i)
            if type(idx)!=int or not 0<=idx<len(cues):raise ValueError('语义分区缺少对应实际字幕cue')
            q=cues[idx];e.setdefault('reveal',{}).update(startMs=round(q['start']*fps)*1000/fps,durationMs=(round(q['end']*fps)-round(q['start']*fps))*1000/fps)
            e['subtitle']=q['text']
    last=0
    for e in elements:
        r=e.get('reveal',{});a=round(r.get('startMs',-1000)*fps/1000);d=round(r.get('durationMs',0)*fps/1000)
        if a<last or d<3 or a+d>n:raise ValueError('分区时序需连续串行、至少3帧且不超出镜头')
        r.update(startMs=a*1000/fps,durationMs=d*1000/fps);last=a+d
    ann['elements']=elements;ann['sceneDurationMs']=n*1000/fps
    return ann

def render_shot(ep,meta,shot,kind,cfg):
    from production_stage import require
    import composition as c
    from output_backends import require_web_shots
    require(ep);require_web_shots(ep,[shot['id']]);validate_config(ep,kind,cfg,shot['end_frame']-shot['start_frame'],meta)
    ep=Path(ep).resolve();n=shot['end_frame']-shot['start_frame']
    h=hashlib.sha256(json.dumps([kind,cfg,meta['width'],meta['height'],meta['fps'],n],sort_keys=True,ensure_ascii=False).encode())
    # Conservative complete episode inputs, plus implementation and pinned vendor code.
    for p in sorted((ep/'assets').rglob('*')):
        if p.is_file():h.update(p.relative_to(ep).as_posix().encode());h.update(p.read_bytes())
    for key in ('entry','dsl','scene','annotation','srt'):
        if cfg.get(key):h.update(c.entry_path(ep,cfg[key]).read_bytes())
    if cfg.get('align_narration'):h.update((ep/'work/timing.json').read_bytes())
    vendor=VENDOR/({'remotion':'livecanvas','simo':'simo','srt':'srt_whiteboard'}[kind])
    h.update(Path(__file__).read_bytes())
    for p in sorted(vendor.rglob('*')):
        if p.is_file() and 'node_modules' not in p.parts and '__pycache__' not in p.parts:h.update(p.read_bytes())
    cache=ep/'work/shot_cache'/h.hexdigest()[:24];out=cache/'clip.mp4';proof=cache/'complete.json'
    if proof.exists() and out.exists() and c.read(proof).get('sha256')==hashlib.sha256(out.read_bytes()).hexdigest():return out
    cache.mkdir(parents=True,exist_ok=True);started=time.perf_counter()
    if kind=='remotion':render_remotion(ep,meta,shot,cfg,cache,out)
    elif kind=='simo':render_simo(ep,meta,shot,cfg,cache,out)
    else:render_srt(ep,meta,shot,cfg,cache,out)
    info=json.loads(subprocess.check_output([executable('ffprobe'),'-v','error','-count_frames','-show_streams','-of','json',str(out)]));stream=next(s for s in info['streams'] if s['codec_type']=='video')
    if int(stream['nb_read_frames'])!=n or [stream['width'],stream['height']]!=[meta['width'],meta['height']]:raise ValueError('镜头缓存帧数或尺寸不符：'+shot['id'])
    c.save(proof,dict(kind=kind,frames=n,sha256=hashlib.sha256(out.read_bytes()).hexdigest(),seconds=time.perf_counter()-started,source_commit=c.read(vendor/'provenance.json')['commit']))
    return out

def render_remotion(ep,meta,shot,cfg,cache,out):
    import composition as c
    project=cache/'remotion';(project/'src').mkdir(parents=True,exist_ok=True);(project/'public').mkdir(exist_ok=True)
    # Keep Node module resolution local to the optional runtime, without copying dependencies.
    for p in (VENDOR/'livecanvas').glob('package*.json'):shutil.copy2(p,project/p.name)
    for value in cfg.get('inputs',[]):
        p=c.asset_path(ep,value);dest=project/'public'/value;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    source=c.entry_path(ep,cfg['entry']);shutil.copy2(source,project/'src/Scene.tsx')
    # Episode code can import adjacent modules; explicit dependency entries remain inside episode.
    for value in cfg.get('code_files',[]):
        p=c.entry_path(ep,value);shutil.copy2(p,project/'src'/p.name)
    w,h,fps,n=meta['width'],meta['height'],meta['fps'],shot['end_frame']-shot['start_frame']
    (project/'src/index.tsx').write_text('import React from "react";import {Composition,registerRoot} from "remotion";import Scene from "./Scene";registerRoot(()=> <Composition id="LiveCanvas" component={Scene} width={'+str(w)+'} height={'+str(h)+'} fps={'+str(fps)+'} durationInFrames={'+str(n)+'} defaultProps={'+json.dumps(cfg.get('props',{}),ensure_ascii=False)+'}/>);',encoding='utf-8')
    # Remotion bundler supports explicit webpack aliases to the pinned optional install.
    run={'entry':str(project/'src/index.tsx'),'publicDir':str(project/'public'),'props':cfg.get('props',{}),'output':str(out)};c.save(cache/'remotion-job.json',run)
    env=os.environ.copy();env['HVP_BROWSER']=browser_executable()
    subprocess.run([shutil.which('node') or 'node',str(runtime_vendor('livecanvas')/'render-shot.mjs'),str(cache/'remotion-job.json')],env=env,check=True)

def render_simo(ep,meta,shot,cfg,cache,out):
    import composition as c
    if cfg.get('dsl'):
        runner=cache/'dsl-run.cjs';runner.write_text('const fs=require("fs");const scene=require('+json.dumps(str(c.entry_path(ep,cfg['dsl'])))+');fs.writeFileSync(process.argv[2],JSON.stringify(scene));',encoding='utf-8')
        subprocess.run([shutil.which('node') or 'node',str(runner),str(cache/'scene.json')],check=True);scene=c.read(cache/'scene.json')
    else:scene=c.read(c.entry_path(ep,cfg['scene']))
    elements=scene.get('elements',[]);intervals=scene.get('intervals',[]);n=shot['end_frame']-shot['start_frame'];fps=meta['fps']
    if not elements or len(elements)!=len(intervals):raise ValueError('simo场景需要elements及逐元素intervals帧区间')
    last=0
    for a,b in intervals:
        if type(a)!=int or type(b)!=int or a<last or not a<b<=n:raise ValueError('simo绘制区间需串行并落在镜头内')
        last=b
    files={}
    for key,value in scene.get('files',{}).items():
        if 'asset' not in value:raise ValueError('simo贴纸需assets引用，不能内嵌未审核图片')
        files[key]={'dataURL':c.data_url(c.asset_path(ep,value['asset']))}
    html=(VENDOR/'simo/lib/render.html').read_text(encoding='utf-8').replace('../node_modules/roughjs/bundled/rough.js',(runtime_vendor('simo')/'node_modules/roughjs/bundled/rough.js').as_uri()).replace('../assets/fonts/Xiaolai-Regular.ttf',(VENDOR/'simo/assets/fonts/Xiaolai-Regular.ttf').as_uri())
    pagepath=cache/'simo.html';pagepath.write_text(html,encoding='utf-8')
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser=p.chromium.launch(**browser_launch_options());page=browser.new_page(viewport={'width':meta['width'],'height':meta['height']},device_scale_factor=1);page.goto(pagepath.as_uri());page.evaluate('document.fonts.ready')
        page.evaluate('([w,h,els,files,n,fps,intervals,paper])=>{setCanvas(w,h);setPaper(paper);setCaptions([]);loadScene(els,els.map(()=>0),[[0,n/fps]],files,n/fps);setIntervals(intervals.map(v=>v.map(f=>f/fps)))}',[meta['width'],meta['height'],elements,files,n,fps,intervals,meta.get('visual',{}).get('paper','#fcf7ea')])
        page.evaluate('imagesReady()')
        command=[executable('ffmpeg'),'-y','-v','error','-f','image2pipe','-framerate',str(fps),'-c:v','png','-i','-','-c:v','libx264','-pix_fmt','yuv420p',str(out)]
        proc=subprocess.Popen(command,stdin=subprocess.PIPE)
        try:
            for f in range(n):
                page.evaluate('t=>seek(t)',f/fps);proc.stdin.write(page.screenshot(type='png'))
            proc.stdin.close()
            if proc.wait():raise RuntimeError('simo编码失败')
        finally:
            browser.close()
            if proc.poll() is None:proc.kill();proc.wait()

def render_srt(ep,meta,shot,cfg,cache,out):
    import composition as c
    from types import SimpleNamespace
    folder=VENDOR/'srt_whiteboard/scripts';sys.path.insert(0,str(folder))
    import render_stream_whiteboard as engine
    import stream_render as sr
    import cv2
    ann=aligned_annotation(ep,meta,shot,cfg)
    import math
    options=dict(sr.Config().__dict__);options.update(output_width=meta['width'],output_height=meta['height'],fps=meta['fps'],grid_edge=math.gcd(meta['width'],meta['height'],cfg.get('grid_edge',6)),canvas_hex=meta.get('visual',{}).get('paper','#fcf7ea'),ink_path_mode=cfg.get('ink_path','grid'),target_hand_height=round(meta['height']*.27))
    image=sr._imread_any(str(c.asset_path(ep,cfg['image'])));hand=c.asset_path(ep,cfg['hand']) if cfg.get('hand') else None
    ih,iw=image.shape[:2];w,h=meta['width'],meta['height']
    if abs(iw/ih-w/h)>.001:
        if cfg.get('fit','contain')!='contain':raise ValueError('SRT白板不同画幅默认contain；其他裁切需要本期重新编排线稿与标注')
        import numpy as np
        scale=min(w/iw,h/ih);nw,nh=round(iw*scale),round(ih*scale);dx,dy=(w-nw)//2,(h-nh)//2
        sx,sy=nw/iw,nh/ih;letterbox=np.empty((h,w,3),dtype=np.uint8);letterbox[:]=sr._hex_to_bgr(options['canvas_hex']);letterbox[dy:dy+nh,dx:dx+nw]=cv2.resize(image,(nw,nh));image=letterbox
        def rect(r):return {'x':r['x']*sx+dx,'y':r['y']*sy+dy,'width':r['width']*sx,'height':r['height']*sy}
        for e in ann['elements']:
            e['region']=rect(e['region']);e['reveal']['protectedRegions']=[rect(r) for r in e['reveal'].get('protectedRegions',[])]
        ann['canvas']={'width':w,'height':h}
    c.save(cache/'aligned-annotation.json',ann)
    renderer=engine.RegionStreamRenderer(image,ann,SimpleNamespace(**options),hand,cfg.get('bare_tip',False));raw=cache/'raw.mp4'
    renderer.render_to(raw,ann['sceneDurationMs'])
    subprocess.run([executable('ffmpeg'),'-y','-v','error','-i',str(raw),'-an','-c:v','libx264','-pix_fmt','yuv420p',str(out)],check=True)
