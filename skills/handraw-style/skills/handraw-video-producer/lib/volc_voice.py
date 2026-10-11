"""Bridge to the bundled sibling voice Skill; never invoke an external CLI repo."""
from pathlib import Path
import sys
import importlib.util


def module(name):
    root=Path(__file__).resolve().parents[2]/'handraw-volc-tts/scripts'
    if not (root/'handraw_volc/credentials.py').is_file():
        raise RuntimeError('缺少随包handraw-volc-tts Skill，请安装该子Skill；不会读取其他本地项目')
    if str(root) not in sys.path:sys.path.insert(0,str(root))
    if name=='cli':
        spec=importlib.util.spec_from_file_location('handraw_volc_cli',root/'volc_voice.py')
        value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
    return __import__('handraw_volc.'+name,fromlist=[name])


def produce_episode(ep):return module('workflow').episode(ep)
