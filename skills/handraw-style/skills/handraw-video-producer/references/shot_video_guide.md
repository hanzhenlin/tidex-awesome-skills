# 分镜工程指南 · composition-v2

素材准备先读[分镜素材目录](shot-materials/README.md)，再按ST编号打开独立文档；目录字段`material_guide`提供入口。配置示例用于说明输入格式，不能把示例文件当本期已具备的素材。

## 文件与入口

```text
python skills/handraw-video-producer/bin/hvp.py catalog --kind shot
python skills/handraw-video-producer/bin/hvp.py new "标题" --aspect 16:9 --media-policy auto --output-target web
hvp production-status <工程>
hvp asset-check <工程>
hvp video-pack <工程>
hvp video-import <工程> --clip C01 --file <文件>
hvp video-status <工程>
hvp validate <工程>
hvp runtime-status
hvp runtime-install --engine base|browser|edge|remotion|simo|srt
hvp export-plan <工程> --target web|jianying
hvp render <工程>
hvp mix <工程>
hvp build <工程> --target web|jianying
hvp export <工程> --target web|jianying
```

上文 `hvp` 为 `python skills/handraw-video-producer/bin/hvp.py` 简写。仅 new 创建空方案；不调用生成或渲染。依赖安装是独立显式入口。Node 依赖由随附 package-lock 固定，Python 版本见 requirements-shot-engines.txt。运行时不隐式安装。

随包资源、外部工具和服务的完整边界见[安装与依赖](installation_and_dependencies.md)。新安装无需已有`videos`目录；`new`按方案创建期工程。可设置`HVP_WORKSPACE`选择工程保存位置。实际渲染需要FFmpeg/FFprobe与浏览器，Remotion/simo另需Node.js；`runtime-status`逐项报告，不用开发者机器的工具路径。

新建前必须由用户确定--output-target web|jianying，CLI不再缺省选择。总控分派浏览器或剪映制作Skill；后者默认仅ST-001～004及可原生配置，其他类型/JS效果阻止导出，不自动预渲染。已有工程的output_target保留；未填写字段的历史统一工程仍按原web读取，不批量改写。明确切换输出须先检查方案与能力。

`episode.json`：workflow=composition-v2，title、brief（受众/目标/依据/脚本结构等）、visual、width/height/fps、media_policy、output_target、narration、subtitle_mode。

`composition.json`：version=2、duration_frames、shots、audio_tracks、subtitle_cues、local_types。镜头连续覆盖 [start_frame,end_frame)，所有事件、图层显示与类型配置采用镜头内帧号。字幕与音轨用全片帧号。

```json
{"id":"S01","purpose":"让观众理解行动带来的变化","type":"ST-003","start_frame":0,"end_frame":120,"voice_anchor":"第一句","intent":{"action":"挥手回应"},"config":{"background":"assets/bg.png","sprites":[{"id":"hero","playback":"loop","frames":[{"asset":"assets/a.png","hold_frames":12},{"asset":"assets/b.png","hold_frames":12}],"region":[0.1,0.2,0.3,0.6],"start_frame":0,"end_frame":120,"contact_anchors":{"foot":[0.5,1]},"z_index":1,"motion":{"type":"oscillate","amplitude":[0.03,0],"period_frames":60,"start_frame":0,"end_frame":120}}]},"layers":[],"events":[],"transition":{"type":"cut","frames":0},"render_backend":"auto"}
```

## 七类配置

ST-001：config.asset 完整图片；region 归一化[x,y,w,h]；keyframes 的 region 控制位置与缩放，rotation_keyframes（度）、opacity_keyframes（0～1）。at_frame 递增，可加 easing=linear/ease_in/ease_out/ease_in_out。fit=contain/cover/stretch，默认contain。

单图动画只列两种模式：**全屏模式**以完整主图组织全屏画面；**绘本模式**在纸底或纯色背景中布置插画区和文字区。两者都以每镜一张完整主图为主体，关键帧动画可选。按镜头设计region、视觉背景和text辅助图层；全屏也须保持主体与安全区，使用cover时说明裁切。模式为ST-001内部编排说明，不新增分类、版式画廊或未经实现的config模式开关。

绘本请求须按[绘本制作指南](picturebook_guide.md)设计：默认纸页留白、居中完整插画、下方短句；多页为多个ST-001镜头。指定图型时按[手绘出图规则](image_prompt_rules.md)生成完整图文画面，config.region对应整页，不重复叠加已有文案，图内文字不可编辑；实际旁白字幕独立。未指定图型时文案、实际旁白字幕与插画默认分层。剪映与浏览器均可组织核心布局，按各自能力选关键帧、转场及可选环境效果；独立文字居中须按真实宽度计算region，不发明mode/align开关。

