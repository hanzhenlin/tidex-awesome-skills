# 🌟 Tidex Awesome Skills

> 业界顶级高质量 AI Agent 技能精选库与全端安装套件（Curated Awesome Agent Skills for Claude Code, Codex, ZCode, Workbuddy & Cursor）。  
> 汇聚开源社区最惊艳、最深模块、最经得起考验的明星级 Agent 技能，经标准化工程整理，提供一键全端跨平台安装与管理。

---

## 🎯 仓库定位与策展原则

本仓库与 [**`tidex-agent-skills`（Tidex 原创工程技能库）**](https://github.com/hanzhenlin/tidex-agent-skills) 彻底分离：
- **`tidex-agent-skills`**：专注收录由 Tidex 原创的软件工程开发与代码治理套件（管家、新功能开发、缺陷精修）；
- **`tidex-awesome-skills`（本仓库）**：专注收录开源社区的明星神作，尊重并保留原作者署名与开源协议，进行跨 Runtime 标准化适配（补齐 Agent 接口契约），并提供一键式全端无损安装挂载。

---

## 🧭 精选明星技能大盘

### 🧬 元技能与认知操作系统 (Meta & Perspectives)

| 技能名称 | 原创作者 / 来源 | 技能定位与核心能力 | 常见触发词 |
| :--- | :--- | :--- | :--- |
| **`nuwa-skill`**<br>(女娲造人) | [花叔 (@alchaincyf)](https://github.com/alchaincyf/nuwa-skill) | • 从一手语料（著作/访谈/决策史）蒸馏认知操作系统<br>• 提炼心智模型、决策启发式、表达 DNA 与行为反模式<br>• 内置 15+ 精品人物视角范例（马斯克/乔布斯/费曼/张一鸣等）<br>• 自动运行质量自检与保真度评分 | `女娲`、`造skill`、`造人`、`蒸馏XX`、`做个XX视角`、`我想提升决策质量` |

*(后续将持续引入花叔及社区的 `darwin-skill` 技能进化器、`huashu-design` 原型设计等顶级开源作品)*

---

## ⚡ 快速安装指引

### 方式 A：主流安装法（两步搞定）

在终端中执行以下命令：

```bash
# 1. 克隆本精选库到本地
git clone https://github.com/hanzhenlin/tidex-awesome-skills.git

# 2. 进入目录并执行一键安装
cd tidex-awesome-skills
bash install.sh
```

脚本将自动执行雷达扫描，将精选技能以软链接方式挂载到您电脑上所有已识别的 Agent 宿主目录（如 `~/.agents/skills`、`~/.zcode/skills`、`~/.claude/skills`、`~/.codex/skills`、`~/.workbuddy/skills` 等）。

---

### 方式 B：特定项目挂载（团队工作区共享）

如果希望仅将技能部署在某个特定开发项目的根目录下：

```bash
bash install.sh --target /path/to/your/project/.agents/skills
```

---

### 方式 C：安全卸载（纯净无残留）

如果需要卸载或清理挂载：

```bash
# 执行卸载
bash install.sh --uninstall

# 或直接运行快捷脚本
./uninstall.sh
```
> **安全承诺**：卸载程序只会移除由本套件建立的软链接，绝不影响您的其他技能与自定义配置。

---

## 🙏 致谢与版权声明

本仓库收录的所有技能版权归原作者所有。衷心感谢开源社区杰出创作者的卓越贡献：
- 感谢 [**花叔 (@alchaincyf)**](https://github.com/alchaincyf) 创造的 `nuwa-skill`（女娲造人）及其开拓性的 Agent Skills 生态体系。

本项目采用 [MIT License](./LICENSE) 协议，所有作品严格遵循原作者开源许可与规范。
