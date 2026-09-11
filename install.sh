#!/usr/bin/env bash
# ==============================================================================
# Tidex Awesome Skills - 明星技能精选库 · 一键装机式安装管理脚本
#
# 双源机制：优先实时拉取原作者上游最新源码，失败自动降级仓库内置快照
# 冲突策略：静默模式默认跳过保留用户已有版本（--force 可备份替换）
#           交互模式逐个询问（r 替换 / k 跳过 / a 全部替换 / s 全部跳过）
# ==============================================================================

set -e

# 颜色定义
BOLD="\033[1m"
GREEN="\033[32m"
BLUE="\033[34m"
YELLOW="\033[33m"
RED="\033[31m"
CYAN="\033[36m"
RESET="\033[0m"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGISTRY_FILE="${SCRIPT_DIR}/registry.txt"
SNAPSHOT_DIR="${SCRIPT_DIR}/skills"
CACHE_ROOT="${HOME}/.tidex-awesome-skills/upstream"
GLOBAL_STORE_DIR="${HOME}/.tidex-awesome-skills"

# 运行模式标记
FORCE=false          # --force：静默模式下冲突时备份替换
INTERACTIVE=false    # 交互模式：菜单选择 + 冲突逐个询问
TARGET_DIR=""        # --target 指定的单一目标目录

# 冲突决策（交互过程中动态更新：""=逐个询问 / replace-all / skip-all）
CONFLICT_POLICY=""

# 登记表解析结果（并行数组）
R_NAME=(); R_AUTHOR=(); R_UPSTREAM=(); R_LICENSE=(); R_DESC=()

# 收尾账单
BILL_LINES=()
CONFLICT_LINES=()

# ------------------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------------------

print_banner() {
    echo -e "${BOLD}${CYAN}"
    echo "============================================================"
    echo "         🌟 Tidex Awesome Skills 明星技能精选套件            "
    echo "============================================================"
    echo -e "${RESET}"
}

normalize_url() {
    echo "$1" | tr 'A-Z' 'a-z' | sed -e 's#\.git$##' -e 's#/$##'
}

# 判断路径是否由本套件创建（指向缓存目录或仓库快照目录）
is_own_mount() {
    local t="$1"
    case "$(normalize_url "$t")" in
        *".tidex-awesome-skills"*) return 0 ;;
        *"tidex-awesome-skills/skills"*) return 0 ;;
        *) return 1 ;;
    esac
}

# 读取 git 仓库的 origin 地址（无则返回空）
git_origin_of() {
    git -C "$1" config --get remote.origin.url 2>/dev/null || true
}

is_interactive_tty() {
    [ "${TIDEX_INTERACTIVE:-}" = "1" ] && return 0
    [ -t 0 ] && return 0
    return 1
}

# ------------------------------------------------------------------------------
# 登记表解析
# ------------------------------------------------------------------------------

