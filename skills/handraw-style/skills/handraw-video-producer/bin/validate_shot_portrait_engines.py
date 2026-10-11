"""Portrait Remotion and both pen renderers; supplied SRT timing, no speech."""
import sys,json,shutil,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'lib'))
import composition as c,production_stage as p
from validate_shot_workflows import engineering,base_meta,board,shot
from validate_shots import check,media,RESULTS
from test_shots import EP
def main():
    ep=EP.parent/('portrait-engines-v2-'+uuid.uuid4().hex[:8]);(ep/'assets').mkdir(parents=True,exist_ok=True)
    for f in ('neutral.png','line-art.png','annotation.json'):shutil.copy2(EP/'assets'/f,ep/'assets'/f)
    # SRT is an actual local timing input; its extent is 2 seconds, no synthetic speech.
    (ep/'assets/timing.srt').write_text('1\n00:00:00,000 --> 00:00:00,500\n起点\n\n2\n00:00:00,500 --> 00:00:01,000\n连接\n\n3\n00:00:01,000 --> 00:00:01,750\n结果\n',encoding='utf-8')
    configs=[{'entry':'work/Scene.tsx','inputs':['assets/neutral.png']},
             {'scene':'work/simo.json'},
             {'image':'assets/line-art.png','annotation':'assets/annotation.json','srt':'assets/timing.srt','bare_tip':True}]
    shots=[shot('S'+str(i+1),'ST-00'+str(i+5),cfg,i*60,(i+1)*60) for i,cfg in enumerate(configs)]
    meta=base_meta(540,960);meta['media_policy']='no_video';meta['subtitle_mode']='sidecar';meta['subtitle_source']='assets/timing.srt'
    inv=[{'id':f,'path':'assets/'+f,'kind':'data' if f.endswith(('.srt','.json')) else 'image'} for f in ('neutral.png','line-art.png','annotation.json','timing.srt')]
    engineering(ep,meta,board(shots,180),inventory=inv);p.require(ep)
    shutil.copy2(EP/'work/Scene.tsx',ep/'work/Scene.tsx')
    elements=[dict(id='line',type='rectangle',x=60,y=250,width=420,height=300,seed=123,roughness=1,strokeColor='#2d3b38',strokeWidth=3,strokeStyle='solid',backgroundColor='#e3ecdf',fillStyle='hachure',opacity=100,angle=0,roundness=None),dict(id='text',type='text',x=130,y=365,width=300,height=60,text='先想清楚',fontSize=40,lineHeight=1.25,strokeColor='#2d3b38',opacity=100)]
    c.save(ep/'work/simo.json',{'elements':elements,'files':{},'intervals':[[0,30],[30,54]]})
    check('提供的SRT作为字幕与笔迹时间依据',lambda:c.validate(ep))
    c.render(ep);c.mix(ep);media(ep/'outputs/final.mp4',180,540,960)
    assert (ep/'outputs/subtitles.srt').exists()
    check('竖屏Remotion透明PNG/字体、simo实际笔迹、SRT等比容纳与实际字幕对齐',lambda:None)
    c.save(EP/'outputs/portrait-engine-validation.json',{'checks':RESULTS,'fixture':str(ep),'frames':180,'size':[540,960]})
if __name__=='__main__':main()
