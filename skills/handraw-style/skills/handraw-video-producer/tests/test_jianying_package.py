"""Portable draft delivery: local fixtures; no paid services or browser frames."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

from test_output_routes import fixture, shot, RUN, ROOT
import composition as comp
import output_backends as ob
from jianying_package import check_package, inspect_draft, digest
from jianying_install import install


class Portable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s = shot('S1', 'ST-003', {'background':'assets/background.png', 'sprites':[
            {'id':'cat','asset':'assets/neutral.png','playback':'static','region':[.1,.2,.3,.6]}]})
        s['layers'] = [{'id':'label','kind':'text','text':'开工吧','region':[.5,.2,.3,.15]}]
        ep = fixture('portable', [s])
        # Voice remains disabled; the bundled authored test tone exercises audio packaging.
        b = comp.read(ep/'composition.json')
        b['audio_tracks'] = [{'path':'assets/tone.wav','start_frame':0,'end_frame':60,'source_in':1,'gain':.25}]
        comp.save(ep/'composition.json', b)
        from production_stage import record_approval
        record_approval(ep, '可以')
        with patch('render_engine.render_html_to_video', side_effect=AssertionError('browser forbidden')):
            cls.package = ob.export(ep)
        cls.root = RUN/'portable-tests'
        cls.root.mkdir()

    def clone(self, name):
        target=self.root/name
        shutil.copytree(self.package,target)
        return target

    def refresh(self, folder):
        m=comp.read(folder/'manifest.json')
        for row in m['files']:row['sha256']=digest(folder/'draft'/row['path'])
        comp.save(folder/'manifest.json',m)

    def test_portable_offline_install_and_editable_layers(self):
        moved=self.clone('moved');root=self.root/'drafts';root.mkdir()
        # -S disables installed packages: only Python's standard library is available to the installer.
        r=subprocess.run([sys.executable,'-S',str(moved/'install.py'),str(moved),'--draft-dir',str(root)],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(r.returncode,0,r.stderr)
        dst=Path(r.stdout.strip());checked=inspect_draft(dst)
        self.assertTrue(checked['valid'],checked['errors'])
        self.assertEqual(comp.read(dst/'draft_info.json'),comp.read(dst/'draft_content.json'))
        self.assertIn('text',[t['type'] for t in checked['tracks']]);self.assertIn('audio',[t['type'] for t in checked['tracks']])
        for a in checked['assets']:self.assertTrue(Path(a['path']).is_relative_to(dst))
        second=install(moved,root);self.assertNotEqual(dst,second);self.assertTrue(dst.exists())
        self.assertEqual(inspect_draft(second)['duration_us'],2_000_000)
        # Saved destination is consumed by standalone and project installers alike.
        profile=self.root/'saved-profile'
        with patch.dict(__import__('os').environ,{'HVP_CONFIG_DIR':str(profile)}):
            from user_settings import save_draft_dir
            save_draft_dir(root)
            r=subprocess.run([sys.executable,'-S',str(moved/'install.py'),str(moved)],capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertTrue(inspect_draft(Path(r.stdout.strip()))['valid'])
            third=install(moved);self.assertEqual(third.parent,root.resolve())

    def test_hash_damage_and_missing_material(self):
        damaged=self.clone('damaged');p=next((damaged/'draft/assets').iterdir());p.write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError,'哈希'):check_package(damaged)
        missing=self.clone('missing');next((missing/'draft/assets').iterdir()).unlink()
        with self.assertRaisesRegex(ValueError,'清单'):check_package(missing)

    def test_unknown_reference_and_invalid_time(self):
        for name,change,expected in [('reference',lambda s:s.update(material_id='unknown'),'引用'),
                                     ('boundary',lambda s:s['target_timerange'].update(start=9_000_000),'边界')]:
            folder=self.clone(name);c=comp.read(folder/'draft/draft_content.json');change(c['tracks'][0]['segments'][0])
            for n in ('draft_info.json','draft_content.json'):comp.save(folder/'draft'/n,c)
            self.refresh(folder);r=check_package(folder);self.assertFalse(r['valid']);self.assertIn(expected,' '.join(r['errors']))

    def test_divergent_copies_and_unlisted_external_dependency(self):
        folder=self.clone('divergent');c=comp.read(folder/'draft/draft_info.json');c['id']='other';comp.save(folder/'draft/draft_info.json',c)
        self.refresh(folder);self.assertIn('不一致',' '.join(check_package(folder)['errors']))
        folder=self.clone('external');c=comp.read(folder/'draft/draft_info.json')
        next(x for rows in c['materials'].values() if isinstance(rows,list) for x in rows if x.get('path'))['path']=str(ROOT/'AGENTS.md')
        for n in ('draft_info.json','draft_content.json'):comp.save(folder/'draft'/n,c)
        self.refresh(folder);self.assertIn('未纳入',' '.join(check_package(folder)['errors']))

    def test_only_new_content_name(self):
        folder=self.clone('new-name');(folder/'draft/draft_content.json').unlink()
        m=comp.read(folder/'manifest.json');m['files']=[r for r in m['files'] if r['path']!='draft_content.json'];comp.save(folder/'manifest.json',m)
        self.assertTrue(check_package(folder)['valid'])

    def test_delivery_tool_damage_and_safe_publication(self):
        folder=self.clone('tool-damage');(folder/'install.py').write_text('broken')
        checked=check_package(folder);self.assertFalse(checked['valid']);self.assertIn('交付文件',' '.join(checked['errors']))
        root=self.root/'failure-drafts';root.mkdir()
        with patch('jianying_install._publish',side_effect=ValueError('test interruption')):
            with self.assertRaises(ValueError):install(self.package,root)
        self.assertEqual(list(root.iterdir()),[])

    def test_resource_lookup_never_claims_availability(self):
        from jianying_resources import search
        rows=search('', 'transition', 3)['results'];self.assertTrue(rows)
        for r in rows:
            self.assertTrue(r['effect_id']);self.assertEqual(r['automatic_export'],'draft_binding_implemented_app_unverified')
        self.assertEqual(search('no_such_resource_xyz', 'filter')['matches'],0)


if __name__=='__main__':unittest.main()
