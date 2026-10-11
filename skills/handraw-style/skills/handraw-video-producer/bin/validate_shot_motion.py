"""Pixel observations for animation modes, geometry, overlays and transitions."""
import sys,copy,hashlib,base64,json,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'lib'))
import composition as c,production_stage as p
from validate_shot_workflows import engineering,base_meta,board,shot
from validate_shots import check,RESULTS
from test_shots import EP
from PIL import Image,ImageDraw
from render_engine import local_server
from playwright.sync_api import sync_playwright

def main():
    ep=EP.parent/('motion-v2-'+uuid.uuid4().hex[:8]);(ep/'assets').mkdir(parents=True,exist_ok=True)
    for name,col in [('bg','#ffffff'),('bg2','#0000ff')]:Image.new('RGB',(320,180),col).save(ep/'assets'/(name+'.png'))
    for name,col in [('red','#ff0000'),('green','#00ff00'),('yellow','#ffff00')]:
        im=Image.new('RGBA',(32,32));ImageDraw.Draw(im).rectangle([4,4,27,27],fill=col);im.save(ep/'assets'/(name+'.png'))
    seq=[{'asset':'assets/red.png','hold_frames':5},{'asset':'assets/green.png','hold_frames':5}]
    cfg={'background':'assets/bg.png','sprites':[
        dict(id='loop',playback='loop',frames=seq,region=[.05,.08,.15,.26],z_index=1),
        dict(id='hold',playback='once',frames=seq,region=[.27,.08,.15,.26],z_index=1),
        dict(id='hide',playback='once',on_end='hide',frames=seq,region=[.49,.08,.15,.26],z_index=1),
        dict(id='static',playback='static',asset='assets/yellow.png',region=[.72,.08,.15,.26],start_frame=5,z_index=1),
        dict(id='over',playback='static',asset='assets/yellow.png',region=[.05,.08,.15,.26],start_frame=20,z_index=2),
        dict(id='path',playback='static',asset='assets/red.png',region=[.05,.5,.15,.26],motion={'type':'path','points':[[0,0],[.2,-.2],[.3,.1],[.5,0]],'start_frame':0,'end_frame':60}),
        dict(id='orbit',playback='static',asset='assets/green.png',region=[.75,.5,.15,.26],motion={'type':'orbit','radius':[.10,.10],'period_frames':30,'start_frame':0,'end_frame':60})]}
    s1=shot('S1','ST-003',cfg,0,60);s2=shot('S2','ST-001',{'asset':'assets/bg2.png'},60,90);s2['transition']={'type':'dissolve','frames':10}
    b=board([s1,s2],90);meta=base_meta(320,180);meta['media_policy']='no_video'
    inv=[{'id':x,'path':'assets/'+x+'.png','kind':'image'} for x in ('bg','bg2','red','green','yellow')];engineering(ep,meta,b,inventory=inv)
    html,_=c.prepare(ep)
    with local_server(ep) as base,sync_playwright() as pw:
        browser=pw.chromium.launch(channel='msedge');page=browser.new_page();page.goto(base+'/'+html.relative_to(ep).as_posix());page.evaluate('window.ready')
        def frame(f):page.evaluate('t=>renderFrame(t)',f/30)
        def pixel(x,y):return page.evaluate('([x,y])=>Array.from(__canvas.getContext("2d").getImageData(x,y,1,1).data)',[x,y])
        # Parent exposes the composition canvas for instrumentation as well as renderFrame.
        page.evaluate('window.__canvas=document.getElementById("stage")')
        frame(0);assert pixel(40,38)[:3]==[255,0,0] and pixel(250,38)[:3]==[255,255,255]
        frame(5);assert pixel(40,38)[:3]==[0,255,0] and pixel(250,38)[:3]==[255,255,0]
        frame(10);assert pixel(40,38)[:3]==[255,0,0] and pixel(110,38)[:3]==[0,255,0] and pixel(180,38)[:3]==[255,255,255]
        frame(20);assert pixel(40,38)[:3]==[255,255,0]
        # Alpha margin leaves the background visible rather than a black rectangle.
        assert pixel(17,16)[:3]==[255,255,255]
        check('静态/循环/一次播放、末帧保持/隐藏、同时与依次出场、透明遮挡',lambda:None)
        frame(0);start=page.evaluate('renderFrame(0)');frame(30);mid=page.evaluate('renderFrame(1)');assert start!=mid
        frame(59);end=page.evaluate('renderFrame(59/30)');assert end!=mid
        frame(0);assert page.evaluate('renderFrame(0)')==start
        frame(60);a=pixel(305,170)[:3];assert a!=[0,0,255] and a!=[255,255,255]
        frame(69);assert pixel(305,170)[:3]==[0,0,255]
        check('曲线与环绕运动、反向复算、溶解转场边界',lambda:None)
        # Test the same timeline with wipe; no new content/route, no stale transition frame.
        b['shots'][1]['transition']['type']='wipe';c.save(ep/'composition.json',b);p.record_approval(ep,'PLEASE IMPLEMENT THIS PLAN: 验证规律运动和转场边界。')
        html,_=c.prepare(ep);page.reload();page.evaluate('window.ready');page.evaluate('window.__canvas=document.getElementById("stage")');frame(60);assert pixel(10,170)[:3]==[0,0,255] and pixel(305,170)[:3]==[255,255,255]
        frame(69);assert pixel(305,170)[:3]==[0,0,255]
        check('擦拭转场边界',lambda:None);browser.close()
    c.save(EP/'outputs/motion-validation.json',{'checks':RESULTS,'fixture':str(ep)})
if __name__=='__main__':main()
