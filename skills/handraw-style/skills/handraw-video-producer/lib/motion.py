"""Flat authored layers shared by the browser and the Jianying adapter."""
import copy
import math

BASIC = ('image', 'video', 'sprite', 'text', 'highlight', 'path')
EASINGS = ('linear', 'ease_in', 'ease_out', 'ease_in_out')


def ease(p, name='linear'):
    if name == 'ease_in': return p*p
    if name == 'ease_out': return 1-(1-p)*(1-p)
    if name == 'ease_in_out': return 2*p*p if p < .5 else 1-2*(1-p)*(1-p)
    if name != 'linear': raise ValueError('Unknown easing: '+str(name))
    return p


def sample(keys, frame, field, default):
    if not keys: return default
    if frame <= keys[0]['at_frame']: return keys[0][field]
    a = keys[0]
    for b in keys[1:]:
        if frame <= b['at_frame']:
            p = ease((frame-a['at_frame'])/(b['at_frame']-a['at_frame']), b.get('easing','linear'))
            if isinstance(a[field],list): return [x+(y-x)*p for x,y in zip(a[field],b[field])]
            return a[field]+(b[field]-a[field])*p
        a=b
    return a[field]

def validate_motion(m,duration):
    kind=m.get('type');a=m.get('start_frame');b=m.get('end_frame')
    if kind not in ('translate','oscillate','orbit','path') or type(a)!=int or type(b)!=int or not 0<=a<b<=duration:
        raise ValueError('有规律运动需明确type、start_frame和end_frame')
    def pair(p):return isinstance(p,list) and len(p)==2 and all(type(x) in (int,float) and math.isfinite(x) for x in p)
    if kind=='translate' and not pair(m.get('delta')):raise ValueError('translate需要delta')
    if kind in ('oscillate','orbit'):
        if not pair(m.get('amplitude' if kind=='oscillate' else 'radius')) or type(m.get('period_frames'))!=int or m['period_frames']<=0:raise ValueError('周期运动需振幅/半径与period_frames')
        if not isinstance(m.get('phase',0),(int,float)) or not math.isfinite(m.get('phase',0)):raise ValueError('phase无效')
    if kind=='path' and (len(m.get('points',[])) not in (2,4) or not all(pair(x) for x in m['points'])):raise ValueError('轨迹需2个直线点或4个三次贝塞尔控制点')


