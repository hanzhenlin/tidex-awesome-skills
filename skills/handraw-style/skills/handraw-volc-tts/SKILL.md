---
name: handraw-volc-tts
description: 使用火山引擎或豆包语音为文本及已确认的视频工程生成分段配音和实际时间字幕；保存用户提交的账户密钥，更新Skill时保留本机配置。
---

# 火山语音 · v1.0

使用随包 `scripts/volc_voice.py`，不读取其他本地项目或全局火山CLI。客户端仅需Python 3.10+、FFmpeg和火山语音服务权限；配置管理只需Python，不调用付费服务。

## 账户提交与保存

用户可以提交新版API Key，或旧版AppID＋Access Token。用户明确提交用于保存时，直接保存；不要在回复、日志、方案或工程文件中复述密钥。CLI只接受标准输入JSON、隐藏交互输入或用户明确要求保存的环境变量，不把密钥放进命令行参数、临时文本文件、仓库或安装包。

```powershell
python scripts/volc_voice.py config --interactive
python scripts/volc_voice.py config --from-env
python scripts/volc_voice.py status
```

代理保存用户已提交的凭据时，用执行工具向 `config --stdin-json` 的标准输入直接写JSON，不用shell字符串拼接，关闭终端回显。接受字段是 `api_key`，或同时提交 `app_id` 与 `access_token`；可带非密钥设置 `speaker`、`tts_resource`、`asr_resource`。用户没有提交新密钥时，不从聊天历史或其他项目文件找密钥；已配置环境变量可用于运行，但只有明确保存操作才持久化。

Windows保存于 `%APPDATA%/handraw-video-producer/volc-tts.json`，用当前用户DPAPI加密。更新仓库、重装或同步Skill都不读写此文件。换电脑或Windows账户需重新提交。其他系统采用用户配置文件、0600权限。路径覆盖及认证优先级见[账户与接口](references/account_and_api.md)。成功仅报告“已保存”和配置状态，不显示密钥前后缀。

## 视频配音

通过总控 `hvp volc-config`、`hvp volc-status`、`hvp tts <工程>` 使用相同实现。独立入口也可执行：

```powershell
python scripts/volc_voice.py episode "工程目录"
```

视频任务须先通过同包 `handraw-video-producer` 的方案确认、全部视觉素材审查与输出路线检查。读取 `episode.json.narration` 和每镜 `voice_anchor`；没有已确认的音色ID时核对服务控制台可用音色，不猜ID、不切换到Edge。参数格式见[配音工程](references/episode_voice.md)。

- 按镜头语义分段。情绪、节奏、停顿依据本期受众和叙事设计，不固定五阶段，不一律用男声或女声。
- 服务合成后解码为PCM，以采样数测实际时长；不以末句结束点替代文件时长。按请求及资源缓存，每次续作先过阶段检查，再复用音频。
- 用ASR的实际词或句边界生成SRT和timing.json；句级返回不伪装成词级，不按字符比例猜时间。ASR与批准文本不同就保留结果并要求审听，不能静默替换。
- 旁白与停顿超过镜头时，报告镜头编号和所需帧数，不截断、不变速、不修改时间线。AI在已确认方向内重排时间，并核对视频、动作、字幕后续作。请求缓存避免重复合成；失败无自动付费重试。
- 技术成功仍须审听音色、读音、情绪、停顿和字幕。用户审美接受单独记录，离线测试不能证明真实服务或听感通过。

## 独立文本与音频识别

```powershell
python scripts/volc_voice.py tts --text-file "台词.txt" --out-dir "语音输出" --speaker "控制台音色ID" --direction "温和、自然的生活讲述" --speech-rate 0
python scripts/volc_voice.py asr --audio "录音.wav" --out-dir "识别输出" --expected-text-file "台词.txt"
```

独立任务按用户要求执行；输入或输出位于视频工程内时，执行相同开工检查。视频制作始终优先使用 `episode`/`hvp tts`，不得用复制到工程外的独立任务绕过阶段门槛。ASR会向火山服务上传用户指定音频。操作需要相应服务权限和网络；网络执行被拒绝时报告实际原因，不绕过限制。

接口来源、支持边界和离线验证见[账户与接口](references/account_and_api.md)及[验证记录](references/validation.md)。不附带任何真实账号、密钥、付费额度或成片。
