---
name: handraw-browser-producer
description: 已选浏览器输出路线时制作手绘视频与绘本视频；执行七类分镜、程序动画、统一合成与MP4验收。与视频总控共用方案和素材门槛。
---

# 浏览器视频制作

由[视频总控](../handraw-video-producer/SKILL.md)在用户明确选择浏览器路线后调用。工程使用composition-v2，episode.output_target=web。先读[分镜工程](../handraw-video-producer/references/shot_video_guide.md)及[素材契约](../handraw-video-producer/references/frame_and_asset_contract.md)。

## 方案与实现

图片提示词与出图沿用[手绘出图规则](../handraw-video-producer/references/image_prompt_rules.md)。指定图型时直接按原图型生成完整图文画面，不能用视频或绘本默认流程拆成无字素材；整页图不重复添加相同文案，独立字幕仍须检查遮挡。

按镜头ST编号读取[分镜素材准备目录](../handraw-video-producer/references/shot-materials/README.md)及对应文档，核对画面输入与文件格式。方案确认后为可生成的缺项交付具体提示词、实际参考图及回传要求；真实录屏和数据等改为采集要求。全部输入审查通过后再生成动画实现、绘制编排与实际配音字幕。

可使用ST-001～007；每镜一个主类型，配合必要辅助图层。ST-001只有全屏或绘本模式，环境特效可选。Remotion、两种白板使用各自锁定的运行时生成逐镜缓存，随后统一合成；不将所有类型描述为同一种浏览器动画。

### 绘本制作

用户要求绘本时必须读[绘本制作指南](../handraw-video-producer/references/picturebook_guide.md)。以多个ST-001镜头组织故事页，采用纸页留白、居中插画、下方短句；每页原始插画与可编辑文案分离，按实际画幅和字体测量排版。基础页面使用现有image/text/region/keyframes与共享字幕、声音，不需要调用白板或Remotion。轻微运镜、显现与跨页叠化按方案编排；雨滴、涟漪、水彩蒙版和纸纹为可选，只有本期实际实现并审片后才可报告通过，不强制复制旧案例代码。任何程序效果均按帧复算，跳转后结果一致。页面故事短句与实际旁白字幕分别排布，避免重叠或重复显示。

完整方案确认、所有画面素材实际审查通过后才编写动画、配音和渲染。Flow任务、素材策略、配音与字幕仍使用[共享阶段](../handraw-video-producer/references/production_stages.md)和[外部视频流程](../handraw-video-producer/references/external_video_workflow.md)，不得另建较宽松门槛。

所有运动按帧确定；保留renderFrame(t)与任意时间跳转。缺少素材、运行时或实现时明确报告，不静默替换。新类型只在本期定义，实际验证后由用户决定是否共享。

## 执行与交付

交付或修改预览时执行[镜头审查与交付核对](../handraw-video-producer/references/delivery_review.md)。实际查看用户指定的案例与素材，区分无字插画和已排版整页；截图/成片、素材卡片与静态布局示意明确标注。页面截图未取得时不能标记视觉通过；检查实际输出关键帧、字号、换行、主体边界与字幕面板，再同步预览、素材引用和验证记录。

通过总控hvp入口执行：export-plan检查；render与mix或export/build输出MP4。export不生成配音；build遵循用户指定服务。不要把render_backend=jianying的镜头交给浏览器自动回退。

火山配音使用同包[火山语音Skill](../handraw-volc-tts/SKILL.md)及hvp tts，不读取外部本地CLI。用户账户保存在仓库外本机配置，更新Skill不覆盖；实际配音超时先重排镜头，不能变速凑时长。

交付成片、预览、封面、字幕与制作记录。检查帧数/时长、完整解码、透明边缘、转场、字幕与音频，技术通过与动态审美接受分别记录。