load_registry() {
    if [ ! -f "${REGISTRY_FILE}" ]; then
        echo -e "${RED}[✗] 未找到技能登记表: ${REGISTRY_FILE}${RESET}"
        exit 1
    fi
    local line
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in
            ''|\#*) continue ;;
        esac
        local name author upstream license desc
        name="$(echo "$line"  | awk -F'|' '{print $1}' | xargs)"
        author="$(echo "$line" | awk -F'|' '{print $2}' | xargs)"
        upstream="$(echo "$line" | awk -F'|' '{print $3}' | xargs)"
        license="$(echo "$line" | awk -F'|' '{print $4}' | xargs)"
        desc="$(echo "$line" | awk -F'|' '{print $5}' | xargs)"
        [ -z "$name" ] && continue
        R_NAME+=("$name"); R_AUTHOR+=("$author"); R_UPSTREAM+=("$upstream")
        R_LICENSE+=("$license"); R_DESC+=("$desc")
    done < "${REGISTRY_FILE}"

    if [ ${#R_NAME[@]} -eq 0 ]; then
        echo -e "${RED}[✗] 登记表中没有任何技能条目。${RESET}"
        exit 1
    fi
}

registry_index_of() {
    local want="$1" i
    for i in "${!R_NAME[@]}"; do
        [ "${R_NAME[$i]}" = "$want" ] && { echo "$i"; return 0; }
    done
    return 1
}

# ------------------------------------------------------------------------------
# 双源解析：优先上游最新（HTTPS→SSH 双通道），失败降级内置快照
# ------------------------------------------------------------------------------

# 尝试浅克隆：先 HTTPS（慢速 25s 自动放弃），失败改走 SSH（国内网络 HTTPS 常超时）
try_clone_latest() {
    local upstream="$1" dest="$2"
    local ssh_url
    ssh_url="$(echo "${upstream}" | sed -e 's#^https://github.com/#git@github.com:#' -e 's#\.git$##').git"

    mkdir -p "$(dirname "${dest}")"
    rm -rf "${dest}"
    if git -c http.version=HTTP/1.1 -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=25 \
         clone --depth 1 "${upstream}" "${dest}" >/dev/null 2>&1; then
        return 0
    fi
    rm -rf "${dest}"
    if git -c http.version=HTTP/1.1 -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=25 \
         clone --depth 1 "${ssh_url}" "${dest}" >/dev/null 2>&1; then
        return 0
    fi
    rm -rf "${dest}"
    return 1
}

resolve_skill_source() {
    local idx="$1"
    local name="${R_NAME[$idx]}"
    local upstream="${R_UPSTREAM[$idx]}"
    local cache_dir="${CACHE_ROOT}/${name}"
    local snapshot_dir="${SNAPSHOT_DIR}/${name}"

    # 1) 上游实时拉取（缓存已存在则 ff 更新，更新失败重新克隆）
    if command -v git >/dev/null 2>&1; then
        if [ -d "${cache_dir}/.git" ]; then
            if git -C "${cache_dir}" pull --ff-only >/dev/null 2>&1; then
                RESOLVED_PATH="${cache_dir}"
                RESOLVED_TAG="上游最新"
                return 0
            fi
        fi
        if try_clone_latest "${upstream}" "${cache_dir}"; then
            RESOLVED_PATH="${cache_dir}"
            RESOLVED_TAG="上游最新"
            return 0
        fi
    fi

    # 2) 内置快照兜底（从 snapshots.lock 读取精确版本锚点展示给用户）
    if [ -d "${snapshot_dir}" ]; then
        RESOLVED_PATH="${snapshot_dir}"
        local anchor=""
        if [ -f "${SCRIPT_DIR}/snapshots.lock" ]; then
            anchor="$(grep "^${name}|" "${SCRIPT_DIR}/snapshots.lock" | head -1 | cut -d'|' -f2,3 | tr '|' '@')"
        fi
        if [ -n "${anchor}" ]; then
            RESOLVED_TAG="内置快照@${anchor}"
        else
            RESOLVED_TAG="内置快照@未锚定"
        fi
        return 0
    fi

    return 1
}

# ------------------------------------------------------------------------------
# 分层冲突处理：返回 DECISION = replace / skip
# ------------------------------------------------------------------------------

resolve_conflict() {
    local dest="$1" idx="$2"
    local name="${R_NAME[$idx]}"
    local upstream="${R_UPSTREAM[$idx]}"
    DECISION="skip"

    # ① 本套件软链：幂等保持（若指向过期可安全重定向）
    if is_own_mount "$(readlink "${dest}")"; then
        DECISION="replace-silent"   # 软链重定向无破坏性，直接重建
        return 0
    fi

    # 静默模式：默认跳过保留用户版；--force 才备份替换
    if ! ${INTERACTIVE}; then
        if ${FORCE}; then
            DECISION="replace"
        else
            DECISION="skip"
            CONFLICT_LINES+=("${name} @ ${dest}（保留用户现有版本；如需覆盖请加 --force）")
        fi
        return 0
    fi

    # 交互快捷策略已定：直接沿用，不再重复询问
    case "${CONFLICT_POLICY}" in
        replace-all) DECISION="replace"; return 0 ;;
        skip-all)
            DECISION="skip"
            CONFLICT_LINES+=("${name} @ ${dest}（按您选择的策略保留现有版本）")
            return 0 ;;
    esac

    # ③ 实体目录同源识别：用户装的就是同一个上游仓库 → 提供就地升级/重定向
    if [ -d "${dest}/.git" ]; then
        local origin dest_n upstream_n
        origin="$(git_origin_of "${dest}")"
        dest_n="$(normalize_url "${origin}")"
        upstream_n="$(normalize_url "${upstream}")"
        if [ -n "${dest_n}" ] && [ "${dest_n}" = "${upstream_n}" ]; then
            echo -e "  ${YELLOW}⚠ 发现同名技能且来自同一上游仓库:${RESET} ${dest}"
            echo -e "    该目录 origin = ${origin}"
            printf "    请选择 [u]就地 git pull 升级 / [r]重定向到本套件托管 / [k]保留跳过: "
            local ans; read -r ans || ans="k"
            case "$ans" in
                u) DECISION="upgrade-inplace"; return 0 ;;
                r) DECISION="replace"; return 0 ;;
                *) DECISION="skip"; return 0 ;;
            esac
        fi
    fi

    # ②/③ 异源冲突：逐个询问 + 快捷策略
    while :; do
        echo -e "  ${YELLOW}⚠ 检测到同名技能已存在（非本套件安装）:${RESET} ${dest}"
        if [ -L "${dest}" ]; then
            echo -e "    类型: 软链接 -> $(readlink "${dest}")"
        else
            echo -e "    类型: 实体目录（可能含您的本地改动）"
        fi
        printf "    请选择 [r]备份后替换 / [k]保留跳过 / [a]本次全部替换 / [s]本次全部跳过: "
        local ans; read -r ans || { ans="s"; CONFLICT_POLICY="skip-all"; }
        case "$ans" in
            r) DECISION="replace"; return 0 ;;
            k) DECISION="skip"; return 0 ;;
            a) CONFLICT_POLICY="replace-all"; DECISION="replace"; return 0 ;;
            s) CONFLICT_POLICY="skip-all"; DECISION="skip"; return 0 ;;
            *) echo -e "    ${YELLOW}无效输入，请重新选择。${RESET}" ;;
        esac
    done
}

