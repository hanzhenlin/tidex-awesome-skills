"""Native resources and adjacent primary clips; no browser/paid generation/app export."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch
from test_output_routes import fixture,shot
import composition as c
import output_backends as ob
from jianying_native import resolve
from jianying_package import check_package
from production_stage import record_approval


class Native(unittest.TestCase):
    def episode(self,name):
        shots=[shot('S1','ST-001',{'asset':'assets/background.png'}),
               shot('S2','ST-002',{'asset':'assets/video.mp4','source_in':1,'source_out':3},60),
               shot('S3','ST-003',{'background':'assets/background.png','sprites':[{'id':'cat','asset':'assets/neutral.png','playback':'static','region':[.1,.2,.3,.6]}]},120),
               shot('S4','ST-004',{'frames':[{'asset':'assets/full-scene-pose-0.png','hold_frames':30},{'asset':'assets/full-scene-pose-1.png','hold_frames':30}]},180)]
        for s in shots[:3]:s['jianying']={'transition_out':{'name':'叠化','frames':10,'scope':'primary'}}
        shots[0]['jianying']['effects']=[{'name':'1998','start_frame':5,'end_frame':50,'params':[],'scope':'scene'}]
        shots[1]['jianying']['filters']=[{'name':'1980','intensity':35,'start_frame':10,'end_frame':50}]
        ep=fixture(name,shots);record_approval(ep,'不对啊，转场和特效我记得是有编号和名称的，直接在草稿中编辑也可以，不行么？')
        return ep

    def test_real_name_or_ids_and_conflicts(self):
        a=resolve('transition',{'name':'叠化'})
        self.assertEqual(a.value.resource_id,'6724845717472416269');self.assertEqual(a.value.effect_id,'322577')
        self.assertEqual(a,resolve('transition',{'resource_id':a.value.resource_id}))
        self.assertEqual(a,resolve('transition',{'effect_id':a.value.effect_id}))
        self.assertEqual(a,resolve('transition',{'name':'叠化','effect_id':'322577'}))
        with self.assertRaisesRegex(ValueError,'冲突'):resolve('transition',{'name':'叠化','effect_id':'unknown'})
        with self.assertRaises(ValueError):resolve('effect',{'name':'不存在的效果名称_xyz'})

    def test_four_types_transition_effect_filter_written_without_browser(self):
        ep=self.episode('native-resources');report=ob.plan(ep)
        self.assertTrue(report['valid'],report['errors']);self.assertEqual(report['browser_frames'],0)
        self.assertEqual(report['shots'][2]['native_resources'][0]['scope'],'primary')
        with patch('render_engine.render_html_to_video',side_effect=AssertionError('browser forbidden')):package=ob.export(ep)
        self.assertTrue(check_package(package)['valid'])
        content=c.read(package/'draft/draft_info.json');self.assertEqual(content['duration'],8_000_000)
        primary=next(t for t in content['tracks'] if t['name']=='hvp_primary');self.assertEqual(len(primary['segments']),5)
        spans=[s['target_timerange'] for s in primary['segments']]
        self.assertEqual(spans[0]['start'],0)
        for a,b in zip(spans,spans[1:]):self.assertEqual(a['start']+a['duration'],b['start'])
        materials=content['materials'];transitions=materials['transitions'];self.assertEqual(len(transitions),3)
        ids={t['id'] for t in transitions}
        for i in range(3):self.assertTrue(ids.intersection(primary['segments'][i]['extra_material_refs']))
        self.assertTrue(all(t['name']=='叠化' and t['effect_id']=='322577' and t['duration']==333333 for t in transitions))
        self.assertEqual(len(materials['video_effects']),1)
        self.assertEqual(materials['video_effects'][0]['effect_id'],resolve('effect',{'name':'1998'}).value.effect_id)
        effect=next(t for t in content['tracks'] if t['type']=='effect')['segments'][0]
        self.assertEqual(effect['target_timerange'],{'start':166667,'duration':1500000})
        filtr=next(t for t in content['tracks'] if t['type']=='filter')['segments'][0]
        self.assertEqual(filtr['target_timerange'],{'start':2333333,'duration':1333334})
        self.assertEqual(next(m for m in materials['effects'] if m.get('type')=='filter')['value'],.35)
        self.assertEqual(c.read(package/'draft/draft_info.json'),c.read(package/'draft/draft_content.json'))
        self.assertEqual(c.read(package/'manifest.json')['validation']['app_open'],'pending')

    def test_unsupported_scope_unknown_resource_and_bad_time_block_plan(self):
        for name,edit in [('scope',lambda b:b['shots'][0]['jianying']['transition_out'].update(scope='whole_scene')),
                          ('unknown',lambda b:b['shots'][0]['jianying']['transition_out'].update(name='missing_xyz')),
                          ('time',lambda b:b['shots'][0]['jianying']['effects'][0].update(end_frame=90)),
                          ('params',lambda b:b['shots'][0]['jianying']['effects'][0].update(params=[-1])),
                          ('duration',lambda b:b['shots'][0]['jianying']['transition_out'].update(frames=40)),
                          ('last',lambda b:b['shots'][3].update(jianying={'transition_out':{'name':'叠化','frames':10}}))]:
            ep=self.episode('bad-native-'+name);b=c.read(ep/'composition.json');edit(b);c.save(ep/'composition.json',b)
            self.assertFalse(ob.plan(ep)['valid'],name)
            self.assertFalse((ep/'outputs/jianying').exists())

    def test_native_config_is_never_silently_ignored_in_browser(self):
        ep=self.episode('native-to-web');m=c.read(ep/'episode.json');m['output_target']='web';c.save(ep/'episode.json',m)
        self.assertFalse(ob.plan(ep,'web')['valid'])
        with self.assertRaisesRegex(ValueError,'禁止静默忽略'):c.prepare(ep)

    def test_effect_change_invalidates_plan_approval(self):
        ep=self.episode('effect-approval');b=c.read(ep/'composition.json')
        b['shots'][1]['jianying']['filters'][0]['intensity']=90;c.save(ep/'composition.json',b)
        from production_stage import require
        with self.assertRaisesRegex(ValueError,'确认'):require(ep)

    def test_sprite_frames_share_one_lane_separate_from_background_and_text(self):
        frames=[{'asset':'assets/wave-a.png','hold_frames':10},
                {'asset':'assets/wave-b.png','hold_frames':10}]
        scenes=[]
        for i,play in enumerate(('loop','once')):
            s=shot('S'+str(i+1),'ST-003',{'background':'assets/background.png','sprites':[
                {'id':'hero','playback':play,'frames':frames,'region':[.1,.2,.2,.6]},
                {'id':'static','playback':'static','asset':'assets/neutral.png','region':[.6,.2,.2,.6]}]},i*60)
            s['layers']=[{'id':'label','kind':'text','text':'角色动作','region':[.1,.02,.5,.1],'font_size':24}]
            scenes.append(s)
        ep=fixture('sprite-track-layout',scenes)
        with patch('render_engine.render_html_to_video',side_effect=AssertionError('browser forbidden')):package=ob.export(ep)
        content=c.read(package/'draft/draft_info.json');tracks={t['name']:t for t in content['tracks']}
        for sid,count in [('S1',6),('S2',3)]:
            role=tracks[sid+'_hero'];background=tracks[sid+'_background'];label=tracks[sid+'_label']
            self.assertEqual(len(role['segments']),count)
            self.assertEqual(len(background['segments']),1)
            self.assertEqual(label['type'],'text')
            self.assertEqual(len({role['id'],background['id'],label['id'],tracks[sid+'_static']['id']}),4)
            self.assertFalse(any(n.startswith(sid+'_hero_') for n in tracks))
            for a,b in zip(role['segments'],role['segments'][1:]):
                self.assertEqual(a['target_timerange']['start']+a['target_timerange']['duration'],b['target_timerange']['start'])
        self.assertTrue(check_package(package)['valid'])


if __name__=='__main__':unittest.main()
