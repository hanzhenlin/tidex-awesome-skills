"""Offline API-contract, credential persistence and real PCM/timeline tests."""
import base64
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL/'scripts'))
from handraw_volc import credentials as cred, client, timing, workflow

FAKE = 'offline-fixture-secret'


class Response(io.BytesIO):
    def __init__(self, data, headers=None):
        super().__init__(data)
        self.headers = headers or {}


class Credentials(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'HVP_VOICE_CONFIG_DIR': self.tmp.name,
                'VOLC_API_KEY':'', 'VOLC_APPID':'', 'VOLC_ACCESS_TOKEN':''}, clear=False)
        self.env.start()

    def tearDown(self):
        self.env.stop(); self.tmp.cleanup()

    def test_persistence_and_private_storage(self):
        result = cred.save(dict(api_key=FAKE, speaker='test-voice'))
        self.assertTrue(result['saved']); self.assertNotIn(FAKE, json.dumps(result))
        self.assertEqual(cred.resolve()['api_key'], FAKE)
        raw = cred.config_path().read_text()
        if sys.platform == 'win32':
            self.assertNotIn(FAKE, raw); self.assertIn('windows-dpapi', raw)
        else:
            self.assertEqual(cred.config_path().stat().st_mode & 0o077, 0)
        proc = subprocess.run([sys.executable, str(SKILL/'scripts/volc_voice.py'), 'status'],
                              env=os.environ.copy(), capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(json.loads(proc.stdout)['saved']); self.assertNotIn(FAKE, proc.stdout+proc.stderr)

    def test_account_replacement_no_mixing(self):
        cred.save(dict(api_key=FAKE))
        with self.assertRaises(ValueError):cred.save(dict(app_id='offline-account'))
        cred.save(dict(app_id='offline-account', access_token=FAKE))
        self.assertNotIn('api_key', cred.resolve())
        cred.save(dict(api_key=FAKE+'new'))
        self.assertNotIn('app_id', cred.resolve())
        cred.save(dict(speaker='new-voice'))
        self.assertEqual(cred.resolve()['api_key'], FAKE+'new')

    def test_environment_auth_is_not_mixed_or_saved(self):
        cred.save(dict(api_key=FAKE))
        with patch.dict(os.environ, {'VOLC_APPID':'other-account'}):
            with self.assertRaises(ValueError):cred.resolve()
        with patch.dict(os.environ, {'VOLC_API_KEY':FAKE+'env'}):
            self.assertEqual(cred.resolve()['api_key'], FAKE+'env')
        self.assertEqual(cred.resolve()['api_key'], FAKE)

    def test_stdin_and_relocated_updated_skill_keep_config(self):
        copied = Path(self.tmp.name)/'updated-skill'
        shutil.copytree(SKILL/'scripts', copied/'scripts', ignore=shutil.ignore_patterns('__pycache__'))
        # Installer changes only Skill files, not the user config root.
        proc = subprocess.run([sys.executable, str(copied/'scripts/volc_voice.py'), 'config', '--stdin-json'],
                 input=json.dumps(dict(api_key=FAKE)), capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn(FAKE, proc.stdout+proc.stderr)
        (copied/'scripts/revision-marker.txt').write_text('updated implementation')
        proc = subprocess.run([sys.executable, str(copied/'scripts/volc_voice.py'), 'status'],
                              capture_output=True, text=True, encoding='utf-8')
        self.assertTrue(json.loads(proc.stdout)['saved'])

    def test_reject_repo_storage_and_malformed_input_without_echo(self):
        with patch.dict(os.environ, {'HVP_VOICE_CONFIG_DIR':str(SKILL/'config')}):
            with self.assertRaises(ValueError):cred.config_path()
        proc = subprocess.run([sys.executable, str(SKILL/'scripts/volc_voice.py'), 'config', '--stdin-json'],
                  input=FAKE, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(proc.returncode, 2); self.assertNotIn(FAKE, proc.stderr)


class Contracts(unittest.TestCase):
    def test_auth_and_payload(self):
        h = client.headers(dict(api_key=FAKE), 'test-resource', True)
        self.assertEqual(h['X-Api-Key'], FAKE);self.assertEqual(h['X-Api-Sequence'], '-1')
        old = dict(app_id='offline-account', access_token=FAKE)
        self.assertIn('X-Api-App-Id', client.headers(old, 'test'))
        self.assertIn('X-Api-App-Key', client.headers(old, 'test', True))
        request = client.tts_request('你好', 'voice', 0, '温和')
        self.assertNotIn(FAKE, json.dumps(request))
        self.assertEqual(json.loads(request['req_params']['additions'])['context_texts'], ['温和'])
        with self.assertRaises(ValueError):client.tts_request('你好', 'voice', 1.0)

    def test_stream_audio_and_error_atomicity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'voice.mp3'
            chunks = [b'first', b'second']
            data = b'\n'.join(json.dumps(dict(code=0, data=base64.b64encode(c).decode())).encode() for c in chunks)
            account = dict(api_key=FAKE, tts_resource='test')
            client.synthesize({}, path, account, opener=lambda *a, **k:Response(data))
            self.assertEqual(path.read_bytes(), b'firstsecond')
            error = json.dumps(dict(code=45000001, message=FAKE)).encode()
            with self.assertRaises(RuntimeError) as caught:
                client.synthesize({}, path, account, opener=lambda *a, **k:Response(error))
            self.assertNotIn(FAKE, str(caught.exception)); self.assertEqual(path.read_bytes(), b'firstsecond')
            self.assertFalse(path.with_suffix('.mp3.partial').exists())

    def test_real_boundaries_mismatch_and_utterance_fallback(self):
        utterance = dict(start_time=100, end_time=900, text='你好。', words=[
                    dict(start_time=100, end_time=300, text='你'),dict(start_time=500, end_time=900, text='好。')])
        result = {'result':{'utterances':[utterance]}}
        cues, granularity = timing.actual_cues(result, '你好', 1)
        self.assertEqual(granularity, 'word');self.assertEqual(cues[1]['start'], .5)
        with self.assertRaises(ValueError):timing.actual_cues(result, '不好')
        utterance.pop('words')
        cues, granularity = timing.actual_cues(result, '你好', 1)
        self.assertEqual(granularity, 'utterance');self.assertEqual(len(cues), 1)
        with self.assertRaises(ValueError):timing.actual_cues({'result':{}})

    def test_http_failure_does_not_echo_reflected_secret(self):
        import urllib.error
        def denied(*args, **kwargs):
            raise urllib.error.HTTPError(client.TTS_URL, 401, FAKE, {}, io.BytesIO(FAKE.encode()))
        with self.assertRaises(RuntimeError) as caught:
            client._open(client.TTS_URL, {}, {}, 1, denied)
        self.assertNotIn(FAKE, str(caught.exception))


class Pipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {'HVP_VOICE_CONFIG_DIR':str(self.root/'user')}, clear=False)
        self.env.start()
        # Production fixtures have no credential or live request dependencies.
        self.account = dict(api_key=FAKE, tts_resource='test', asr_resource='test')
        self.wav = self.root/'source.wav'
        with wave.open(str(self.wav), 'wb') as w:
            w.setparams((1,2,24000,0,'NONE','not compressed'));w.writeframes(b'\0\0'*4800)
        self.mp3 = self.root/'source.mp3'
        subprocess.run([workflow.executable('ffmpeg'),'-y','-v','error','-i',str(self.wav),str(self.mp3)],check=True)
        self.result = {'result':{'utterances':[dict(start_time=10,end_time=150,text='你好',words=[
                        dict(start_time=10,end_time=70,text='你'),dict(start_time=70,end_time=150,text='好')])]}}

    def tearDown(self):self.env.stop();self.tmp.cleanup()

    def synth(self, request, output, account):
        Path(output).write_bytes(self.mp3.read_bytes())

    def fixture(self, frames=60):
        p, _ = workflow.video_modules()
        import composition as c
        from PIL import Image
        ep = c.new_episode(self.root/'episodes', 'test', dict(width=320,height=240,fps=30,aspect_ratio='4:3'),
                           'sidecar','offline',output_target='web')
        Image.new('RGB',(320,240),'white').save(ep/'assets/image.png')
        meta=c.read(ep/'episode.json');meta['narration'].update(voice='offline-test-voice');c.save(ep/'episode.json',meta)
        c.save(ep/'composition.json',dict(version=2,duration_frames=frames,shots=[dict(id='S1',type='ST-001',
                  purpose='离线语音测试',voice_anchor='你好',start_frame=0,end_frame=frames,
                  config={'asset':'assets/image.png'},layers=[],events=[],transition={'type':'cut','frames':0})],
                  subtitle_cues=[],audio_tracks=[],local_types=[]))
        (ep/'script.txt').write_text('你好',encoding='utf-8');(ep/'plan.md').write_text('离线工程夹具，不调用真实服务',encoding='utf-8')
        doc=c.read(ep/'production.json');doc['plan']['complete']=True;doc['inventory_complete']=True
        doc['visual_assets']=[dict(id='image',kind='image',path='assets/image.png',required=True)]
        c.save(ep/'production.json',doc)
        return ep,p,c

    def ready(self, ep, p):
        p.record_approval(ep,'确认离线测试夹具')
        p.review_asset(ep,'image',{'status':'pass','notes':'已核对代码生成的纯白技术夹具；仅验证素材门槛，不代表业务审美通过'})

    def test_cached_paid_stages_no_repeat_and_corruption(self):
        with patch.object(client,'synthesize',side_effect=self.synth) as synth, patch.object(client,'recognize',return_value=self.result) as asr:
            wav, info=workflow.produce('你好',self.root/'audio','test',account=self.account)
            workflow.produce('你好',self.root/'audio','test',account=self.account)
            self.assertEqual(synth.call_count,1);self.assertEqual(asr.call_count,1)
            self.assertAlmostEqual(info['duration'],.2,places=2)
            wav.with_suffix('.mp3').write_bytes(b'corrupt')
            with self.assertRaises(ValueError):workflow.produce('你好',self.root/'audio','test',account=self.account)
            self.assertEqual(synth.call_count,1)

    def test_failed_asr_reuses_tts(self):
        with patch.object(client,'synthesize',side_effect=self.synth) as synth:
            with patch.object(client,'recognize',side_effect=RuntimeError('offline service denied')):
                with self.assertRaises(RuntimeError):workflow.produce('你好',self.root/'audio','test',account=self.account)
            with patch.object(client,'recognize',return_value=self.result):
                workflow.produce('你好',self.root/'audio','test',account=self.account)
            self.assertEqual(synth.call_count,1)

    def test_real_gate_blocks_before_service_and_allows_ready_binding(self):
        ep,p,c=self.fixture()
        with patch.object(cred,'resolve',return_value=self.account), patch.object(client,'synthesize',side_effect=self.synth) as synth, patch.object(client,'recognize',return_value=self.result):
            with self.assertRaises(ValueError):workflow.episode(ep)
            self.assertEqual(synth.call_count,0)
            p.record_approval(ep,'确认离线测试夹具')
            with self.assertRaises(ValueError):workflow.episode(ep)
            self.assertEqual(synth.call_count,0)
            p.review_asset(ep,'image',{'status':'pass','notes':'已核对代码生成的纯白技术夹具；仅验证门槛'})
            info=workflow.episode(ep)
            meta=c.read(ep/'episode.json');board=c.read(ep/'composition.json')
            self.assertEqual(info['duration'],2);self.assertEqual(board['duration_frames'],60)
            self.assertEqual(board['subtitle_cues'][0]['start_frame'],0)
            self.assertEqual(meta['narration']['actual_voice'],'offline-test-voice')
            self.assertTrue((ep/meta['narration']['path']).is_file());p.require(ep)

    def test_overflow_retains_audio_and_does_not_mutate_timeline(self):
        ep,p,c=self.fixture(frames=6);self.ready(ep,p)
        before=(ep/'composition.json').read_bytes()
        with patch.object(cred,'resolve',return_value=self.account), patch.object(client,'synthesize',side_effect=self.synth) as synth, patch.object(client,'recognize',return_value=self.result):
            with self.assertRaisesRegex(ValueError,'需要'):workflow.episode(ep)
            self.assertEqual((ep/'composition.json').read_bytes(),before)
            self.assertNotIn('path',c.read(ep/'episode.json')['narration'])
            self.assertTrue((ep/'work/volc-voice/measurements.json').exists())
            board=c.read(ep/'composition.json');board['duration_frames']=60;board['shots'][0]['end_frame']=60;c.save(ep/'composition.json',board)
            workflow.episode(ep)
            self.assertEqual(synth.call_count,1)

    def test_hvp_dispatch_and_standalone_gate(self):
        ep,p,c=self.fixture()
        with self.assertRaises(ValueError):workflow.gate_paths(ep/'script.txt')
        self.ready(ep,p)
        file=SKILL.parent/'handraw-video-producer/bin/hvp.py'
        spec=importlib.util.spec_from_file_location('test_hvp_voice',file)
        hvp=importlib.util.module_from_spec(spec);spec.loader.exec_module(hvp)
        with patch.object(cred,'resolve',return_value=self.account), patch.object(client,'synthesize',side_effect=self.synth), patch.object(client,'recognize',return_value=self.result):
            data=hvp.tts(ep)
        self.assertEqual(data['duration'],2)
        self.assertIn('actual',data['boundary_source'])


if __name__=='__main__':unittest.main()
