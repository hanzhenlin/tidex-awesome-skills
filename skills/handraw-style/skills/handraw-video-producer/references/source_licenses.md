# 来源、许可与适配记录

|组件|源提交|来源及许可|本项目适配|
|---|---|---|---|
|LiveCanvas|a04f18f1bd43d1a7434dfbff5a908fe9452ceba4|pengchujin，MIT；vendor/livecanvas/LICENSE、THIRD_PARTY_NOTICES.md|Remotion工程/锁定依赖/帧驱动编排，参数化镜头，无Live Photo/固定时长/固定画幅|
|simon-skills whiteboard-video|3ad0a25127c17da48a0e869c9efbf4136c40848b|trustfuture，MIT；vendor/simo/LICENSE|Scene DSL、rough.js逐笔及贴纸擦入，移除品牌和配音流程，按帧节拍|
|Xiaolai字体|随simo源提交|OFL，vendor/simo/assets/fonts/OFL.txt|保留字体和许可证|
|srt-whiteboard-animation|696a7243c0e6ffb6827676e539c2ca5ebae2bf6b|江哥是老登啊，MIT；vendor/srt_whiteboard/LICENSE|未来区域保护、流式墨/彩，精确画幅/帧数，移除强制末尾全图露出|
|pyJianYingDraft|6bb2d06a713f7b58e1375269daec835a03882086|Apache 2.0，vendor/jianying/LICENSE、NOTICE|独立可选草稿后端|
|jianying-editor-skill方法|32c56928ded4f9e2c2b80e099dc7abb793d2c30b|luoluoluo22，MIT及源项目第三方声明；vendor/jianying_editor_methods/LICENSE|吸收双草稿识别、轨道检查与真实元数据查找；本地重写并增强完整性、独立安装，不依赖JyWrapper或外部目录|
|角色导演方法|随附来源说明|MIT，[版权说明](licenses/stickman-video-director-NOTICE.md)与[许可证](licenses/stickman-video-director-LICENSE.txt)|具象隐喻、动作节拍、身份一致和首尾交接；未引入上游角色或媒体|

每个vendor目录provenance.json记录公开来源及子目录、完整提交、引入文件哈希和适配。Node依赖安装后的软件遵守各自许可证；Remotion有独立许可，不将其宣称为MIT。没有打包上游演示媒体或外部品牌素材。

本地测试橘猫图来自本项目既有2026-10-08案例的原始素材副本，原文件保留；无外部付费生成。示例只证明技术流程，审美接受待用户审看。
