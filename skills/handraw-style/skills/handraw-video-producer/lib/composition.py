"""composition-v2: one primary shot type, composable private drawing layers."""
import base64, copy, hashlib, json, math, mimetypes, re, shutil, subprocess
from pathlib import Path
from frame_layout import resolve_frame
from subtitles import resolve_subtitle_mode, export_subtitles
from shot_catalog import ROOT, types
WORKFLOW='composition-v2'
KINDS=('image','video','text','highlight','path','html','remotion','simo','srt')
def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def unified(meta): return meta.get('workflow')==WORKFLOW
def new_episode(parent,title,frame,subtitle_mode,date,media_policy='auto',output_target=None):
    from video_tasks import POLICIES
    if output_target is None:raise ValueError('新建工程前必须选择输出路线：web（浏览器成片）或jianying（剪映草稿）')
    if media_policy not in POLICIES or output_target not in ('web','jianying'): raise ValueError('素材策略或输出方式无效')
    ep=Path(parent)/(date+' '+title)
    ep.mkdir(parents=True,exist_ok=False)
    for x in ('assets','work','outputs'): (ep/x).mkdir()
    save(ep/'episode.json',dict(title=title,workflow=WORKFLOW,**frame,subtitle_mode=subtitle_mode,brief={},visual={},media_policy=media_policy,output_target=output_target,narration={'enabled':True,'provider':'volc'},status='planning'))
    save(ep/'composition.json',dict(version=2,duration_frames=0,shots=[],subtitle_cues=[],audio_tracks=[],local_types=[]))
    save(ep/'video_tasks.json',dict(version=2,tasks=[]))
    (ep/'script.txt').write_text('',encoding='utf-8')
    from production_stage import initialize
    initialize(ep)
    return ep
def asset_path(ep,value):
    if not isinstance(value,str) or not value or Path(value).is_absolute(): raise ValueError('需要本期assets相对路径')
    p=(Path(ep)/value).resolve();r=(Path(ep)/'assets').resolve()
    if not p.is_relative_to(r) or not p.is_file(): raise ValueError('素材缺失或不在assets：'+value)
    return p
def entry_path(ep,value):
    if not isinstance(value,str) or not value: raise ValueError('缺少本期实现entry')
    p=(Path(ep)/value).resolve()
    if not p.is_relative_to(Path(ep).resolve()) or not p.is_file(): raise ValueError('缺少本期实现：'+value)
    return p
def finite(x): return type(x) in (int,float) and math.isfinite(x)
def rectangle(x): return isinstance(x,list) and len(x)==4 and all(finite(v) for v in x) and x[2]>0 and x[3]>0
def validate_keys(keys,duration,field):
    from motion import EASINGS
    last=-1
    for k in keys:
        a=k.get('at_frame');v=k.get(field)
        ok=rectangle(v) if field in ('region','view') else finite(v)
        if field=='opacity':ok=ok and 0<=v<=1
        if type(a)!=int or not last<a<=duration or not ok or k.get('easing','linear') not in EASINGS: raise ValueError('无效或乱序关键帧：'+field)
        last=a
def image_check(ep,value,transparent=False):
    from PIL import Image
    p=asset_path(ep,value)
    with Image.open(p) as im:
        if transparent and (im.mode not in ('RGBA','LA') or im.getextrema()[-1][0]==255): raise ValueError('sprite需要真实透明图：'+value)
    with Image.open(p) as im:im.verify()
