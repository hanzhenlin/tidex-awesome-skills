#!/usr/bin/env bash
# ==============================================================================
# Tidex Awesome Skills - 策展人快照刷新工具
#
# 用途：遍历 registry.txt 登记表，从各原作者上游仓库拉取最新源码，
#       原子替换 skills/ 下的内置快照，保证兜底源始终可用且不过时。
# 说明：本脚本只改工作副本，不代替策展人提交；审阅刷新报告后自行 commit/push。
# ==============================================================================

set -e

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
CYAN="\033[36m"
RESET="\033[0m"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGISTRY_FILE="${SCRIPT_DIR}/registry.txt"
SNAPSHOT_DIR="${SCRIPT_DIR}/skills"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "${WORK_DIR}"' EXIT

UPDATED=(); UNCHANGED=(); FAILED=()

load_registry() {
    local line
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in ''|\#*) continue ;; esac
        local name upstream
        name="$(echo "$line" | awk -F'|' '{print $1}' | xargs)"
        upstream="$(echo "$line" | awk -F'|' '{print $3}' | xargs)"
        [ -z "$name" ] && continue
        R_NAME+=("$name"); R_UPSTREAM+=("$upstream")
    done < "${REGISTRY_FILE}"
}

sync_one() {
    local name="$1" upstream="$2"
    local snapshot="${SNAPSHOT_DIR}/${name}"
    local tmp="${WORK_DIR}/${name}"
    local ssh_url
    ssh_url="$(echo "${upstream}" | sed -e 's#^https://github.com/#git@github.com:#' -e 's#\.git$##').git"

    echo -e "${BOLD}▶ 同步:${RESET} ${name}"
    if ! git -c http.version=HTTP/1.1 -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=25 \
            clone --depth 1 "${upstream}" "${tmp}" >/dev/null 2>&1 \
        && ! git -c http.version=HTTP/1.1 -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=25 \
            clone --depth 1 "${ssh_url}" "${tmp}" >/dev/null 2>&1; then
        echo -e "  ${RED}✗ 上游拉取失败（仓库搬家/删除/断网），快照保持原样${RESET}"
        FAILED+=("${name}")
        return 0
    fi
    rm -rf "${tmp}/.git"

    if [ -d "${snapshot}" ]; then
        if diff -qr "${snapshot}" "${tmp}" >/dev/null 2>&1; then
            echo -e "  ${CYAN}• 与上游一致，无需更新${RESET}"
            UNCHANGED+=("${name}")
            return 0
        fi
        rm -rf "${snapshot}"
    fi
    mkdir -p "${SNAPSHOT_DIR}"
    cp -R "${tmp}" "${snapshot}"
    local commit
    commit="$(git -C "${WORK_DIR}/${name}" rev-parse HEAD 2>/dev/null || true)"
    # clone 后 .git 已删，改从临时 clone 记录；此处直接从缓存重新查不可行，简单标记日期
    echo -e "  ${GREEN}✓ 快照已刷新为上游最新版${RESET}"
    UPDATED+=("${name}")
}

main() {
    [ -f "${REGISTRY_FILE}" ] || { echo -e "${RED}[✗] 未找到登记表: ${REGISTRY_FILE}${RESET}"; exit 1; }
    command -v git >/dev/null 2>&1 || { echo -e "${RED}[✗] 未安装 git，无法同步上游。${RESET}"; exit 1; }

    echo -e "${BOLD}${CYAN}============================================================"
    echo -e "         🔄 Tidex Awesome Skills 快照同步工具"
    echo -e "============================================================${RESET}"
    echo ""

    R_NAME=(); R_UPSTREAM=()
    load_registry

    local i
    for i in "${!R_NAME[@]}"; do
        sync_one "${R_NAME[$i]}" "${R_UPSTREAM[$i]}"
    done

    echo ""
    echo "============================================================"
    echo -e "${BOLD}同步报告:${RESET}"
    echo -e "  已更新: ${#UPDATED[@]} 个 ${UPDATED[*]:-}"
    echo -e "  无变化: ${#UNCHANGED[@]} 个 ${UNCHANGED[*]:-}"
    echo -e "  失败  : ${#FAILED[@]} 个 ${FAILED[*]:-}"
    echo ""
    echo -e "${YELLOW}请审阅快照变更（git status / git diff）后自行提交推送，本脚本不代替提交。${RESET}"
    echo "============================================================"
}

main "$@"
