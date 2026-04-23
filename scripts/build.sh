#!/usr/bin/env bash
#
# Build the single OpenUTM Verification Docker image (backend + built GUI).
#
# Usage:
#   ./scripts/build.sh [--force] [--verbose]

set -euo pipefail

SCRIPT_DIR="$(dirname "$0")"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

readonly NAMESPACE="${NAMESPACE:-openutm}"
readonly APP="${APP:-verification}"
readonly IMAGE_LATEST="${NAMESPACE}/${APP}:latest"

show_usage() {
    cat << EOF
Build the OpenUTM Verification Docker image.

Usage: $0 [OPTIONS]

Options:
    -f, --force     Force rebuild without cache
    -v, --verbose   Verbose build output (--progress=plain)
    -h, --help      Show this help message
EOF
}

main() {
    local force_rebuild="false"
    local verbose="false"

    while [[ $# -gt 0 ]]; do
        case $1 in
            -f|--force) force_rebuild="true"; shift ;;
            -v|--verbose) verbose="true"; shift ;;
            -h|--help) show_usage; exit 0 ;;
            *) log_error "Unknown option: $1"; show_usage; exit 1 ;;
        esac
    done

    check_dependencies

    local build_args=()
    [[ "${force_rebuild}" == "true" ]] && build_args+=(--no-cache)
    [[ "${verbose}" == "true" ]] && build_args+=(--progress=plain)

    log_info "Building ${IMAGE_LATEST}"
    DOCKER_BUILDKIT=1 docker build \
        --build-arg UV_COMPILE_BYTECODE=1 \
        --build-arg UV_LINK_MODE=copy \
        --build-arg UID="${HOST_UID}" \
        --build-arg GID="${HOST_GID}" \
        ${build_args[@]+"${build_args[@]}"} \
        -t "${IMAGE_LATEST}" \
        .

    log_success "Built ${IMAGE_LATEST}"
}

main "$@"
