"""Optional, local-only Jianying draft output. No app automation, generation or overwrite."""
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

from PIL import Image, ImageDraw, ImageFont
import composition as comp
from motion import sample
from output_backends import frame_us
from runtime_tools import executable

VENDOR=Path(__file__).parent/'vendor/jianying'


def draft_api():
    # A private namespace prevents an unrelated globally installed version winning.
    name='_hvp_pinned_jianying'
    if name not in sys.modules:
        path=VENDOR/'pyJianYingDraft/__init__.py'
        spec=importlib.util.spec_from_file_location(name,path,submodule_search_locations=[str(path.parent)])
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module
        try:spec.loader.exec_module(module)
        except Exception:sys.modules.pop(name,None);raise
    return sys.modules[name]


def narration_path(ep,meta):
    voice=meta.get('narration',{})
    if not voice.get('enabled',True):return None
    if voice.get('path'):return comp.asset_path(ep,voice['path'])
    for p in (Path(ep)/'work/dialogue_mix.wav',Path(ep)/'work/narration.mp3'):
        if p.is_file():return p
    raise ValueError('缺少实际旁白；导入narration.path、先执行已配置配音流程或明确关闭narration.enabled')


def probe(path):
    return json.loads(subprocess.check_output([executable('ffprobe'),'-v','error','-show_streams','-show_format','-of','json',str(path)]))


def video_material(api,path):
    """Adapt upstream material fields, using existing runtimes instead of pymediainfo."""
    m=api.VideoMaterial.__new__(api.VideoMaterial)
    m.path=str(Path(path).resolve());m.material_name=Path(path).name
    m.material_id=uuid.uuid4().hex;m.local_material_id='';m.crop_settings=api.CropSettings()
    if Path(path).suffix.lower()=='.png':
        with Image.open(path) as im:m.width,m.height=im.size
        m.duration=10_800_000_000;m.material_type='photo'
    else:
        from video_tasks import probe as video_probe
        info=video_probe(path);m.width,m.height=info['width'],info['height']
        m.duration=round(info['duration']*1e6);m.material_type='video'
    return m


def audio_material(api,path):
    info=probe(path);stream=next((s for s in info['streams'] if s['codec_type']=='audio'),None)
    if stream is None:raise ValueError('音轨没有实际音频流：'+str(path))
    m=api.AudioMaterial.__new__(api.AudioMaterial)
    m.path=str(Path(path).resolve());m.material_name=Path(path).name;m.material_id=uuid.uuid4().hex
    raw=stream.get('duration',info.get('format',{}).get('duration'))
    m.duration=round(float(raw)*1e6)
    return m


def color(value):
    value=value.lstrip('#')
    if len(value)==3:value=''.join(c*2 for c in value)
    return tuple(int(value[i:i+2],16)/255 for i in (0,2,4))


def visible(scene,layer):
    n=scene['end_frame']-scene['start_frame'];events={e['id']:e['at_frame'] for e in scene.get('events',[])}
    a,b=layer.get('start_frame',0),layer.get('end_frame',n)
    if layer.get('show_after'):a=max(a,events[layer['show_after']])
    if layer.get('hide_after'):b=min(b,events[layer['hide_after']])
    return a,b


def geometry(scene,layer,frame,W,H,sw,sh):
    r=sample(layer.get('keyframes',[]),frame,'region',layer.get('region',[0,0,1,1]))
    x,y,w,h=r[0]*W,r[1]*H,r[2]*W,r[3]*H
    if layer.get('fit','contain')=='stretch':dw,dh=w,h
    else:
        factor=min(w/sw,h/sh);dw,dh=sw*factor,sh*factor
    cx,cy=x+w/2,y+h/2
    view=sample(scene.get('camera',{}).get('keyframes',[]),frame,'view',[0,0,1,1])
    cx=(cx-view[0]*W)/view[2];cy=(cy-view[1]*H)/view[3]
    dw/=view[2];dh/=view[3]
    # Jianying initially contains media in the canvas, before its clip transform.
    base=min(W/sw,H/sh)
    return {'position_x':2*cx/W-1,'position_y':1-2*cy/H,
            'scale_x':dw/(sw*base),'scale_y':dh/(sh*base)}


