"""End-to-end shot regression and deterministic rendering evidence."""
import base64,copy,hashlib,json,shutil,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'lib'))
import composition as c
import production_stage as production
import output_backends,video_tasks
from runtime_tools import executable
from render_engine import local_server,render_html_to_video
from playwright.sync_api import sync_playwright
from test_shots import EP,fixtures

RESULTS=[]
def check(name,fn):
    fn();RESULTS.append({'check':name,'status':'pass'});print('[PASS]',name,flush=True)
def blocked(fn,part=''):
    try:fn()
    except (ValueError,RuntimeError,OSError) as e:
        if part and part not in str(e):raise AssertionError(str(e))
        return
    raise AssertionError('Expected a concrete rejection')
def media(path,frames,w,h):
    x=json.loads(subprocess.check_output([executable('ffprobe'),'-v','error','-count_frames','-show_streams','-show_format','-of','json',str(path)]));v=next(s for s in x['streams'] if s['codec_type']=='video')
    assert int(v['nb_read_frames'])==frames and [v['width'],v['height']]==[w,h]
    assert abs(float(v['duration'])-frames/30)<.001
    subprocess.run([executable('ffmpeg'),'-v','error','-xerror','-i',str(path),'-f','null','-'],check=True,capture_output=True)

def variants(ep):
    meta=c.read(ep/'episode.json');board=c.read(ep/'composition.json');doc=c.read(ep/'production.json')
    def restore():c.save(ep/'episode.json',meta);c.save(ep/'composition.json',board);c.save(ep/'production.json',doc)
    try:
        modified=copy.deepcopy(doc);modified['approval']=None;c.save(ep/'production.json',modified)
        check('未确认阻止准备、配音与两种输出',lambda:[blocked(lambda fn=fn:fn(ep)) for fn in (c.prepare,lambda x:output_backends.export(x,'web'),lambda x:output_backends.export(x,'jianying'))])
        c.save(ep/'production.json',doc)
        modified=copy.deepcopy(doc);modified['visual_assets'][0]['review']['status']='pending';c.save(ep/'production.json',modified)
        check('缺素材审查阻止制作',lambda:blocked(lambda:c.prepare(ep),'制作阶段未就绪'))
        c.save(ep/'production.json',doc)
        (ep/'script.txt').write_text('改变内容。',encoding='utf-8')
        check('脚本变更使确认失效',lambda:blocked(lambda:production.require(ep),'旧确认失效'))
        (ep/'script.txt').write_text('无配音技术测试。',encoding='utf-8') # restore canonical below
    finally:
        (ep/'script.txt').write_text('无配音技术测试。',encoding='utf-8')
        restore()
    # Original fixture text is intentional and must retain its exact confirmation hash.
    (ep/'script.txt').write_text('无配音技术测试。',encoding='utf-8')
    return meta,board,doc

def structural(ep):
    meta=c.read(ep/'episode.json');board=c.read(ep/'composition.json')
    def validate_change(change):
        m=copy.deepcopy(meta);b=copy.deepcopy(board);change(m,b);c.save(ep/'episode.json',m);c.save(ep/'composition.json',b)
        try:return c.validate(ep,m)
        finally:c.save(ep/'episode.json',meta);c.save(ep/'composition.json',board)
    check('no_video拒绝视频层',lambda:blocked(lambda:validate_change(lambda m,b:m.update(media_policy='no_video')),'no_video'))
    check('video_only拒绝非视频主画面',lambda:blocked(lambda:validate_change(lambda m,b:m.update(media_policy='video_only')),'video_only'))
    check('auto支持零视频',lambda:validate_change(lambda m,b:b['shots'][1].update(type='ST-001',config={'asset':'assets/full-scene-pose-0.png'})))
    check('未知类型拒绝且不回退',lambda:blocked(lambda:validate_change(lambda m,b:b['shots'][0].update(type='UNKNOWN')),'未知'))
    check('完整图帧时长不补帧',lambda:blocked(lambda:validate_change(lambda m,b:b['shots'][3]['config']['frames'][0].update(hold_frames=29)),'精确覆盖'))
    check('缺图报告具体镜头',lambda:blocked(lambda:validate_change(lambda m,b:b['shots'][0]['config'].update(asset='assets/missing.png')),'镜头S1'))
    check('视频过短/截取越界',lambda:blocked(lambda:validate_change(lambda m,b:b['shots'][1]['config'].update(source_out=7)),'视频需要明确'))
    def native_fail():
        b=copy.deepcopy(board);b['shots'][4]['render_backend']='jianying';c.save(ep/'composition.json',b)
        try:
            result=output_backends.plan(ep,'jianying');assert not result['valid'] and any('S5' in s for s in result['errors'])
        finally:c.save(ep/'composition.json',board)
    check('不支持剪映原生时拒绝',native_fail)

