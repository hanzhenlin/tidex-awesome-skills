"""Exact manifest sync for video routing/production Skills and scoped style gallery."""
from pathlib import Path
import hashlib,json,shutil
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'skills/handraw-video-producer/catalog/shots.json').is_file())
VIDEO_EXTENSIONS={'.mp4','.mov','.webm','.m4v','.mkv','.avi','.wmv','.mpg','.mpeg','.mts','.m2ts'}

def included(p):return p.is_file() and p.suffix.lower() not in VIDEO_EXTENSIONS and not any(x in p.parts for x in ('node_modules','__pycache__','.pytest_cache')) and p.name not in ('release_manifest.json','volc-tts.json','credentials.json') and not p.name.startswith('.env')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def sync():
    reports=[]
    for name in ('handraw-video-producer','knowledge-video-director','handraw-browser-producer','handraw-jianying-producer','handraw-volc-tts'):
        source=(ROOT/'skills'/name).resolve();dest=(ROOT/'.agents/skills'/name).resolve()
        if dest.parent!=(ROOT/'.agents/skills').resolve():raise RuntimeError('Invalid installed Skill root')
        backup=ROOT/'tmp/installed-before-shot-sync'/name
        if dest.exists() and not backup.exists():shutil.copytree(dest,backup,ignore=shutil.ignore_patterns('node_modules','__pycache__'))
        files={p.relative_to(source).as_posix():digest(p) for p in source.rglob('*') if included(p)}
        removed=[]
        if dest.exists():
            for p in sorted(dest.rglob('*')):
                if p.is_file() and p.relative_to(dest).as_posix() not in files and 'node_modules' not in p.parts:
                    if not p.resolve().is_relative_to(dest):raise RuntimeError('Unsafe stale path')
                    removed.append(p.relative_to(dest).as_posix());p.unlink()
        for value,sha in files.items():
            target=dest/value;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source/value,target)
            if digest(target)!=sha:raise RuntimeError('Installed hash mismatch: '+value)
        # Empty legacy subdirectories carry no active code, but remove them too.
        for p in sorted(dest.rglob('*'),key=lambda p:len(p.parts),reverse=True):
            if p.is_dir() and not any(p.iterdir()):p.rmdir()
        excluded_videos=[p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS and 'node_modules' not in p.parts]
        report=dict(skill=name,files=files,removed=removed,excluded_videos=excluded_videos,installed_hashes='all_match');reports.append(report)
        (source/'release_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');shutil.copy2(source/'release_manifest.json',dest/'release_manifest.json')
    source=ROOT/'skills/handdraw-style-prompter';dest=ROOT/'.agents/skills/handdraw-style-prompter'
    poster_names={'manifest.json',*(f'ST-{i:03}.png' for i in range(1,8))}
    subset=[source/'SKILL.md',*list((source/'gallery').glob('*.html')),*(source/'gallery/video-shot-previews'/name for name in sorted(poster_names))]
    subset += [source/'scripts'/name for name in ('build_library.py','build_tutorial_gallery.py','build_video_shot_gallery.py')]
    hashes={}
    for p in subset:
        if not p.is_file():continue
        target=dest/p.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
        hashes[p.relative_to(source).as_posix()]=digest(p);assert digest(p)==digest(target)
    preview_dir=(dest/'gallery/video-shot-previews').resolve()
    for p in preview_dir.glob('*'):
        if p.is_file() and p.name not in poster_names:
            if not p.resolve().is_relative_to(preview_dir):raise RuntimeError('Unsafe poster cleanup')
            backup=ROOT/'tmp/installed-before-shot-sync/style-gallery/video-shot-previews'/p.name
            backup.parent.mkdir(parents=True,exist_ok=True)
            if not backup.exists():shutil.copy2(p,backup)
            p.unlink()
    # Remove precisely retired video UI files and assets, retaining unrelated styles.
    stale=[dest/'gallery'/name for name in ('video-techniques.html','video-composer.html','video-art-scenes','video-technique-previews','video-techniques-data.js','video-catalog.js')]
    stale+=list((dest/'scripts').glob('*video*'))
    for p in stale:
        if not p.exists() or p.name=='build_video_shot_gallery.py':continue
        if not p.resolve().is_relative_to(dest.resolve()):raise RuntimeError('Unsafe gallery cleanup')
        if p.is_dir():
            backup=ROOT/'tmp/installed-before-shot-sync/style-gallery'/p.name
            if not backup.exists():shutil.copytree(p,backup)
            shutil.rmtree(p)
        else:p.unlink()
    report={'video_skills':reports,'style_gallery_hashes':hashes,'gallery_screenshots_only':True}
    (ROOT/'tmp').mkdir(exist_ok=True)
    (ROOT/'tmp/shot-sync-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'video_skill_files':{r['skill']:len(r['files']) for r in reports},'stale_removed':sum(len(r['removed']) for r in reports),'gallery_files':len(hashes),'hashes':'all_match'},ensure_ascii=False))
if __name__=='__main__':sync()
