"""Verify the public gallery works without private sample media or tooling."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
BUILDER = Path('skills/handdraw-style-prompter/scripts/build_video_shot_gallery.py')
CATALOG = Path('skills/handraw-video-producer/catalog/shots.json')
GALLERY = Path('skills/handdraw-style-prompter/gallery')
TEST_TMP = ROOT/'tmp/gallery-distribution-tests'
TEST_TMP.mkdir(parents=True, exist_ok=True)

class GalleryDistributionTests(unittest.TestCase):
    def test_standalone_build_has_seven_screenshots_and_no_video(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as directory:
            root = Path(directory)
            for path in (BUILDER, CATALOG, *(GALLERY/'video-shot-previews'/f'ST-{i:03}.png' for i in range(1, 8))):
                target = root/path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT/path, target)
            subprocess.run([sys.executable, '-S', str(root/BUILDER)], check=True, capture_output=True)
            self.assertFalse((root/'videos').exists())
            page = (root/GALLERY/'video-shots.html').read_text(encoding='utf-8')
            manifest = json.loads((root/GALLERY/'video-shot-previews/manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(page.count('<article class="card"'), 7)
            self.assertNotRegex(page, r'<(?:video|source)\b|videos/|\.mp4|\.webm|实测案例|detailCase|card-case')
            self.assertEqual(len(manifest['items']), 7)
            for i, item in enumerate(manifest['items'], 1):
                self.assertEqual(item['renderers'], ['剪映', '浏览器'] if i <= 4 else ['浏览器'])
                self.assertTrue(item['description'])
                self.assertNotIn('case', item)
                screenshot = item['image'].split('?')[0]
                self.assertEqual(hashlib.sha256((root/GALLERY/screenshot).read_bytes()).digest(), hashlib.sha256((ROOT/GALLERY/screenshot).read_bytes()).digest())

    def test_installer_excludes_videos_and_keeps_typescript(self):
        spec = importlib.util.spec_from_file_location('skill_sync', ROOT/'skills/handraw-video-producer/bin/sync_skill.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as directory:
            for extension in (*module.VIDEO_EXTENSIONS, '.MP4', '.ts', '.tsx', '.png'):
                file = Path(directory)/('sample'+extension)
                file.write_bytes(b'test')
                self.assertEqual(module.included(file), extension.lower() not in module.VIDEO_EXTENSIONS)

if __name__ == '__main__':
    unittest.main()
