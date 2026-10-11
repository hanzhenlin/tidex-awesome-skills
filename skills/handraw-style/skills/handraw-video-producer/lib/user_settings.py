"""Persistent per-user preferences, outside the repository and installed Skills.

Standard library only; also shipped with standalone draft packages.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile


def config_path():
    override=os.environ.get('HVP_CONFIG_DIR')
    if override:
        root=Path(override).expanduser()
        if not root.is_absolute():raise ValueError('HVP_CONFIG_DIR必须为绝对路径')
    elif sys.platform=='win32':
        root=Path(os.environ.get('APPDATA') or Path.home()/'AppData/Roaming')/'handraw-video-producer'
    else:
        root=Path(os.environ.get('XDG_CONFIG_HOME') or Path.home()/'.config')/'handraw-video-producer'
    return root/'config.json'


def read_settings():
    path=config_path()
    if not path.exists():return {'version':1}
    try:value=json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError,ValueError) as exc:raise ValueError('用户配置读取失败，请检查'+str(path)+': '+str(exc)) from exc
    if not isinstance(value,dict) or value.get('version')!=1 or not isinstance(value.get('jianying',{}),dict):
        raise ValueError('用户配置格式不支持：'+str(path))
    return value


def directory(value):
    path=Path(value).expanduser()
    if not path.is_absolute():raise ValueError('草稿箱位置必须为绝对路径')
    path=path.resolve()
    if not path.is_dir():raise ValueError('草稿箱目录不存在，请在剪映设置中确认：'+str(path))
    return path


def save_draft_dir(value):
    path=directory(value);settings=read_settings()
    settings.setdefault('jianying',{})['draft_dir']=str(path)
    target=config_path();target.parent.mkdir(parents=True,exist_ok=True)
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',prefix='config-',suffix='.tmp',dir=target.parent,delete=False) as stream:
            temporary=Path(stream.name);json.dump(settings,stream,ensure_ascii=False,indent=2);stream.write('\n')
            stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,target)
    finally:
        if temporary is not None and temporary.exists():temporary.unlink()
    return status()


def status():
    value=read_settings().get('jianying',{}).get('draft_dir')
    if value is not None and (not isinstance(value,str) or not Path(value).is_absolute()):raise ValueError('已保存草稿箱路径无效：'+str(config_path()))
    return {'config_file':str(config_path()),'draft_dir':value,'configured':bool(value),
            'directory_exists':bool(value and Path(value).is_dir()),
            'storage':'user_profile_outside_repository','explicit_override_is_saved':False}


def draft_dir(override=None):
    if override is not None:return directory(override)
    value=status()['draft_dir']
    if not value:raise ValueError('尚未保存草稿箱位置；先用hvp jianying-config --draft-dir "目录"，或本次安装指定--draft-dir')
    return directory(value)


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description='保存或查看本机剪映草稿箱位置；配置在仓库外')
    parser.add_argument('--draft-dir',type=Path)
    args=parser.parse_args()
    try:print(json.dumps(save_draft_dir(args.draft_dir) if args.draft_dir is not None else status(),ensure_ascii=False,indent=2))
    except (ValueError,OSError) as exc:print('[ERROR] '+str(exc),file=sys.stderr);raise SystemExit(2)
