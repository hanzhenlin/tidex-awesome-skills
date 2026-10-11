"""Plan approval and reviewed visual inputs precede episode production.

Approval/review helpers record evidence supplied by the directing agent AFTER
the human reply or actual viewing. They do not infer either from a file existing.
All production entry points use the same confirmed-plan and reviewed-input gate.
"""
from pathlib import Path
import csv
import hashlib
import json
import math
import subprocess

VERSION = 1
POLICY = 'confirmed-plan-visual-assets-v1'
KINDS = ('image', 'video', 'recording', 'action', 'data')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def owner(ep):
    """Nested previews inherit their containing episode's gate, never a fresh gate."""
    ep = Path(ep).resolve()
    candidates = [p for p in (ep, *ep.parents) if (p/'production.json').exists()]
    # Prefer the outer episode if a nested preview also carries its own record.
    if candidates:
        return candidates[-1]
    episodes=[p for p in (ep,*ep.parents) if (p/'episode.json').exists()]
    if episodes:return episodes[-1]
    return ep


def initialize(ep):
    ep = Path(ep).resolve()
    inherited = owner(ep)
    if (inherited/'production.json').exists():
        return inherited
    meta = read(ep/'episode.json')
    plan = ep/'plan.md'
    if not plan.exists():
        plan.write_text('# '+meta.get('title', ep.name)+'：待确认方案\n\n'
            '补齐后交用户确认，不将制作请求当作具体方案确认。\n\n'
            '## 受众、目标、依据、标题、脚本与预计时长\n\n'
            '## 全片视觉与运动方向\n\n'
            '## 逐镜编号、时间、画面、动作、手法与来源\n\n'
            '## 画面素材清单与准备责任\n\n'
            '## 配音、字幕、音乐与交付\n', encoding='utf-8')
    save(ep/'production.json', {'version': VERSION,
        'plan': {'path': 'plan.md', 'revision': 1, 'complete': False},
        'approval': None, 'inventory_complete': False, 'visual_assets': []})
    meta['production_policy'] = POLICY
    save(ep/'episode.json', meta)
    return ep


def document(ep):
    ep = owner(ep)
    if not (ep/'production.json').exists():
        return ep, None
    doc = read(ep/'production.json')
    if doc.get('version') != VERSION or not isinstance(doc.get('plan'), dict):
        raise ValueError('production.json需要version=1及plan对象')
    if not isinstance(doc.get('visual_assets'), list):
        raise ValueError('production.json需要visual_assets数组')
    return ep, doc


def local(ep, value, assets=False):
    if not isinstance(value, str) or not value:
        raise ValueError('需要实际本期文件路径')
    p = (ep/value).resolve()
    base = (ep/'assets').resolve() if assets else ep.resolve()
    if not p.is_relative_to(base) or not p.is_file():
        raise ValueError('缺失或不在本期目录：'+value)
    return p


