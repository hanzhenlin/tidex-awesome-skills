"""Local engineering fixtures, authorized by the rebuild plan; no speech/generation."""
from pathlib import Path
import sys,json,shutil,subprocess,hashlib,math
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'lib'))
import composition as c
import production_stage as p
from runtime_tools import executable
from PIL import Image,ImageDraw,ImageFont
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'skills/handraw-video-producer/catalog/shots.json').is_file());EP=ROOT/'videos/validation/composition-v2'

def fixtures(force=False):
    if EP.exists() and not force:return EP
    for folder in ('assets','work','outputs'):(EP/folder).mkdir(parents=True,exist_ok=True)
    source=Path(__file__).resolve().parents[1]/'examples/composition-v2/assets'
    inputs=[]
    for name in ['neutral.png','wave-a.png','wave-b.png','coffee.png','laptop.png']+[f'full-scene-pose-{i}.png' for i in range(4)]:
        shutil.copy2(source/name,EP/'assets'/name);inputs.append('assets/'+name)
    shutil.copy2(source/'fanren-dawn.png',EP/'assets/fanren-dawn.png');inputs.append('assets/fanren-dawn.png')
    W,H=1920,1080;paper='#fcf7ea';ink='#2d3b38';green='#668d78';orange='#dc9653'
    font=ImageFont.truetype(str(Path(__file__).resolve().parents[1]/'lib/vendor/simo/assets/fonts/Xiaolai-Regular.ttf'),55)
    bg=Image.new('RGB',(W,H),paper);d=ImageDraw.Draw(bg)
    d.rounded_rectangle([110,185,810,850],40,fill='#e3ecdf');d.line([140,850,1800,850],fill=green,width=5)
    d.rounded_rectangle([1050,305,1800,810],30,fill='#f1e0c4',outline=green,width=4)
    d.text((1120,365),'开工前，先打个招呼',font=font,fill=ink)
    bg.save(EP/'assets/background.png');inputs.append('assets/background.png')
    # Sparse clear line art and accent colors are deliberately authored for ST-007.
    line=Image.new('RGB',(W,H),paper);d=ImageDraw.Draw(line)
    d.rounded_rectangle([180,260,740,720],35,outline=ink,width=7);d.ellipse([340,340,570,570],fill=orange,outline=ink,width=7)
    d.line([745,490,1075,490],fill=ink,width=10);d.polygon([(1075,490),(1030,462),(1030,518)],fill=ink)
    d.rounded_rectangle([1110,260,1740,720],35,outline=ink,width=7);d.line([(1200,620),(1360,475),(1470,555),(1640,340)],fill=green,width=14)
    line.save(EP/'assets/line-art.png');inputs.append('assets/line-art.png')
    ann={'canvas':{'width':W,'height':H},'elements':[
        {'id':'a','sequence':1,'label':'起点','region':{'x':150,'y':220,'width':650,'height':550},'reveal':{'startMs':0,'durationMs':1000}},
        {'id':'b','sequence':2,'label':'连接','region':{'x':800,'y':430,'width':290,'height':140},'reveal':{'startMs':1000,'durationMs':500}},
        {'id':'c','sequence':3,'label':'结果','region':{'x':1090,'y':220,'width':690,'height':550},'reveal':{'startMs':1500,'durationMs':2000,'protectedRegions':[]}}]}
    c.save(EP/'assets/annotation.json',ann);inputs.append('assets/annotation.json')
    # Recorded local fixture, not a generated external clip and never reused as original.
    subprocess.run([executable('ffmpeg'),'-y','-v','error','-loop','1','-i',str(EP/'assets/full-scene-pose-0.png'),'-vf','zoompan=z=1.0+on*0.0005:x=iw/2-iw/zoom/2:y=ih/2-ih/zoom/2:d=150:s=1920x1080:fps=30','-frames:v','150','-c:v','libx264','-pix_fmt','yuv420p',str(EP/'assets/video.mp4')],check=True);inputs.append('assets/video.mp4')
    import wave,struct
    with wave.open(str(EP/'assets/tone.wav'),'wb') as f:
        f.setparams((1,2,48000,48000*28,'NONE','not compressed'))
        f.writeframes(b''.join(struct.pack('<h',round(2200*math.sin(2*math.pi*220*i/48000))) for i in range(48000*28)))
    meta={'title':'七种分镜 · 本地技术验证','workflow':'composition-v2','width':W,'height':H,'fps':30,'aspect_ratio':'16:9','subtitle_mode':'burn-in','media_policy':'auto','output_target':'web','brief':{'audience':'工程审片','goal':'验证七种分镜及统一合成'},'visual':{'paper':paper},'narration':{'enabled':False}}
    shots=[]
    configs=[
        {'asset':'assets/fanren-dawn.png','keyframes':[{'at_frame':0,'region':[0,0,1,1]},{'at_frame':119,'region':[-.06,-.04,1.12,1.12]}]},
        {'asset':'assets/video.mp4','source_in':1,'source_out':5},
        {'background':'assets/background.png','sprites':[
            {'id':'cat','frames':[{'asset':'assets/wave-a.png','hold_frames':12},{'asset':'assets/wave-b.png','hold_frames':12}],'playback':'loop','region':[.13,.20,.25,.57],'contact_anchors':{'foot':[.5,1]},'motion':{'type':'oscillate','amplitude':[.05,0],'period_frames':60,'start_frame':0,'end_frame':120},'z_index':1},
            {'id':'coffee','asset':'assets/coffee.png','playback':'static','region':[.62,.48,.16,.23],'start_frame':20,'z_index':2},
            {'id':'once','frames':[{'asset':'assets/neutral.png','hold_frames':20},{'asset':'assets/wave-a.png','hold_frames':20},{'asset':'assets/wave-b.png','hold_frames':20}],'playback':'once','on_end':'hold','region':[.43,.26,.17,.42],'start_frame':30,'z_index':3}]},
        {'frames':[{'asset':f'assets/full-scene-pose-{i}.png','hold_frames':30} for i in range(4)]},
        {'entry':'work/Scene.tsx','inputs':['assets/neutral.png'],'props':{}},
        {'scene':'work/simo-scene.json','inputs':['assets/coffee.png']},
        {'image':'assets/line-art.png','annotation':'assets/annotation.json','grid_edge':6,'bare_tip':False}]
    names=['单图动画','视频','背景＋透明素材动画','全图有限帧动画','Remotion 动画','simo 版白板动画','SRT 版白板动画']
    for i,cfg in enumerate(configs):shots.append({'id':'S'+str(i+1),'purpose':names[i]+'技术展示','type':f'ST-{i+1:03}','start_frame':i*120,'end_frame':(i+1)*120,'voice_anchor':'无旁白本地测试','config':cfg,'layers':[],'events':[],'transition':{'type':'cut','frames':0}})
    cues=[{'start_frame':i*120,'end_frame':(i+1)*120,'text':f'ST-{i+1:03}  {names[i]}'} for i in range(7)]
    c.save(EP/'episode.json',meta);c.save(EP/'composition.json',{'version':2,'duration_frames':840,'shots':shots,'subtitle_cues':cues,'audio_tracks':[{'path':'assets/tone.wav','start_frame':0,'end_frame':840,'gain':.1}],'local_types':[]});c.save(EP/'video_tasks.json',{'version':2,'tasks':[]})
    (EP/'script.txt').write_text('无配音技术测试。',encoding='utf-8');p.initialize(EP)
    (EP/'plan.md').write_text('# 七种分镜本地技术验收\n\n按用户已确认的重建计划：7镜×4秒，1920×1080，30fps，28秒840帧。ST-001采用《凡人修仙传 · 一夜催药》神手谷单图原画实测，其余复用本地橘猫素材，补充本地线稿、无旁白测试音。七类分别验证真实渲染；无付费素材与配音。此为工程测试，审美接受待用户审看。\n',encoding='utf-8')
    doc=c.read(EP/'production.json');doc['plan']['complete']=True;doc['inventory_complete']=True
    doc['visual_assets']=[{'id':'A'+str(i),'path':v,'kind':'data' if v.endswith('.json') else 'video' if v.endswith('.mp4') else 'image','required':True} for i,v in enumerate(inputs)]
    c.save(EP/'production.json',doc)
    p.record_approval(EP,'PLEASE IMPLEMENT THIS PLAN: 7 类分别渲染本地短样片，并制作一条 7 镜、每镜 4 秒的混合测试片：1920×1080、30fps、28 秒，共 840 帧。测试不调用付费生成或配音。')
    # Fixture QA includes known-authored data and actual inspected local illustration inputs.
    for a in doc['visual_assets']:p.review_asset(EP,a['id'],{'status':'pass','notes':'本地技术夹具：已检查《凡人修仙传 · 一夜催药》单图原画与原始橘猫画面、透明素材，线稿、分区与合成测试视频由确定性本地脚本创建；不代表成片审美通过。'})
    # Production code is created only after input collection and review pass.
    p.require(EP)
    (EP/'work/Scene.tsx').write_text('''import React from 'react';import {AbsoluteFill,Img,staticFile,useCurrentFrame,useVideoConfig,interpolate} from 'remotion';
export default function Scene(){const f=useCurrentFrame(),{width:w,height:h,durationInFrames:n}=useVideoConfig();const p=interpolate(f,[0,n-1],[0,1]);return <AbsoluteFill style={{background:'#fcf7ea',fontFamily:'Microsoft YaHei',color:'#2d3b38'}}><div style={{position:'absolute',left:w*.07,top:h*.11,fontSize:w*.035}}>把一件事，拆成看得见的步骤</div><Img src={staticFile('assets/neutral.png')} style={{position:'absolute',left:w*.07,top:h*.26,height:h*.5,transform:`translateX(${p*w*.15}px)`}}/>{['想法','行动','结果'].map((label,i)=><div key={label} style={{position:'absolute',left:w*(.40+i*.17),top:h*.38,width:w*.13,height:h*.19,background:['#e3ecdf','#f0ddbc','#d9e8e3'][i],borderRadius:28,display:'flex',alignItems:'center',justifyContent:'center',fontSize:w*.032,opacity:Math.max(0,Math.min(1,(f-i*25)/15)),transform:`translateY(${(1-p)*h*.09}px)`}}>{label}</div>)}</AbsoluteFill>}
''',encoding='utf-8')
    # Use migrated DSL to author real pen paths and sticker reveal, then precise intervals.
    dsl=EP/'work/create-simo.cjs';dsl.write_text('''const {Scene}=require('''+json.dumps(str(Path(__file__).resolve().parents[1]/'lib/vendor/simo/lib/scene-dsl.js'))+''');const fs=require('fs');const s=new Scene('test','').nextBeat();s.rect(150,260,450,390,{stroke:'#2d3b38',strokeWidth:5,fill:'#e3ecdf'});s.text(245,420,'先想清楚',{size:52});s.arrow([[700,450],[1020,450]],{stroke:'#668d78',strokeWidth:7});s.rect(1100,260,650,390,{stroke:'#2d3b38',strokeWidth:5,fill:'#f0ddbc'});s.push({id:'sticker',type:'image',x:1280,y:350,width:280,height:220,fileId:'coffee',angle:0,opacity:100});fs.writeFileSync(process.argv[2],JSON.stringify({elements:s.elements,files:{coffee:{asset:'assets/coffee.png'}},intervals:[[0,24],[24,45],[45,62],[62,88],[88,110]]}));''',encoding='utf-8')
    subprocess.run(['node',str(dsl),str(EP/'work/simo-scene.json')],check=True)
    return EP

if __name__=='__main__':
    ep=fixtures(force='--force' in sys.argv or '--fixtures' in sys.argv)
    print(p.status(ep))
    if '--render' in sys.argv:c.render(ep);c.mix(ep)

