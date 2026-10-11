"""Local external-video handoff. No generation API, implicit selection or paid calls."""
import copy
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path
import re
import shutil
import subprocess

from runtime_tools import executable

POLICIES = ('auto', 'no_video', 'video_only')
REVIEW_KEYS = ('content', 'identity', 'action', 'continuity')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def local_asset(ep, value):
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError('需要assets内的相对路径：' + str(value))
    ep = Path(ep).resolve()
    path = (ep / value).resolve()
    if not path.is_relative_to(ep / 'assets') or not path.is_file():
        raise ValueError('素材缺失或不在本期assets：' + value)
    return path


def probe(path):
    p = subprocess.run([executable('ffprobe'), '-v', 'error', '-show_streams',
                        '-show_format', '-of', 'json', str(path)],
                       check=True, capture_output=True, text=True, encoding='utf-8')
    info = json.loads(p.stdout)
    stream = next((s for s in info.get('streams', []) if s.get('codec_type') == 'video'), None)
    if not stream:
        raise ValueError('文件没有视频流')
    # Container duration can be extended by audio; only the chosen video counts.
    raw_duration = stream.get('duration')
    if raw_duration not in (None, 'N/A'):
        duration = float(raw_duration)
    else:
        packets = subprocess.run([executable('ffprobe'), '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'packet=pts_time,duration_time', '-of', 'json', str(path)],
            check=True, capture_output=True, text=True, encoding='utf-8')
        intervals = []
        rate = Fraction(stream.get('avg_frame_rate') or '0/1')
        for packet in json.loads(packets.stdout).get('packets', []):
            if packet.get('pts_time') in (None, 'N/A'):
                continue
            start = float(packet['pts_time'])
            raw_length = packet.get('duration_time')
            length = float(raw_length) if raw_length not in (None, 'N/A') else (float(1/rate) if rate > 0 else 0)
            if math.isfinite(start) and math.isfinite(length) and length > 0:
                intervals.append((start, start+length))
        if not intervals:
            raise ValueError('无法核实视频流时长')
        duration = max(b for a,b in intervals)-min(a for a,b in intervals)
    if not math.isfinite(duration) or duration <= 0 or not stream.get('width') or not stream.get('height'):
        raise ValueError('视频时长或尺寸无效')
    return {'duration': duration, 'width': stream['width'], 'height': stream['height'],
            'fps': stream.get('avg_frame_rate'), 'codec': stream.get('codec_name'),
            'has_audio': any(s.get('codec_type') == 'audio' for s in info['streams'])}


def documents(ep):
    ep = Path(ep)
    meta, board = read(ep/'episode.json'), read(ep/'composition.json')
    if meta.get('workflow') != 'composition-v2':
        raise ValueError('视频续作命令用于composition-v2工程；旧工程不转换')
    policy = meta.get('media_policy', 'auto')
    if policy not in POLICIES:
        raise ValueError('未知media_policy：' + str(policy))
    manifest = read(ep/'video_tasks.json') if (ep/'video_tasks.json').exists() else {'version': 2, 'tasks': []}
    if manifest.get('version') != 2 or not isinstance(manifest.get('tasks'), list):
        raise ValueError('video_tasks.json需要version=2和tasks数组')
    if policy == 'no_video' and manifest['tasks']:
        raise ValueError('no_video不能安排外部视频任务')
    seen = set()
    bindings = set()
    for task in manifest['tasks']:
        tid = task.get('id')
        if not isinstance(tid, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', tid) or tid in seen:
            raise ValueError('片段编号必须唯一且只含字母、数字、下划线或短横线')
        if re.fullmatch(r'CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]', tid, re.I):
            raise ValueError('片段编号不能使用Windows保留文件名')
        seen.add(tid)
        try:scene,layer=layer_for(board,task)
        except (ValueError,KeyError,StopIteration):raise ValueError(f'片段{tid}缺少ST-002镜头绑定')
        binding=task.get('shot_id')
        if binding in bindings:raise ValueError('同镜头不能重复绑定视频任务')
        bindings.add(binding)
        if type(task.get('prompt_revision')) is not int or task['prompt_revision'] < 1:
            raise ValueError(f'片段{tid}需要正整数prompt_revision')
        for key in ('purpose', 'instructions_zh', 'first_state', 'last_state'):
            if not isinstance(task.get(key), str) or not task[key].strip():
                raise ValueError(f'片段{tid}缺少{key}')
        duration = task.get('target_duration')
        if type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0:
            raise ValueError(f'片段{tid}目标时长无效')
        prompts = task.get('prompts', {})
        if not isinstance(prompts, dict) or not prompts or any(not isinstance(v, str) or not v.strip() for v in prompts.values()):
            raise ValueError(f'片段{tid}缺少可复制的生成提示词')
        if not isinstance(task.get('reference_assets', []), list):
            raise ValueError(f'片段{tid}reference_assets必须为数组')
        if type(task.get('audio', {}).get('keep_original', False)) is not bool:
            raise ValueError(f'片段{tid}keep_original必须为布尔值')
        candidates = task.get('candidates', [])
        if not isinstance(candidates, list) or any(not c.get('id') or not c.get('sha256') or not c.get('path') for c in candidates):
            raise ValueError(f'片段{tid}候选记录无效')
        if len({c['id'] for c in candidates}) != len(candidates):
            raise ValueError(f'片段{tid}候选编号重复')
    return meta, board, manifest


def task_signature(task, ep=None):
    # Detect prompt edits even when the author forgot to bump the revision number.
    data = {k: v for k, v in task.items() if k not in ('candidates', 'selected', 'exports', 'regeneration_reason')}
    if ep is not None:
        data = copy.deepcopy(data)
        data['reference_hashes'] = []
        for ref in task.get('reference_assets', []):
            try:
                data['reference_hashes'].append(digest(local_asset(ep, ref)))
            except ValueError:
                data['reference_hashes'].append('missing:'+str(ref))
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def layer_for(board,task):
    shot=next(s for s in board['shots'] if s['id']==task['shot_id'])
    if shot['type']!='ST-002':raise ValueError('外部视频任务只绑定ST-002主画面')
    return shot,shot['config']


def binding_signature(meta, board, task):
    scene, layer = layer_for(board, task)
    data = {'frame': [meta['width'], meta['height'], meta['fps']], 'layer': layer,
            'range': [scene['start_frame'], scene['end_frame']],
            'events': scene.get('events', []), 'camera': scene.get('camera', {})}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def ready_errors(ep, meta, board, task):
    errors = []
    for ref in task.get('reference_assets', []):
        try:
            local_asset(ep, ref)
        except ValueError as exc:
            errors.append(str(exc))
    selected = task.get('selected')
    if not selected:
        return errors + ['尚未选用并审看候选']
    candidate = next((c for c in task.get('candidates', []) if c['id'] == selected.get('candidate_id')), None)
    if not candidate:
        return ['选用的候选不存在']
    signature = task_signature(task, ep)
    if selected.get('task_signature') != signature or selected.get('prompt_revision') != task['prompt_revision']:
        errors.append('提示词或任务已改版，需要重新审看')
    if selected.get('binding_signature') != binding_signature(meta, board, task):
        errors.append('截取、镜头时间或构图已变化，需要重新审看')
    review = selected.get('review', {})
    if any(review.get(k) != 'pass' for k in REVIEW_KEYS) or not str(review.get('notes', '')).strip():
        errors.append('需要内容、身份、动作、衔接的实际审看结果和说明')
    try:
        path = local_asset(ep, candidate['path'])
        if digest(path) != candidate['sha256']:
            errors.append('选用文件哈希已变化，需要重新导入')
        info = probe(path)
        scene, layer = layer_for(board, task)
        start = layer.get('start_frame', 0)
        end = layer.get('end_frame', scene['end_frame']-scene['start_frame'])
        offset = selected.get('source_in', 0)
        if type(offset) not in (int, float) or not math.isfinite(offset) or offset < 0:
            errors.append('截取起点无效')
        elif offset + (end-start)/meta['fps'] > info['duration'] + .001:
            errors.append('候选不足以覆盖镜头，请重新编排或补生成')
        if layer.get('asset') != candidate['path'] or layer.get('source_in', 0) != offset:
            errors.append('选用记录与composition图层未同步绑定')
        mismatch = abs(info['width']/info['height']-meta['width']/meta['height']) > .01
        if mismatch and not review.get('framing'):
            errors.append('画幅不符，需要构图审看说明；默认contain')
        if layer.get('fit', 'contain') != 'contain' and not review.get('framing'):
            errors.append('裁切或拉伸需要明确构图说明')
        if task.get('audio', {}).get('keep_original', False):
            if not info['has_audio']:
                errors.append('要求保留原声，但候选没有音频流')
            elif not any(t.get('path') == candidate['path'] for t in board.get('audio_tracks', [])):
                errors.append('要求保留原声，请显式加入audio_tracks')
    except (ValueError, subprocess.CalledProcessError, OSError, KeyError) as exc:
        errors.append(str(exc))
    return errors


def status(ep):
    meta, board, manifest = documents(ep)
    rows = []
    for task in manifest['tasks']:
        signature = task_signature(task, ep)
        errors = ready_errors(ep, meta, board, task) if task.get('selected') else []
        if task.get('regeneration_reason'):
            state, next_step = 'needs_regeneration', task['regeneration_reason']
        elif task.get('selected') and not errors:
            state, next_step = 'ready', '可进入合成；整片审美验收另记'
        elif task.get('candidates'):
            state, next_step = 'imported', '审看候选、选择截取范围并绑定图层'
        elif signature in task.get('exports', []):
            state, next_step = 'prompt_delivered', '等待用户在外部平台生成并回传'
        else:
            state, next_step = 'planned', '完善并交付提示词包'
        missing_refs = []
        for ref in task.get('reference_assets', []):
            try:
                local_asset(ep, ref)
            except ValueError:
                missing_refs.append(ref)
        rows.append({'clip': task['id'], 'shot': task['shot_id'], 'layer': 'main',
                     'state': state, 'candidates': len(task.get('candidates', [])),
                     'issues': errors, 'missing_references': missing_refs, 'next_step': next_step})
    states = {r['state'] for r in rows}
    stage = ('planning' if not board.get('shots') else 'no_external_tasks') if not rows else (
        'ready_for_composition' if states == {'ready'} else
        'awaiting_clips' if 'prompt_delivered' in states else
        'reviewing_clips' if 'imported' in states else 'planning_clips')
    return {'media_policy': meta.get('media_policy', 'auto'), 'stage': stage, 'tasks': rows,
            'note': '阶段由任务推导；其他素材、声音和整片验收仍需检查'}


def preflight(ep, meta, board, registry):
    policy = meta.get('media_policy', 'auto')
    if policy not in POLICIES:
        raise ValueError('未知media_policy：' + str(policy))
    for scene in board['shots']:
        layers = scene.get('layers', [])
        videos = [l for l in layers if registry.get(l.get('kind'), {}).get('adapter') == 'video']
        if policy == 'no_video' and videos:
            raise ValueError(f"镜头{scene['id']}: no_video禁止视频画面层")
        if policy=='no_video':
            from production_stage import visual_paths
            if any(Path(v).suffix.lower() in ('.mp4','.mov','.webm','.mkv','.avi') for v in visual_paths(Path(ep))):
                raise ValueError(f"镜头{scene['id']}: no_video禁止动画实现输入外部视频")
        if policy == 'video_only':
            first = layers[0] if layers else {}
            span = scene['end_frame']-scene['start_frame']
            if (registry.get(first.get('kind'), {}).get('adapter') != 'video'
                    or first.get('start_frame', 0) != 0 or first.get('end_frame', span) != span
                    or first.get('region', [0,0,1,1]) != [0,0,1,1]
                    or first.get('opacity', 1) != 1 or first.get('show_after') or first.get('hide_after')):
                raise ValueError(f"镜头{scene['id']}: video_only需要覆盖全镜头的视频主画面")
    if (Path(ep)/'video_tasks.json').exists():
        meta, board, manifest = documents(ep)
        for task in manifest['tasks']:
            errors = ready_errors(ep, meta, board, task)
            if task.get('regeneration_reason'):
                errors.insert(0, task['regeneration_reason'])
            if errors:
                raise ValueError(f"镜头{task['shot_id']} / 片段{task['id']}: " + '; '.join(errors))


def export_pack(ep):
    from production_stage import require
    require(ep, 'assets')
    ep = Path(ep)
    meta, board, manifest = documents(ep)
    if not manifest['tasks']:
        raise ValueError('没有外部生成任务；无需交付提示词包')
    # Verify all references before creating a package or changing delivery state.
    refs = {t['id']: [local_asset(ep, r) for r in t.get('reference_assets', [])] for t in manifest['tasks']}
    package_sig = hashlib.sha256(''.join(task_signature(t, ep) for t in manifest['tasks']).encode()).hexdigest()[:16]
    out = ep/'outputs/video-pack'/package_sig
    out.mkdir(parents=True, exist_ok=True)
    instructions = [f"# {meta['title']}：外部视频任务包", '',
                    '在Flow或其他支持的平台逐段生成，按编号回传本地视频。平台参数按实际能力设置。',
                    '默认不要生成旁白、字幕或可见文字；声音与标注后期统一制作。',
                    '不保证平台输出符合时长或动作要求；回传后检查并剪辑。', '']
    packaged = []
    for task in manifest['tasks']:
        tid = task['id']
        text = [f"# {tid} · {task['purpose']}", '',
                f"镜头/图层：{task['shot_id']} / {task.get('layer_id','main')}",
                f"目标尺寸：{meta['width']}×{meta['height']}；目标时长：{task['target_duration']}秒（不是平台保证）",
                f"提示词版本：{task['prompt_revision']}", f"预期回传名：{tid}.mp4", '',
                '## 制作说明', task['instructions_zh'], '',
                '## 首尾交接', '首帧：'+task['first_state'], '末帧：'+task['last_state'], '',
                '## 上传参考文件']
        ref_records = []
        for index, path in enumerate(refs[tid], 1):
            name = f'{tid}_{index:02d}{path.suffix.lower()}'
            destination = out/'references'/name
            destination.parent.mkdir(exist_ok=True)
            shutil.copy2(path, destination)
            ref_records.append({'file': 'references/'+name, 'sha256': digest(path)})
            text.append('- references/'+name)
        if not ref_records:
            text.append('无；如角色一致性需要身份图，应先补齐参考。')
        for language, prompt in task['prompts'].items():
            text.extend(['', '## 可复制提示词 · '+language, '', prompt])
        text.extend(['', '## 声音', '保留平台原声：'+str(task.get('audio', {}).get('keep_original', False)),
                     '原声不会自动混入，回传后需显式配置音轨。'])
        (out/(tid+'.md')).write_text('\n'.join(text)+'\n', encoding='utf-8')
        signature = task_signature(task, ep)
        if signature not in task.setdefault('exports', []):
            task['exports'].append(signature)
        record = copy.deepcopy(task)
        record.pop('candidates', None)
        record.pop('selected', None)
        record['packaged_references'] = ref_records
        packaged.append(record)
        instructions.append(f'- {tid}：{tid}.md → 回传 {tid}.mp4')
    (out/'README.md').write_text('\n'.join(instructions)+'\n', encoding='utf-8')
    save(out/'tasks.json', {'version': 2, 'tasks': packaged})
    save(ep/'video_tasks.json', manifest)
    save(ep/'work/video_status.json', status(ep))
    return out


def import_clip(ep, clip, file):
    from production_stage import require
    require(ep, 'assets')
    ep = Path(ep)
    meta, board, manifest = documents(ep)
    task = next((t for t in manifest['tasks'] if t['id'] == clip), None)
    if not task:
        raise ValueError('未知片段编号：'+clip)
    source = Path(file).resolve()
    if not source.is_file() or source.suffix.lower() not in ('.mp4', '.mov', '.webm', '.mkv', '.avi', '.m4v'):
        raise ValueError('需要本地视频文件')
    info = probe(source)
    subprocess.run([executable('ffmpeg'), '-v', 'error', '-xerror', '-i', str(source),
                    '-map', '0:v:0', '-map', '0:a?', '-f', 'null', '-'], check=True, capture_output=True)
    sha = digest(source)
    signature = task_signature(task, ep)
    candidates = task.setdefault('candidates', [])
    existing = next((c for c in candidates if c['sha256'] == sha and c.get('task_signature') == signature), None)
    if existing:
        if digest(local_asset(ep, existing['path'])) != sha:
            raise ValueError('已导入的候选文件被改动，请检查工程')
        return existing
    index = len(candidates)+1
    folder = ep/'assets/video'/clip
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder/(f'v{index:03d}'+source.suffix.lower())
    while destination.exists():
        index += 1
        destination = folder/(f'v{index:03d}'+source.suffix.lower())
    # Exclusive creation: originals and prior candidates are never overwritten.
    with source.open('rb') as src, destination.open('xb') as dst:
        shutil.copyfileobj(src, dst)
    if digest(destination) != sha:
        raise ValueError('导入过程中源文件发生变化，请重新导入')
    issues = []
    if info['duration']+.001 < task['target_duration']:
        issues.append('实际时长短于计划；审看后重新编排或补生成')
    if abs(info['width']/info['height']-meta['width']/meta['height']) > .01:
        issues.append('画幅不符；默认contain，需构图审看')
    candidate = {'id': f'v{index:03d}', 'path': destination.relative_to(ep).as_posix(),
                 'sha256': sha, 'prompt_revision': task['prompt_revision'], 'task_signature': signature,
                 'media': info, 'issues': issues, 'source_name': source.name, 'full_decode': True}
    candidates.append(candidate)
    save(ep/'video_tasks.json', manifest)
    save(ep/'work/video_status.json', status(ep))
    return candidate


def select_candidate(ep, clip, candidate_id, review, source_in=0):
    """For the directing agent after actual viewing; this function performs no visual QA."""
    from production_stage import require
    require(ep, 'assets')
    ep = Path(ep)
    meta, board, manifest = documents(ep)
    task = next((t for t in manifest['tasks'] if t['id'] == clip), None)
    if not task:
        raise ValueError('未知片段编号：'+clip)
    candidate = next((c for c in task.get('candidates', []) if c['id'] == candidate_id), None)
    if not candidate:
        raise ValueError('未知候选编号：'+candidate_id)
    scene, layer = layer_for(board, task)
    layer.update({'asset': candidate['path'], 'source_in': source_in,
                  'source_out':source_in+(scene['end_frame']-scene['start_frame'])/meta['fps']})
    layer.setdefault('fit', 'contain')
    task['selected'] = {'candidate_id': candidate_id, 'source_in': source_in,
                        'prompt_revision': task['prompt_revision'], 'task_signature': task_signature(task, ep),
                        'binding_signature': binding_signature(meta, board, task),
                        'review': review}
    task.pop('regeneration_reason', None)
    errors = ready_errors(ep, meta, board, task)
    if errors:
        raise ValueError('; '.join(errors))
    save(ep/'composition.json', board)
    save(ep/'video_tasks.json', manifest)
    save(ep/'work/video_status.json', status(ep))
    return status(ep)