def alpha(layer,f):
    value=sample(layer.get('opacity_keyframes',[]),f,'opacity',layer.get('opacity',1))
    if layer.get('reveal_frames'):value*=max(0,min(1,(f-layer.get('start_frame',0)+1)/layer['reveal_frames']))
    return value


def _font(size):
    configured=os.environ.get('HVP_FONT')
    if configured:
        if not Path(configured).is_file():raise ValueError('HVP_FONT指定的字体不存在')
        return ImageFont.truetype(configured,round(size))
    windows=os.environ.get('WINDIR')
    candidates=[Path(windows)/'Fonts'/name for name in ('msyh.ttc','msyh.ttf','arial.ttf')] if windows else []
    candidates.append(Path(__file__).parent/'vendor/simo/assets/fonts/Xiaolai-Regular.ttf')
    for p in candidates:
        if p.is_file():return ImageFont.truetype(str(p),round(size))
    raise ValueError('缺少可用字体；请设置HVP_FONT')


def text_layout(layer,W,H):
    r=layer.get('region',[0,0,1,1]);size=layer.get('font_size',min(W,H)*.045);font=_font(size)
    lines=[];line=''
    for ch in layer['text']:
        if ch=='\n':lines.append(line);line='';continue
        if font.getlength(line+ch)>r[2]*W and line:lines.append(line);line=''
        if font.getlength(ch)>r[2]*W:raise ValueError('文字区域太窄：'+layer['id'])
        line+=ch
    if line:lines.append(line)
    if len(lines)*size*1.3>r[3]*H:raise ValueError('文字超出区域：'+layer['id'])
    return '\n'.join(lines),size,max(font.getlength(s) for s in lines),len(lines)*size*1.3


class Package:
    def __init__(self,folder):
        self.folder=folder;self.assets=folder/'draft/assets';self.assets.mkdir(parents=True)
        self.materials=[];self.by_hash={}
    def copy(self,path):
        path=Path(path);sha=hashlib.sha256(path.read_bytes()).hexdigest();name=sha[:24]+path.suffix.lower()
        if name not in self.by_hash:
            dest=self.assets/name;shutil.copy2(path,dest);self.by_hash[name]=dest
            self.materials.append({'path':'assets/'+name,'original_path':str(dest.resolve()),'sha256':sha,'source_path':str(path.resolve())})
        return self.by_hash[name]
    def png(self,image):
        import io
        data=io.BytesIO();image.save(data,format='PNG');data=data.getvalue();sha=hashlib.sha256(data).hexdigest();name=sha[:24]+'.png'
        if name not in self.by_hash:
            dest=self.assets/name;dest.write_bytes(data);self.by_hash[name]=dest
            self.materials.append({'path':'assets/'+name,'original_path':str(dest.resolve()),'sha256':sha})
        return self.by_hash[name]


def shape_image(layer,W,H):
    r=layer.get('region',[0,0,1,1]);w,h=max(1,round(r[2]*W)),max(1,round(r[3]*H))
    im=Image.new('RGBA',(w,h));draw=ImageDraw.Draw(im)
    ink=layer.get('color','#f6762b' if layer['kind']=='highlight' else '#194ac8')
    stroke=round(layer.get('line_width',min(W,H)*(.008 if layer['kind']=='highlight' else .005)))
    if layer['kind']=='highlight':
        draw.rectangle([0,0,w-1,h-1],fill=layer.get('fill'),outline=ink,width=max(1,stroke))
    else:
        draw.line([(round(p[0]*(w-1)),round(p[1]*(h-1))) for p in layer['points']],fill=ink,width=max(1,stroke),joint='curve')
    return im


