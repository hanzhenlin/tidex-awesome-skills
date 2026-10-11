"""Offline draft inspection and portable package validation (standard library only).

Adapted methods: jianying-editor-skill draft_inspector/formatters; see source notice.
No user project repair, network, app automation, or global vendor imports.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

CONTENT_NAMES = ('draft_info.json', 'draft_content.json')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def safe_file(root, relative):
    root = Path(root).resolve()
    raw = Path(relative)
    path = (root / raw).resolve()
    if raw.is_absolute() or not path.is_relative_to(root) or not path.is_file():
        raise ValueError('非法或缺失交付文件：' + str(relative))
    # Resolve does not retain symlink flags; inspect all lexical components first.
    lexical = root / raw
    if any(p.is_symlink() for p in (lexical, *lexical.parents) if p != root and p.is_relative_to(root)):
        raise ValueError('交付包不接受符号链接：' + str(relative))
    return path


def inspect_draft(folder, path_map=None):
    folder = Path(folder).resolve()
    errors = []
    files = [folder / n for n in CONTENT_NAMES if (folder / n).is_file()]
    if not files:
        raise ValueError('缺少draft_info.json或draft_content.json')
    content = read(files[0])
    if not isinstance(content, dict) or not isinstance(content.get('tracks'), list):
        raise ValueError('不是可检查的明文草稿结构')
    if len(files) == 2 and read(files[1]) != content:
        errors.append('双草稿文件内容不一致，禁止猜测选用版本')
    duration = content.get('duration', 0)
    if type(duration) is not int or duration <= 0:
        errors.append('草稿时长无效')
        duration = 0
    materials = content.get('materials', {})
    ids = set()
    for rows in materials.values():
        if isinstance(rows, list):
            for row in rows:
                if row.get('id'):
                    if row['id'] in ids: errors.append('素材ID重复：' + row['id'])
                    ids.add(row['id'])
    assets = []
    for rows in materials.values():
        if not isinstance(rows, list): continue
        for row in rows:
            if not row.get('path'): continue
            original = row['path']
            path = Path((path_map or {}).get(original, original))
            if path_map is not None and original not in path_map:
                errors.append('素材未纳入交付清单：' + original)
            if not path.is_file(): errors.append('缺失素材：' + original)
            assets.append({'name': row.get('material_name', row.get('name', '')), 'path': str(path), 'exists': path.is_file()})
    tracks = []
    for track in content['tracks']:
        spans = []
        segments = track.get('segments', [])
        for segment in segments:
            label = str(track.get('name', track.get('id', ''))) + '/' + str(segment.get('id', ''))
            if segment.get('material_id') not in ids:
                errors.append(label + '：素材引用不存在')
            for ref in segment.get('extra_material_refs', []):
                if ref not in ids: errors.append(label + '：附加素材引用不存在：' + ref)
            r = segment.get('target_timerange', {})
            a, n = r.get('start'), r.get('duration')
            if type(a) is not int or type(n) is not int or a < 0 or n <= 0 or a + n > duration:
                errors.append(label + '：时间边界无效')
            else: spans.append((a, a+n))
            source = segment.get('source_timerange')
            if source and (source.get('start', -1) < 0 or source.get('duration', 0) <= 0):
                errors.append(label + '：源截取无效')
        spans.sort()
        if any(b > c for (_, b), (c, _) in zip(spans, spans[1:])):
            errors.append(str(track.get('name', '')) + '：同轨片段重叠')
        tracks.append({'name': track.get('name', ''), 'type': track.get('type'), 'segments': len(segments)})
    return {'valid': not errors, 'errors': errors, 'content_file': files[0].name,
            'duration_us': duration, 'fps': content.get('fps'), 'canvas': content.get('canvas_config'),
            'tracks': tracks, 'segment_count': sum(t['segments'] for t in tracks),
            'assets': assets, 'app_open': 'not_verified', 'actual_export': 'not_verified'}


def check_package(package):
    package = Path(package).resolve()
    manifest = read(package/'manifest.json')
    if manifest.get('format') != 'hvp-jianying-package-v1': raise ValueError('未知交付包格式')
    root = package/'draft'
    if root.is_symlink() or not root.is_dir(): raise ValueError('非法或缺失draft目录')
    meta = read(safe_file(root, 'draft_meta_info.json'))
    files = manifest.get('files', [])
    names = [r['path'] for r in files]
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if len(names) != len(set(names)) or actual != set(names): raise ValueError('交付包文件清单不完整或重复')
    for r in files:
        if digest(safe_file(root, r['path'])) != r['sha256']: raise ValueError('交付包哈希不符：' + r['path'])
    mapping = {}
    for r in manifest.get('materials', []):
        path = safe_file(root, r['path'])
        if not path.is_relative_to((root/'assets').resolve()) or digest(path) != r['sha256']:
            raise ValueError('素材清单无效：' + r['path'])
        if r['original_path'] in mapping: raise ValueError('重复素材映射')
        mapping[r['original_path']] = str(path)
    result = inspect_draft(root, mapping)
    content = read(root/result['content_file'])
    if meta.get('draft_id') != content.get('id') or meta.get('tm_duration') != result['duration_us']:
        result['errors'].append('草稿元信息与内容ID/时长不一致')
    fps, frames = manifest.get('fps'), manifest.get('duration_frames')
    if not isinstance(fps, (int, float)) or not math.isfinite(fps) or fps <= 0 or type(frames) is not int or frames <= 0:
        result['errors'].append('清单帧数或帧率无效')
    elif result['duration_us'] != round(frames*1_000_000/fps) or result['fps'] != fps:
        result['errors'].append('清单与草稿时长/帧率不一致')
    for r in manifest.get('delivery_files', []):
        if digest(safe_file(package, r['path'])) != r['sha256']: result['errors'].append('交付文件哈希不符：'+r['path'])
    result['valid'] = not result['errors']
    result['material_count'] = len(mapping)
    result['format'] = manifest['format']
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='离线检查剪映交付包或草稿；不修改文件')
    parser.add_argument('path', type=Path)
    args = parser.parse_args()
    try:
        result = check_package(args.path) if (args.path/'manifest.json').is_file() else inspect_draft(args.path)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {'valid': False, 'errors': [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['valid'] else 2)