def sequence_layers(spec,duration,prefix,full=False):
    frames=spec.get('frames',[]);play=spec.get('playback','once')
    if play not in ('static','loop','once'): raise ValueError('sprite播放方式需要static、loop或once')
    if full and (len(frames)<2 or play!='once'): raise ValueError('全图有限帧需要至少两张完整图片，按一次性序列播放')
    if full and ('source_rect' in spec or any('source_rect' in f for f in frames)):raise ValueError('全图有限帧不能使用sprite裁切')
    if play=='static':
        if not spec.get('asset') or frames: raise ValueError('静态sprite只使用asset')
        return [{**spec,'id':prefix,'kind':'image'}]
    if not frames: raise ValueError('动画缺少真实帧序列')
    for f in frames:
        if not f.get('asset') or type(f.get('hold_frames'))!=int or f['hold_frames']<=0: raise ValueError('每帧需asset与正整数hold_frames')
    a=spec.get('start_frame',0);b=spec.get('end_frame',duration);span=sum(f['hold_frames'] for f in frames)
    if full and span!=b-a: raise ValueError('全图停留帧数必须精确覆盖镜头，不自动补帧')
    if spec.get('on_end','hold') not in ('hold','hide'): raise ValueError('on_end需要hold或hide')
    result=[];cursor=a;i=0
    while cursor<b:
        if play=='once' and i>=len(frames):
            if spec.get('on_end','hold')=='hide':break
            f=frames[-1];end=b
        else:
            f=frames[i%len(frames)];end=min(b,cursor+f['hold_frames'])
        result.append({**{k:v for k,v in spec.items() if k not in ('frames','asset','playback','on_end')},**{k:v for k,v in f.items() if k not in ('hold_frames',)},'id':prefix+'_'+str(i),'kind':'image','asset':f['asset'],'start_frame':cursor,'end_frame':end,'sequence_index':i})
        cursor=end;i+=1
    return result
def normalize(authored):
    b=copy.deepcopy(authored)
    for s in b.get('shots',[]):
        cfg=copy.deepcopy(s.get('config',{}));d=s['end_frame']-s['start_frame'];t=s['type'];layers=[]
        if t=='ST-001':layers=[{**cfg,'id':'main','kind':'image'}]
        elif t=='ST-002':layers=[{**cfg,'id':'main','kind':'video'}]
        elif t=='ST-003':
            bg=cfg.get('background')
            if not bg:raise ValueError('背景＋透明素材动画缺少background')
            layers=[{**({'asset':bg} if isinstance(bg,str) else bg),'id':'background','kind':'image'}]
            sprites=cfg.get('sprites',[])
            if not sprites:raise ValueError('ST-003需要至少一个sprite')
            ids=set()
            for sp in sorted(sprites,key=lambda x:x.get('z_index',0)):
                if not sp.get('id') or sp['id'] in ids:raise ValueError('sprite需唯一id')
                ids.add(sp['id'])
                layers+=sequence_layers({**sp,'transparent':True},d,sp['id'])
        elif t=='ST-004':layers=sequence_layers({**cfg,'playback':'once'},d,'full',True)
        elif t in ('ST-005','ST-006','ST-007'):
            layers=[{'id':'main','kind':{'ST-005':'remotion','ST-006':'simo','ST-007':'srt'}[t],'config':cfg,'fit':'stretch'}]
        else:
            definition=next((x for x in b.get('local_types',[]) if x.get('id')==t),None)
            if not definition or definition.get('adapter')!='html' or definition.get('status')!='implemented' or not definition.get('asset_contract'):raise ValueError('未知或未实现分镜类型：'+str(t))
            layers=[{'id':'main','kind':'html','entry':cfg.get('entry',definition.get('entry'))}]
        s['layers']=layers+s.get('layers',[])
    return b
