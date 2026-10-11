# 剪映原生转场、特效与滤镜

有名称和ID的原生资源可以直接写入草稿。本项目使用固定上游的真实元数据；无需网页模拟。名称、key、resource_id、effect_id至少填写一种，同时填写时必须对应同一条目；未知、冲突或不唯一时拒绝。

先用hvp jianying-resources检索。示例叠化：resource_id=6724845717472416269，effect_id=322577。资源名称/ID、VIP状态及本机可用性分开，不猜ID，不下载或自动购买资源。

在composition.json的镜头对象中增加：

```json
{
  "jianying": {
    "transition_out": {
      "name": "叠化",
      "resource_id": "6724845717472416269",
      "effect_id": "322577",
      "frames": 10,
      "scope": "primary"
    },
    "effects": [
      {"name": "1998", "kind": "effect", "params": [], "start_frame": 5, "end_frame": 50, "scope": "scene"}
    ],
    "filters": [
      {"name": "1980", "intensity": 35, "start_frame": 10, "end_frame": 50, "scope": "scene"}
    ]
  }
}
```

示例假定每镜60帧、30fps且后面还有镜头；属于配置示例，不是完整镜头对象。参数实际含义和顺序由选定元数据决定。

## 写入规则

- transition_out：前镜向后镜的转场。写在前片段上；主画面片段共用hvp_primary轨道，底纸固定在更下方hvp_paper轨道。镜头时长、截取与原速不改变。frames需正整数，且不超过两侧相邻实际片段较短者的一半；不是整镜时长的一半。
- primary作用域：ST-001主图、ST-002视频、ST-003背景、ST-004最后完整图到下一镜首图。额外文字、角色、字幕不随该转场。多图层整镜转场当前拒绝，不宣称背景转场等于全部图层转场。
- effects：独立特效轨道，scope=scene。kind为effect或character_effect，params按元数据顺序给0～100值或null使用默认；区间为本镜相对帧、结束帧不含。
- filters：独立滤镜轨道，scope=scene，intensity为0～100，起止帧规则相同。两个以上效果各用独立轨道，可叠加。
- 原生效果字段修改参与方案确认签名；声音生成或草稿导出依旧要求完整方案确认与素材审查。时间精调沿用既有时序规则。

export-plan列出native_resources，包括真实ID、作用域、帧数与本机未验证状态；editing-map.json附镜头对照。未知名称/ID、参数/时段越界、最后一镜片间转场、边界显示有空隙、整镜作用域、网页混用未适配时明确报错。不默默去掉效果，不自动转网页预渲染。

浏览器输出不能执行这些剪映原生资源；必须使用其本来支持的效果实现，或改选剪映。原有transition.dissolve/wipe仍是网页语义，不能因视觉名称相近就自动替换。intro/outro入出场动画尚未接入写入，仅可检索。

## 实测边界

技术样例已检查4类主画面同轨、3个叠化转场材料及前片段引用、独立1998特效、1980滤镜、ID、参数、帧时间和包内完整性。无浏览器预渲染、付费素材或配音调用。

这是草稿结构验证。剪映10.9能否找到资源、VIP是否可用、转场的实际边缘行为、特效视觉和最终导出仍需在软件里审看；不把元数据目录全部条目写成已完成视觉验证。
