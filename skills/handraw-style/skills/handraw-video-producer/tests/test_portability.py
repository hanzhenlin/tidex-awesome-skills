"""Exercise release relocation and dependency discovery without private resources."""
from pathlib import Path
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SKILL=Path(__file__).resolve().parents[1]
ROOT=SKILL.parents[1]
TEMP=ROOT/'tmp/portability-tests'
TEMP.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(SKILL/'lib'))
import runtime_tools

class Portability(unittest.TestCase):
    def test_no_author_ffmpeg_fallback(self):
        with patch.dict(os.environ,{},clear=True),patch.object(runtime_tools.shutil,'which',return_value=None):
            with self.assertRaisesRegex(RuntimeError,'HVP_FFMPEG'):
                runtime_tools.executable('ffmpeg')

    def test_explicit_browser_does_not_silently_fallback(self):
        with patch.dict(os.environ,{'HVP_BROWSER':'missing-browser'},clear=True):
            with self.assertRaisesRegex(RuntimeError,'existing browser'):
                runtime_tools.browser_executable()

    def test_new_episode_works_after_relocation_without_existing_videos(self):
        spec=importlib.util.spec_from_file_location('sync_rules',SKILL/'bin/sync_skill.py')
        rules=importlib.util.module_from_spec(spec);spec.loader.exec_module(rules)
        with tempfile.TemporaryDirectory(dir=TEMP) as directory:
            root=Path(directory)
            installed=root/'skills/handraw-video-producer'
            for source in SKILL.rglob('*'):
                if rules.included(source):
                    target=installed/source.relative_to(SKILL)
                    target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
            self.assertFalse((root/'videos').exists())
            env=os.environ.copy();env.pop('HVP_WORKSPACE',None);env['PYTHONIOENCODING']='utf-8'
            cli=[sys.executable,'-S',str(installed/'bin/hvp.py')]
            cat=subprocess.run([*cli,'catalog','--kind','shot'],cwd=root,env=env,capture_output=True,text=True,encoding='utf-8',check=True)
            self.assertEqual(len(json.loads(cat.stdout)['items']),7)
            created=subprocess.run([*cli,'new','移植测试','--output-target','jianying'],cwd=root,env=env,capture_output=True,text=True,encoding='utf-8',check=True)
            episode=Path(json.loads(created.stdout))
            self.assertTrue(episode.resolve().is_relative_to(root))
            self.assertEqual(json.loads((episode/'episode.json').read_text(encoding='utf-8'))['output_target'],'jianying')
            self.assertIsNone(json.loads((episode/'production.json').read_text(encoding='utf-8'))['approval'])
            self.assertFalse(any(p.suffix.lower() in rules.VIDEO_EXTENSIONS for p in installed.rglob('*') if p.is_file()))

if __name__=='__main__':unittest.main()