def validate(ep,meta=None):
    ep=Path(ep);meta=meta or read(ep/'episode.json')
    if not unified(meta):raise ValueError('仅支持composition-v2；旧工程保留但不转换或继续执行')
    resolve_frame(width=meta['width'],height=meta['height'],fps=meta['fps']);resolve_subtitle_mode(meta)
    if meta.get('output_target','web') not in ('web','jianying'):raise ValueError('未知输出方式')
    for color in meta.get('visual',{}).get('palette',{}).values():
        if not isinstance(color,str) or not re.fullmatch(r'#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?',color):raise ValueError('配色需要实际十六进制色值')
    authored=read(ep/'composition.json');total=authored.get('duration_frames')
    if authored.get('version')!=2 or type(total)!=int or total<=0 or not authored.get('shots'):raise ValueError('需要version=2、正duration_frames及shots；目前仍为方案草稿')
    shared=types();local=set()
    for t in authored.get('local_types',[]):
        if not t.get('id') or t['id'] in shared or t['id'] in local:raise ValueError('本期类型不能覆盖共享类型')
        local.add(t['id']);entry_path(ep,t.get('entry'))
    seen=set();cursor=0
    for s in authored['shots']:
        sid=s.get('id');a=s.get('start_frame');z=s.get('end_frame')
        if not isinstance(sid,str) or not re.fullmatch(r'[\w-]+',sid) or sid in seen or not s.get('purpose'):raise ValueError('镜头需要唯一id及purpose')
        if type(a)!=int or type(z)!=int or a!=cursor or not a<z<=total:raise ValueError('镜头'+sid+'需连续覆盖时间线，结束帧不包含')
        seen.add(sid);cursor=z
    if cursor!=total:raise ValueError('未覆盖最后一帧')
    b=copy.deepcopy(authored);b['shots']=[]
    for s in authored['shots']:
        try:b['shots']+=normalize({**authored,'shots':[s]})['shots']
        except (ValueError,KeyError,TypeError) as e:raise ValueError('镜头'+s['id']+': '+str(e)) from e
    for index,s in enumerate(b['shots']):
        try:
            d=s['end_frame']-s['start_frame']
            if 'jianying' in s:
                from jianying_native import validate_scene
                validate_scene(s,b['shots'][index+1] if index+1<len(b['shots']) else None)
            if s.get('render_backend','auto') not in ('auto','web','jianying'):raise ValueError('未知逐镜后端')
            tr=s.get('transition',{'type':'cut','frames':0});n=tr.get('frames',0)
            if tr.get('type') not in ('cut','dissolve','wipe') or type(n)!=int or not 0<=n<d or (tr['type']=='cut' and n) or (s is b['shots'][0] and n):raise ValueError('转场类型或帧数无效')
            ev={};ids=set()
            for e in s.get('events',[]):
                at=e.get('at_frame')
                if not e.get('id') or e['id'] in ev or type(at)!=int or not 0<=at<d:raise ValueError('无效事件')
                ev[e['id']]=at
            for l in s['layers']:
                if not l.get('id') or l['id'] in ids:raise ValueError('图层编号重复或缺失')
                ids.add(l['id']);k=l.get('kind')
                if k not in KINDS:raise ValueError('未知图层实现：'+str(k))
                if not rectangle(l.get('region',[0,0,1,1])):raise ValueError('region需要归一化[x,y,w,h]')
                if l.get('fit','contain') not in ('contain','cover','stretch'):raise ValueError('未知fit')
                a=l.get('start_frame',0);z=l.get('end_frame',d)
                if type(a)!=int or type(z)!=int or not 0<=a<z<=d:raise ValueError('无效显示区间')
                for gate in ('show_after','hide_after'):
                    if gate in l and l[gate] not in ev:raise ValueError('未知动作事件')
                if not finite(l.get('opacity',1)) or not 0<=l.get('opacity',1)<=1:raise ValueError('无效透明度')
                for field,keys in [('region','keyframes'),('opacity','opacity_keyframes'),('rotation','rotation_keyframes')]:validate_keys(l.get(keys,[]),d,field)
                if 'motion' in l:
                    from motion import validate_motion
                    validate_motion(l['motion'],d)
                for anchor,point in l.get('contact_anchors',{}).items():
                    if not isinstance(point,list) or len(point)!=2 or not all(finite(v) and 0<=v<=1 for v in point):raise ValueError('接触锚点需要图内归一化坐标')
                if k=='image':
                    image_check(ep,l.get('asset'),l.get('transparent',False))
                    if l.get('source_rect'):
                        from PIL import Image
                        r=l['source_rect']
                        with Image.open(asset_path(ep,l['asset'])) as im:
                            if not rectangle(r) or r[0]<0 or r[1]<0 or r[0]+r[2]>im.width or r[1]+r[3]>im.height:raise ValueError('素材裁切超出原图')
                elif k=='video':
                    from video_tasks import probe
                    info=probe(asset_path(ep,l.get('asset')));offset=l.get('source_in');out=l.get('source_out')
                    if not finite(offset) or not finite(out) or not 0<=offset<out<=info['duration']+.001 or abs(out-offset-(z-a)/meta['fps'])>.001:raise ValueError('视频需要明确source_in/source_out，原速精确覆盖显示时长')
                    if l.get('audio'):raise ValueError('原声只能显式加入audio_tracks')
                elif k=='text':
                    if not isinstance(l.get('text'),str) or not l['text'].strip():raise ValueError('文字为空')
                elif k=='path':
                    if len(l.get('points',[]))<2 or any(len(p)!=2 or not all(finite(v) for v in p) for p in l['points']):raise ValueError('路径节点无效')
                elif k=='html':entry_path(ep,l.get('entry'))
                elif k in ('remotion','simo','srt'):
                    from shot_engines import validate_config
                    validate_config(ep,k,l['config'],d,meta,check_runtime=False)
            validate_keys(s.get('camera',{}).get('keyframes',[]),d,'view')
        except (ValueError,KeyError,TypeError) as e:raise ValueError('镜头'+s['id']+': '+str(e)) from e
    for cue in b.get('subtitle_cues',[]):
        if type(cue.get('start_frame'))!=int or type(cue.get('end_frame'))!=int or not 0<=cue['start_frame']<cue['end_frame']<=total or not cue.get('text'):raise ValueError('字幕时间或文本无效')
    for track in b.get('audio_tracks',[]):
        asset_path(ep,track.get('path'));a=track.get('start_frame',0);z=track.get('end_frame',total)
        if type(a)!=int or type(z)!=int or not 0<=a<z<=total or not finite(track.get('gain',1)) or not 0<=track.get('gain',1)<=4:raise ValueError('无效音轨')
        if not finite(track.get('source_in',0)) or track.get('source_in',0)<0:raise ValueError('无效音轨截取起点')
        for field in ('fade_in_frames','fade_out_frames'):
            if type(track.get(field,0))!=int or not 0<=track.get(field,0)<=z-a:raise ValueError('音轨淡入淡出帧范围无效')
        from runtime_tools import executable
        info=json.loads(subprocess.check_output([executable('ffprobe'),'-v','error','-show_streams','-show_format','-of','json',str(asset_path(ep,track['path']))]))
        if not any(x['codec_type']=='audio' for x in info['streams']) or track.get('source_in',0)<0 or track.get('source_in',0)+(z-a)/meta['fps']>float(info['format']['duration'])+.001:raise ValueError('音轨不存在或不足，不自动补时长')
    from video_tasks import preflight
    preflight(ep,meta,b,{k:{'adapter':k} for k in KINDS})
    return b,{k:{'adapter':k} for k in KINDS}
