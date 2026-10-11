# Flow等外部视频：提示词、参考图、回传续作

视频素材格式、真实录屏采集要求及缺视频时的提示词模板见[ST-002 视频素材指南](shot-materials/ST-002-video.md)；其他分镜的图片或动作帧缺项使用[分镜素材目录](shot-materials/README.md)。正式交付按本镜填写完整，并提供实际参考文件。

先确认完整方案，然后只为ST-002外部生成镜头建立video_tasks.json（version=2）。任务绑定shot_id，不使用旧镜头/分类字段。任务含id、purpose、target_duration、prompt_revision、reference_assets、first_state、last_state、instructions_zh、prompts（默认中文说明/英文生成提示词）、audio.keep_original、candidates、selected、exports。

独立提示词完整描述主体辨识特征、场景、手绘特征、建立情境→行动解释→结果交接节拍、镜头运动、首尾状态、画幅、平台实际时长与负面约束。默认不要旁白、字幕或画内文字。参考图必须随任务包实际复制提供；不只给文件名或让用户自行猜测。首尾与相邻镜头连续，动作具体解释概念；保留真实事实。软件教程需要真实录屏时不要用生成提示词替代操作记录。

video-pack只导出已填写任务、中文说明、可复制提示词、实际参考图与回传清单，不调用平台。阶段记录可恢复未回传任务。用户生成后video-import复制候选并保留版本，核对哈希、媒体信息与完整解码，不自动选用。重复导入同文件返回已有候选；部分回传状态可持久恢复。

实际审看后调用video_tasks.select_candidate(ep,clip,candidate_id,review,source_in)，review包含content/identity/action/continuity=pass和notes；比例不符或裁切需framing构图说明。函数同步ST-002 config.asset/source_in/source_out。原声需要显式audio_tracks。新提示词/参考图/截取/时间/构图变化需重核对，不自动沿用旧审查。

全部片段与其他必需画面素材审查通过后才配音、编写本期动画和合成。缺失、损坏、过短、动作不对时继续等待或交付补生成要求。素材路线或核心视觉变化重新确认方案；实际片段允许在已确认方向内精确对齐。

素材策略：auto可无视频；no_video拒绝视频输入与任务；video_only需ST-002视频主画面覆盖每镜。渲染器自行生成的Remotion/白板缓存不是外部输入。外部视频生成质量不由任务流程验证代表。
