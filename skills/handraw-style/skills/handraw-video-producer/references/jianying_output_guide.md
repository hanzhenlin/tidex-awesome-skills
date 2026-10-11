# 两条制作路线与剪映草稿

交付、用户反馈修正和轨道整理须执行[镜头审查与交付核对](delivery_review.md)，核对实际导出而非仅看工程配置。结构检查、预览页面审看、应用轨道/画面审看与导出验收分别记录。

方案设计前明确episode.output_target=web|jianying；总控分别分派浏览器制作或剪映制作Skill。shot.render_backend=auto|web|jianying是实现请求，不能代替用户对预渲染的同意。

浏览器路线可按已实现能力使用七类分镜，输出MP4；明确剪映逐镜实现不支持，报告并阻止。

剪映路线默认原生，限ST-001～004并逐项检查配置：基础图片、视频、透明PNG、静态矢量、可编辑文字、字幕、显式音轨、区域与透明度关键帧可原生。有规律运动、旋转、连续笔画/特效、复杂裁切、HTML、Remotion、两种白板当前不能直接原生。即使编号在1～4也不保证所有效果都支持。auto或web请求遇到原生缺口都报告并阻止，不自动生成网页缓存；明确原生且不支持仍阻止。

绘本核心布局（纸色、居中完整插画、下方可编辑短句、小标题、轻微运镜）按ST-001原生制作，见[绘本指南](picturebook_guide.md)。每页对应一个镜头；跨页转场使用真实剪映资源并按主画面作用域检查。基础绘本无需浏览器缓存；可选JS环境效果仍须按下述例外流程处理。草稿结构通过与剪映实际打开/导出分别登记。

## 经用户同意的按镜预渲染

先说明镜头编号、效果、浏览器制作耗时来源及画面合并后不可编辑的限制。确认包含该路线的完整方案后，调用output_backends.record_prerender_approval(ep,真实用户回复,[镜头编号])。记录episode.jianying_prerender_approval{source:human_user,user_reply,shot_ids,plan_signature}；无记录、镜头未在名单或方案改版均不生效。不设--yes或开关替代人类同意。

export-plan分别报告原生、经同意预渲染、被阻止及转场依赖镜头；未获同意时计入blocked_frames，不给出已允许预渲染的误导状态。预渲染仅按镜进行，转场如需读取前镜末帧，在dependency_shots列明。剪映工程的render/mix和全片prepare被阻止；逐镜引擎及草稿导出同样检查授权。

## 剪映内的转场与特效

原生轨道按对象分开：背景、每个sprite、文字、字幕和显式音轨互相独立。同一sprite的有限循环/非循环帧在一条角色轨道按时段排列，非循环结束保持末帧也留在该轨道；不同sprite保持独立遮挡顺序。全图有限帧在一条主画面轨道排列。仅转场涉及的相邻主画面使用hvp_primary共享轨道；无转场连接的镜头按自身background/main轨道组织，不能把其角色或文字塞入主画面轨道。editing-map.json列出轨道名称、片段数量与时间范围，便于查看。

可编辑文字的透明度关键帧及淡入/淡出已接入原生alpha关键帧，文字保持TextSegment，不转成图片。样例《让素材活起来》已检查草稿字段、帧边界与0～1透明度值；剪映内实际显示仍待打开与导出审查。文字缩放、字体替代及全场相机语义继续按具体配置检查。

用户可在剪映中编辑原生图层。当前导出器可按真实名称、resource_id或effect_id写入原生转场、场景/人物特效与滤镜，配置在每镜jianying字段，详见[原生资源配置](jianying_native_resources.md)。独立特效/滤镜轨道包含明确帧区间及参数；转场挂前片段，并将相邻主画面放入同一轨道。ST-003仅背景转场，角色/文字不随转场；多图层整镜转场尚未适配。composition原有transition.dissolve/wipe仍为网页语义，不暗中替换成原生。未配置时保留cut；未知/冲突ID、参数越界、最后一镜片间转场或不支持的作用域会阻止输出。

export-plan只报告素材、实现和阶段状态；export使用已准备的声音/素材，先执行同一开工检查，不隐式生成配音。剪映路线不全片逐帧渲染，不拆已有最终MP4充当原生。缓存按本期视觉输入与实现哈希保存；声音/字幕独立。

ST-003真实帧序列转为互斥图片片段；ST-004保持各完整图停留时间。时间边界按帧号单独转换整数微秒；原速视频明确截取。复杂不适配的类型明确标注，不强行原生。

pyJianYingDraft可选依赖固定上游提交，见lib/vendor/jianying/provenance.json，Apache 2.0版权与许可保留。网页无此Python包仍可执行。

生成版本化包：draft、真实素材、manifest、install.py、中文说明。hvp jianying-install <包> --draft-dir <指定目录>重新绑定绝对路径，只新建唯一草稿，不覆盖。用户在剪映10.9打开并手动导出；不接旧UI自动导出、不承诺CapCut/手机/加密模板兼容。

首次用hvp jianying-config --draft-dir "草稿箱绝对路径"保存，之后hvp jianying-install <包>无需重复传路径；hvp jianying-config可查看。Windows配置文件为%APPDATA%/handraw-video-producer/config.json，独立于仓库、Skill与期工程，仓库更新或同步不删除它。命令行显式--draft-dir优先但只作用本次；目录不存在时停止，不创建/猜测替代草稿箱。独立包含user_settings.py，可用python user_settings.py --draft-dir "目录"保存后运行python install.py .；配置仅留本机，不写入交付包。

已吸收jianying-editor-skill的双文件识别、轨道检查及真实效果查找方法，本地实现详见[独立交付说明](jianying_local_integration.md)。包内包含离线检查器、镜头对照、来源许可；无需外部项目即可检查与安装。hvp jianying-check检查结构、实际素材、哈希和帧边界；生成与安装均实际检查，不再仅因写出JSON就标注结构通过。hvp jianying-resources检索资源；自动写入结构、资源可用性和软件实际导出分别记录，元数据命中不能证明已安装或效果视觉正确。

草稿结构、应用打开、实际导出与审美接受分别记录。此次新体系的应用打开/导出由用户实测后登记；不能继承旧工程验证状态。原生字体和混音仍需应用内检查。仅切换后端且内容/视觉/素材路线不变可保留确认；剪映手工修改不反向同步。
