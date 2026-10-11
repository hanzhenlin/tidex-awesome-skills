"""Standalone portable draft installer. Only creates a new uniquely named directory."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time
import uuid
from jianying_package import check_package, inspect_draft, CONTENT_NAMES
from user_settings import draft_dir as resolve_draft_dir


def install(package, draft_dir=None):
    package=Path(package).resolve();root=resolve_draft_dir(draft_dir)
    if not root.is_dir():raise ValueError('请先在剪映设置中选择并创建草稿目录')
    report=check_package(package)
    if not report['valid']:raise ValueError('交付包检查失败：'+'；'.join(report['errors']))
    manifest=json.loads((package/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('format')!='hvp-jianying-package-v1':raise ValueError('未知交付包格式')
    src=(package/'draft').resolve()
    if not src.is_dir():raise ValueError('缺失draft目录')
    files=manifest.get('files',[])
    actual={p.relative_to(src).as_posix() for p in src.rglob('*') if p.is_file()}
    if actual!={r['path'] for r in files}:raise ValueError('交付包文件清单不完整')
    for r in files:
        p=(src/r['path']).resolve()
        if not p.is_relative_to(src) or not p.is_file() or p.is_symlink():raise ValueError('非法文件路径')
        if hashlib.sha256(p.read_bytes()).hexdigest()!=r['sha256']:raise ValueError('交付包哈希不符：'+r['path'])
    for r in manifest.get('materials',[]):
        p=(src/r['path']).resolve()
        if not p.is_relative_to(src/'assets') or r['path'] not in actual or not p.is_file():
            raise ValueError('非法素材清单路径')
        if hashlib.sha256(p.read_bytes()).hexdigest()!=r['sha256']:raise ValueError('素材哈希不符')
    # Do not accept a caller-provided folder name; never overwrite user projects.
    name='HVP_'+time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]
    dst=(root/name).resolve()
    if not dst.is_relative_to(root) or dst.exists():raise ValueError('草稿目标不安全或已存在')
    # Incomplete copies stay outside the app's draft list; only publish after inspection.
    staging=root/('.hvp-install-'+uuid.uuid4().hex)
    staging.mkdir()
    try:
        return _publish(src,staging,dst,root,manifest,name)
    finally:
        if staging.exists():
            if staging.resolve().parent!=root or staging.is_symlink():raise ValueError('临时目录边界异常')
            shutil.rmtree(staging)


def _publish(src, staging, dst, root, manifest, name):
    shutil.copytree(src,staging,dirs_exist_ok=True)
    paths={r['original_path']:str(dst/r['path']) for r in manifest['materials']}
    def rebind(value):
        if isinstance(value,dict):return {k:rebind(v) for k,v in value.items()}
        if isinstance(value,list):return [rebind(v) for v in value]
        if isinstance(value,str):return paths.get(value,value)
        return value
    content_path=next(staging/n for n in CONTENT_NAMES if (staging/n).is_file())
    content=json.loads(content_path.read_text(encoding='utf-8'))
    content=rebind(content);content['id']=str(uuid.uuid4()).upper()
    for group in content.get('materials',{}).values():
        if isinstance(group,list):
            for material in group:
                # Destination paths become live only when the staging folder is renamed.
                check=Path(material.get('path',''))
                if check.is_relative_to(dst):check=staging/check.relative_to(dst)
                if material.get('path') and not check.is_file():
                    raise ValueError('重绑定后素材仍不存在：'+material['path'])
    for n in CONTENT_NAMES:
        (staging/n).write_text(json.dumps(content,ensure_ascii=False,indent=2),encoding='utf-8')
    meta=json.loads((staging/'draft_meta_info.json').read_text(encoding='utf-8'))
    meta.update({'draft_id':content['id'],'draft_name':manifest['title']+' '+name,
                 'draft_fold_path':str(dst),'draft_root_path':str(root),
                 'tm_draft_create':round(time.time()*1e6),'tm_draft_modified':round(time.time()*1e6)})
    (staging/'draft_meta_info.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    mapping={str(dst/r['path']):str(staging/r['path']) for r in manifest['materials']}
    checked=inspect_draft(staging,mapping)
    if not checked['valid']:raise ValueError('安装后检查失败：'+'；'.join(checked['errors']))
    for row in checked['assets']:
        p=Path(row['path'])
        if p.is_relative_to(staging):row['path']=str(dst/p.relative_to(staging))
    (staging/'hvp_install_report.json').write_text(json.dumps(checked,ensure_ascii=False,indent=2),encoding='utf-8')
    if dst.exists():raise ValueError('草稿目录已存在，禁止覆盖')
    staging.rename(dst)
    return dst


if __name__=='__main__':
    ap=argparse.ArgumentParser(description='安装HVP剪映草稿包；只新建，不覆盖')
    ap.add_argument('package',type=Path);ap.add_argument('--draft-dir',type=Path,help='本次覆盖已保存位置，不修改用户配置')
    args=ap.parse_args();print(install(args.package,args.draft_dir))
