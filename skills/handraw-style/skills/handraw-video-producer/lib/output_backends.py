"""Output routing is independent of shot type. No paid generation here."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import time

import composition as comp
from motion import sample

TARGETS=('web','jianying')
NATIVE=('image','video','sprite','text','highlight','path')
JIANYING_NATIVE_TYPES=('ST-001','ST-002','ST-003','ST-004')


def approved_prerender_shots(ep,meta):
    approval=meta.get('jianying_prerender_approval',{})
    if not isinstance(approval,dict) or approval.get('source')!='human_user' or not str(approval.get('user_reply','')).strip():return set()
    from production_stage import document,plan_signature,approval_errors
    owner,doc=document(ep)
    try:
        if doc is None or approval_errors(owner,doc) or approval.get('plan_signature')!=plan_signature(owner,doc):return set()
    except (ValueError,OSError,KeyError):return set()
    ids=approval.get('shot_ids')
    return set(ids) if isinstance(ids,list) and all(isinstance(x,str) for x in ids) else set()


def record_prerender_approval(ep,user_reply,shot_ids):
    """Record actual human authorization of named shots, never infer it from auto/web."""
    from production_stage import document,plan_signature,approval_errors
    ep=Path(ep).resolve();owner,doc=document(ep)
    if doc is None or approval_errors(owner,doc):raise ValueError('先确认包含预渲染说明的完整方案，再记录用户对具体镜头的真实同意')
    board=comp.read(ep/'composition.json');known={s['id'] for s in board['shots']}
    if not isinstance(user_reply,str) or not user_reply.strip() or not isinstance(shot_ids,list) or not shot_ids or any(not isinstance(x,str) or x not in known for x in shot_ids):raise ValueError('需要真实用户回复及有效预渲染镜头编号')
    meta=comp.read(ep/'episode.json')
    meta['jianying_prerender_approval']={'source':'human_user','user_reply':user_reply,'shot_ids':sorted(set(shot_ids)),'plan_signature':plan_signature(owner,doc)}
    comp.save(ep/'episode.json',meta)


def frame_us(frame, fps):
    # Convert boundaries independently, not rounded per-frame durations.
    return round(frame*1_000_000/fps)


def native_reasons(scene, registry, meta):
    reasons=[]
    if scene.get('transition',{}).get('frames',0):
        reasons.append('入场转场需网页合成，保留上一镜最后一帧及原转场语义')
    for layer in scene['layers']:
        lid=layer['id'];adapter=layer['kind']
        if layer.get('motion'):reasons.append(lid+': 有规律运动需预渲染，原生尚未验证')
        if layer.get('rotation') or layer.get('rotation_keyframes'):reasons.append(lid+': 旋转需预渲染，原生尚未适配')
        if adapter not in NATIVE:
            reasons.append(lid+': '+adapter+'尚无原生适配，需要按镜预渲染')
            continue
        if adapter=='path' and layer.get('reveal_frames'):
            reasons.append(lid+': 连续笔画揭示需网页渲染')
        if adapter=='text' and scene.get('camera',{}).get('keyframes'):
            reasons.append(lid+': 带文字的全场相机缩放需网页保持排版')
        if adapter in ('text','highlight','path'):
            sizes=[layer.get('region',[0,0,1,1])[2:]]+[l['region'][2:] for l in layer.get('keyframes',[])]
            if sizes and any(size!=sizes[0] for size in sizes):
                reasons.append(lid+': 区域大小变化需网页保持文字换行/恒定线宽')
        if adapter=='text' and layer.get('font_family'):
            reasons.append(lid+': 指定字体尚无原生映射；不能静默替换')
        if adapter=='video':
            if layer.get('source_rect'): reasons.append(lid+': 视频源裁切需网页实现')
            if layer.get('fit','contain')=='cover':
                from video_tasks import probe
                info=probe(comp.asset_path(meta['_ep'],layer['asset']))
                regions=[layer.get('region',[0,0,1,1])]+[k['region'] for k in layer.get('keyframes',[])]
                if any(abs(r[2]*meta['width']/(r[3]*meta['height'])-info['width']/info['height'])>.001 for r in regions):
                    reasons.append(lid+': 视频cover裁切需网页实现；不能静默换成contain')
        if adapter in ('image','sprite') and layer.get('fit','contain')=='cover':
            regions=[layer.get('region',[0,0,1,1])]+[k['region'] for k in layer.get('keyframes',[])]
            if any(abs(r[2]/r[3]-regions[0][2]/regions[0][3])>.001 for r in regions):
                reasons.append(lid+': 动态cover区域比例变化需网页裁切')
    return reasons


def plan(ep, target=None):
    """Read-only; usable before approval, does not synthesize or write reports."""
    ep=Path(ep).resolve();meta=comp.read(ep/'episode.json');target=target or meta.get('output_target','web')
    if target not in TARGETS:raise ValueError('Unknown output target: '+str(target))
    result={'target':target,'valid':False,'errors':[],'shots':[], 'browser_frames':0,'native_frames':0,'blocked_frames':0,
            'production_skill':'handraw-browser-producer' if target=='web' else 'handraw-jianying-producer',
            'native_only_default':target=='jianying',
            'app_validation':'剪映10.9打开与实际导出状态见验证记录；生成JSON不等于应用验证'}
    if not comp.unified(meta):
        result['errors'].append('剪映/统一export仅支持composition-v2；旧工程保留但不执行或转换');return result
    try: board,registry=comp.validate(ep,meta)
    except (ValueError,KeyError,TypeError,OSError) as e:
        result['errors'].append(str(e));return result
    meta['_ep']=ep;approved=approved_prerender_shots(ep,meta)
    for scene in board['shots']:
        from shot_engines import runtime_status
        available=runtime_status()
        for layer in scene['layers']:
            if layer['kind'] in available and not available[layer['kind']]:
                result['errors'].append('镜头'+scene['id']+': '+layer['kind']+'依赖缺失；hvp runtime-install --engine '+layer['kind'])
        selected=scene.get('render_backend','auto');reasons=native_reasons(scene,registry,meta) if target=='jianying' else []
        if target=='jianying' and scene['type'] not in JIANYING_NATIVE_TYPES:reasons.insert(0,scene['type']+'不在剪映默认ST-001～004范围；需经用户同意按镜预渲染')
        if target=='jianying' and selected=='web':reasons.insert(0,'该镜明确请求网页预渲染')
        implementation='web' if target=='web' else 'jianying'
        if scene.get('jianying') and target=='web':
            result['errors'].append('镜头'+scene['id']+': 配置剪映原生转场/特效；浏览器不执行这些资源，禁止静默忽略')
            implementation='blocked'
        if target=='web' and selected=='jianying':
            result['errors'].append('镜头'+scene['id']+': 网页输出不能执行明确指定的剪映实现')
            implementation='blocked'
        elif target=='jianying' and reasons:
            if selected=='jianying':
                result['errors'].append('镜头'+scene['id']+': 明确指定原生实现不支持：'+'；'.join(reasons));implementation='blocked'
            elif scene['id'] in approved:implementation='web'
            else:
                result['errors'].append('镜头'+scene['id']+': 剪映路线默认原生制作，禁止自动预渲染：'+'；'.join(reasons)+'。请调整为原生效果、改选浏览器路线，或先提交具体镜头预渲染说明取得用户同意')
                implementation='blocked'
        if target=='jianying' and scene.get('jianying') and implementation=='web':
            result['errors'].append('镜头'+scene['id']+': 原生效果和网页预渲染混合尚未适配；不能静默忽略剪映配置')
            implementation='blocked'
        native_bindings=[]
        if scene.get('jianying'):
            from jianying_native import validate_scene
            i=board['shots'].index(scene)
            native_bindings=validate_scene(scene,board['shots'][i+1] if i+1<len(board['shots']) else None)
        n=scene['end_frame']-scene['start_frame']
        result[{'web':'browser_frames','jianying':'native_frames','blocked':'blocked_frames'}[implementation]]+=n
        dependencies=[]
        if implementation=='web' and target=='jianying' and scene.get('transition',{}).get('frames',0):dependencies=[board['shots'][board['shots'].index(scene)-1]['id']]
        result['shots'].append({'id':scene['id'],'selected':selected,'implementation':implementation,
            'native_resources':native_bindings,
            'frames':n,'reason':reasons,'dependency_shots':dependencies,'prerender_approved':scene['id'] in approved,
            'editable':'图层与文字可编辑；静态图形为PNG' if implementation=='jianying' else '该镜画面合并为视频；声音和字幕独立' if implementation=='web' else '未制作；输出路线不支持或未获预渲染同意'})
    if target=='jianying':
        for i,scene in enumerate(board['shots']):
            if scene.get('jianying',{}).get('transition_out') and (result['shots'][i]['implementation']!='jianying' or result['shots'][i+1]['implementation']!='jianying'):
                result['errors'].append('镜头'+scene['id']+': 原生转场两侧必须均为原生主画面，网页例外混接未适配')
    result.update({'fps':meta['fps'],'duration_frames':board['duration_frames'],
                   'pre_render_seconds':result['browser_frames']/meta['fps'], 'valid':not result['errors']})
    from production_stage import status
    result['production']=status(ep)
    return result


def require_plan(ep,target):
    result=plan(ep,target)
    if not result['valid']: raise ValueError('\n'.join(result['errors']))
    return result


def require_web_shots(ep,shot_ids=None):
    """Jianying projects can prepare only explicitly approved web shots/dependencies."""
    meta=comp.read(Path(ep)/'episode.json')
    if meta.get('output_target','web')!='jianying':
        if any(s.get('jianying') for s in comp.read(Path(ep)/'composition.json').get('shots',[])):require_plan(ep,'web')
        return
    report=require_plan(ep,'jianying');allowed=set()
    for route in report['shots']:
        if route['implementation']=='web':allowed.update([route['id'],*route['dependency_shots']])
    if not shot_ids or not set(shot_ids).issubset(allowed):raise ValueError('剪映工程禁止全片或未授权镜头的浏览器准备；仅允许用户同意的预渲染镜头及转场依赖')


def _visual_hash(ep, meta, board, scenes):
    h=hashlib.sha256()
    def code_inputs(value):
        if isinstance(value,str):
            p=(Path(ep)/value).resolve()
            if p.is_relative_to(Path(ep).resolve()) and p.is_file():h.update(value.encode());h.update(p.read_bytes())
        elif isinstance(value,dict):
            for v in value.values():code_inputs(v)
        elif isinstance(value,list):
            for v in value:code_inputs(v)
    code_inputs(scenes);code_inputs(board.get('local_types',[]))
    # Include complete assets tree: custom HTML can import local JS/images indirectly.
    inputs={}
    for p in sorted((Path(ep)/'assets').rglob('*')):
        if p.is_file():
            inputs[p.relative_to(ep).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    # Conservative dependency manifest; omit sound from visual cache invalidation.
    for name,value in inputs.items():
        if Path(name).suffix.lower() not in ('.wav','.mp3','.aac','.m4a','.flac'):
            h.update(name.encode());h.update(value.encode())
    h.update(json.dumps({'size':[meta['width'],meta['height'],meta['fps']], 'visual':meta.get('visual',{}),
        'shots':scenes,'custom':board.get('local_types',[])},sort_keys=True,ensure_ascii=False).encode())
    for p in sorted(comp.ROOT.rglob('*')):
        if p.is_file() and p.suffix in ('.py','.js','.html','.json') and 'vendor' not in p.parts and '__pycache__' not in p.parts:
            h.update(p.relative_to(comp.ROOT).as_posix().encode());h.update(p.read_bytes())
    return h.hexdigest()[:24]


def pre_render(ep,meta,board,scene):
    from production_stage import require
    require(ep)
    report=require_plan(ep,'jianying')
    if not any(r['id']==scene['id'] and r['implementation']=='web' for r in report['shots']):raise ValueError('镜头未获准预渲染：'+scene['id'])
    from render_engine import render_html_to_video
    index=board['shots'].index(scene)
    selected=[scene]
    if scene.get('transition',{}).get('frames',0):selected.insert(0,board['shots'][index-1])
    cache=Path(ep)/'work/jianying_cache'/_visual_hash(ep,meta,board,selected)
    out=cache/(scene['id']+'.mp4');n=scene['end_frame']-scene['start_frame']
    proof=cache/'complete.json'
    if proof.exists() and out.is_file() and comp.read(proof).get('sha256')==hashlib.sha256(out.read_bytes()).hexdigest():
        return out,{'scene':scene['id'],'frames':n,'seconds':0,'cached':True}
    page,_=comp.prepare(ep,shot_ids={s['id'] for s in selected},subtitle_mode='none')
    cache.mkdir(parents=True,exist_ok=True);start=time.perf_counter()
    render_html_to_video(page,out,n/meta['fps'],meta['fps'],meta['width'],meta['height'],serve_root=ep,start_time=scene['start_frame']/meta['fps'])
    elapsed=time.perf_counter()-start
    from runtime_tools import executable
    info=json.loads(subprocess.check_output([executable('ffprobe'),'-v','error','-count_frames','-show_streams','-of','json',str(out)]))
    stream=next(s for s in info['streams'] if s['codec_type']=='video')
    if int(stream['nb_read_frames'])!=n:raise ValueError('预渲染帧数不符：'+scene['id'])
    comp.save(proof,{'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'frames':n})
    return out,{'scene':scene['id'],'frames':n,'seconds':elapsed,'cached':False}


def export(ep,target=None):
    from production_stage import require
    require(ep,initialize_legacy=False)
    ep=Path(ep).resolve();meta=comp.read(ep/'episode.json');target=target or meta.get('output_target','web')
    report=require_plan(ep,target)
    # Enforce prepared narration before expensive visuals. No implicit TTS.
    from jianying_backend import narration_path
    narration_path(ep,meta)
    if target=='web':
        if meta.get('output_target','web')!='web':raise ValueError('先明确将工程output_target切换为web并检查方案，不通过export覆盖已选剪映路线')
        comp.render(ep);return comp.mix(ep)
    from jianying_backend import export_draft
    return export_draft(ep,report)
