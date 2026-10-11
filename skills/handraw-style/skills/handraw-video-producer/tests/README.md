# 分镜体系回归

## 可移植安装

`python -m unittest discover -s skills/handraw-video-producer/tests -p test_portability.py -v`

验证源码复制到新位置、不带私有视频目录、仅Python标准库时仍可查询目录及新建工程；缺少工具或显式浏览器路径失效时明确报错。

完整工程/输出路线回归会使用随包图片、字体、测试音，缺少基础夹具时按`test_shots.py`准备确定性技术视频；需要已声明的运行工具，但不读取私有案例目录或生成配音。

## 轻量截图画廊与安装分发

`python -m unittest discover -s skills/handraw-video-producer/tests -p test_gallery_distribution.py -v`

验证无私有案例目录和第三方Python依赖时能构建7张截图的画廊，页面不引用视频，安装同步排除视频但保留TypeScript。无需生成素材或渲染成片。

真实渲染与像素/流程验收使用以下脚本，不调用付费素材或配音：

```powershell
python skills/handraw-video-producer/bin/test_shots.py --render
python skills/handraw-video-producer/bin/validate_shots.py --clips
python skills/handraw-video-producer/bin/validate_shot_workflows.py
python skills/handraw-video-producer/bin/validate_shot_motion.py
```

七类实际样片、28秒混合片、像素哈希、续作、竖屏/字幕、原生草稿与运动记录保存在本项目videos/validation。技术证据不能代表审美或剪映应用导出验证。
# 独立剪映交付检查

`python -m unittest discover -s skills/handraw-video-producer/tests -p test_jianying_package.py -v`

用本地PNG及已有视频音轨检查迁移后独立安装（python -S，禁用第三方site-packages）、可编辑文字/声音、双草稿一致、唯一目录防覆盖、损坏/缺失素材、未知引用、非法时间、外部遗漏依赖、交付工具损坏和安装失败清理。效果检索只查真实元数据，不证明软件资源可用。与test_output_routes.py一起共15项；不渲染动画、不配音、不调用付费生成。

`test_jianying_native.py`另有5项：按名称/ID绑定及冲突拒绝、四类主画面同轨与转场/特效/滤镜结构、作用域与时段拒绝、浏览器不静默忽略原生字段、效果改版确认失效。完整套件共20项；草稿写入验证与剪映实际打开/导出分开。

`test_user_settings.py`另有5项：跨进程及代码副本持久化、临时覆盖不保存、目录缺失/相对路径拒绝、保留其他配置与损坏文件不覆盖、用户目录与CLI保存。素材包用例同时验证项目及独立安装器省略--draft-dir后读取保存位置。当前套件共25项；使用隔离用户配置和草稿目录，不往真实用户草稿箱安装测试工程。