def image_crop(ep,layer,rect,meta):
    with Image.open(comp.asset_path(ep,layer['asset'])) as source:
        im=source.convert('RGBA')
    if rect:
        x,y,w,h=rect;im=im.crop((round(x),round(y),round(x+w),round(y+h)))
    if layer.get('fit','contain')=='cover':
        from PIL import ImageOps
        r=layer.get('region',[0,0,1,1]);size=(max(1,round(r[2]*meta['width'])),max(1,round(r[3]*meta['height'])))
        im=ImageOps.fit(im,size,method=Image.Resampling.LANCZOS)
    return im


def add_layer(api,script,pack,ep,meta,scene,layer,track_name=None):
    W,H,fps=meta['width'],meta['height'],meta['fps'];a,b=visible(scene,layer)
    if a>=b:return []
    kind=layer['kind']
    if kind=='text':
        value,size,tw,th=text_layout(layer,W,H);r=layer.get('region',[0,0,1,1])
        # Native font-size units are draft units, calibrated conservatively at 1080.
        style=api.TextStyle(size=size*100/1080,color=color(layer.get('color','#242b38')),
                            bold=layer.get('weight',600)>=600,alpha=1,align=0)
        start=frame_us(scene['start_frame']+a,fps);end=frame_us(scene['start_frame']+b,fps)
        first=sample(layer.get('keyframes',[]),a,'region',r)
        settings=api.ClipSettings(alpha=alpha(layer,a),transform_x=2*(first[0]+tw/W/2)-1,transform_y=1-2*(first[1]+th/H/2))
        segment=api.TextSegment(value,api.Timerange(start,end-start),style=style,clip_settings=settings)
        track=track_name or scene['id']+'_'+layer['id']
        if track not in script.tracks:script.append_track(api.TrackSpec(api.TrackType.text,track))
        if layer.get('keyframes'):
            for f in range(a,b):
                r=sample(layer['keyframes'],f,'region',first);offset=frame_us(scene['start_frame']+f,fps)-start
                segment.add_keyframe(api.KeyframeProperty.position_x,offset,2*(r[0]+tw/W/2)-1)
                segment.add_keyframe(api.KeyframeProperty.position_y,offset,1-2*(r[1]+th/H/2))
        if layer.get('opacity_keyframes') or layer.get('reveal_frames'):
            for f in range(a,b):
                offset=frame_us(scene['start_frame']+f,fps)-start
                segment.add_keyframe(api.KeyframeProperty.alpha,offset,alpha(layer,f))
        script.add_segment(segment,track)
        # Pinned upstream omits a TextSegment's inherited speed from ScriptMaterial,
        # despite exporting its ID in extra_material_refs. Register it explicitly.
        if segment.speed not in script.materials.speeds:script.materials.speeds.append(segment.speed)
        return []
    track=track_name or scene['id']+'_'+layer['id']
    if track not in script.tracks:script.append_track(api.TrackSpec(api.TrackType.video,track))
    created=[]
    intervals=[(a,b,layer.get('source_rect'))]
    if kind=='sprite':
        poses=layer['frames'];intervals=[]
        for i,pose in enumerate(poses):
            lo=max(a,pose['at_frame']);hi=min(b,poses[i+1]['at_frame'] if i+1<len(poses) else b)
            if lo<hi:intervals.append((lo,hi,pose['source_rect']))
    for lo,hi,rect in intervals:
        if kind in ('image','sprite'):path=pack.png(image_crop(ep,layer,rect,meta))
        elif kind in ('highlight','path'):path=pack.png(shape_image(layer,W,H))
        else:path=pack.copy(comp.asset_path(ep,layer['asset']))
        material=video_material(api,path)
        start=frame_us(scene['start_frame']+lo,fps);end=frame_us(scene['start_frame']+hi,fps)
        original=0
        # source_in is seconds, retain microsecond precision independent of output fps.
        if kind=='video':original=round(layer.get('source_in',0)*1e6)+frame_us(lo-layer.get('start_frame',0),fps)
        props=geometry(scene,layer,lo,W,H,material.width,material.height)
        settings=api.ClipSettings(alpha=alpha(layer,lo),transform_x=props['position_x'],transform_y=props['position_y'],scale_x=props['scale_x'],scale_y=props['scale_y'])
        segment=api.VideoSegment(material,api.Timerange(start,end-start),source_timerange=api.Timerange(original,end-start),speed=1,volume=0,clip_settings=settings)
        segment.uniform_scale=False
        animated=bool(layer.get('keyframes') or scene.get('camera',{}).get('keyframes') or layer.get('opacity_keyframes') or layer.get('reveal_frames'))
        if animated:
            # Sampling preserves compound camera transforms and nonlinear authored easing.
            for f in range(lo,hi):
                offset=frame_us(scene['start_frame']+f,fps)-start
                for name,value in geometry(scene,layer,f,W,H,material.width,material.height).items():
                    segment.add_keyframe(getattr(api.KeyframeProperty,name),offset,value)
                segment.add_keyframe(api.KeyframeProperty.alpha,offset,alpha(layer,f))
        script.add_segment(segment,track)
        created.append(segment)
    return created


