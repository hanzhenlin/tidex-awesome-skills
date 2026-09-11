# 🌟 Tidex Awesome Skills

> **一台刚装好 Agent 工具的新电脑，两行命令拥有经过标准化策展的业界顶级明星技能。**  
> 本仓库精选、收纳并工程化标准化业界开源明星级 AI Agent 技能，默认实时拉取原作者最新源码安装，内置高质量快照与 `agents/interface.yaml` 契约兜底，保证任何环境永久可用。

---

## 🎯 这个仓库解决什么问题

刚拿到一台新电脑、装好 Claude Code / Codex / ZCode / Workbuddy 等 Agent 工具后，逐个寻找、鉴别、适配、安装优质技能非常繁琐。本仓库提供：

1. **一份高质量精选清单**：所有收录技能登记在 `registry.txt`，含原作者、上游地址、开源协议与能力契约；
2. **一键全端跨平台安装**：脚本自动探测本机所有 Agent 环境（`~/.agents`、`~/.claude`、`~/.codex`、`~/.zcode`、`~/.workbuddy`）并无损软链挂载；
3. **双源保障与跨平台契约**：
   - **默认实时**：安装时优先 `git clone` 原作者仓库最新源码（保证第一时间获取上游更新）；
   - **快照兜底**：断网或上游访问受限时，自动降级使用仓库内置标准化快照 `skills/`；
   - **接口契约**：所有技能均补齐 `agents/interface.yaml`，跨 Agent Runtime 零障碍解析。

