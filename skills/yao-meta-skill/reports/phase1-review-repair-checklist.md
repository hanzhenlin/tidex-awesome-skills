# Yao Meta Skill 第一阶段复核与修复清单

- 复核日期：2026-08-12
- 复核基线：`4cbb6d19f76b556162072070adddb3490017308e`
- 复核分支：`codex/trusted-generation-core-v1`
- 实施范围：M1 可信运行与证据发布、M2 Canonical Skill IR、M3 Provider Output Eval 与三人盲评、M4 触发边界与上下文预算
- 复核方法：方案逐条核对、架构复核、安全复核、差异审查、故障注入、focused tests、当前完整 CI、M1–M4 提交级完整 CI 回放
- 当前结论：本地可闭环问题已修复；真实 Provider 调用与三人独立评审继续保持外部待办；第一阶段质量晋级与 world-class 声明继续保持 `pending`

## 一、总体结果

| 类别 | 数量 | 结果 |
|---|---:|---|
| P1 / 高优先级本地问题 | 9 | 已修复并覆盖回归测试 |
| P2 / 中优先级本地问题 | 10 | 已修复并覆盖回归测试 |
| P3 / 清理与审计项 | 3 | 已处理或形成可审计记录 |
| 外部依赖项 | 2 | 保持 pending，未降低门槛 |
| 当前分支完整 CI | 83 / 83 | 通过 |
| M1–M4 提交级完整 CI 回放 | 4 × 83 | 全部通过 |

## 二、修复清单

