#!/usr/bin/env bash
# ==============================================================================
# Tidex Awesome Skills - 智能全端自适应安装与管理脚本
# 支持：全端自动识别、软链同步挂载、防重复幂等安装、安全无损卸载
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
LOCAL_SKILLS_DIR="${SCRIPT_DIR}/skills"
GLOBAL_STORE_DIR="${HOME}/.tidex-awesome-skills"

# 默认精选技能清单
AVAILABLE_SKILLS=("nuwa-skill")

# 打印横幅
print_banner() {
    echo -e "${BOLD}${CYAN}"
    echo "============================================================"
    echo "         🌟 Tidex Awesome Skills 明星技能精选套件            "
    echo "============================================================"
    echo -e "${RESET}"
}

# 打印帮助信息
show_help() {
    print_banner
    echo -e "${BOLD}使用方式:${RESET}"
    echo "  bash install.sh [选项]"
    echo ""
    echo -e "${BOLD}选项列表:${RESET}"
    echo "  (无参数)              全端智能探测安装（自动打通所有已识别的 Agent）"
    echo "  -u, --uninstall      安全卸载已挂载的明星精选技能软链接"
    echo "  -t, --target <DIR>   指定安装到特定目录（例如指定项目的 .agents/skills）"
    echo "  -l, --list           查看当前系统中各 Agent 的安装与挂载状态"
    echo "  -h, --help           显示此帮助信息"
    echo ""
}

# 探测本地可用的 Agent 宿主环境路径
detect_agent_paths() {
    local detected=()

    # 1. 通用标准路径 (Claude Code / Codex / 通用 Agent)
    local standard_path="${HOME}/.agents/skills"
    detected+=("${standard_path}")

    # 2. ZCode 专属全局路径
    local zcode_path="${HOME}/.zcode/skills"
    if [ -d "${HOME}/.zcode" ] || [ -d "${zcode_path}" ]; then
        detected+=("${zcode_path}")
    fi

    # 3. Claude Code 专属兼容路径
    local claude_path="${HOME}/.claude/skills"
    if [ -d "${HOME}/.claude" ] || [ -d "${claude_path}" ]; then
        detected+=("${claude_path}")
    fi

    # 4. Codex 专属兼容路径
    local codex_path="${HOME}/.codex/skills"
    if [ -d "${HOME}/.codex" ] || [ -d "${codex_path}" ]; then
        detected+=("${codex_path}")
    fi

    # 5. Workbuddy 专属兼容路径
    local workbuddy_path="${HOME}/.workbuddy/skills"
    if [ -d "${HOME}/.workbuddy" ] || [ -d "${workbuddy_path}" ]; then
        detected+=("${workbuddy_path}")
    fi

    # 6. 当前项目工作区
    local current_pwd="$(pwd)"
    if [ "${current_pwd}" != "${SCRIPT_DIR}" ] && [ "${current_pwd}" != "${HOME}" ]; then
        if [ -d "${current_pwd}/.git" ] || [ -d "${current_pwd}/.svn" ] || [ -f "${current_pwd}/pom.xml" ] || [ -f "${current_pwd}/package.json" ]; then
            detected+=("${current_pwd}/.agents/skills")
        fi
    fi

    # 去重返回
    local unique_paths=($(echo "${detected[@]}" | tr ' ' '\n' | sort -u | tr '\n' ' '))
    echo "${unique_paths[@]}"
}

# 确保基准真实源存在
ensure_source_skills() {
    if [ -d "${LOCAL_SKILLS_DIR}" ]; then
        SOURCE_DIR="${LOCAL_SKILLS_DIR}"
    elif [ -d "${GLOBAL_STORE_DIR}/skills" ]; then
        SOURCE_DIR="${GLOBAL_STORE_DIR}/skills"
    else
        echo -e "${YELLOW}[i] 正在初始化本地技能基准库至 ${GLOBAL_STORE_DIR}...${RESET}"
        mkdir -p "${GLOBAL_STORE_DIR}"
        if command -v git >/dev/null 2>&1; then
            git clone --depth=1 https://github.com/hanzhenlin/tidex-awesome-skills.git "${GLOBAL_STORE_DIR}" >/dev/null 2>&1
            SOURCE_DIR="${GLOBAL_STORE_DIR}/skills"
        else
            echo -e "${RED}[✗] 未找到本地 skills 目录且未安装 git，无法初始化基准源。${RESET}"
            exit 1
        fi
    fi
}