def add_audio(api,script,pack,ep,meta,board):
    tracks=copy.deepcopy(board.get('audio_tracks',[]));voice=narration_path(ep,meta)
    if voice:tracks.insert(0,{'resolved_path':str(voice),'start_frame':0,'end_frame':board['duration_frames'],'gain':1})
    fps=meta['fps']
    for i,track in enumerate(tracks):
        path=Path(track['resolved_path']) if track.get('resolved_path') else comp.asset_path(ep,track['path'])
        info=probe(path)
        if any(s['codec_type']=='video' for s in info['streams']):
            dest=ep/'work/jianying_audio'/('source_'+hashlib.sha256(path.read_bytes()).hexdigest()[:20]+'.wav');dest.parent.mkdir(parents=True,exist_ok=True)
            if not dest.exists():subprocess.run([executable('ffmpeg'),'-y','-v','error','-i',str(path),'-vn','-c:a','pcm_s16le',str(dest)],check=True)
            path=dest
        material=audio_material(api,pack.copy(path));a=track.get('start_frame',0);b=track.get('end_frame',board['duration_frames']);offset=round(track.get('source_in',0)*1e6)
        start=frame_us(a,fps);duration=frame_us(b,fps)-start
        if offset>=material.duration:raise ValueError('音轨source_in越界')
        # Narration may end before the picture; silence is natural, never stretch it.
        if voice and i==0:duration=min(duration,material.duration-offset)
        elif offset+duration>material.duration+1000:raise ValueError('音轨过短；不循环或变速补时长')
        duration=min(duration,material.duration-offset)
        segment=api.AudioSegment(material,api.Timerange(start,duration),source_timerange=api.Timerange(offset,duration),speed=1,volume=track.get('gain',1))
        if track.get('fade_in_frames') or track.get('fade_out_frames'):
            segment.add_fade(frame_us(track.get('fade_in_frames',0),fps),frame_us(track.get('fade_out_frames',0),fps))
        name='audio_'+str(i);script.append_track(api.TrackSpec(api.TrackType.audio,name));script.add_segment(segment,name)


def layer_track(scene,layer):
    """Keep one editable lane per authored subject, never one lane per pose."""
    if scene['type']=='ST-003':
        for sprite in scene.get('config',{}).get('sprites',[]):
            sid=sprite['id']
            expected=sid+'_'+str(layer['sequence_index']) if 'sequence_index' in layer else sid
            if layer['id']==expected:
                return scene['id']+'_'+sid
    if scene['type']=='ST-004' and 'sequence_index' in layer:
        return scene['id']+'_full'
    return scene['id']+'_'+layer['id']


