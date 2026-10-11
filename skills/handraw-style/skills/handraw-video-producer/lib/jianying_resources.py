"""Read-only lookup of pinned resource metadata, never guesses or downloads IDs."""
GROUPS = {'transition': 'TransitionType', 'filter': 'FilterType',
          'effect': 'VideoSceneEffectType', 'character_effect': 'VideoCharacterEffectType', 'intro': 'IntroType', 'outro': 'OutroType'}


def search(query='', kind=None, limit=20):
    from jianying_backend import draft_api
    api = draft_api()
    if kind and kind not in GROUPS: raise ValueError('未知剪映资源类别')
    if limit < 1 or limit > 100: raise ValueError('limit需在1～100之间')
    rows = []
    for group, enum in GROUPS.items():
        if kind and group != kind: continue
        for item in getattr(api, enum):
            value = item.value
            name = getattr(value, 'name', getattr(value, 'title', item.name))
            if query.casefold() not in (item.name+' '+name+' '+value.resource_id+' '+value.effect_id).casefold(): continue
            rows.append({'kind': group, 'key': item.name, 'name': name,
                         'resource_id': value.resource_id, 'effect_id': value.effect_id,
                         'vip': getattr(value, 'is_vip', None),
                         'availability': 'not_verified_on_target_app',
                         'automatic_export': 'draft_binding_implemented_app_unverified' if group in ('transition','filter','effect','character_effect') else 'not_adapted',
                         'source': 'pinned_pyJianYingDraft_metadata'})
    return {'matches': len(rows), 'results': rows[:limit],
            'note': '转场/特效/滤镜可通过镜头jianying配置写入草稿；检索不下载或自动选用，资源可用性与剪映实际导出另行验证。intro/outro仅查询。'}