> 本仓库与姊妹仓库 [**`tidex-agent-skills`（Tidex 原创工程技能库）**](https://github.com/hanzhenlin/tidex-agent-skills) 彻底分离：原创自研开发套件请看那边，本仓库专注开源明星神作的策展、标准化与落地。

---

## 🧭 精选明星技能大盘（已收录 8 款顶级神作）

### 🧬 1. 元技能与认知进化操作系统 (Meta & Evolution)

| 技能名称 | 原创作者 / 来源 | 协议 | 技能定位与核心能力 | 常见触发词 |
| :--- | :--- | :--- | :--- | :--- |
| **`nuwa-skill`**<br>(女娲造人) | [花叔 @alchaincyf](https://github.com/alchaincyf/nuwa-skill) | MIT | • 从一手语料（著作/访谈/决策史）蒸馏认知操作系统<br>• 提炼心智模型、决策启发式、表达 DNA 与行为反模式<br>• 内置 15+ 精品人物视角范例（马斯克/乔布斯/费曼等） | `女娲`、`造skill`、`造人`、`蒸馏XX`、`做个XX视角`、`我想提升决策质量` |
| **`yao-meta-skill`**<br>(Skill OS 2.0) | [Yao Team @yaojingang](https://github.com/yaojingang/yao-meta-skill) | MIT | • **Yielding AI Outcomes**：全生命周期技能工程系统<br>• 引入 Skill IR（中间表示）实现多端编译器（OpenAI/Claude/Codex/VS Code）<br>• 严苛 Output Eval Lab 评测实验室 + Review Studio 2.0 门禁看板 | `yao-meta-skill`、`制作skill`、`Skill OS`、`评测skill`、`skill治理` |
| **`darwin-skill`**<br>(达尔文进化) | [花叔 @alchaincyf](https://github.com/alchaincyf/darwin-skill) | MIT | • 借鉴 Karpathy autoresearch 的自主实验进化循环<br>• 吸收微软 SkillLens 9 维静态评分 + SkillOpt 动态验证<br>• 自动化：评估→改进→实测验证→棘轮保留/回滚 | `达尔文`、`darwin`、`优化skill`、`skill评分`、`自动优化`、`skill review` |

---

### 🎨 2. 视觉设计与生产力流水线 (Visual Design & Pipelines)

| 技能名称 | 原创作者 / 来源 | 协议 | 技能定位与核心能力 | 常见触发词 |
| :--- | :--- | :--- | :--- | :--- |
| **`huashu-design`**<br>(花叔设计系统) | [花叔 @alchaincyf](https://github.com/alchaincyf/huashu-design) | MIT | • **HTML 原生设计系统（24k+ Stars 神作，全量资产完整收录）**<br>• 高保真 Web/App 原型、演示幻灯片、交互动画、可视化<br>• 内置 20 种设计哲学、5 维专家评审机制、全套配乐与音效库、MP4 导出 | `设计`、`原型`、`幻灯片`、`PPT`、`动画`、`可视化`、`design` |
| **`huashu-md-html`**<br>(出版级文档流水线) | [花叔 @alchaincyf](https://github.com/alchaincyf/huashu-md-html) | MIT | • 落地「Markdown 生产，多端消费」多向出版级流水线<br>• 任意文件（PDF/DOCX/PPTX/音频/网页）提取转为干净 Markdown<br>• Markdown 加工为出版级 HTML、DOCX、PDF（A4/A5/大32开）、EPUB3 | `md转html`、`出版级排版`、`排版`、`万物转md`、`格式转换` |
| **`huashu-excel`**<br>(数据分析大师) | [花叔 @alchaincyf](https://github.com/alchaincyf/huashu-excel) | MIT | • 严肃数据分析全流程：体检脏表→数据清洗→定口径→算指标→对账→报告<br>• 极简轻量（依赖仅 `openpyxl`），让每个算出来的数字经得起追问 | `数据分析`、`分析表格`、`清洗Excel`、`对账`、`算指标` |
| **`tramstop-skill`**<br>(电车站去AI味) | [花叔 @alchaincyf](https://github.com/alchaincyf/tramstop-skill) | MIT | • 实证驱动的「去 AI 腔」方法论（来自四版本真实盲测对照实验）<br>• 四层 AI 味诊断：词汇层、句式层、结构层、经验层<br>• 结构外科手术 + 真实经验素材注入，拒绝假大空套话 | `去AI味`、`AI味太重`、`像AI写的`、`没人味`、`降AI感`、`humanize` |

---

### 👤 3. 标杆级认知操作系统 (Persona OS)

| 技能名称 | 原创作者 / 来源 | 协议 | 技能定位与核心能力 | 常见触发词 |
| :--- | :--- | :--- | :--- | :--- |
| **`zhangxuefeng-skill`**<br>(张雪峰视角) | [花叔 @alchaincyf](https://github.com/alchaincyf/zhangxuefeng-skill) | MIT | • **女娲蒸馏的爆款标杆（10k+ Stars）**<br>• 沉淀张雪峰核心心智模型与决策启发式（成本收益、壁垒考量、阶层跃升路径）<br>• 作为深度思维顾问，分析高考填报、考研择校、求职与职业规划决策 | `张雪峰`、`用张雪峰的视角`、`雪峰视角`、`考研抉择`、`职业规划` |

---

## ⚡ 快速开始（新电脑装机）

```bash
# 1. 克隆本仓库
git clone https://github.com/hanzhenlin/tidex-awesome-skills.git
cd tidex-awesome-skills

# 2. 交互式安装（推荐）：查看菜单并按需挑选，或输入 a 一键全装
bash install.sh
```

脚本会自动探测本机的 **Claude Code**（`~/.claude`、`~/.agents`）、**Codex**（`~/.codex`）、**ZCode**（`~/.zcode`）、**Workbuddy**（`~/.workbuddy`）等所有 Agent 宿主目录，以软链接方式无损挂载。

### 更多安装方式

```bash
# 脚本化一键全装（跳过菜单，适合自动化初始化脚本）
bash install.sh --all

# 只装指定的某几个技能
bash install.sh nuwa-skill darwin-skill yao-meta-skill

# 安装到特定项目的 .agents/skills（随代码库供团队即时共享）
bash install.sh --target /path/to/project/.agents/skills
```

---

## 🛡️ 冲突安全策略（绝不破坏现有环境）

安装时如果检测到目标位置已有同名技能，按以下分层策略处理：

| 检测到的情况 | 交互模式（默认） | 静默模式（`--all` / 非终端） |
| :--- | :--- | :--- |
| 本套件之前挂载的软链 | 自动保持同步 | 自动保持同步 |
| 外来软链 / 实体目录 | 逐个询问：`r` 备份替换 / `k` 保留 / `a` 全部替换 / `s` 全部跳过 | **默认跳过保留用户版本**，并在账单中明确列出 |
| 同一上游仓库的 git 克隆 | 额外提供「就地 `git pull` 升级」选项 | 同上，默认跳过 |
| 强制覆盖模式 | — | 加 `--force` 参数改为「先完整备份为 `.bak_时间戳` 再替换」 |

> **安全承诺**：任何替换动作都会执行完整备份，绝不静默销毁您的现有文件。

---

## 🧰 常用维护命令

```bash
bash install.sh              # 交互式菜单安装
bash install.sh --all        # 一键全量安装
bash install.sh -l           # 查看登记表与全端挂载状态大盘
bash install.sh -d           # 【环境医生】全系统宿主环境体检（排查死链/垃圾备份/非标目录）
bash install.sh -d --fix     # 一键安全清理失效死链与历史备份残留
bash install.sh -u           # 安全卸载（仅清理本套件软链，不伤用户配置）
./uninstall.sh               # 快捷卸载脚本
./sync.sh                    # 【策展人工具】从各上游自动刷新内置快照
```

---

## 🙏 致谢与版权声明

本仓库收录的所有技能版权完全归原作者所有，各技能均严格保留其原始 LICENSE 与署名。衷心感谢开源社区杰出创作者的开拓性贡献：

- 感谢 [**花叔 (@alchaincyf)**](https://github.com/alchaincyf) 创造的 `nuwa-skill`、`huashu-design`、`darwin-skill`、`huashu-md-html`、`huashu-excel`、`tramstop-skill`、`zhangxuefeng-skill` 及其开拓性的 Agent Skills 开源生态体系；
- 感谢 [**姚金刚老师及 Yao 团队 (@yaojingang)**](https://github.com/yaojingang) 创造的 `yao-meta-skill`（Skill OS 2.0）全生命周期技能编译与治理架构。

本仓库工程化套件与脚本采用 [MIT License](./LICENSE)。
