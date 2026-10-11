"""Additional integration cases: handoff, native output, portrait and local types."""
from pathlib import Path
import sys,copy,json,shutil,subprocess,base64,hashlib
import uuid
RUN=uuid.uuid4().hex[:8]
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'lib'))
import composition as c,production_stage as p,video_tasks as vt,output_backends as ob
from test_shots import EP
from validate_shots import check,blocked,media,RESULTS
from render_engine import render_html_to_video,local_server
from playwright.sync_api import sync_playwright
from PIL import Image,ImageDraw

def engineering(ep,meta,board,tasks=None,inventory=None):
    for f in ('assets','work','outputs'):(ep/f).mkdir(parents=True,exist_ok=True)
    c.save(ep/'episode.json',meta);c.save(ep/'composition.json',board);c.save(ep/'video_tasks.json',{'version':2,'tasks':tasks or []});(ep/'script.txt').write_text('无配音工程检查。',encoding='utf-8')
    p.initialize(ep);(ep/'plan.md').write_text('# 本地工程回归\n\n用户重建计划中的横竖画幅、视频回传、透明遮挡、三种字幕、本期类型与输出检查；只本地素材，无付费生成或配音。审美待用户审看。',encoding='utf-8')
    doc=c.read(ep/'production.json');doc.update(inventory_complete=True);doc['plan']['complete']=True;doc['visual_assets']=inventory or [];c.save(ep/'production.json',doc)
    p.record_approval(ep,'PLEASE IMPLEMENT THIS PLAN: 检查横竖画幅、三种字幕策略、视频截取、音轨；验证素材策略、视频回传及本期新增类型。测试不调用付费生成或配音。')
    for a in doc['visual_assets']:
        if not a.get('video_task'):p.review_asset(ep,a['id'],{'status':'pass','notes':'本地已审看夹具副本或明确作者的纯色像素测试；只验证工程，不代表审美通过。'})

def base_meta(w=1920,h=1080):return {'workflow':'composition-v2','title':'本地续作检查','width':w,'height':h,'fps':30,'aspect_ratio':'16:9' if w>h else '9:16','media_policy':'auto','output_target':'web','subtitle_mode':'none','narration':{'enabled':False},'visual':{},'brief':{'goal':'工程回归'}}
def shot(id,t,cfg,a=0,b=120):return dict(id=id,type=t,purpose='工程检查',start_frame=a,end_frame=b,config=cfg,layers=[])
def board(shots,n=120):return dict(version=2,shots=shots,duration_frames=n,local_types=[],subtitle_cues=[],audio_tracks=[])

def handoff():
    ep=EP.parent/('handoff-v2-'+RUN);ep.mkdir(exist_ok=True);(ep/'assets').mkdir(exist_ok=True);shutil.copy2(EP/'assets/neutral.png',ep/'assets/neutral.png')
    tasks=[]
    shots=[]
    for i in range(2):
        sid='S'+str(i+1);shots.append(shot(sid,'ST-002',{'source_in':0,'source_out':4},i*120,(i+1)*120))
        tasks.append(dict(id='C'+str(i+1),shot_id=sid,purpose='挥手交接',target_duration=4,prompt_revision=1,reference_assets=['assets/neutral.png'],instructions_zh='上传参考图生成4秒片段，保留橘猫身份，先站立，再挥手，末尾收手。不要文字或旁白。',first_state='站立',last_state='收手站立',prompts={'en':'An original orange cat in a green hoodie, warm hand-drawn illustration. Establish a standing pose, gently wave, then return to standing. Fixed camera, 16:9. Preserve identity and outfit. No text, logos or speech.'},audio={'keep_original':False},candidates=[]))
    inv=[{'id':'ref','kind':'image','path':'assets/neutral.png'}]+[{'id':'V'+str(i),'kind':'video','video_task':t['id']} for i,t in enumerate(tasks)]
    engineering(ep,base_meta(),board(shots,240),tasks,inv)
    pack=vt.export_pack(ep);assert (pack/'references/C1_01.png').exists()
    check('提示词与真实参考图交付、重载仍待回传',lambda:assertion(vt.status(ep)['stage']=='awaiting_clips'))
    blocked(lambda:p.require(ep),'制作阶段未就绪')
    cand=vt.import_clip(ep,'C1',EP/'assets/video.mp4');assert vt.import_clip(ep,'C1',EP/'assets/video.mp4')['id']==cand['id']
    check('部分回传/重复导入、未审看不可制作',lambda:blocked(lambda:p.require(ep),'尚未选用'))
    review=dict(content='pass',identity='pass',action='pass',continuity='pass',notes='本地技术片复用已观察的橘猫镜头；本例验证候选和截取绑定，未声称外部生成质量通过。')
    vt.select_candidate(ep,'C1',cand['id'],review,0)
    blocked(lambda:p.require(ep),'尚未选用')
    cand2=vt.import_clip(ep,'C2',EP/'assets/video.mp4');vt.select_candidate(ep,'C2',cand2['id'],review,1)
    p.require(ep);meta=c.read(ep/'episode.json');meta['media_policy']='video_only';c.save(ep/'episode.json',meta);p.record_approval(ep,'PLEASE IMPLEMENT THIS PLAN: 验证视频素材主导策略、本地片段和视频截取。')
    check('video_only全部主镜头通过',lambda:c.validate(ep))
    c.render(ep);c.mix(ep);media(ep/'outputs/final.mp4',240,1920,1080)
    check('提示词改版使旧选用失效',lambda:prompt_change(ep))
    check('未知片段编号拒绝',lambda:blocked(lambda:vt.import_clip(ep,'UNKNOWN',EP/'assets/video.mp4'),'未知片段'))
    bad=ep/'work/broken.mp4';bad.write_bytes(b'broken')
    try:vt.import_clip(ep,'C1',bad)
    except (ValueError,subprocess.CalledProcessError):pass
    else:raise AssertionError('corrupt clip accepted')
    RESULTS.append({'check':'损坏视频拒绝','status':'pass'})
    return ep

