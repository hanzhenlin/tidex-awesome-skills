"""Output route checks: local fixtures, no voice/generation/video rendering."""
from pathlib import Path
import copy,json,shutil,sys,unittest,uuid,subprocess
LIB=Path(__file__).resolve().parents[1]/'lib';sys.path.insert(0,str(LIB))
import composition as c,output_backends as ob,production_stage as p
ROOT=next(v for v in LIB.parents if (v/'skills/handraw-video-producer/catalog/shots.json').is_file())
BASE=ROOT/'videos/validation/composition-v2'
if not (BASE/'episode.json').is_file():
 sys.path.insert(0,str(LIB.parent/'bin'))
 from test_shots import fixtures
 BASE=fixtures()
RUN=ROOT/'tmp'/('output-routes-'+uuid.uuid4().hex[:8])
RUN.mkdir(parents=True)

def shot(sid,kind,cfg,start=0):return dict(id=sid,type=kind,purpose='输出分派测试',intent={'action':'验证路线约束'},start_frame=start,end_frame=start+60,config=cfg,layers=[],events=[],transition={'type':'cut','frames':0})

def fixture(name,shots):
 ep=RUN/name
 for n in ('assets','work','outputs'):(ep/n).mkdir(parents=True)
 files=['background.png','neutral.png','wave-a.png','wave-b.png','full-scene-pose-0.png','full-scene-pose-1.png']
 for n in files:shutil.copy2(BASE/'assets'/n,ep/'assets'/n)
 shutil.copy2(BASE/'assets/video.mp4',ep/'assets/video.mp4')
 shutil.copy2(LIB.parent/'examples/composition-v2/assets/tone.wav',ep/'assets/tone.wav')
 shutil.copy2(BASE/'work/Scene.tsx',ep/'work/Scene.tsx')
 c.save(ep/'episode.json',dict(title='输出路线技术夹具',workflow='composition-v2',width=1920,height=1080,fps=30,aspect_ratio='16:9',subtitle_mode='none',media_policy='auto',output_target='jianying',brief={'goal':'测试用户已同意的Skill拆分和原生默认门槛'},visual={'paper':'#fcf7ea'},narration={'enabled':False}))
 c.save(ep/'composition.json',dict(version=2,duration_frames=len(shots)*60,shots=shots,audio_tracks=[],subtitle_cues=[],local_types=[]))
 (ep/'plan.md').write_text('# 输出路线工程测试\n用户回复“可以”，同意先选路线及拆分制作Skill；本期夹具验证原生限制、同意记录及草稿结构。不是新成片或审美批准，不调用付费素材或配音。测试含需要预渲染的明确镜头，记录同意仅供该技术夹具，不授权真实业务工程。\n',encoding='utf-8')
 (ep/'script.txt').write_text('无旁白，仅工程验证。',encoding='utf-8');p.initialize(ep)
 doc=c.read(ep/'production.json');doc['plan']['complete']=True;doc['inventory_complete']=True
 doc['visual_assets']=[dict(id=n,kind='video' if n.endswith('.mp4') else 'image',path='assets/'+n,required=True) for n in [*files,'video.mp4']]
 c.save(ep/'production.json',doc);p.record_approval(ep,'可以')
 for a in doc['visual_assets']:p.review_asset(ep,a['id'],{'status':'pass','notes':'已检查既有本地测试夹具及原视频的实际画面；仅复用技术输入，非新业务成片认可。'})
 return ep