def plan_signature(ep, doc):
    """Timing, selected candidate paths and rendering outputs are derived, not approval."""
    plan = doc['plan']
    if type(plan.get('revision')) is not int or plan['revision'] < 1:
        raise ValueError('方案revision必须是正整数')
    meta = read(ep/'episode.json')
    payload = {'revision': plan['revision'], 'plan_sha256': digest(local(ep, plan.get('path'))),
        'script_sha256': digest(ep/'script.txt') if (ep/'script.txt').exists() else None,
        'design': {k: meta.get(k) for k in ('title', 'brief', 'visual', 'media_policy', 'width', 'height', 'aspect_ratio', 'fps', 'subtitle_mode')},
        'voice': {k: meta.get('narration', {}).get(k) for k in ('enabled', 'provider', 'voice')}}
    if (ep/'composition.json').exists():
        board = read(ep/'composition.json')
        def intent(value):
            excluded=('asset','background','entry','dsl','scene','annotation','srt','inputs','code_files','source_in','source_out','start_frame','end_frame','at_frame','hold_frames','render_backend')
            if isinstance(value,dict):return {k:intent(v) for k,v in value.items() if k not in excluded}
            if isinstance(value,list):return [intent(v) for v in value]
            return value
        def config_intent(shot):
            cfg=dict(shot.get('config',{}))
            if shot.get('type') in ('ST-001','ST-002'):cfg.setdefault('fit','contain')
            return intent(cfg)
        payload['shots']=[{'id':shot.get('id'),'purpose':shot.get('purpose'),'type':shot.get('type'),'config':config_intent(shot),
            'intent':shot.get('intent',{}),'layers':[{'id':l.get('id'),'kind':l.get('kind')} for l in shot.get('layers',[])],
            **({'jianying':intent(shot['jianying'])} if shot.get('jianying') else {})}
            for shot in board.get('shots',[])]
        payload['local_types']=[{'id':t.get('id'),'asset_contract':t.get('asset_contract')} for t in board.get('local_types',[])]
    if (ep/'video_tasks.json').exists():
        payload['video_intent'] = [{k: t.get(k) for k in ('id', 'shot_id', 'layer_id', 'purpose', 'first_state', 'last_state')}
            for t in read(ep/'video_tasks.json').get('tasks', [])]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def approval_errors(ep, doc):
    if not doc['plan'].get('complete'):
        return ['方案尚未完整提交用户']
    approval = doc.get('approval')
    if not isinstance(approval, dict) or approval.get('source') != 'human_user' or not str(approval.get('user_reply', '')).strip():
        return ['缺少用户对本期具体方案的确认记录']
    try:
        if approval.get('plan_signature') != plan_signature(ep, doc):
            return ['方案、脚本或设计已变化，旧确认失效，请重新提交用户确认']
    except (ValueError, OSError) as e:
        return [str(e)]
    return []


def record_approval(ep, user_reply):
    """Record a real human reply; no CLI --yes or automatic inferred approval."""
    ep, doc = document(ep)
    if doc is None:
        raise ValueError('先initialize本期流程')
    if not doc['plan'].get('complete') or not str(user_reply).strip():
        raise ValueError('先提交完整方案，再记录实际用户确认')
    doc['approval'] = {'source': 'human_user', 'user_reply': user_reply,
        'revision': doc['plan']['revision'], 'plan_signature': plan_signature(ep, doc)}
    save(ep/'production.json', doc)


def visual_paths(ep):
    """Check actual visual bindings too, so omitted/optional inventory cannot hide inputs."""
    paths = set()
    def walk(value):
        if isinstance(value, str) and value.startswith('assets/'):
            paths.add(value)
        elif isinstance(value, dict):
            for v in value.values(): walk(v)
        elif isinstance(value, list):
            for v in value: walk(v)
    if (ep/'composition.json').exists():
        def inputs(value):
            if isinstance(value,dict):return {k:inputs(v) for k,v in value.items() if k not in ('entry','dsl','scene','annotation','srt','code_files')}
            if isinstance(value,list):return [inputs(v) for v in value]
            return value
        for shot in read(ep/'composition.json').get('shots',[]):walk(inputs(shot))
        for shot in read(ep/'composition.json').get('shots',[]):
            for key in ('scene','annotation','srt'):
                value=shot.get('config',{}).get(key)
                if value and value.startswith('assets/'):walk(value)
    if (ep/'video_tasks.json').exists():
        for t in read(ep/'video_tasks.json').get('tasks', []):
            walk(t.get('reference_assets', []))
    if (ep/'episode.json').exists():walk(read(ep/'episode.json').get('subtitle_source'))
    return paths


