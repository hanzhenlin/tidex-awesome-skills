# ST-002 · 视频：素材准备

先执行[共用缺素材规则](README.md)。录屏、生成视频与其他来源视频均用此类型，但真实性要求不同。

## 所需素材与格式

|素材|必要性|交付格式|要求|
|---|---|---|---|
|实际视频片段|必需|优先MP4/H.264；其他格式实际检查后转兼容副本|画幅、清晰度、动作、首尾状态符合本镜；无损保留原件|
|明确截取记录|必需|composition.json的source_in/source_out秒数|原速覆盖显示时长，不自动循环、冻结或变速补齐|
|生成参考图|任务需要时必需|实际PNG/JPG/WebP|身份/场景/首尾参考，任务包中提供真实文件|
|录屏步骤|录屏路线必需|MD/TXT采集清单|窗口、操作起点、点击路径、成功结果及需要遮挡的信息|
|原声选择|必需说明|关闭，或显式audio_tracks|默认静音画面；原声不自动混入|

参考图只是输入，不能算视频已完成。素材比例不符先报告，默认等比容纳；裁切须明确可见主体与构图，不擅自补帧。

## 文件与配置

推荐`assets/S02/S02_VID01_v01.mp4`。两秒镜头截取原视频1～3秒：

```json
{
  "asset": "assets/S02/S02_VID01_v01.mp4",
  "source_in": 1,
  "source_out": 3,
  "fit": "contain"
}
```

外部生成任务登记`video_tasks.json`，任务绑定实际shot_id及片段ID；使用[既有video-pack/import与审看流程](../external_video_workflow.md)。不要伪造候选检查通过。

## 缺生成视频：正式任务包提示词

任务包说明文件名、目标时长、画幅、需上传参考图、回传目录和原声策略。时长按动作和平台实际能力设计，交接前后留可剪辑余量，不统一要求十秒。

中文说明模板：

```text
S02 / VID01：用{真实提供的参考文件}保持{角色/场景}一致。镜头目的：{内容目标}。{时长}秒，{画幅}。先{建立情境}，再{具体动作}，最后{可见结果与交接状态}。首帧为{状态}，末帧为{状态}，镜头{明确运动或固定}。按{本期手绘视觉特征和概念配色}制作。不生成字幕、旁白、水印或无关文字。平台原声{保留/关闭及用途}。回传S02_VID01_v01.mp4及实际时长。
```

英文生成提示词模板（正式交付填满并独立可读）：

```text
Create a {duration}-second {aspect ratio} shot in {specific hand-drawn visual style and palette}. The subject is {complete identity, outfit and prop description}, in {complete setting}. Use the supplied {reference images and their purposes}.
Opening state: {visible initial pose and situation}. Action beats: establish {situation}; then {concrete action and contact}; finally show {observable result and reaction}. Ending state: {pose, position and handoff to the next shot}. Camera: {framing and precise movement}. Keep {identity, lighting, scale and scene continuity constraints}. Leave {specified head/tail editing room}.
No subtitles, narration, watermarks or invented interface text. Avoid {shot-specific identity drift, impossible action, cropping or continuity errors}. Audio: {explicit ambient-sound policy}.
```

缺参考图时，先交付角色/场景参考生成提示词和实际图，再导出视频任务。不能只提示“用参考图”但不提供文件。

## 缺真实录屏：采集任务替代生成提示词

写明：录哪个软件/页面、窗口尺寸、从什么状态开始、逐步操作、鼠标位置/停留、需要展示的结果、需隐藏的隐私、首尾余量与文件名。软件操作证据必须真实录制，不用Flow虚构UI代替。其他来源视频缺失时列素材来源与使用条件，不默认下载无授权素材。

## 验收与输出路线

- 检查完整解码、实际时长/尺寸、准确截取；实际审看身份、动作、首尾衔接和信息可读性。
- 过短/动作不对：重新生成或在已确认方向内重新编排；不能靠冻结/循环凑数。
- 浏览器与剪映均可原速导入，具体裁切配置需检查。原生转场/特效通过名称/ID配置，不改变视频真实性。