class Routes(unittest.TestCase):
 def test_choice_is_required(self):
  with self.assertRaisesRegex(ValueError,'必须选择'):c.new_episode(RUN,'missing',dict(width=1920,height=1080,fps=30),'none','2026-10-10')
  proc=subprocess.run([sys.executable,str(LIB.parent/'bin/hvp.py'),'new','route-must-not-create'],capture_output=True,text=True,encoding='utf-8')
  self.assertEqual(proc.returncode,2);self.assertIn('--output-target',proc.stderr)
  for target in ('web','jianying'):
   ep=c.new_episode(RUN,'chosen-'+target,dict(width=1920,height=1080,fps=30),'none','2026-10-10',output_target=target)
   self.assertEqual(c.read(ep/'episode.json')['output_target'],target)

 def test_seven_browser_and_strict_jianying(self):
  self.assertTrue(ob.plan(BASE,'web')['valid'])
  report=ob.plan(BASE,'jianying');self.assertFalse(report['valid']);self.assertEqual(report['browser_frames'],0)
  for sid in ('S5','S6','S7'):self.assertTrue(any(sid in e for e in report['errors']))

 def test_browser_preparation_still_works(self):
  ep=fixture('web-prepare',[shot('S1','ST-001',{'asset':'assets/background.png'})]);meta=c.read(ep/'episode.json');meta['output_target']='web';c.save(ep/'episode.json',meta)
  page,timing=c.prepare(ep);self.assertTrue(page.is_file());self.assertEqual(timing['duration'],2)

 def test_four_native_export_never_uses_browser(self):
  ep=fixture('native',[shot('S1','ST-001',{'asset':'assets/background.png'}),shot('S2','ST-002',{'asset':'assets/video.mp4','source_in':1,'source_out':3},60),shot('S3','ST-003',{'background':'assets/background.png','sprites':[{'id':'cat','asset':'assets/neutral.png','playback':'static','region':[.1,.2,.2,.6]}]},120),shot('S4','ST-004',{'frames':[{'asset':'assets/full-scene-pose-0.png','hold_frames':30},{'asset':'assets/full-scene-pose-1.png','hold_frames':30}]},180)])
  report=ob.plan(ep);self.assertTrue(report['valid'],report['errors']);self.assertEqual(report['native_frames'],240);self.assertEqual(report['browser_frames'],0)
  import render_engine
  original=render_engine.render_html_to_video
  render_engine.render_html_to_video=lambda *a,**k:(_ for _ in ()).throw(AssertionError('Native route called browser'))
  try:package=ob.export(ep)
  finally:render_engine.render_html_to_video=original
  self.assertEqual(c.read(package/'draft/draft_content.json')['duration'],8_000_000)
  with self.assertRaisesRegex(ValueError,'剪映工程'):c.render(ep)
  with self.assertRaisesRegex(ValueError,'剪映工程'):c.prepare(ep)

 def test_type_one_complex_effect_is_not_native(self):
  ep=fixture('rotation',[shot('S1','ST-001',{'asset':'assets/background.png','rotation_keyframes':[{'at_frame':0,'rotation':0},{'at_frame':59,'rotation':10}]})])
  report=ob.plan(ep);self.assertFalse(report['valid']);self.assertIn('旋转',''.join(report['errors']))

 def test_explicit_web_is_not_approval(self):
  s=shot('S1','ST-001',{'asset':'assets/background.png'});s['render_backend']='web';ep=fixture('explicit-web',[s])
  self.assertFalse(ob.plan(ep)['valid'])

 def test_actual_named_approval_and_stale_plan(self):
  ep=fixture('exception',[shot('S1','ST-005',{'entry':'work/Scene.tsx','inputs':['assets/neutral.png']})])
  self.assertFalse(ob.plan(ep)['valid'])
  from shot_engines import render_shot
  meta=c.read(ep/'episode.json');s=c.read(ep/'composition.json')['shots'][0]
  with self.assertRaisesRegex(ValueError,'默认原生'):render_shot(ep,meta,s,'remotion',s['config'])
  ob.record_prerender_approval(ep,'可以',['S1'])
  report=ob.plan(ep);self.assertTrue(report['valid'],report['errors']);self.assertEqual(report['browser_frames'],60)
  ob.require_web_shots(ep,['S1'])
  with self.assertRaisesRegex(ValueError,'全片'):ob.require_web_shots(ep)
  board=c.read(ep/'composition.json');board['shots'][0]['render_backend']='jianying';c.save(ep/'composition.json',board)
  self.assertFalse(ob.plan(ep)['valid'])
  board['shots'][0]['render_backend']='auto';c.save(ep/'composition.json',board)
  (ep/'plan.md').write_text('已改版，旧确认和旧例外不能沿用。',encoding='utf-8')
  self.assertFalse(ob.plan(ep)['valid'])

 def test_unknown_approval_shot(self):
  ep=fixture('unknown',[shot('S1','ST-001',{'asset':'assets/background.png'})])
  with self.assertRaisesRegex(ValueError,'有效'):ob.record_prerender_approval(ep,'可以',['missing'])

if __name__=='__main__':
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(Routes);result=unittest.TextTestRunner(verbosity=2).run(suite)
 report={'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'passed':result.wasSuccessful(),'fixture_root':str(RUN),'scope':'routing + native draft structure; no animation render, no TTS, no paid generation','jianying_app_open':'not_tested','actual_jianying_export':'not_tested'}
 dest=ROOT/'videos/validation/output-routes';dest.mkdir(parents=True,exist_ok=True);c.save(dest/'validation.json',report)
 sys.exit(0 if result.wasSuccessful() else 1)