| ID | 优先级 | 发现 | 修复结果 | 主要验证 |
|---|---|---|---|---|
| R-01 | P1 | 发布锁采用可残留文件语义，并发与异常退出后可能产生错误阻断 | 改为操作系统 advisory lock；进程退出自动释放；并发发布继续返回稳定错误码 | 并发发布、异常退出、重复发布测试 |
| R-02 | P1 | dry-run 在遗留发布事务存在时会触发恢复写入 | dry-run 保持只读并返回 `recovery-required`；恢复改为显式 `--recover`；publish 可在锁内恢复 | dry-run 零写入、显式恢复、损坏事务测试 |
| R-03 | P1 | 发布在首个 release、镜像刷新和 pointer 更新阶段存在崩溃窗口 | 增加 canonical snapshot、publish transaction、首发恢复、pointer-last 协议和三个崩溃点恢复 | `after-release`、`after-mirrors`、`before-pointer` 故障注入 |
| R-04 | P1 | run artifact 更新存在 artifact、index、manifest 三文件部分写入窗口 | 增加 artifact mutation journal；重入校验前自动回滚到完整旧状态 | artifact 后崩溃、index 后崩溃、恢复后 hash 校验 |
| R-05 | P1 | run、release、raw output 和 canonical report 路径存在 symlink 或路径逃逸风险 | 对现有路径组件执行 symlink 拒绝与 trusted-root 校验；raw output 使用安全创建方式 | `..`、绝对路径、父目录 symlink、raw-output symlink 测试 |
| R-06 | P1 | 正式 ZIP 与 package、registry、benchmark 中的归档 hash 漂移，release lock 可出现假阳性 | 定义非自引用 payload scope；归档排除 report 与 registry checksum consumers；ZIP 写入固定时间戳与权限；一致性闸门直接计算实际 ZIP hash | 连续构建 hash 相同、实际 ZIP ↔ 三份报告 lockstep |
| R-07 | P1 | sync target 会在 attestation 之后重建 ZIP，安装源可能与验证报告不一致 | sync target 保留已验证 ZIP；同步前校验 ZIP SHA256 与 `package_verification.json`；安装精确解压归档内容 | 篡改 ZIP 被拒绝、源码后改动不影响安装字节、portable index 安装测试 |
| R-08 | P1 | 发布包缺少可移植证据入口，本地 `.yao/releases` 路径无法在安装后解析 | ZIP 内生成 portable `.current-run.json` 与 `artifact-index.json`；逐项校验包内报告 hash | portable pointer/index、缺失报告、hash 篡改测试 |
| R-09 | P1 | M3 官方 0/40 状态与旧 10-run 证据混用，benchmark 与 Skill OS 可能显示错误完成 | 新增 `phase1_provider_matrix_complete`、`phase1_human_review_complete`、`phase1_quality_promotion_complete` 与 `phase1_completion_ready`；正式阶段只读取 Phase 1 报告 | provider 0/40 时四项均 false；一致性闸门阻断矛盾状态 |
| R-10 | P1 | world-class operator、Review Studio 和人工评审入口仍指向旧 Provider 与单评审流程 | Phase 1 路由统一为固定 DeepSeek 双模型 matrix、60 秒超时、20 对材料、三份 reviewer packet 与 multi-review finalizer；旧证据标记为 legacy | plan、ledger、intake、preflight、runbook、Review Studio 全链路测试 |
| R-11 | P1 | 盲评包曾携带可推断 with-skill / baseline 的角色信息 | 使用密码学随机 A/B 映射；公开材料仅含中性 variant 与 commitment；answer key 留在 run-private 路径 | 公共包角色泄漏扫描、answer key 隔离、commitment 绑定测试 |
| R-12 | P1 | Reviewer 身份仅靠提交内容自我声明，三人独立性缺少可验证绑定 | finalizer 要求受控 reviewer registry；固定 reviewer-a/b/c；registry 绑定 packet SHA256、submission id 与评审 attestation | 重复身份、错 packet、错 blind-pack、缺失 reviewer 测试 |
| R-13 | P1 | 三人盲评缺少可恢复的正式闭环入口 | 新增 `evidence-finalize-review`；绑定 source run、blind pack、私有 answer key、三份决定和 reviewer registry；支持同 run 的 `--resume` | 完整生命周期、断点恢复、跨 run 拒绝测试 |
| R-14 | P1 | 250,000 token hard cap 仅在请求结束后判断，临界请求可越界 | 每次调用前预留输入估算与模型最大输出；预算不足时记录 skipped failure 并停止下一次调用 | 249k 临界预算、无额外调用、失败 run 留存测试 |
| R-15 | P1 | Provider 异常可能把 HTTP 响应正文带入报告 | 报告仅保留稳定错误分类和脱敏摘要；凭证与响应正文不进入 artifact | 恶意 Provider fixture、secret/response body 泄漏扫描 |
| R-16 | P2 | runner 默认在仓库根目录执行，目标 Skill 语义可能漂移 | runner 显式接收并固定目标 `skill_dir`；Provider、model、thinking mode、temperature、timeout 与输出上限均校验 matrix | 错 Skill、错 Provider、错 model、错参数测试 |
| R-17 | P2 | 正式 blind pack 可能在 40 次调用未完整时生成 | 仅接受 2 模型 × 10 案例 × 2 variant 的精确成功集合；存在重复、缺失或失败 run 时禁止生成材料 | 39/40、重复 case/model、失败 run 测试 |
| R-18 | P2 | IR resolver 仅校验部分顶层字段，嵌套结构和身份一致性不足 | 增加 dependency-free JSON Schema 校验；manifest 与 IR 全量 schema 校验；统一 name、schema、description 和 manifest identity | 错 nested type、缺 required、name/description 漂移测试 |
| R-19 | P2 | 官方消费者仍有直接读取报告和 wildcard IR 扫描路径 | compiler、packager、registry、conformance、Overview、Review Studio 和 evidence consumer 统一使用 resolver；删除 wildcard example fallback | 多候选冲突、显式 source、name-matched fallback、无 wildcard 测试 |
| R-20 | P2 | 证据 provenance 曾引用 amend 后的悬空中间提交 | 最终发布要求 source commit 等于锁内当前 clean HEAD；最终 bundle 的 source commit 通过分支父提交保持可达；发布前后重新校验 run manifest 与 artifact index | source commit 变化、run mutation、dirty publish 拒绝测试 |
| R-21 | P2 | Review Studio 同时展示 legacy 10-run 与 Phase 1 0/40，语义不清 | legacy output eval 明确作为既有基线；Phase 1 Provider、三人评审和 promotion 使用独立字段与 pending 提示 | Output Lab 显示 `external-required`、`0/3`、`promotion pending` |
| R-22 | P2 | `ci_test.py` 的执行顺序可能在 package verification 后再次重建 archive | `package-check` 前移到 registry/package verification 之前；sync target 移除隐式重建 | CI 顺序契约、最终实际 ZIP hash gate |
| R-26 | P2 | ignored `reports/release_snapshots` 会进入 ZIP 和 evidence bundle，测试运行可改变正式包 hash | package 与 evidence source discovery 明确排除本地 release snapshots；正式报告仍由 canonical artifact index 管理 | ZIP snapshot 条目为 0、两次构建 hash 稳定、artifact index scope 测试 |
| R-27 | P2 | package verifier 要求 registry 总体 `ok`，registry 又要求 package verification 通过，旧失败状态会形成循环阻断 | package verifier 直接校验 registry 的 name、version 与 target compatibility；registry 总体状态在 package verification 更新后独立重算 | 从双方 stale-fail 状态恢复到双 pass、metadata parity 测试 |
| R-23 | P3 | 仓库缺少可独立审计的 M1–M4 完整 CI 运行记录 | 2026-08-12 在四个临时 detached worktree 回放对应提交的 83 项完整 CI，四组均通过；本报告记录 commit、命令和结果 | `5bf7efb`、`ac19921`、`4f0e96d`、`4e5cede` 均为 83/83 |
| R-24 | P3 | 当前 host 的系统 make 受未接受 Xcode license 影响 | CLI test runner 优先使用 Command Line Tools make；测试在无需修改系统 license 的环境下完成 | 当前完整 CI 与四提交回放 |
| R-25 | P3 | `tests/tmp*` 遗留目录影响工作区审计 | 验证结束后按 `AGENTS.md` 的精确范围清理 test scratch；保留其他 untracked 文件 | 清理前后目录计数、原工作区状态复核 |