def technical(path, kind, full_decode=False):
    if kind not in KINDS:
        raise ValueError('未知画面素材类型：'+str(kind))
    if kind == 'data' or (kind == 'action' and path.suffix.lower()=='.json'):
        if path.suffix.lower() == '.json':
            value = read(path)
            if not value: raise ValueError('数据文件为空')
        elif path.suffix.lower() == '.csv':
            with path.open(encoding='utf-8-sig', newline='') as f:
                if len(list(csv.reader(f))) < 2: raise ValueError('CSV缺少数据行')
        elif path.suffix.lower()=='.srt':
            from shot_engines import srt_cues
            srt_cues(path)
        else:
            raise ValueError('数据输入需要JSON、CSV或SRT文件')
        return {'type': 'data', 'parse': 'pass'}
    if kind in ('video', 'recording') or path.suffix.lower() in ('.mp4', '.mov', '.webm', '.mkv', '.avi', '.m4v'):
        from video_tasks import probe
        info = probe(path)
        if full_decode:
            from runtime_tools import executable
            subprocess.run([executable('ffmpeg'), '-v', 'error', '-xerror', '-i', str(path),
                '-map', '0:v:0', '-f', 'null', '-'], check=True, capture_output=True)
        return {'type': 'video', **info, 'full_decode': full_decode}
    from PIL import Image
    with Image.open(path) as image:
        size = list(image.size); image.verify()
    return {'type': 'image', 'size': size, 'decode': 'pass'}


def review_asset(ep, asset_id, visual_review):
    """Technical checks plus supplied actual visual review, never auto visual pass."""
    require(ep, 'assets')
    ep, doc = document(ep)
    asset = next((a for a in doc['visual_assets'] if a.get('id') == asset_id), None)
    if asset is None: raise ValueError('未知素材编号：'+asset_id)
    if visual_review.get('status') != 'pass' or not str(visual_review.get('notes', '')).strip():
        raise ValueError('需要实际画面/数据审查通过及说明')
    path = local(ep, asset.get('path'), assets=True)
    info = technical(path, asset.get('kind'), full_decode=True)
    asset['review'] = {'status': 'pass', 'notes': visual_review['notes'], 'sha256': digest(path), 'technical': info}
    save(ep/'production.json', doc)