# ------------------------------------------------------------------------------
# 挂载单个技能到指定宿主目录
# ------------------------------------------------------------------------------

mount_skill_to_dir() {
    local idx="$1" target_dir="$2" src="$3" tag="$4"
    local name="${R_NAME[$idx]}"
    local dest="${target_dir}/${name}"

    if [ ! -e "${dest}" ] && [ ! -L "${dest}" ]; then
        ln -s "${src}" "${dest}"
        BILL_LINES+=("[挂载成功·${tag}] ${name} -> ${dest}")
        return 0
    fi

    resolve_conflict "${dest}" "$idx"
    case "$DECISION" in
        replace-silent)
            rm -f "${dest}"
            ln -s "${src}" "${dest}"
            BILL_LINES+=("[重定向同步·${tag}] ${name} -> ${dest}")
            ;;
        replace)
            local backup="${dest}.bak_$(date +%s)"
            mv "${dest}" "${backup}"
            ln -s "${src}" "${dest}"
            BILL_LINES+=("[备份替换·${tag}] ${name}（原版已备份: $(basename "${backup}")）")
            ;;
        upgrade-inplace)
            if git -C "${dest}" pull --ff-only >/dev/null 2>&1; then
                BILL_LINES+=("[就地升级] ${name} @ ${dest}")
            else
                BILL_LINES+=("[就地升级失败·已跳过] ${name} @ ${dest}（请手动处理）")
            fi
            ;;
        skip)
            BILL_LINES+=("[保留用户版·已跳过] ${name} @ ${dest}")
            ;;
    esac
}

# ------------------------------------------------------------------------------
# Agent 宿主环境雷达探测（与原创库保持一致的探测矩阵）
# ------------------------------------------------------------------------------

detect_agent_paths() {
    local detected=()
    detected+=("${HOME}/.agents/skills")

    local zcode_path="${HOME}/.zcode/skills"
    { [ -d "${HOME}/.zcode" ] || [ -d "${zcode_path}" ]; } && detected+=("${zcode_path}")

    local claude_path="${HOME}/.claude/skills"
    { [ -d "${HOME}/.claude" ] || [ -d "${claude_path}" ]; } && detected+=("${claude_path}")

    local codex_path="${HOME}/.codex/skills"
    { [ -d "${HOME}/.codex" ] || [ -d "${codex_path}" ]; } && detected+=("${codex_path}")

    local workbuddy_path="${HOME}/.workbuddy/skills"
    { [ -d "${HOME}/.workbuddy" ] || [ -d "${workbuddy_path}" ]; } && detected+=("${workbuddy_path}")

    local current_pwd="$(pwd)"
    if [ "${current_pwd}" != "${SCRIPT_DIR}" ] && [ "${current_pwd}" != "${HOME}" ]; then
        if [ -d "${current_pwd}/.git" ] || [ -d "${current_pwd}/.svn" ] || [ -f "${current_pwd}/pom.xml" ] || [ -f "${current_pwd}/package.json" ]; then
            detected+=("${current_pwd}/.agents/skills")
        fi
    fi

    local unique_paths=($(echo "${detected[@]}" | tr ' ' '\n' | sort -u | tr '\n' ' '))
    echo "${unique_paths[@]}"
}

