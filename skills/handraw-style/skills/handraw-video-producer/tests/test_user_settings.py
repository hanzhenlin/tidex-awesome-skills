"""Persistent draft location: isolated profiles; never installs into the user's draft box."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

LIB=Path(__file__).resolve().parents[1]/'lib';sys.path.insert(0,str(LIB))
import user_settings as settings


class Settings(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.profile=self.root/'user-profile'
        self.drafts=self.root/'剪映 草稿';self.drafts.mkdir()
        self.env=patch.dict(os.environ,{'HVP_CONFIG_DIR':str(self.profile)})
        self.env.start()

    def tearDown(self):
        self.env.stop();self.temp.cleanup()

    def test_persists_across_process_and_copied_updated_code(self):
        result=settings.save_draft_dir(self.drafts);self.assertTrue(result['directory_exists'])
        before=settings.config_path().read_bytes()
        updated=self.root/'updated-repository';updated.mkdir()
        shutil.copy2(LIB/'user_settings.py',updated/'user_settings.py')
        r=subprocess.run([sys.executable,'-S',str(updated/'user_settings.py')],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(json.loads(r.stdout)['draft_dir'],str(self.drafts.resolve()))
        self.assertEqual(settings.config_path().read_bytes(),before)
        self.assertFalse(settings.config_path().is_relative_to(updated))

    def test_explicit_override_does_not_change_saved_value(self):
        settings.save_draft_dir(self.drafts);other=self.root/'other';other.mkdir()
        self.assertEqual(settings.draft_dir(other),other.resolve())
        self.assertEqual(settings.draft_dir(),self.drafts.resolve())

    def test_missing_and_invalid_directory_fail_without_overwrite(self):
        with self.assertRaisesRegex(ValueError,'尚未保存'):settings.draft_dir()
        settings.save_draft_dir(self.drafts);before=settings.config_path().read_bytes()
        with self.assertRaises(ValueError):settings.save_draft_dir('relative')
        with self.assertRaises(ValueError):settings.save_draft_dir(self.root/'absent')
        self.assertEqual(settings.config_path().read_bytes(),before)
        self.drafts.rmdir();self.assertFalse(settings.status()['directory_exists'])
        with self.assertRaisesRegex(ValueError,'不存在'):settings.draft_dir()

    def test_preserves_other_preferences_and_rejects_corrupt_file(self):
        self.profile.mkdir();settings.config_path().write_text(json.dumps({'version':1,'other':{'value':42},'jianying':{'extra':True}}),encoding='utf-8')
        settings.save_draft_dir(self.drafts);value=settings.read_settings()
        self.assertEqual(value['other']['value'],42);self.assertTrue(value['jianying']['extra'])
        settings.config_path().write_text('broken',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'读取失败'):settings.save_draft_dir(self.drafts)
        self.assertEqual(settings.config_path().read_text(),'broken')

    def test_default_is_in_user_profile_and_cli_saves(self):
        with patch.dict(os.environ,{'HVP_CONFIG_DIR':''}):
            path=settings.config_path()
            self.assertFalse(path.is_relative_to(LIB.parent))
            if sys.platform=='win32':self.assertEqual(path.parent,Path(os.environ['APPDATA'])/'handraw-video-producer')
        r=subprocess.run([sys.executable,str(LIB.parent/'bin/hvp.py'),'jianying-config','--draft-dir',str(self.drafts)],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(settings.draft_dir(),self.drafts.resolve())


if __name__=='__main__':unittest.main()