## 三、方案逐项符合性

### M1：可信运行与证据发布

- `.yao/runs/<run-id>`、`.yao/releases/<run-id>`、run manifest、artifact index、publish lock 与恢复协议已实现。
- `evidence-build` 默认 dry-run；`--publish` 要求 clean worktree；`--recover` 提供显式恢复。
- canonical pointer 最后更新；三个指定崩溃点与首次发布恢复均有测试。
- 跨 Skill、并发、路径逃逸、symlink、hash 篡改、run mutation 与 artifact mutation 均覆盖。
- package 使用 portable evidence pointer/index；安装面可在缺少 `.yao` 本地状态时解析官方报告。

### M2：Canonical Skill IR

- `manifest.json.skill_ir_source` 与 manifest schema 已落地。
- resolver 顺序保持为 manifest 显式声明、name-matched `reports/skill-ir.json`、`skill-ir/examples/<name>.json`。
- wildcard 扫描已删除；全量 schema、name、description 和 manifest identity 均校验。
- compiler、packager、registry、conformance、Overview、Review Studio 使用统一 resolver。
- 当前 conformance 为 5/5。

### M3：真实 Output Eval 与三人盲评

- Provider matrix 固定 DeepSeek V4 Flash、V4 Pro、non-thinking、temperature 0、60 秒超时和单次 3,000 output tokens。
- 10 案例、双模型、with/without skill、40 调用的精确集合已固化为执行契约。
- 250,000 token 硬上限在调用前执行保守预算校验。
- raw outputs、private answer key、role-neutral review materials 与公开 evidence artifacts 分区存储。
- 20 对材料、三位注册 reviewer、独立 packet、registry binding、multi-review adjudication 和晋级阈值已实现。
- 当前环境缺少 `DEEPSEEK_API_KEY`，正式状态保持 `external-required`、`0/40`、`0/3`、quality promotion `pending`。

### M4：触发边界与上下文

- frozen holdout 为 30 个案例，包含 12 positive、12 hard negative、6 near-neighbor confusion。
- 当前指标为 precision 1.000、recall 0.917、hard-negative false positive 0；66 个既有案例无回归。
- `SKILL.md` body 为 764 tokens；`SKILL.md + agents/interface.yaml` initial load 为 947 tokens。
- `updated_at` 与 `review_due` 已按发布日和 90 天周期处理。
- embedding 与 cross-encoder challenger 保留在第二阶段。

## 四、CI 与验证记录

### 当前修复分支

| 命令 | 结果 |
|---|---|
| `python3 scripts/ci_test.py` | 83 / 83 通过 |
| `python3 tests/verify_evidence_build.py` | 通过 |
| `python3 tests/verify_output_provider_matrix.py` | 通过 |
| `python3 tests/verify_skill_ir_paths.py` | 通过 |
| `python3 tests/verify_package_verification.py` | 通过 |
| `python3 tests/verify_local_install_sync.py` | 通过 |
| `python3 tests/verify_review_studio.py` | 通过 |
| `python3 tests/verify_evidence_consistency.py` | 通过 |

### M1–M4 提交级回放

回放环境使用独立 detached worktree 与 Command Line Tools make。每组执行 `python3 scripts/ci_test.py`。

| 里程碑 | Commit | 完整 CI |
|---|---|---:|
| M1 | `5bf7efb` | 83 / 83 |
| M2 | `ac19921` | 83 / 83 |
| M3 | `4f0e96d` | 83 / 83 |
| M4 | `4e5cede` | 83 / 83 |

历史 focused-test 控制台日志未随原提交保存。本轮通过提交级完整 CI 回放补足可复核结果；后续里程碑应在提交时同步记录 focused command、exit code、时间和关键 artifact hash。

## 五、外部待办与发布边界

| 待办 | 当前状态 | 完成条件 |
|---|---|---|
| DeepSeek 真实 Provider matrix | `external-required`，0 / 40 | 配置 `DEEPSEEK_API_KEY`，完成固定 40 调用，failure 0，总 token ≤ 250,000 |
| 三人独立盲评 | `human-required`，0 / 3 | 三位注册 reviewer 各完成同一 20 对材料，绑定 packet SHA256，critical failure 0，Fleiss' kappa ≥ 0.40 |

在以上两项完成前：

- `phase1_provider_matrix_complete = false`
- `phase1_human_review_complete = false`
- `phase1_quality_promotion_complete = false`
- `phase1_completion_ready = false`
- world-class ledger 保持 pending
- 1.2.0 可以保留候选工程状态，质量晋级与 world-class 声明不可发布

## 六、最终判断

第一阶段的本地基础设施已经形成完整闭环：生成、隔离、验证、发布、恢复、打包、安装、IR 解析、Provider 执行、盲评、裁决、证据展示和反过度声明均有统一契约与自动化闸门。当前剩余工作集中在真实 DeepSeek 调用和三位真人评审，两项均需要外部输入，系统已用机器可读状态准确表达依赖与门槛。