# 执行安装挂载（幂等、防重）
do_install() {
    local custom_target="$1"
    print_banner
    ensure_source_skills

    echo -e "${BOLD}[1/3] 确定技能基准存储库:${RESET}"
    echo -e "  -> ${CYAN}${SOURCE_DIR}${RESET}"
    echo ""

    local target_dirs=()
    if [ -n "${custom_target}" ]; then
        target_dirs=("${custom_target}")
        echo -e "${BOLD}[2/3] 安装至指定目标目录:${RESET}"
        echo -e "  -> ${CYAN}${custom_target}${RESET}"
    else
        echo -e "${BOLD}[2/3] 正在全端智能探测 Agent 宿主环境...${RESET}"
        read -r -a target_dirs <<< "$(detect_agent_paths)"
        for t in "${target_dirs[@]}"; do
            echo -e "  ${GREEN}[✓] 发现 Agent 宿主路径:${RESET} ${t}"
        done
    fi
    echo ""

    echo -e "${BOLD}[3/3] 正在挂载精选技能（软链接同步模式，防重幂等）...${RESET}"
    local installed_count=0
    local skipped_count=0

    for target_dir in "${target_dirs[@]}"; do
        mkdir -p "${target_dir}"
        echo -e "  ${BLUE}▶ 正在配置:${RESET} ${target_dir}"

        for skill in "${AVAILABLE_SKILLS[@]}"; do
            local src="${SOURCE_DIR}/${skill}"
            local dest="${target_dir}/${skill}"

            if [ ! -d "${src}" ]; then
                continue
            fi

            # 幂等检查：目标如果已经是软链接
            if [ -L "${dest}" ]; then
                local current_target="$(readlink "${dest}")"
                if [ "${current_target}" = "${src}" ]; then
                    echo -e "    ${CYAN}• ${skill}${RESET}: [已挂载，保持同步更新]"
                    skipped_count=$((skipped_count + 1))
                    continue
                else
                    rm -f "${dest}"
                    ln -s "${src}" "${dest}"
                    echo -e "    ${GREEN}• ${skill}${RESET}: [已重定向修复软链接]"
                    installed_count=$((installed_count + 1))
                    continue
                fi
            fi

            # 如果目标是真实目录而非软链接，先安全备份
            if [ -d "${dest}" ] && [ ! -L "${dest}" ]; then
                local backup_dir="${dest}.bak_$(date +%s)"
                mv "${dest}" "${backup_dir}"
                echo -e "    ${YELLOW}• ${skill}${RESET}: [发现旧实体目录，已安全备份为 $(basename ${backup_dir})]"
            fi

            ln -s "${src}" "${dest}"
            echo -e "    ${GREEN}• ${skill}${RESET}: [挂载成功 ✓]"
            installed_count=$((installed_count + 1))
        done
        echo ""
    done

    echo "============================================================"
    echo -e "${BOLD}${GREEN}🎉 明星技能精选库安装就绪！${RESET}"
    echo -e "已挂载/更新: ${installed_count} 处 | 保持同步: ${skipped_count} 处"
    echo ""
    echo -e "${BOLD}当前已就绪的明星技能:${RESET}"
    echo -e "  • ${BOLD}nuwa-skill${RESET} - 女娲造人（花叔 @alchaincyf 原创，思维框架与人物视角蒸馏工厂）"
    echo "============================================================"
}

# 执行安全卸载
do_uninstall() {
    print_banner
    ensure_source_skills

    echo -e "${BOLD}[!] 正在启动安全卸载程序...${RESET}"
    echo -e "将只清理指向 Tidex 精选技能库的软链接，绝不影响您的其他技能与自定义配置。"
    echo ""

    read -r -a target_dirs <<< "$(detect_agent_paths)"
    local removed_count=0

    for target_dir in "${target_dirs[@]}"; do
        if [ ! -d "${target_dir}" ]; then
            continue
        fi

        echo -e "  ${BLUE}▶ 检查目录:${RESET} ${target_dir}"
        local found_in_dir=0

        for skill in "${AVAILABLE_SKILLS[@]}"; do
            local dest="${target_dir}/${skill}"
            if [ -L "${dest}" ]; then
                local current_target="$(readlink "${dest}")"
                if [[ "${current_target}" == *"${SOURCE_DIR}/${skill}"* ]] || [[ "${current_target}" == *"tidex-awesome-skills"* ]]; then
                    rm -f "${dest}"
                    echo -e "    ${RED}✗ 已移除软链接:${RESET} ${skill}"
                    removed_count=$((removed_count + 1))
                    found_in_dir=1
                fi
            fi
        done

        if [ ${found_in_dir} -eq 0 ]; then
            echo -e "    ${CYAN}• 无 Tidex 精选技能挂载记录，已跳过${RESET}"
        fi
        echo ""
    done

    echo "============================================================"
    if [ ${removed_count} -gt 0 ]; then
        echo -e "${BOLD}${GREEN}✔ 卸载完成！共清理了 ${removed_count} 处技能软链接。${RESET}"
    else
        echo -e "${BOLD}${YELLOW}未在系统中发现挂载中的 Tidex 精选技能软链接。${RESET}"
    fi
    echo "============================================================"
}

# 列出状态
do_list() {
    print_banner
    ensure_source_skills

    echo -e "${BOLD}当前系统 Agent 宿主环境与明星精选技能挂载大盘:${RESET}"
    echo ""

    read -r -a target_dirs <<< "$(detect_agent_paths)"
    for target_dir in "${target_dirs[@]}"; do
        echo -e "${BOLD}▶ 宿主目录:${RESET} ${CYAN}${target_dir}${RESET}"
        if [ ! -d "${target_dir}" ]; then
            echo -e "  ${YELLOW}(目录不存在)${RESET}\n"
            continue
        fi

        for skill in "${AVAILABLE_SKILLS[@]}"; do
            local dest="${target_dir}/${skill}"
            if [ -L "${dest}" ]; then
                local current_target="$(readlink "${dest}")"
                echo -e "  [✓] ${GREEN}${skill}${RESET} -> ${current_target}"
            elif [ -d "${dest}" ]; then
                echo -e "  [!] ${YELLOW}${skill}${RESET} (普通目录，非软链)"
            else
                echo -e "  [-] ${skill} (未安装)"
            fi
        done
        echo ""
    done
}

main() {
    case "$1" in
        -h|--help)
            show_help
            ;;
        -u|--uninstall)
            do_uninstall
            ;;
        -l|--list)
            do_list
            ;;
        -t|--target)
            if [ -z "$2" ]; then
                echo -e "${RED}[✗] 错误: --target 需要指定目标目录路径！${RESET}"
                exit 1
            fi
            do_install "$2"
            ;;
        *)
            do_install ""
            ;;
    esac
}

main "$@"
