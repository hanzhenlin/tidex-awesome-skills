# 配音工程字段与续作

统一视频保持 `composition-v2`。在完整方案中选定 `narration.provider=volc` 和声音方向；具体音色ID应核对控制台，示例字段中的 `控制台音色ID` 不可直接调用。

```json
{
  "narration": {
    "enabled": true,
    "provider": "volc",
    "direction": "温和自然，节奏适合本期受众",
    "volc": {
      "speaker": "控制台音色ID",
      "speech_rate": 0,
      "pause_after": 0.4,
      "subtitle_max_chars": 16
    }
  }
}
```

每镜 `voice_anchor` 是该镜批准台词；全部台词按顺序拼接需与 `script.txt` 一致（核对忽略标点、空白与英文大小写，不忽略词语）。静音镜头可不填台词，但整个有旁白工程不能为空。

每镜可有 `voice: {direction, speech_rate, pause_after}` 覆盖全片默认。以内容节拍设计，不把固定情绪阶段或0.4秒当美学要求。此实现按现有镜头起始帧安排声音，未用时段补静音；长停顿应审听并由AI重排，不能把“能放进镜头”当节奏通过。

`narration.volc.speaker` 优先，其次 `narration.voice`，再其次本机保存的默认speaker。旧工程中没有具体ID时先核对再填写。声音方向或类型变更需按总控确认规则处理。

## 输出与续作

1. `hvp tts <工程>` 先检查方案、素材、输出路线及台词；合成请求前检查FFmpeg。按镜头生成并核对实际字幕。
2. 缓存位于 `work/volc-voice/clips/<请求哈希>`，含业务请求、音频回执、MP3/WAV、ASR响应、实际字幕。相同有效请求直接复用，不因重启对话而重复计费。ASR失败后保留TTS，续作只补识别。
3. `work/volc-voice/measurements.json`列每镜实测秒数、包含停顿的最小帧数和原时长。超时先阻止绑定，用户方向内调整分镜后重跑；程序不移动sprite、事件或视频截取点。AI需检查调整后的所有这些时间配置。
4. 全部符合现有时间线时，合成到 `assets/audio/volc-narration-<哈希>.wav`，更新 `narration.path`、`actual_voice`、`composition.subtitle_cues` 和 `work/timing.json`。不改方案、镜头长度、原速和字幕显示策略，不覆盖原素材。
5. 有现存 `narration.path` 的总控沿用该音频，核对实际时间。重新配音须明确版本管理，不直接删旧文件。独立入口拒绝覆盖已有绑定。

ASR返回只有句级边界时保留整句，不按长度拆出假词级时间；返回词级时按真实词边界分行。文本不一致时保留服务原文及响应，人工审听后决定修正、重录或复核缓存，不能用字符相似度阈值自动改成批准台词。

客户端日志和工程输出不含认证字段。账户配置与生成音频分开存放，更新Skill只同步实现。没有成功调用真实服务时，交付记录须注明服务/声音仍待验证。
