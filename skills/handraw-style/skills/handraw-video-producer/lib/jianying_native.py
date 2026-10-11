"""Authored native resource bindings. Resolve actual metadata; no guessed IDs/downloads."""
import math

GROUPS={'transition':'TransitionType','effect':'VideoSceneEffectType',
        'character_effect':'VideoCharacterEffectType','filter':'FilterType'}


def resolve(kind,spec):
    from jianying_backend import draft_api
    if kind not in GROUPS or not isinstance(spec,dict):raise ValueError('无效剪映资源配置')
    def norm(value):return str(value).casefold().replace(' ','').replace('_','')
    selectors={k:spec[k] for k in ('name','key','resource_id','effect_id') if k in spec}
    if not selectors or any(not isinstance(v,str) or not v.strip() for v in selectors.values()):raise ValueError('需实际名称、key、resource_id或effect_id；编号必须为字符串')
    candidates=[]
    for item in getattr(draft_api(),GROUPS[kind]):
        value=item.value
        fields={'key':[item.name],'name':[item.name,getattr(value,'name',getattr(value,'title',item.name))],
                'resource_id':[value.resource_id],'effect_id':[value.effect_id]}
        if all(any(norm(v)==norm(x) if k in ('name','key') else v==x for x in fields[k]) for k,v in selectors.items()):candidates.append(item)
    if len(candidates)!=1:raise ValueError('剪映'+kind+'名称/编号未知、冲突或不唯一：'+str(selectors))
    return candidates[0]


def summary(kind,spec):
    item=resolve(kind,spec);v=item.value
    return {'kind':kind,'key':item.name,'name':getattr(v,'name',getattr(v,'title',item.name)),
            'resource_id':v.resource_id,'effect_id':v.effect_id,'vip':getattr(v,'is_vip',None),
            'app_resource_available':'not_verified','draft_binding':'implemented'}


def primary_layers(scene):
    if scene['type'] in ('ST-001','ST-002'):return [l for l in scene['layers'] if l['id']=='main']
    if scene['type']=='ST-003':return [l for l in scene['layers'] if l['id']=='background']
    if scene['type']=='ST-004':return [l for l in scene['layers'] if l['id'].startswith('full_') and 'sequence_index' in l]
    return []


def interval(scene,spec):
    n=scene['end_frame']-scene['start_frame'];a=spec.get('start_frame',0);b=spec.get('end_frame',n)
    if type(a)!=int or type(b)!=int or not 0<=a<b<=n:raise ValueError('原生效果显示区间需镜头内整数帧')
    return a,b


def validate_scene(scene,next_scene=None):
    cfg=scene.get('jianying',{})
    if not isinstance(cfg,dict) or set(cfg)-{'effects','filters','transition_out'}:raise ValueError('未知剪映原生配置字段')
    result=[]
    for field,default in (('effects','effect'),('filters','filter')):
        items=cfg.get(field,[])
        if not isinstance(items,list):raise ValueError(field+'需列表')
        for spec in items:
            if not isinstance(spec,dict):raise ValueError('原生效果需对象')
            permitted={'name','key','resource_id','effect_id','start_frame','end_frame','scope','kind'}|({'params'} if field=='effects' else {'intensity'})
            if set(spec)-permitted:raise ValueError('未知原生效果字段：'+str(set(spec)-permitted))
            if spec.get('scope','scene')!='scene':raise ValueError('独立效果轨道当前只支持scope=scene；不能静默改成其他作用域')
            kind=spec.get('kind',default)
            if kind not in (('effect','character_effect') if field=='effects' else ('filter',)):raise ValueError('原生效果类别不匹配')
            item=resolve(kind,spec);a,b=interval(scene,spec)
            if field=='effects':
                params=spec.get('params',[])
                if not isinstance(params,list) or len(params)>len(item.value.params) or any(p is not None and (type(p) not in (int,float) or not math.isfinite(p) or not 0<=p<=100) for p in params):raise ValueError('特效参数数量或0～100范围无效')
                item.value.parse_params(params)
            else:
                value=spec.get('intensity',100)
                if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=100:raise ValueError('滤镜强度需0～100')
            result.append({**summary(kind,spec),'start_frame':a,'end_frame':b,'scope':'scene'})
    if 'transition_out' in cfg:
        spec=cfg['transition_out']
        if not isinstance(spec,dict) or set(spec)-{'name','key','resource_id','effect_id','frames','scope'}:raise ValueError('无效原生转场配置')
        if spec.get('scope','primary')!='primary':raise ValueError('原生转场当前作用于主画面轨道；多图层整镜转场未适配')
        if next_scene is None:raise ValueError('最后一镜没有后续片段，不能添加片间转场')
        current=primary_layers(scene);following=primary_layers(next_scene)
        if not current or not following:raise ValueError('原生转场两侧需ST-001～004主画面')
        # Transition acts between the last and first actual clips, not entire sequence durations.
        cur=current[-1];nxt=following[0]
        def bounds(s,l):return l.get('start_frame',0),l.get('end_frame',s['end_frame']-s['start_frame'])
        a,b=bounds(scene,cur);c,d=bounds(next_scene,nxt)
        events={e['id']:e['at_frame'] for e in scene.get('events',[])}
        next_events={e['id']:e['at_frame'] for e in next_scene.get('events',[])}
        if cur.get('hide_after'):b=min(b,events[cur['hide_after']])
        if cur.get('show_after'):a=max(a,events[cur['show_after']])
        if nxt.get('show_after'):c=max(c,next_events[nxt['show_after']])
        if nxt.get('hide_after'):d=min(d,next_events[nxt['hide_after']])
        if b!=scene['end_frame']-scene['start_frame'] or c!=0:raise ValueError('转场两侧主画面需在边界连续显示，无空隙')
        frames=spec.get('frames')
        if type(frames)!=int or not 0<frames<=min(b-a,d-c)//2:raise ValueError('转场帧数需正整数，且不超过相邻实际片段较短者的一半')
        result.append({**summary('transition',spec),'frames':frames,'scope':'primary',
                       'next_shot':next_scene['id'],'scope_note':'ST-003作用于背景；其他类型作用于主图/视频，全图序列为末帧到下一镜首帧。字幕、角色和额外图层不随转场。'})
    return result


def add_scene_tracks(api,script,scene,fps):
    from output_backends import frame_us
    cfg=scene.get('jianying',{})
    for field,default,track_type in (('effects','effect',api.TrackType.effect),('filters','filter',api.TrackType.filter)):
        for i,spec in enumerate(cfg.get(field,[])):
            a,b=interval(scene,spec);start=frame_us(scene['start_frame']+a,fps);end=frame_us(scene['start_frame']+b,fps)
            span=api.Timerange(start,end-start);kind=spec.get('kind',default);item=resolve(kind,spec)
            name=scene['id']+'_'+field+'_'+str(i);script.append_track(api.TrackSpec(track_type,name))
            if field=='effects':script.add_effect(item,span,name,params=spec.get('params'))
            else:script.add_filter(item,span,name,intensity=spec.get('intensity',100))