def data_url(path):return 'data:'+(mimetypes.guess_type(str(path))[0] or 'application/octet-stream')+';base64,'+base64.b64encode(path.read_bytes()).decode()

def timing_for(ep, meta, board):
    fps = meta['fps']
    path = Path(ep) / 'work/timing.json'
    existing = read(path) if path.exists() else {'segments': []}
    if board.get('subtitle_cues'):
        segments = [{'start': c['start_frame']/fps, 'end': c['end_frame']/fps, 'text': c['text']} for c in board['subtitle_cues']]
    elif meta.get('subtitle_source'):
        from shot_engines import srt_cues
        segments=srt_cues(asset_path(ep,meta['subtitle_source']))
    else:
        segments = existing.get('segments', []) if meta.get('narration', {}).get('enabled', True) else []
    duration = board['duration_frames']/fps
    if any(not 0 <= s['start'] < s['end'] <= duration+.001 for s in segments):
        raise ValueError('实际语音/字幕时间超出统一时间线；请调整分镜，不截断声音')
    if existing.get('duration', 0) > duration+.001 and meta.get('narration', {}).get('enabled', True):
        raise ValueError('实际旁白比画面长；先调整分镜总时长')
    narration = meta.get('narration', {})
    if narration.get('enabled',True) and narration.get('path'):
        from runtime_tools import executable
        audio = asset_path(ep,narration['path'])
        details = json.loads(subprocess.check_output([executable('ffprobe'),'-v','error','-show_format','-show_streams','-of','json',str(audio)]))
        if not any(s['codec_type']=='audio' for s in details['streams']):
            raise ValueError('narration.path没有音频流')
        if float(details['format']['duration']) > duration+.001:
            raise ValueError('导入旁白比画面长；先调整分镜总时长')
    return {'duration': duration, 'segments': segments}