def deterministic(ep):
    pagepath,_=c.prepare(ep)
    hashes={}
    with local_server(ep) as base,sync_playwright() as pw:
        browser=pw.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1920,'height':1080});url=base+'/'+pagepath.relative_to(ep).as_posix();page.goto(url);page.evaluate('window.ready')
        frames=[0,30,119,120,239,240,260,299,330,350,359,360,389,390,419,420,449,450,479,480,535,599,600,644,645,719,720,735,749,750,765,779,780,810,839]
        def snap(f):return base64.b64decode(page.evaluate('t=>renderFrame(t)',f/30))
        for f in frames:hashes[str(f)]=hashlib.sha256(snap(f)).hexdigest()
        for f in reversed(frames):assert hashlib.sha256(snap(f)).hexdigest()==hashes[str(f)],f
        page.reload();page.evaluate('window.ready')
        for f in frames:assert hashlib.sha256(snap(f)).hexdigest()==hashes[str(f)],f
        # Actual frame region proves once animation holds, independent of a moving loop.
        def crop(f,region):
            page.evaluate('t=>renderFrame(t)',f/30)
            return page.evaluate('r=>Array.from(document.getElementById("stage").getContext("2d").getImageData(...r).data)',region)
        assert crop(340,[835,290,300,400])==crop(359,[835,290,300,400])
        assert hashes['360']!=hashes['390']
        # Future whiteboard region stays paper before its scheduled ink.
        region=[1130,300,500,350]
        assert crop(720,region)==crop(735,region)
        browser.close()
    c.save(ep/'outputs/determinism.json',{'frames':hashes,'repeat_reverse_reload':'pass','once_hold':'pass','full_frame_boundary':'pass','future_region':'pass'})

def clips(ep):
    board,_=c.validate(ep);meta=c.read(ep/'episode.json')
    for shot in board['shots']:
        page,_=c.prepare(ep,shot_ids={shot['id']},subtitle_mode='none');out=ep/'outputs'/(shot['type']+'.mp4')
        render_html_to_video(page,out,4,30,1920,1080,serve_root=ep,start_time=shot['start_frame']/30)
        media(out,120,1920,1080)
        subprocess.run([executable('ffmpeg'),'-y','-v','error','-ss','2.8' if shot['type'] in ('ST-006','ST-007') else '2','-i',str(out),'-frames:v','1',str(ep/'outputs'/(shot['type']+'.png'))],check=True)

def main():
    ep=fixtures();meta=c.read(ep/'episode.json');board=c.read(ep/'composition.json');doc=c.read(ep/'production.json');script=(ep/'script.txt').read_bytes()
    try:
        check('混合片840帧、28秒、完整解码',lambda:media(ep/'outputs/final.mp4',840,1920,1080))
        structural(ep)
        changed=copy.deepcopy(doc);changed['approval']=None;c.save(ep/'production.json',changed)
        check('未确认两种输出与配音开工均被阻止',lambda:[blocked(lambda fn=fn:fn(ep)) for fn in (c.prepare,lambda x:output_backends.export(x,'web'),lambda x:output_backends.export(x,'jianying'))])
        c.save(ep/'production.json',doc);changed=copy.deepcopy(doc);changed['visual_assets'][0]['review']['status']='pending';c.save(ep/'production.json',changed)
        check('素材尚未审查不可制作',lambda:blocked(lambda:c.prepare(ep),'制作阶段未就绪'))
        c.save(ep/'production.json',doc);(ep/'script.txt').write_text('change',encoding='utf-8')
        check('改版不能沿用确认',lambda:blocked(lambda:production.require(ep),'旧确认失效'))
        (ep/'script.txt').write_bytes(script)
        check('同刻重复、逆向跳转及重载像素一致',lambda:deterministic(ep))
        if '--clips' in sys.argv:check('七类独立120帧镜头',lambda:clips(ep))
        c.save(ep/'outputs/validation.json',{'checks':RESULTS,'aesthetic':'pending_user_review','paid_generation':False,'paid_voice':False})
    finally:
        c.save(ep/'episode.json',meta);c.save(ep/'composition.json',board);c.save(ep/'production.json',doc);(ep/'script.txt').write_bytes(script)
if __name__=='__main__':main()