# ------------------------------------------------------------------------------
# 主安装流程
# ------------------------------------------------------------------------------

do_install() {
    load_registry
    print_banner

    local selected=("$@")
    echo -e "${BOLD}[1/3] 解析技能来源（上游实时优先，快照兜底）...${RESET}"

    local resolved_paths=() resolved_tags=() skill idx
    for skill in "${selected[@]}"; do
        idx="$(registry_index_of "$skill")" || { echo -e "${RED}[✗] 登记表中不存在技能: ${skill}${RESET}"; exit 1; }
        if resolve_skill_source "$idx"; then
            resolved_paths+=("${RESOLVED_PATH}")
            resolved_tags+=("${RESOLVED_TAG}")
            echo -e "  ${GREEN}✓ ${skill}${RESET} [来源: ${RESOLVED_TAG}] -> ${RESOLVED_PATH}"
        else
            echo -e "  ${RED}✗ ${skill}: 上游拉取失败且无内置快照，已跳过${RESET}"
            CONFLICT_LINES+=("${skill}（上游拉取失败且无内置快照）")
        fi
    done

    if [ ${#resolved_paths[@]} -eq 0 ]; then
        echo -e "${RED}[✗] 没有可安装的技能。${RESET}"
        exit 1
    fi

    echo ""
    echo -e "${BOLD}[2/3] 确定挂载目标（全端雷达探测）...${RESET}"
    local target_dirs=()
    if [ -n "${TARGET_DIR}" ]; then
        target_dirs=("${TARGET_DIR}")
        echo -e "  ${CYAN}指定目标: ${TARGET_DIR}${RESET}"
    else
        read -r -a target_dirs <<< "$(detect_agent_paths)"
        local t
        for t in "${target_dirs[@]}"; do
            echo -e "  ${GREEN}[✓] 发现 Agent 宿主路径:${RESET} ${t}"
        done
    fi

    echo ""
    echo -e "${BOLD}[3/3] 开始挂载（幂等软链 + 分层冲突处理）...${RESET}"
    local i target_dir
    for i in "${!resolved_paths[@]}"; do
        # 恢复登记索引（resolved 与 selected 同序，重新取 idx 用于冲突处理中的上游比对）
        idx="$(registry_index_of "${selected[$i]}")"
        for target_dir in "${target_dirs[@]}"; do
            # 交互快捷策略：skip-all 时跳过询问直接保留
            mkdir -p "${target_dir}"
            mount_skill_to_dir "$idx" "${target_dir}" "${resolved_paths[$i]}" "${resolved_tags[$i]}"
        done
    done

    echo ""
    echo "============================================================"
    echo -e "${BOLD}${GREEN}🎉 安装完成！安装账单:${RESET}"
    local line
    for line in "${BILL_LINES[@]}"; do
        echo -e "  • ${line}"
    done
    if [ ${#CONFLICT_LINES[@]} -gt 0 ]; then
        echo ""
        echo -e "${BOLD}${YELLOW}⚠ 冲突/异常清单（默认保留您的现有版本）:${RESET}"
        for line in "${CONFLICT_LINES[@]}"; do
            echo -e "  • ${line}"
        done
        echo -e "  ${YELLOW}如需强制覆盖同名技能，请追加 --force 重新运行。${RESET}"
    fi
    echo "============================================================"
}

# ------------------------------------------------------------------------------
# 交互式菜单
# ------------------------------------------------------------------------------

show_menu_and_select() {
    load_registry
    print_banner
    echo -e "${BOLD}当前精选技能清单（共 ${#R_NAME[@]} 个）:${RESET}"
    echo ""
    local i
    for i in "${!R_NAME[@]}"; do
        echo -e "  ${BOLD}[$((i+1))]${RESET} ${GREEN}${R_NAME[$i]}${RESET}  — ${R_DESC[$i]}"
        echo -e "      作者: ${R_AUTHOR[$i]} | 协议: ${R_LICENSE[$i]} | 上游: ${R_UPSTREAM[$i]}"
    done
    echo ""
    printf "请选择: ${BOLD}a${RESET}=一键全部安装  ${BOLD}编号${RESET}=挑选安装(如 1 或 1,3)  ${BOLD}q${RESET}=退出 > "
    local ans
    read -r ans
    case "$ans" in
        q|Q)
            echo "已退出，未做任何改动。"
            exit 0
            ;;
        a|A)
            SELECTED=("${R_NAME[@]}")
            ;;
        *)
            local part num
            ans="$(echo "$ans" | tr ',，' '  ')"
            for part in $ans; do
                case "$part" in
                    ''|*[!0-9]*)
                        echo -e "${RED}[✗] 无效选择: ${part}${RESET}"; exit 1 ;;
                esac
                num=$((part-1))
                if [ "$num" -lt 0 ] || [ "$num" -ge ${#R_NAME[@]} ]; then
                    echo -e "${RED}[✗] 编号超出范围: ${part}${RESET}"; exit 1
                fi
                SELECTED+=("${R_NAME[$num]}")
            done
            [ ${#SELECTED[@]} -eq 0 ] && { echo -e "${RED}[✗] 未选择任何技能。${RESET}"; exit 1; }
            ;;
    esac
}

# ------------------------------------------------------------------------------
# 卸载 / 状态大盘
# ------------------------------------------------------------------------------

do_uninstall() {
    load_registry
    print_banner
    echo -e "${BOLD}[!] 正在启动安全卸载程序...${RESET}"
    echo -e "将只清理指向本精选库（快照/缓存）的软链接，绝不影响您的其他技能。"
    echo ""

    read -r -a target_dirs <<< "$(detect_agent_paths)"
    local removed_count=0 target_dir skill dest current_target
    for target_dir in "${target_dirs[@]}"; do
        [ -d "${target_dir}" ] || continue
        echo -e "  ${BLUE}▶ 检查目录:${RESET} ${target_dir}"
        local found=0
        for skill in "${R_NAME[@]}"; do
            dest="${target_dir}/${skill}"
            [ -L "${dest}" ] || continue
            current_target="$(readlink "${dest}")"
            if is_own_mount "${current_target}"; then
                rm -f "${dest}"
                echo -e "    ${RED}✗ 已移除软链接:${RESET} ${skill}"
                removed_count=$((removed_count+1))
                found=1
            fi
        done
        [ "$found" -eq 0 ] && echo -e "    ${CYAN}• 无本套件挂载记录，已跳过${RESET}"
        echo ""
    done

    echo "============================================================"
    if [ "$removed_count" -gt 0 ]; then
        echo -e "${BOLD}${GREEN}✔ 卸载完成！共清理 ${removed_count} 处软链接。${RESET}"
    else
        echo -e "${BOLD}${YELLOW}未发现挂载中的本套件技能软链接。${RESET}"
    fi
    echo "============================================================"
}

do_doctor() {
    load_registry
    print_banner
    echo -e "${BOLD}🩺 正在对全系统 Agent 技能宿主环境执行全身体检...${RESET}\n"

    read -r -a target_dirs <<< "$(detect_agent_paths)"
    local broken_links=()
    local backup_items=()
    local non_standard_skills=()
    local external_skills_count=0
    local awesome_mounted_count=0

    local target_dir item item_name
    for target_dir in "${target_dirs[@]}"; do
        echo -e "${BOLD}▶ 检查宿主目录:${RESET} ${CYAN}${target_dir}${RESET}"
        if [ ! -d "${target_dir}" ]; then
            echo -e "  ${YELLOW}• 宿主环境尚未初始化（目录不存在），跳过${RESET}\n"
            continue
        fi

        local dir_clean=true

        # 1. 扫描死链 (Broken symlinks)
        while IFS= read -r -d '' item; do
            if [ -L "${item}" ] && [ ! -e "${item}" ]; then
                broken_links+=("${item}")
                echo -e "  ${RED}[✗ 失效死链]${RESET} $(basename "${item}") -> $(readlink "${item}")"
                dir_clean=false
            fi
        done < <(find "${target_dir}" -maxdepth 1 -type l -print0 2>/dev/null)

        # 2. 扫描历史遗留备份目录 (.bak_*)
        while IFS= read -r -d '' item; do
            backup_items+=("${item}")
            echo -e "  ${YELLOW}[⚠ 历史备份残留]${RESET} $(basename "${item}")"
            dir_clean=false
        done < <(find "${target_dir}" -maxdepth 1 -name "*.bak*" -print0 2>/dev/null)

        # 3. 扫描各技能状态与标准度
        for item in "${target_dir}"/*; do
            [ -e "${item}" ] || continue
            item_name="$(basename "${item}")"
            case "${item_name}" in
                .*|"#SyncVersion"|*.bak*) continue ;;
            esac

            if [ -L "${item}" ]; then
                local link_target
                link_target="$(readlink "${item}")"
                if is_own_mount "${link_target}"; then
                    ((awesome_mounted_count++)) || true
                else
                    ((external_skills_count++)) || true
                fi
            elif [ -d "${item}" ]; then
                ((external_skills_count++)) || true
                # 检查是否缺失标准 SKILL.md
                if [ ! -f "${item}/SKILL.md" ]; then
                    non_standard_skills+=("${item}")
                    echo -e "  ${YELLOW}[⚠ 非标/损坏技能]${RESET} ${item_name} (缺少 SKILL.md 入口)"
                    dir_clean=false
                fi
            fi
        done

        if $dir_clean; then
            echo -e "  ${GREEN}✔ 未发现死链与垃圾残留${RESET}"
        fi
        echo ""
    done

    echo "============================================================"
    echo -e "${BOLD}📋 体检报告与诊断摘要:${RESET}"
    echo -e "  • 🌟 已成功挂载的明星精选技能: ${GREEN}${awesome_mounted_count}${RESET} 处"
    echo -e "  • 📦 本地独立/第三方技能: ${CYAN}${external_skills_count}${RESET} 个"
    echo -e "  • 💔 失效软链接 (Broken Symlinks): ${#broken_links[@]} 处"
    echo -e "  • 🗑️  历史备份垃圾 (.bak 残留): ${#backup_items[@]} 处"
    echo -e "  • ⚠️  缺少 SKILL.md 的非标目录: ${#non_standard_skills[@]} 处"
    echo "============================================================"

    # 发现问题时提供安全修复或自动清理
    if [ ${#broken_links[@]} -gt 0 ] || [ ${#backup_items[@]} -gt 0 ]; then
        if [ "${AUTO_FIX:-false}" = "true" ]; then
            echo -e "\n${BOLD}${GREEN}⚡ 正在自动清理失效死链与历史备份...${RESET}"
            for item in "${broken_links[@]}"; do
                rm -f "${item}" 2>/dev/null && echo -e "  [✔ 已移除死链] ${item}"
            done
            for item in "${backup_items[@]}"; do
                rm -rf "${item}" 2>/dev/null && echo -e "  [✔ 已移除备份] ${item}"
            done
            echo -e "${BOLD}${GREEN}✔ 清理完毕！环境已恢复清爽。${RESET}"
        else
            echo -e "\n${BOLD}🛠️ 修复指引:${RESET}"
            echo -e "  您可以运行 ${CYAN}bash install.sh --doctor --fix${RESET} 自动一键清理；"
            echo "  或者手动执行以下命令:"
            if [ ${#broken_links[@]} -gt 0 ]; then
                for item in "${broken_links[@]}"; do
                    echo "    rm \"${item}\""
                done
            fi
            if [ ${#backup_items[@]} -gt 0 ]; then
                for item in "${backup_items[@]}"; do
                    echo "    rm -rf \"${item}\""
                done
            fi
        fi
    fi

    # 生态联动提示
    if [ "$external_skills_count" -gt 5 ] || [ ${#non_standard_skills[@]} -gt 0 ]; then
        echo -e "\n${BOLD}${CYAN}💡 进阶治理建议:${RESET}"
        echo -e "  检测到您的环境中拥有较多独立/非标技能。如果您需要进行跨 Agent 契约标准化"
        echo -e "  （如补齐 agents/interface.yaml、规范 frontmatter）、代码级治理或任务流水线管理，"
        echo -e "  推荐使用我们的自研开源工程套件:"
        echo -e "  👉 ${BOLD}Tidex Agent Skills (原创库)${RESET}: ${GREEN}https://github.com/hanzhenlin/tidex-agent-skills${RESET}\n"
    fi
}

do_list() {
    load_registry
    print_banner
    echo -e "${BOLD}精选登记表（共 ${#R_NAME[@]} 个）:${RESET}"
    local i
    for i in "${!R_NAME[@]}"; do
        echo -e "  ${GREEN}${R_NAME[$i]}${RESET} — ${R_DESC[$i]}（作者: ${R_AUTHOR[$i]} / 协议: ${R_LICENSE[$i]}）"
    done
    echo ""
    echo -e "${BOLD}宿主环境挂载大盘:${RESET}"
    read -r -a target_dirs <<< "$(detect_agent_paths)"
    local target_dir skill dest
    for target_dir in "${target_dirs[@]}"; do
        echo -e "${BOLD}▶ ${CYAN}${target_dir}${RESET}"
        [ -d "${target_dir}" ] || { echo -e "  ${YELLOW}(目录不存在)${RESET}"; echo ""; continue; }
        for skill in "${R_NAME[@]}"; do
            dest="${target_dir}/${skill}"
            if [ -L "${dest}" ]; then
                echo -e "  [✓] ${GREEN}${skill}${RESET} -> $(readlink "${dest}")"
            elif [ -d "${dest}" ]; then
                echo -e "  [!] ${YELLOW}${skill}${RESET} (实体目录，非本套件软链)"
            else
                echo -e "  [-] ${skill} (未安装)"
            fi
        done
        echo ""
    done
}

# ------------------------------------------------------------------------------
# 帮助与入口
# ------------------------------------------------------------------------------

show_help() {
    print_banner
    cat << 'HELPEOF'
使用方式:
  bash install.sh [选项] [技能名...]

模式说明:
  (无参数, 终端交互)     展示精选清单菜单: a=全部安装 / 编号=挑选安装 / q=退出
  (无参数, 非交互环境)   等同 --all 一键全装
  --all                  跳过菜单，脚本化一键安装全部精选技能
  <技能名>...            按名称安装指定技能（如: bash install.sh nuwa-skill）

冲突策略:
  交互模式              逐个询问: r=备份替换 / k=保留跳过 / a=全部替换 / s=全部跳过
  静默模式(默认)        遇外来同名技能: 跳过保留用户版，账单中列出冲突
  --force               静默模式下改为"备份后替换"

其他选项:
  -d, --doctor          对全系统 Agent 技能宿主环境执行全身体检（排查死链/垃圾备份/非标目录）
  -u, --uninstall       安全卸载本套件挂载的软链接
  -l, --list            查看登记表与各宿主环境挂载状态
  -t, --target <DIR>    安装到指定目录（如某项目的 .agents/skills）
  -h, --help            显示本帮助

双源机制:
  安装时优先 git clone --depth 1 拉取原作者上游最新源码（缓存于 ~/.tidex-awesome-skills/upstream），
  失败（断网/仓库搬家/已删除）自动降级使用仓库内置快照，账单中明确标注实际来源。
HELPEOF
}

main() {
    local args=()
    local run_doctor=false
    while [ $# -gt 0 ]; do
        case "$1" in
            -h|--help) show_help; exit 0 ;;
            -u|--uninstall) do_uninstall; exit 0 ;;
            -l|--list) do_list; exit 0 ;;
            -d|--doctor) run_doctor=true; shift ;;
            --fix) AUTO_FIX=true; shift ;;
            -t|--target)
                [ -z "$2" ] && { echo -e "${RED}[✗] --target 需要指定目录路径！${RESET}"; exit 1; }
                TARGET_DIR="$2"; shift 2 ;;
            --all) args+=("__ALL__"); shift ;;
            --force) FORCE=true; shift ;;
            -*) echo -e "${RED}[✗] 未知选项: $1（--help 查看用法）${RESET}"; exit 1 ;;
            *) args+=("$1"); shift ;;
        esac
    done

    if $run_doctor; then
        do_doctor
        exit 0
    fi

    SELECTED=()
    local has_all=false has_names=false a
    for a in "${args[@]}"; do
        [ "$a" = "__ALL__" ] && has_all=true || has_names=true
    done

    if $has_all && $has_names; then
        echo -e "${RED}[✗] --all 与技能名不能同时使用。${RESET}"; exit 1
    fi

    if $has_names; then
        SELECTED=("${args[@]}")
        INTERACTIVE=false
    elif $has_all; then
        load_registry
        SELECTED=("${R_NAME[@]}")
        INTERACTIVE=false
    elif is_interactive_tty; then
        SELECTED=()
        show_menu_and_select
        INTERACTIVE=true
    else
        load_registry
        SELECTED=("${R_NAME[@]}")
        INTERACTIVE=false
    fi

    do_install "${SELECTED[@]}"
}

main "$@"
