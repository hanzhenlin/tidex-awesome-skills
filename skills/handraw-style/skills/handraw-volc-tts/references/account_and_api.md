# 账户、接口与来源

## 本机配置

- Windows：`%APPDATA%/handraw-video-producer/volc-tts.json`，DPAPI当前用户加密；文件包含版本、加密格式和密文，不保存明文密钥。
- Linux/macOS：`$XDG_CONFIG_HOME/handraw-video-producer/volc-tts.json`，默认 `~/.config`，0600权限。此实现不是跨平台密钥链。
- `HVP_VOICE_CONFIG_DIR` 可指定仓库外绝对目录；禁止位于Git仓库或Skill内。Skill同步与发布排除凭据文件，即使误放也不随包发布。
- 环境 `VOLC_API_KEY` 优先；其次完整 `VOLC_APPID`＋`VOLC_ACCESS_TOKEN`；最后保存的账户。环境变量只用于当次调用，`config --from-env` 才保存。不能把环境账户和保存账户拼成一对。
- 新版Key与旧版账户切换时替换整组认证，不把旧Key继续用于新账户。设置更新保留其他设置。配置通过原子替换保存，不影响同目录剪映的 `config.json`。
- `config --stdin-json` 从stdin接收JSON；不提供 `--api-key`/`--token` 参数，避免进入shell历史和进程命令行。隐藏输入用 `--interactive`。
- `status`仅打印配置文件位置、是否保存、环境是否可用、来源和非密钥设置。配置状态通过不证明服务权限、额度或网络通过。

## 本次使用的官方接口

客户端自主编写，提取本项目临时脚本的分段合成与真实时间原则；未复制或调用其他本地CLI的实现，不依赖其绝对路径。Python标准库实现HTTP、DPAPI及PCM处理，FFmpeg作为另行安装的工具。

- [单向流式语音合成HTTP](https://docs.volcengine.com/docs/DoubaoVoice/unidirectional-streaming-text-to-speech-http?lang=zh)：固定HTTPS `/api/v3/tts/unidirectional`，默认 `seed-tts-2.0`。音色由控制台确认；`speech_rate` 为整数偏移，默认0，`context_texts`用于支持该参数的2.0音色。
- [录音文件极速版识别API](https://www.volcengine.com/docs/6561/1631584?lang=zh)：固定HTTPS `/api/v3/auc/bigmodel/recognize/flash`，默认 `volc.bigasr.auc_turbo`；`X-Api-Sequence=-1`，支持本地音频Base64提交。需单独开通ASR资源权限。最大100MB、两小时；本实现按镜头处理短音频。
- 新账户采用 `X-Api-Key`；旧TTS采用 `X-Api-App-Id` 和 `X-Api-Access-Key`，旧ASR为 `X-Api-App-Key` 和 `X-Api-Access-Key`。请求ID每次新建。

资源ID可以显式配置，但必须由用户服务控制台和当前官方文档确认；不能在服务拒绝后偷偷换资源。HTTP/服务错误仅记录数字错误码；不打印鉴权头、原始代理异常或远端错误正文。没有自动重试、自动创建账号、音色克隆或计费平台操作。

## 文件契约

每个合成请求以文本、音色、方向、语速、资源ID和实现版本计算缓存键；账户密钥不写入请求记录或哈希输入。音频回执记录SHA256，损坏缓存报错，不自动付费重做。ASR缓存使用PCM哈希和识别资源；原始响应留在本期工作目录供核对。

`request.json`只保存业务请求体；音频是MP3及24000Hz单声道16位PCM WAV；`timing.json`含秒时间边界及实际粒度，`subtitles.srt`使用真实边界。字幕不是声纹，也不把完整服务响应作为制作方案。