def export_draft(ep,report):
    from production_stage import require
    require(ep)
    from output_backends import pre_render,require_plan
    ep=Path(ep).resolve();report=require_plan(ep,'jianying');meta=comp.read(ep/'episode.json');board,_=comp.validate(ep,meta);timing=comp.timing_for(ep,meta,board)
    api=draft_api();export_id=time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]
    folder=ep/'outputs/jianying'/export_id;folder.mkdir(parents=True,exist_ok=False);pack=Package(folder)
    script=api.ScriptFile(meta['width'],meta['height'],meta['fps'],False);measurements=[];began=time.perf_counter()
    from jianying_native import primary_layers,resolve,add_scene_tracks
    shared_primary=any('transition_out' in s.get('jianying',{}) for s in board['shots'])
    transition_shots=set()
    for i,scene in enumerate(board['shots'][:-1]):
        if scene.get('jianying',{}).get('transition_out'):
            transition_shots.update((scene['id'],board['shots'][i+1]['id']))
    primary_segments={}
    if shared_primary:
        script.append_track(api.TrackSpec(api.TrackType.video,'hvp_paper'))
        script.append_track(api.TrackSpec(api.TrackType.video,'hvp_primary'))
    for scene,route in zip(board['shots'],report['shots']):
        n=scene['end_frame']-scene['start_frame']
        if route['implementation']=='web':
            path,measurement=pre_render(ep,meta,board,scene);measurements.append(measurement)
            # Explicitly flattened opaque shot; narration/captions remain independent.
            material=video_material(api,pack.copy(path));start=frame_us(scene['start_frame'],meta['fps']);end=frame_us(scene['end_frame'],meta['fps'])
            segment=api.VideoSegment(material,api.Timerange(start,end-start),speed=1,volume=0)
            script.append_track(api.TrackSpec(api.TrackType.video,scene['id']+'_web'));script.add_segment(segment,scene['id']+'_web')
        else:
            paper=Image.new('RGB',(meta['width'],meta['height']),scene.get('paper',meta.get('visual',{}).get('paper','#fcf7ea')))
            path=pack.png(paper);start=frame_us(scene['start_frame'],meta['fps']);end=frame_us(scene['end_frame'],meta['fps'])
            paper_track='hvp_paper' if shared_primary else scene['id']+'_paper'
            if paper_track not in script.tracks:script.append_track(api.TrackSpec(api.TrackType.video,paper_track))
            script.add_segment(api.VideoSegment(video_material(api,path),api.Timerange(start,end-start),volume=0),paper_track)
            primaries=primary_layers(scene);primary_segments[scene['id']]=[]
            for layer in scene['layers']:
                is_primary=scene['id'] in transition_shots and layer in primaries
                created=add_layer(api,script,pack,ep,meta,scene,layer,'hvp_primary' if is_primary else layer_track(scene,layer))
                if is_primary:primary_segments[scene['id']]+=created
    for scene in board['shots']:
        spec=scene.get('jianying',{}).get('transition_out')
        if spec:
            segment=primary_segments[scene['id']][-1]
            segment.add_transition(resolve('transition',spec),duration=frame_us(spec['frames'],meta['fps']))
            # Added after adjacent clips are registered, so register this reference explicitly.
            script.materials.transitions.append(segment.transition)
        add_scene_tracks(api,script,scene,meta['fps'])
    add_audio(api,script,pack,ep,meta,board)
    mode=meta.get('subtitle_mode','burn-in')
    if mode=='burn-in':
        for i,cue in enumerate(timing['segments']):
            a=round(cue['start']*meta['fps']);b=round(cue['end']*meta['fps'])
            # A separate native panel and editable text, never baked into web clips.
            sc={'id':'subtitle_'+str(i),'start_frame':a,'end_frame':b}
            panel={'id':'panel','kind':'image','fit':'stretch','region':[.05,.84,.9,.13]}
            material=video_material(api,pack.png(Image.new('RGB',(round(meta['width']*.9),round(meta['height']*.13)),'#fcf7ea')))
            p=geometry(sc,panel,0,meta['width'],meta['height'],material.width,material.height)
            settings=api.ClipSettings(transform_x=p['position_x'],transform_y=p['position_y'],scale_x=p['scale_x'],scale_y=p['scale_y'])
            name='hvp_subtitle_panels'
            if name not in script.tracks:script.append_track(api.TrackSpec(api.TrackType.video,name))
            script.add_segment(api.VideoSegment(material,api.Timerange(frame_us(a,meta['fps']),frame_us(b,meta['fps'])-frame_us(a,meta['fps'])),volume=0,clip_settings=settings),name)
            add_layer(api,script,pack,ep,meta,sc,{'id':'caption','kind':'text','text':cue['text'],'region':[.08,.86,.84,.09],'font_size':min(meta['width'],meta['height'])*.032},track_name='hvp_subtitles')
    if mode!='none' and timing['segments']:
        from tts_engine import generate_srt
        (folder/'subtitles.srt').write_text(generate_srt(timing['segments']),encoding='utf-8')
    script.duration=frame_us(board['duration_frames'],meta['fps']);content=json.loads(script.dumps());content['id']=str(uuid.uuid4()).upper()
    comp.save(folder/'draft/draft_content.json',content)
    # Editor Skill's newer file discovery pattern; both plain-text views stay identical.
    comp.save(folder/'draft/draft_info.json',content)
    info=comp.read(VENDOR/'pyJianYingDraft/assets/draft_meta_info.json')
    info.update({'draft_id':content['id'],'draft_name':meta['title']+' '+export_id,'draft_fold_path':str((folder/'draft').resolve()),'draft_root_path':str(folder.resolve()),'tm_duration':content['duration'],
                 'tm_draft_create':round(time.time()*1e6),'tm_draft_modified':round(time.time()*1e6)})
    comp.save(folder/'draft/draft_meta_info.json',info)
    files=[{'path':p.relative_to(folder/'draft').as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted((folder/'draft').rglob('*')) if p.is_file()]
    native_seconds=time.perf_counter()-began-sum(x['seconds'] for x in measurements)
    manifest={'format':'hvp-jianying-package-v1','title':meta['title'],'export_id':export_id,'materials':pack.materials,'files':files,
        'source_workflow':'composition-v2','duration_frames':board['duration_frames'],'fps':meta['fps'],'plan':report,
        'measurements':{'package_seconds':native_seconds,'pre_render':measurements},
        'validation':{'draft_structure':'pending','app_open':'pending','actual_export':'pending','aesthetic':'pending_user_review'},
        'limitations':['原生字体尺寸与系统字体需剪映实际审看校准','剪映音轨无统一总线限幅；导出后检查音峰','字幕面板为不透明底，网页面板为94%底','不反向同步剪映人工修改']}
    comp.save(folder/'manifest.json',manifest)
    shutil.copy2(Path(__file__).parent/'jianying_install.py',folder/'install.py')
    shutil.copy2(Path(__file__).parent/'jianying_package.py',folder/'jianying_package.py')
    shutil.copy2(Path(__file__).parent/'user_settings.py',folder/'user_settings.py')
    shutil.copy2(VENDOR/'LICENSE',folder/'LICENSE-pyJianYingDraft');shutil.copy2(VENDOR/'NOTICE',folder/'NOTICE-pyJianYingDraft')
    shutil.copy2(VENDOR/'provenance.json',folder/'source-provenance.json')
    methods=Path(__file__).parent/'vendor/jianying_editor_methods'
    shutil.copy2(methods/'LICENSE',folder/'LICENSE-jianying-editor-skill')
    shutil.copy2(methods/'provenance.json',folder/'editor-methods-provenance.json')
    comp.save(folder/'editing-map.json',{'shots':board['shots'],'routes':report['shots'],
        'subtitle_mode':mode,'audio_tracks':board.get('audio_tracks',[]),
        'primary_track':'hvp_primary' if shared_primary else 'per-shot',
        'tracks':[{'name':t['name'],'type':t['type'],'segments':len(t['segments']),
                   'time_ranges':[s['target_timerange'] for s in t['segments']]} for t in content['tracks']],
        'native_resources':[{'shot':r['id'],'resources':r.get('native_resources',[])} for r in report['shots']],
        'notes':'背景、文字和各sprite分别成轨；同一sprite的循环/非循环帧在其角色轨道顺序排列，不每帧新建轨道。全图序列也在同一轨道排列。仅原生转场相邻主画面共享hvp_primary轨道，其余主画面/背景按镜头独立；文字不并入图像轨道。浏览器例外画面合并。播放素材全部在draft/assets。'})
    (folder/'使用说明.md').write_text('# 剪映草稿交付包\n\n先在剪映设置中查看草稿目录，解压交付包，然后运行：\n\n```powershell\npython install.py . --draft-dir "你的剪映草稿目录"\n```\n\n也可以用hvp jianying-install。只新建唯一目录，不覆盖既有草稿。重新进入草稿列表查看；必要时重启剪映。剪映10.9需实际验证，不自动导出。\n\n文字和声音轨道可编辑；预渲染镜头只有视频画面。字幕.srt不要重复导入已带原生字幕的草稿。原生字体、透明PNG与混音需要实际打开审看，JSON通过不等于成片验证通过。\n',encoding='utf-8')
    with (folder/'使用说明.md').open('a',encoding='utf-8') as guide:
        guide.write('\n## 保存本机草稿箱位置\n\n首次运行`python user_settings.py --draft-dir "你的草稿箱目录"`；之后运行`python install.py .`即可使用保存的位置。配置在Windows用户AppData/Roaming/handraw-video-producer/config.json，独立于仓库与本交付包；仓库更新、Skill同步和解压新包均不覆盖。`python user_settings.py`可查看位置。安装时显式传`--draft-dir`只用于本次，不覆盖保存值；目录不存在会报错，不自动换位置。交付包不附带制作者本机配置。\n')
        guide.write('\n## 独立交付与检查\n\n本包不用安装上述两个源项目，不需访问制作者的参考项目目录。安装和检查只需Python标准库；最终导出需要桌面剪映。\n\n```powershell\npython jianying_package.py .\n```\n\n包内含新版draft_info.json与draft_content.json一致副本、实际素材、可编辑文字和声音轨道、editing-map.json及许可。移动/解压后先检查，再安装到你明确指定的草稿目录；不要直接打开包内含旧绝对路径的草稿。install.py在新目录重绑定后检查，通过才发布，不覆盖或修复用户旧工程。\n\n本期配置的原生转场、特效和滤镜已写入草稿；名称、ID、作用范围及时间见editing-map.json。转场作用于主画面轨道，ST-003仅背景，不包含角色和文字。资源可用性、VIP及最终显示由剪映本机决定；未配置的效果不会自动添加。本包不下载云端资源、不替换指定配音。字体未打包，请在剪映检查本机字体、布局、透明PNG、音量及导出时长。\n')
    manifest['delivery_files']=[{'path':p.relative_to(folder).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(folder.iterdir()) if p.is_file() and p.name!='manifest.json']
    comp.save(folder/'manifest.json',manifest)
    from jianying_package import check_package
    checked=check_package(folder)
    if not checked['valid']:raise ValueError('草稿交付检查失败：'+'；'.join(checked['errors']))
    manifest['validation']['draft_structure']='passed'
    comp.save(folder/'manifest.json',manifest);comp.save(folder/'package-check.json',checked)
    # Include the report in integrity checks as well.
    manifest['delivery_files'].append({'path':'package-check.json','sha256':hashlib.sha256((folder/'package-check.json').read_bytes()).hexdigest()})
    comp.save(folder/'manifest.json',manifest)
    shutil.make_archive(str(folder),'zip',root_dir=folder)
    return folder
