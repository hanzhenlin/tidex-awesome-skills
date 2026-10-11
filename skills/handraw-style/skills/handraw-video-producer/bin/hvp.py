#!/usr/bin/env python3
"""Shot-based video entry point. Only composition-v2 is executable."""
import argparse, json, subprocess, sys
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if hasattr(sys.stdout,'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr,'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')
if hasattr(sys.stdin,'reconfigure'):
    sys.stdin.reconfigure(encoding='utf-8')
sys.path.insert(0,str(ROOT/'lib'))
import composition as c
import production_stage as production
import video_tasks, output_backends
from frame_layout import resolve_frame
from shot_catalog import catalog
from subtitles import SUBTITLE_MODES

def project_root():
    configured=__import__('os').environ.get('HVP_WORKSPACE')
    if configured:
        return Path(configured).expanduser().resolve()
    for p in ROOT.parents:
        if (p/'skills/handraw-video-producer/catalog/shots.json').is_file() and not p.name.startswith('.'):return p
    return Path.cwd().resolve()

def resolve_episode(value):
    p=Path(value)
    if p.is_dir() and (p/'episode.json').exists():result=p.resolve()
    else:
        folder=project_root()/'videos/episodes'
        matches=[x for x in folder.iterdir() if x.is_dir() and value.lower() in x.name.lower()] if folder.is_dir() else []
        if len(matches)!=1:raise ValueError('工程匹配为'+str(len(matches))+'个；请提供绝对路径')
        result=matches[0]
    if not c.unified(c.read(result/'episode.json')):raise ValueError('仅执行composition-v2；旧工程、成片和素材保留，不自动转换')
    return result

def tts(ep):
    production.require(ep);meta=c.read(ep/'episode.json');board=c.read(ep/'composition.json');voice=meta.get('narration',{})
    output_backends.require_plan(ep,meta.get('output_target','web'))
    if board.get('version')!=2 or type(board.get('duration_frames'))!=int or board['duration_frames']<=0:raise ValueError('配音前需完整composition-v2时间线')
    if not voice.get('enabled',True) or voice.get('path'):return c.timing_for(ep,meta,board)
    if (ep/'work/timing.json').exists() and any((ep/'work'/x).exists() for x in ('narration.mp3','dialogue_mix.wav')):return c.timing_for(ep,meta,board)
    if voice.get('provider') in ('volc','volc-tts','volcano'):
        from volc_voice import produce_episode
        return produce_episode(ep)
    if voice.get('provider') not in ('edge','edge-tts'):raise ValueError('请通过指定配音服务生成后导入narration.path与实际字幕/timing.json；不会改用其他服务')
    from tts_engine import process_text_and_synthesize
    from runtime_tools import executable
    import os
    os.environ.setdefault('HVP_FFPROBE',executable('ffprobe'))
    text=(ep/'script.txt').read_text(encoding='utf-8').strip()
    if not text:raise ValueError('script.txt为空')
    return process_text_and_synthesize(text,ep/'work',voice.get('voice','zh-CN-YunxiNeural'),voice.get('rate','+0%'))

def covers(ep):
    production.require(ep)
    from runtime_tools import executable
    final=ep/'outputs/final.mp4'
    if not final.exists():raise FileNotFoundError(final)
    for name,scale in [('cover_4x3.png','1200:900'),('cover_3x4.png','900:1200')]:
        subprocess.run([executable('ffmpeg'),'-y','-v','error','-i',str(final),'-frames:v','1','-vf','scale='+scale+':force_original_aspect_ratio=increase,crop='+scale,str(ep/'outputs'/name)],check=True)

def main(argv=None):
    p=argparse.ArgumentParser(description='hvp · 分镜类型视频制作');sub=p.add_subparsers(dest='cmd',required=True)
    q=sub.add_parser('catalog');q.add_argument('--kind',choices=['shot'],required=True)
    q=sub.add_parser('new');q.add_argument('title');q.add_argument('--aspect');q.add_argument('--width',type=int);q.add_argument('--height',type=int);q.add_argument('--fps',type=int,default=30);q.add_argument('--subtitle-mode',choices=SUBTITLE_MODES,default='burn-in');q.add_argument('--media-policy',choices=video_tasks.POLICIES,default='auto');q.add_argument('--output-target',choices=output_backends.TARGETS,required=True,help='先选择：web浏览器成片 / jianying剪映草稿')
    for cmd in ('validate','production-status','asset-check','video-status','video-pack','video-import','tts','render','mix','covers','build','export-plan','export'):
        q=sub.add_parser(cmd);q.add_argument('episode')
        if cmd in ('build','export-plan','export'):q.add_argument('--target',choices=output_backends.TARGETS)
        if cmd=='video-import':q.add_argument('--clip',required=True);q.add_argument('--file',type=Path,required=True)
    q=sub.add_parser('jianying-install');q.add_argument('package',type=Path);q.add_argument('--draft-dir',type=Path,help='本次覆盖；未指定时使用本机已保存草稿箱位置')
    q=sub.add_parser('jianying-config');q.add_argument('--draft-dir',type=Path,help='保存本机草稿箱位置；不传则查看')
    q=sub.add_parser('jianying-check');q.add_argument('path',type=Path)
    q=sub.add_parser('jianying-resources');q.add_argument('query',nargs='?',default='');q.add_argument('--kind',choices=['transition','filter','effect','character_effect','intro','outro']);q.add_argument('--limit',type=int,default=20)
    sub.add_parser('runtime-status')
    q=sub.add_parser('runtime-install');q.add_argument('--engine',choices=['base','browser','edge','volc','remotion','simo','srt'],required=True)
    q=sub.add_parser('volc-config');group=q.add_mutually_exclusive_group();group.add_argument('--stdin-json',action='store_true');group.add_argument('--from-env',action='store_true');group.add_argument('--interactive',action='store_true');q.add_argument('--speaker');q.add_argument('--tts-resource');q.add_argument('--asr-resource')
    sub.add_parser('volc-status')
    a=p.parse_args(argv)
    if a.cmd=='catalog':result=catalog(a.kind)
    elif a.cmd in ('volc-config','volc-status'):
        from volc_voice import module
        result=module('credentials').status() if a.cmd=='volc-status' else module('cli').configure(a)
    elif a.cmd=='new':
        frame=resolve_frame(a.aspect,a.width,a.height,a.fps,default_aspect='16:9');result=str(c.new_episode(project_root()/'videos/episodes',a.title,frame,a.subtitle_mode,datetime.now().strftime('%Y-%m-%d'),a.media_policy,a.output_target))
    elif a.cmd=='jianying-install':
        from jianying_install import install
        result=str(install(a.package,a.draft_dir))
    elif a.cmd=='jianying-config':
        from user_settings import save_draft_dir,status
        result=save_draft_dir(a.draft_dir) if a.draft_dir is not None else status()
    elif a.cmd=='jianying-check':
        from jianying_package import check_package,inspect_draft
        result=check_package(a.path) if (a.path/'manifest.json').is_file() else inspect_draft(a.path)
        if not result['valid']:print(json.dumps(result,ensure_ascii=False,indent=2));return 2
    elif a.cmd=='jianying-resources':
        from jianying_resources import search
        result=search(a.query,a.kind,a.limit)
    elif a.cmd.startswith('runtime-'):
        from shot_engines import runtime_status,install_runtime
        if a.cmd=='runtime-install':install_runtime(a.engine)
        result=runtime_status()
    else:
        ep=resolve_episode(a.episode)
        if a.cmd in ('production-status','asset-check'):
            result=production.status(ep)
            if a.cmd=='asset-check' and result['stage']!='ready_for_production':print(json.dumps(result,ensure_ascii=False,indent=2));return 2
        elif a.cmd=='validate':
            b,_=c.validate(ep);result={'shots':len(b['shots']),'frames':b['duration_frames'],'validation':'结构与素材检查通过；实际渲染和审美分别检查'}
        elif a.cmd=='video-status':result=video_tasks.status(ep)
        elif a.cmd=='video-pack':result=str(video_tasks.export_pack(ep))
        elif a.cmd=='video-import':result=video_tasks.import_clip(ep,a.clip,a.file)
        elif a.cmd=='tts':result=tts(ep)
        elif a.cmd=='render':result=str(c.render(ep))
        elif a.cmd=='mix':result=str(c.mix(ep))
        elif a.cmd=='covers':covers(ep);result='封面已提取'
        elif a.cmd=='export-plan':
            result=output_backends.plan(ep,a.target)
            if not result['valid']:print(json.dumps(result,ensure_ascii=False,indent=2));return 2
        elif a.cmd in ('build','export'):
            production.require(ep)
            output_backends.require_plan(ep,a.target or c.read(ep/'episode.json').get('output_target','web'))
            if a.cmd=='build':tts(ep)
            result=str(output_backends.export(ep,a.target))
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0
if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,RuntimeError,OSError,KeyError) as e:print('[ERROR] '+str(e),file=sys.stderr);sys.exit(2)
