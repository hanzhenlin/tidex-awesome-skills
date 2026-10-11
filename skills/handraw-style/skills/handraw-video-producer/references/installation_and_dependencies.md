# 安装、自包含范围与外部依赖

## 随包提供

- 七类分镜目录、工程/阶段记录、视频回传流程、动画与剪映适配代码。
- 迁入的Remotion工程、simo DSL、SRT白板源码，锁定的Node依赖清单与许可证。
- Xiaolai字体及OFL许可、7张画廊PNG截图、可复用的示例图片和代码。
- 剪映素材打包、检查、安装工具；不依赖另行克隆的参考项目或开发者本机目录。
- `handraw-volc-tts`火山语音CLI、账户持久保存、分段配音与真实ASR字幕；不要求克隆外部语音项目。

“自包含”指项目资源和实现随包提供，不代表操作系统运行时、软件或在线服务已经安装。`node_modules`、Python环境、浏览器二进制、FFmpeg、剪映及演示视频不随Skill发布。

## 按需要准备

|用途|运行依赖或服务|安装与检查|
|---|---|---|
|浏览画廊、读取规范|浏览器；PNG已随包提供|无需案例工程、视频、FFmpeg或Node.js|
|CLI方案、目录、阶段记录|Python 3.10及以上|运行`hvp catalog --kind shot`|
|图像检查、剪映草稿生成|Python、Pillow；视频/声音检查需要FFprobe，处理媒体时需要FFmpeg|`hvp runtime-install --engine base`|
|浏览器成片ST-001～004|Python、Pillow、Playwright、已安装Edge/Chrome/Chromium、FFmpeg/FFprobe|`hvp runtime-install --engine browser`|
|ST-005 Remotion|上项及Node.js/npm、随附锁文件对应Node包|`hvp runtime-install --engine remotion`|
|ST-006 simo白板|上项及Node.js/npm、随附rough.js等Node包|`hvp runtime-install --engine simo`|
|ST-007 SRT白板|浏览器合成依赖及NumPy、OpenCV、Pillow|`hvp runtime-install --engine srt`|
|明确选择Edge配音|edge-tts、网络服务；FFprobe测实际时长|`hvp runtime-install --engine edge`|
|火山配音及实际字幕|同包handraw-volc-tts、Python标准库、FFmpeg、TTS/ASR服务权限与账户|`hvp runtime-install --engine volc`检查运行时；`hvp volc-config --interactive`保存本机账户；`hvp tts`生成|
|图片生成、Flow视频|用户指定的服务、权限与账号|服务和账号不随包提供，也不自动替换；按方案准备本期素材|
|剪映最终导出|用户安装桌面剪映及所需字体/效果资源|交付草稿与素材包，由用户打开并导出|

Skill不会自行安装这些依赖。用户明确执行`runtime-install`才访问包仓库安装相应依赖；渲染期间不自动下载浏览器或软件。浏览器Python依赖也随Remotion/simo/SRT的显式安装准备，避免仅安装Node包后误报可制作。

## 可移植配置

- FFmpeg/FFprobe从PATH读取；也可分别设置`HVP_FFMPEG`、`HVP_FFPROBE`。
- 浏览器优先使用`HVP_BROWSER`指定的可执行文件，其次查PATH和系统标准安装目录；Playwright可选择`HVP_BROWSER_CHANNEL`。未找到时明确报错。
- 字体测量可设置`HVP_FONT`；默认检查系统字体并使用随包字体作为后备。剪映可编辑文字实际字体需在用户电脑检查，不把测量通过当作视觉验收。
- `HVP_WORKSPACE`可指定新工程保存位置，不要求用户已有开发者的`videos`目录。既有工程可直接用其绝对路径执行。
- 剪映草稿箱保存在用户自己的配置目录，图库路径也属于用户本地配置，不随Git或交付包发布。
- 火山账户保存于仓库外用户目录，Windows使用DPAPI当前用户加密；Skill更新与同步不覆盖。`volc-config --stdin-json`接收用户提交，`--from-env`显式保存环境配置。客户端随包提供不等于免费额度、网络和服务权限已验证。

## 本地验收与发布文件

示例图片可随包提供，示例视频不提供。完整工程回归所需的技术视频由本地夹具脚本按确定性图片生成，不读取私有案例目录，不调用付费生成或配音。实际案例成片、个人工程、用户配置和运行缓存保留在本机。

运行`scripts/audit_release.py`检查Git当前提交候选文件，涵盖已跟踪和未忽略的新文件；报告只给文件/行号和问题类别，不打印密钥值。此扫描不证明所有历史提交均无敏感信息，也不代替图片人工审看。