环境特效为可选辅助图层，按需要及实际实现配置。例如《一片叶子的屋檐》已有期内雨滴与涟漪实现，但不代表任意环境效果已成为通用内置能力。使用本期html图层时须提供确定性时间入口并验证遮挡及区域；缺少实现时明确说明需求。绘本跨页作为多个单图镜头及转场处理，不当作同场景动作帧序列。

ST-002：config.asset、source_in/source_out 秒数必须明确；截取长度与显示时长一致，原速。默认静音；原声另加 audio_tracks，声明截取与gain。不同画幅默认contain；裁切需要构图理由。

ST-003：config.background 和 sprites 数组。每个 sprite 独立id、region、播放、显示区间、motion、contact_anchors及z_index。static 只用 asset；loop/once 用 frames[{asset,hold_frames}]。once 结束默认hold最后帧，可选on_end=hide。不得把循环帧冒充一次性动作。顺序由z_index决定；同一sprites定义中的帧相互排斥，可重复使用同图。

有规律运动：translate + delta；oscillate + amplitude；orbit + radius；两种周期运动需period_frames和可选phase（弧度）。path需2点直线或4点三次贝塞尔点。运动值为归一化位移，需start_frame/end_frame；起点前保持初态，终点后保持终态。可配合独立region关键帧；避免意图冲突。

ST-004：config.frames[{asset,hold_frames}] 至少两张完整图片；hold_frames 总和精确覆盖镜头。一次按顺序播放，不补帧、不拆素材。画面身份/构图的变化须审查，不能用相机横移解释角色变化。

ST-005：config.entry 是本期 TSX 文件，default export React组件；config.props对象；config.inputs 为本期素材列表，将保留 assets/ 路径复制至 Remotion public。组件用 Img/staticFile、useCurrentFrame/useVideoConfig驱动，代码不使用墙钟、未种子随机、CSS动画或音频。code_files 可列同级代码模块。LiveCanvas工程参数由镜头决定，无固定3秒/画幅/封面。

ST-006：config.dsl 可导出迁入 Scene DSL 实例描述，也可 config.scene 为JSON。JSON含 elements、files（贴纸以asset引用）、intervals（每元素[开始帧,结束帧]串行）。保留真实描线、文字逐字擦入和图片擦入；不要称字体为真实书法笔画。共享字体 Xiaolai OFL。无上游品牌/片尾/配音。

ST-007：config.image 清晰线稿；annotation含原图canvas和elements，sequence从1连续；region为原图坐标，reveal含startMs/durationMs/protectedRegions。未来区域及保护区不可提前揭示。config.srt提供真实SRT，元素cue_index选对应cue；也可timing_cues直接提供实际时间。没有SRT时align_narration=true，配音后读取work/timing.json。本期生成的annotation与代码可位于work，不列为前置素材；已有assets里的标注/SRT须盘点。线稿与数据须审核。流式笔迹先墨后彩，编辑代理只用于规划。

镜头内SRT的时间从0起；共享字幕用全片时间。跨多个镜头的SRT先按已确定镜头范围对齐或拆出局部cue；不得直接把全片后段时间当作镜头内时间。不同画幅默认等比容纳线稿与映射标注，重新构图需要同步修改二者。

## 内部图层与事件

每镜 layers 为可选叠加，不是新目录：kind=image/video/text/highlight/path/html。图片asset，文字text，路径points，html为本期entry，均可声明region/opacity/显示帧/关键帧；show_after/hide_after引用events中id及at_frame。相机camera.keyframes用view，转场cut/dissolve/wipe及frames。ST-003的辅助文字/矢量/特效在此设置。独立HTML需ready、__canvas、renderFrame(t)，全尺寸透明叠加且无墙钟依赖；CSS Animation由父级暂停定位。不能把任意复杂HTML视作已验证。

本期新类型 local_types[{id,adapter:"html",entry,status:"implemented",asset_contract}]，镜头type引用该id；入口位于本期；不能覆盖ST共享编号。技术与实际审片后用户选择才收录。

## 字幕与声音

subtitle_mode：burn-in画内、sidecar独立文件、none关闭显示。源画面文字和字幕分开。subtitle_cues为真实字幕帧范围，或读取实际work/timing.json；不推测旁白时间。episode.subtitle_source可直接引用已审查的本期SRT，或将已有本期SRT转成实际cue，同时供ST-007与共享字幕使用。

audio_tracks：path、source_in、start_frame/end_frame、gain、fade_in_frames/fade_out_frames。不自动循环凑时长。网页统一混音限幅；剪映原生音轨需实际导出检查峰值。

引擎缓存键包括输入哈希、类型配置、尺寸/帧率/时长、实现与源提交。缓存完整证明含帧数与文件哈希；不把缓存纳入外部视频输入。
