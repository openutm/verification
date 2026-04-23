#!/usr/bin/env bash
#
# Clean up Docker resources for the OpenUTM Verification GUI.
#
# Usage:
#   ./scripts/cleanup.sh           # stop containers (compose down)
#   ./scripts/cleanup.sh --all     # also remove the image and volumes
#   ./scripts/cleanup.sh --dangling # prune dangling images/volumes/networks

set -euo pipefail

SCRIPT_DIR="$(dirname "$0")"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

readonly IMAGE_PREFIX="openutm/verification"

show_usage() {
    cat << EOF
Clean up OpenUTM Verification Docker resources.

Usage: $0 [OPTIONS]

Options:
    (no flags)         Stop and remove the compose stack (docker compose down)
    -a, --all          Also remove the image and named volumes
    -d, --dangling     Prune dangling images, unused volumes and networks
    -f, --force        Skip confirmation prompts
    -h, --help         Show this help message
EOF
}

confirm() {
    local message="$1"
    [[ "${FORCE:-false}" == "true" ]] && return 0
    read -r -p "$message (y/N): " reply
    [[ $reply =~ ^[Yy]$ ]]
}

stack_down() {
    local extra_args=("$@")
    log_info "Stopping compose stack..."
    docker compose down "${extra_args[@]}"
    log_success "Stack stopped"
}

clean_all() {
    if confirm "Remove containers, image (${IMAGE_PREFIX}:*) and named volumes?"; then
        stack_down --rmi all --volumes --remove-orphans
    fi
}

clean_dangling() {
    log_info "Pruning dangling images, unused volumes and networks..."
    docker image prune -f
    docker volume prune -f
    docker network prune -f
    log_success "Dangling resources pruned"
}

main() {
    local mode="default"
    FORCE="false"

    while [[ $# -gt 0 ]]; do
        case $1 in
            -a|--all) mode="all"; shift ;;
            -d|--dangling) mode="dangling"; shift ;;
            -f|--force) FORCE="true"; shift ;;
            -h|--help) show_usage; exit 0 ;;
            *) log_error "Unknown option: $1"; show_usage; exit 1 ;;
        esac
    done

    check_dependencies

    case "${mode}" in
        default) stack_down --remove-orphans ;;
        all) clean_all ;;
        dangling) clean_dangling ;;
    esac
}

main "$@"