def prepare(ep,shot_ids=None,subtitle_mode=None):
    from production_stage import require
    from runtime_tools import executable
    require(ep);ep=Path(ep).resolve();meta=read(ep/'episode.json')
    from output_backends import require_web_shots
    require_web_shots(ep,shot_ids)
    board,_=validate(ep,meta);timing=timing_for(ep,meta,board)
    work=ep/'work/unified';work.mkdir(parents=True,exist_ok=True);cfg=copy.deepcopy(board)
    if shot_ids is not None:cfg['shots']=[s for s in cfg['shots'] if s['id'] in shot_ids]
    cfg.update(width=meta['width'],height=meta['height'],fps=meta['fps'],subtitle_mode=subtitle_mode or resolve_subtitle_mode(meta),subtitles=timing['segments'],paper=meta.get('visual',{}).get('paper','#fcf7ea'))
    evidence=[]
    for shot in cfg['shots']:
        for layer in shot['layers']:
            kind=layer['adapter']=layer['kind'];path=None
            if kind in ('remotion','simo','srt'):
                from shot_engines import render_shot
                path=render_shot(ep,meta,shot,kind,layer['config']);layer.update(adapter='video',derived=True,source_in=0)
            elif layer.get('asset'):path=asset_path(ep,layer['asset'])
            if path:
                sha=hashlib.sha256(path.read_bytes()).hexdigest();evidence.append({'shot':shot['id'],'layer':layer['id'],'path':str(path.relative_to(ep)),'sha256':sha,'derived':layer.get('derived',False)})
                layer['url']='../../'+path.relative_to(ep).as_posix()
            if layer['adapter']=='video':
                count=layer.get('end_frame',shot['end_frame']-shot['start_frame'])-layer.get('start_frame',0)
                key=hashlib.sha256((sha+json.dumps([meta['fps'],layer.get('source_in',0),count])).encode()).hexdigest()[:24];cache=work/'video_frames'/key
                if not (cache/'complete.json').is_file():
                    cache.mkdir(parents=True,exist_ok=True)
                    subprocess.run([executable('ffmpeg'),'-y','-v','error','-ss',str(layer.get('source_in',0)),'-i',str(path),'-map','0:v:0','-an','-vf','fps='+str(meta['fps']),'-frames:v',str(count),str(cache/'frame-%06d.png')],check=True)
                    if not all((cache/('frame-%06d.png'%i)).is_file() for i in range(1,count+1)):raise ValueError('视频解码帧数不足：'+shot['id'])
                    save(cache/'complete.json',dict(sha256=sha,frames=count,fps=meta['fps']))
                layer.update(frame_base='video_frames/'+key+'/frame-',frame_count=count)
            if kind=='html':layer['url']='../../'+entry_path(ep,layer['entry']).relative_to(ep).as_posix()
    page=work/'scene.html'
    page.write_text('<!doctype html><meta charset="utf-8"><link rel="icon" href="data:,"><style>body{margin:0}canvas{display:block}</style><canvas id="stage"></canvas><script>window.COMPOSITION='+json.dumps(cfg,ensure_ascii=False).replace('<','\\u003c')+';</script><script src="runtime.js"></script>',encoding='utf-8')
    shutil.copy2(ROOT/'lib/composition_runtime.js',work/'runtime.js')
    save(ep/'work/composition_record.json',dict(workflow=WORKFLOW,shot_types=[s['type'] for s in board['shots']],assets=evidence,validation='compiled; technical and aesthetic review separate'))
    return page,timing