def assertion(ok):assert ok
def prompt_change(ep):
    manifest=c.read(ep/'video_tasks.json');changed=copy.deepcopy(manifest);changed['tasks'][0]['prompts']['en']+=' Modified.';c.save(ep/'video_tasks.json',changed)
    try:blocked(lambda:c.validate(ep),'改版')
    finally:c.save(ep/'video_tasks.json',manifest)

def local_and_portrait():
    ep=EP.parent/('portrait-local-v2-'+RUN);meta=base_meta(540,960);meta['media_policy']='no_video';b=board([shot('S1','LOCAL-PANEL',{'entry':'work/local.html'},0,60)],60);b['local_types']=[dict(id='LOCAL-PANEL',adapter='html',entry='work/local.html',status='implemented',asset_contract={'inputs':[],'canvas':[540,960],'deterministic':'frame-driven'})]
    b['subtitle_cues']=[dict(start_frame=0,end_frame=60,text='竖屏实际字幕')]
    engineering(ep,meta,b);p.require(ep)
    (ep/'work/local.html').write_text('''<!doctype html><meta charset="utf-8"><canvas width="540" height="960"></canvas><div id="css" style="animation:pulse 2s linear infinite"></div><style>@keyframes pulse{from{opacity:0}to{opacity:1}}</style><script>window.__canvas=document.querySelector('canvas');window.ready=Promise.resolve();window.renderFrame=t=>{const g=__canvas.getContext('2d');g.clearRect(0,0,540,960);g.fillStyle='#e3ecdf';g.fillRect(0,0,540,960);g.fillStyle='#dc9653';g.fillRect(50+t*100,200,150,200);g.fillStyle='#273832';g.font='30px Microsoft YaHei';g.fillText('本期独立类型',80,100)};</script>''',encoding='utf-8')
    check('本期新类型独立加载',lambda:c.validate(ep))
    frames={}
    for mode in ('burn-in','sidecar','none'):
        meta['subtitle_mode']=mode;c.save(ep/'episode.json',meta);p.record_approval(ep,'PLEASE IMPLEMENT THIS PLAN: 横竖画幅、三种字幕及本期新增类型验证。')
        c.render(ep);c.mix(ep);target=ep/'outputs'/('final-'+mode+'.mp4');shutil.copy2(ep/'outputs/final.mp4',target);media(target,60,540,960)
        active=c.read(ep/'episode.json')['subtitles'];assert bool(active)==(mode!='none')
        pagepath,_=c.prepare(ep)
        with local_server(ep) as base,sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge');page=browser.new_page();page.goto(base+'/'+pagepath.relative_to(ep).as_posix());page.evaluate('window.ready');a=page.evaluate('renderFrame(.5)');page.evaluate('renderFrame(1.5)');assert page.evaluate('renderFrame(.5)')==a;page.reload();page.evaluate('window.ready');assert page.evaluate('renderFrame(.5)')==a;frames[mode]=hashlib.sha256(base64.b64decode(a)).hexdigest();browser.close()
    assert frames['none']==frames['sidecar'] and frames['burn-in']!=frames['none']
    check('竖屏、本期HTML类型、三种字幕与跳转',lambda:assertion(True))

def native():
    ep=EP.parent/('native-v2-'+RUN);(ep/'assets').mkdir(parents=True,exist_ok=True)
    for f in ('background.png','neutral.png','wave-a.png','wave-b.png','video.mp4','tone.wav','full-scene-pose-0.png','full-scene-pose-1.png'):shutil.copy2(EP/'assets'/f,ep/'assets'/f)
    cfg={'background':'assets/background.png','sprites':[dict(id='loop',playback='loop',frames=[{'asset':'assets/wave-a.png','hold_frames':12},{'asset':'assets/wave-b.png','hold_frames':12}],region=[.1,.2,.3,.6]),dict(id='static',playback='static',asset='assets/neutral.png',region=[.55,.2,.3,.6],start_frame=30)]}
    b=board([shot('S1','ST-003',cfg),shot('S2','ST-004',{'frames':[{'asset':'assets/full-scene-pose-0.png','hold_frames':60},{'asset':'assets/full-scene-pose-1.png','hold_frames':60}]},120,240)],240);b['audio_tracks']=[dict(path='assets/tone.wav',start_frame=0,end_frame=240,gain=.1)]
    inv=[dict(id=f,kind='image',path='assets/'+f) for f in ('background.png','neutral.png','wave-a.png','wave-b.png','full-scene-pose-0.png','full-scene-pose-1.png')]
    engineering(ep,base_meta(),b,inventory=inv);report=ob.plan(ep,'jianying');assert report['native_frames']==240 and report['browser_frames']==0
    import jianying_backend as jb
    # A browser renderer call would fail this test: fully native must not use it.
    import render_engine
    original=render_engine.render_html_to_video
    render_engine.render_html_to_video=lambda *a,**k:(_ for _ in ()).throw(AssertionError('native invoked browser'))
    try:package=ob.export(ep,'jianying')
    finally:render_engine.render_html_to_video=original
    doc=c.read(package/'draft/draft_content.json');assert doc['duration']==8_000_000
    check('基础sprite及全图序列原生草稿不调用浏览器',lambda:assertion(True))
    return package

if __name__=='__main__':
    handoff();local_and_portrait();package=native()
    c.save(EP/'outputs/workflow-validation.json',{'checks':RESULTS,'jianying_native_package':str(package),'app_open':'pending','actual_export':'pending','aesthetic':'pending_user_review'})