def asset_errors(ep, doc):
    errors = []
    if not doc.get('inventory_complete'):
        errors.append('画面素材清单尚未完整盘点；纯程序画面也需明确完成盘点')
    seen, covered = set(), set()
    used = visual_paths(ep)
    for a in doc['visual_assets']:
        aid = a.get('id')
        if not isinstance(aid, str) or not aid or aid in seen:
            errors.append('素材需要唯一id'); continue
        seen.add(aid)
        value = a.get('path')
        if value: covered.add(value)
        needed = a.get('required', True) or value in used or a.get('video_task')
        if not needed: continue
        label = '素材'+aid
        if a.get('kind') not in KINDS:
            errors.append(label+': 未知素材类型'); continue
        if a.get('video_task'):
            from video_tasks import documents, ready_errors, layer_for
            try:
                meta, board, manifest = documents(ep)
                task = next((t for t in manifest['tasks'] if t['id'] == a['video_task']), None)
                if task is None: raise ValueError('未知外部视频任务')
                _, layer = layer_for(board, task)
                # The logical task is already inventoried even before its file returns.
                if layer.get('asset'): covered.add(layer['asset'])
                issues = ready_errors(ep, meta, board, task)
                if task.get('regeneration_reason'): issues.append(task['regeneration_reason'])
                if issues: raise ValueError('; '.join(issues))
                covered.add(layer['asset'])
                candidate = next(c for c in task['candidates'] if c['id'] == task['selected']['candidate_id'])
                if not candidate.get('full_decode'): raise ValueError('候选缺少完整解码记录')
                continue
            except (ValueError, KeyError, OSError) as e:
                errors.append(label+': '+str(e)); continue
        try:
            path = local(ep, value, assets=True)
            review = a.get('review') or {}
            if review.get('status') != 'pass' or not str(review.get('notes', '')).strip():
                raise ValueError('尚未实际审查通过')
            if review.get('sha256') != digest(path):
                raise ValueError('文件已变化，需重新审查')
            receipt = review.get('technical', {})
            if not receipt: raise ValueError('缺少技术检查记录')
            info = technical(path, a['kind'])
            if info['type'] == 'video':
                if not receipt.get('full_decode'): raise ValueError('缺少完整视频解码检查')
                minimum = a.get('min_duration', 0)
                if not isinstance(minimum, (int, float)) or not math.isfinite(minimum) or minimum < 0:
                    raise ValueError('min_duration无效')
                if info['duration']+.001 < minimum: raise ValueError('视频过短，需补素材或重新确认编排')
        except (ValueError, OSError, subprocess.CalledProcessError) as e:
            errors.append(label+': '+str(e))
    for p in sorted(used-covered):
        errors.append('实际镜头/参考使用的素材未列入清单：'+p)
    if (ep/'video_tasks.json').exists():
        listed = {a.get('video_task') for a in doc['visual_assets']}
        for t in read(ep/'video_tasks.json').get('tasks', []):
            if t['id'] not in listed:
                errors.append('外部视频任务未列入素材清单：'+t['id'])
    if (ep/'composition.json').exists():
        board = read(ep/'composition.json'); meta = read(ep/'episode.json')
        tasks = read(ep/'video_tasks.json').get('tasks', []) if (ep/'video_tasks.json').exists() else []
        external={t['shot_id'] for t in tasks if t['id'] in {a.get('video_task') for a in doc['visual_assets']}}
        for shot in board.get('shots',[]):
            if shot.get('type')!='ST-002' or shot.get('id') in external:continue
            layer=shot.get('config',{})
            try:
                info=technical(local(ep,layer.get('asset'),assets=True),'video')
                span=(shot['end_frame']-shot['start_frame'])/meta['fps']
                if layer.get('source_in',0)+span>info['duration']+.001:raise ValueError('视频不足以覆盖镜头')
            except (ValueError,OSError,KeyError,subprocess.CalledProcessError) as e:errors.append('镜头'+str(shot.get('id'))+': '+str(e))
    return errors


def status(ep):
    ep, doc = document(ep)
    if (ep/'episode.json').exists() and read(ep/'episode.json').get('workflow')!='composition-v2':
        return {'stage':'unsupported_project','episode':str(ep),'issues':['旧工程仅保留，不执行或自动转换'],'next_step':'新建composition-v2方案'}
    if doc is None:
        return {'stage':'missing_production_record','episode':str(ep),'next_step':'需要composition-v2工程及完整阶段记录','issues':['缺少production.json']}
    approval = approval_errors(ep, doc)
    assets = asset_errors(ep, doc)
    stage = 'awaiting_plan_confirmation' if approval else ('collecting_visual_assets' if assets else 'ready_for_production')
    return {'stage': stage, 'episode': str(ep), 'plan_revision': doc['plan'].get('revision'),
        'approved': not approval, 'visual_assets_ready': not assets, 'issues': approval+assets,
        'next_step': {'awaiting_plan_confirmation': '提交完整方案并等待用户确认',
            'collecting_visual_assets': '仅准备画面素材、交付提示词、检查回传；不得配音或制作预演',
            'ready_for_production': '可进行配音、动画实现、渲染与合成；最终审美验收另记'}[stage]}


def require(ep, operation='production', initialize_legacy=False):
    ep = Path(ep).resolve()
    if initialize_legacy: raise ValueError('不支持旧工程自动初始化或转换')
    ep, doc = document(ep)
    if not (ep/'episode.json').is_file() or read(ep/'episode.json').get('workflow')!='composition-v2':raise ValueError('仅执行composition-v2；旧工程保留，不执行或自动转换')
    if doc is None:raise ValueError('缺少production.json，不能绕过制作阶段')
    errors = approval_errors(ep, doc)
    if operation != 'assets': errors += asset_errors(ep, doc)
    if errors:
        raise ValueError('制作阶段未就绪：'+'; '.join(errors))
