# 剪映本地整合与独立交付

## 已吸收内容

|来源|本地用途|边界|
|---|---|---|
|pyJianYingDraft，6bb2d06a|内置固定源码生成图片/原速视频/透明图/帧序列、文字、字幕、音轨与已适配关键帧|无需另装源项目；最终导出依赖桌面剪映|
|jianying-editor-skill，32c56928|吸收draft_info.json与draft_content.json识别、轨道及素材摘要、按真实元数据检索效果|本地实现，不迁入配音服务、云端音乐、旧UI导出或自动Web录制|
|本项目增强|流式哈希校验、悬空引用/时间边界检查、包内素材依赖检查、安全迁移、安装失败不发布|不覆盖、不自动修复用户原工程；不承诺所有软件版本|

来源与许可证位于lib/vendor/jianying及lib/vendor/jianying_editor_methods。本次检查发现固定版本上游的文字片段导出速度ID却未注册素材，本地适配器显式注册该素材；检查器仍拒绝其他未知引用。

## 用户得到什么

版本化ZIP及同名目录，含：

- draft/draft_info.json、draft/draft_content.json：同源一致的明文草稿；draft_meta_info.json。
- draft/assets：实际图片/视频/音频；透明PNG及图形图层保持独立，文字与字幕保留可编辑轨道。
- manifest.json：逐文件哈希、素材映射、制作路线、耗时、验证边界。editing-map.json：镜头与轨道对照。
- install.py和jianying_package.py：只用Python标准库；无需本项目或源Skill即可检查、迁移安装。
- user_settings.py：保存/读取本机草稿箱位置；配置在仓库外，不随交付包分发个人配置。
- 许可、来源记录、中文说明、package-check.json；有字幕时另附SRT。

包内原工程路径只用于追溯；播放素材不得遗漏在外部工程中。压缩包解压后不要直接打开未安装的原草稿，旧绝对路径由安装器在新目录统一绑定。字体不擅自复制或分发，请按本机字体及许可准备；效果资源ID不等于效果二进制素材，不打包剪映云端/VIP资源。

## 执行

```text
hvp export-plan <工程> --target jianying
hvp export <工程> --target jianying
hvp jianying-check <交付包>
hvp jianying-install <交付包> --draft-dir <用户指定草稿目录>
hvp jianying-check <新安装草稿目录>
hvp jianying-resources 模糊 --kind effect --limit 10
```

在另一台机器，解压包后运行：

```text
python jianying_package.py .
python install.py . --draft-dir "你的剪映草稿目录"
```

生成工程需要本项目已有Python/Pillow/FFmpeg等运行环境；独立安装和结构检查只需Python标准库。网页路线不引入剪映运行包。没有外部目录或网络调用。

要记住草稿箱位置：hvp jianying-config --draft-dir "目录"。Windows保存在%APPDATA%/handraw-video-producer/config.json，仓库更新不会覆盖；不传参数查看设置。独立包用python user_settings.py --draft-dir "目录"使用相同配置。此后安装命令省略--draft-dir即可。显式传路径只临时覆盖；保存时验证现有目录，不自动创建草稿箱，安装时再次验证。HVP_CONFIG_DIR可显式指定独立用户配置目录用于测试或受控部署，不是默认仓库配置。

资源查询报告resource_id、effect_id、VIP元数据及未验证状态，供方案设计。已接入每镜jianying字段，选定的原生转场、特效和滤镜会写入草稿，见[配置契约](jianying_native_resources.md)。查询不自动选用或下载，intro/outro仅查询。支持通用元数据绑定不等于所有条目已在剪映实测；JS及ST-005～007规则不变。

## 验证状态

结构检查包含：文件及工具哈希、素材确实打包、主/附加引用完整、目标帧边界换算、同轨重叠、双草稿一致、元信息ID/时长一致；移动后的安装重新检查路径，仅新建唯一目录。

当前本地测试证明工具可在禁用site-packages的Python中执行，不需要两个参考项目。此证据不代表剪映10.9已打开或导出，不证明具体转场/特效、字体、透明边缘与混音的最终视觉质量。应用打开、实际导出、技术审片和用户审美接受分别登记。
