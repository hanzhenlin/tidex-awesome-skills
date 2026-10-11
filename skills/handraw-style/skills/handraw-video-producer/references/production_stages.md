# 方案确认与开工检查

production.json保存version=1、plan{path,revision,complete}、approval、inventory_complete、visual_assets。

方案开始前先确定output_target=web|jianying并读取相应制作Skill；声音、素材与确认门槛共用。剪映预渲染仅在用户真实同意具体镜头后记录jianying_prerender_approval，绑定当前方案签名与镜头编号，不能用auto、web字段或已有缓存替代同意。调整素材/视觉路线仍须确认完整方案。

AI先提交完整plan.md与script.txt，记录用户对具体方案的真实回复，再调用production_stage.record_approval。禁止伪造确认、自动推断或提供--yes绕过。工程测试记录用户明确授权的测试计划，和正式内容确认区分。

确认签名包含方案/脚本哈希、brief/visual/素材策略/画幅/声音方向、镜头目的/类型/内容意图、视频首尾任务。修改已确认内容后旧确认失效。仅输出后端切换、实际配音后的时间对齐或选用已批准路线的候选可以继续；改变内容或视觉路线先更新方案并重新确认。

visual_assets每项{id,kind,path,required,review}；kind=image/video/recording/action/data。所有镜头使用的素材与视频参考图须完整盘点；动作帧、真实数据、提供的标注和SRT也属于输入。配音、动画代码、渲染文件以及制作阶段生成的对齐标注不作为前置材料。

review_asset需实际画面或数据审查通过与说明，同时记录哈希/技术检查。视频完整解码与实际身份/动作/衔接审看均必须通过；文件变化需重审。外部任务用video_task引用逻辑任务，回传候选不能自动视作通过。

所有tts/prepare/render/mix/build/export以及逐镜缓存生成调用require。未确认仅调研方案；确认后仅收集画面与交付任务；全部必需输入通过才进入制作。不使用占位素材预演。缺少production.json或旧工程均不能执行。期内制作脚本需调用同一require；新增文件不能绕过门槛。