def render(ep):
    from output_backends import require_plan
    if read(Path(ep)/'episode.json').get('output_target','web')!='web':raise ValueError('剪映工程使用export/build输出草稿；不能通过render进行全片浏览器渲染')
    require_plan(ep,'web')
    from render_engine import render_html_to_video
    ep = Path(ep)
    meta = read(ep/'episode.json')
    page, timing = prepare(ep)
    render_html_to_video(page,ep/'work/raw_video.mp4',timing['duration'],meta['fps'],meta['width'],meta['height'],serve_root=ep)
    meta['subtitles'] = export_subtitles(ep,meta,timing) if timing['segments'] else None
    save(ep/'episode.json',meta)
    return page


def mix(ep):
    from production_stage import require
    require(ep)
    from runtime_tools import executable
    ep = Path(ep).resolve()
    meta = read(ep/'episode.json')
    if meta.get('output_target','web')!='web':raise ValueError('剪映工程使用export/build输出草稿，不执行网页成片mix')
    board, _ = validate(ep,meta)
    raw = ep/'work/raw_video.mp4'
    if not raw.is_file(): raise FileNotFoundError(raw)
    out = ep/'outputs/final.mp4'
    duration = board['duration_frames']/meta['fps']
    tracks = copy.deepcopy(board.get('audio_tracks', []))
    voice = meta.get('narration',{})
    if voice.get('enabled',True):
        path = asset_path(ep,voice['path']) if voice.get('path') else next((p for p in [ep/'work/dialogue_mix.wav',ep/'work/narration.mp3'] if p.exists()),None)
        if path is None: raise ValueError('缺少实际旁白；执行tts、导入音频或明确关闭narration.enabled')
        tracks.insert(0,{'resolved_path':str(path),'gain':1,'start_frame':0,'end_frame':board['duration_frames']})
    if not tracks:
        shutil.copy2(raw,out)
    else:
        cmd = [executable('ffmpeg'),'-y','-v','error','-i',str(raw)]
        filters = []
        for i,track in enumerate(tracks,1):
            path = Path(track['resolved_path']) if track.get('resolved_path') else asset_path(ep,track['path'])
            cmd += ['-i',str(path)]
            start = track.get('start_frame',0)/meta['fps']
            length = (track.get('end_frame',board['duration_frames'])-track.get('start_frame',0))/meta['fps']
            fade=''
            if track.get('fade_in_frames'):fade+=f",afade=t=in:d={track['fade_in_frames']/meta['fps']}"
            if track.get('fade_out_frames'):fade+=f",afade=t=out:st={length-track['fade_out_frames']/meta['fps']}:d={track['fade_out_frames']/meta['fps']}"
            filters.append(f"[{i}:a]atrim=start={track.get('source_in',0)}:duration={length},asetpts=PTS-STARTPTS,volume={track.get('gain',1)}{fade},adelay={round(start*1000)}:all=1[a{i}]")
        filters.append(''.join(f'[a{i}]' for i in range(1,len(tracks)+1))+f'amix=inputs={len(tracks)}:normalize=0,alimiter=limit=0.95:level=0:latency=1,apad,atrim=duration={duration}[audio]')
        cmd += ['-filter_complex',';'.join(filters),'-map','0:v:0','-map','[audio]','-c:v','copy','-c:a','aac','-t',str(duration),str(out)]
        subprocess.run(cmd,check=True)
    timing = timing_for(ep,meta,board)
    meta.update({'subtitles':export_subtitles(ep,meta,timing) if timing['segments'] else None,
                 'status':'technical_review_pending','output':'outputs/final.mp4'})
    save(ep/'episode.json',meta)
    (ep/'preview.html').write_text('<!doctype html><meta charset="utf-8"><title>'+meta['title'].replace('<','&lt;')+'</title><video controls style="max-width:100%" src="outputs/final.mp4">'+
         ('<track kind="subtitles" srclang="zh" src="outputs/subtitles.vtt">' if meta.get('subtitles') else '')+'</video>',encoding='utf-8')
    if meta.get('subtitles'):
        from tts_engine import generate_srt
        text = generate_srt(timing['segments'])
        import re
        vtt = re.sub(r'(\d{2}:\d{2}:\d{2}),(\d{3})', r'\1.\2', text)
        (ep/'outputs/subtitles.vtt').write_text('WEBVTT\n\n'+vtt,encoding='utf-8')
    return out
