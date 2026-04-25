#!/usr/bin/env bash
#
# Start the OpenUTM Verification GUI (backend + built frontend) via Docker
# Compose. Equivalent to `make gui`.
#
# For local development without Docker, use `make dev-backend` and
# `make dev-frontend` instead.
#
# Usage:
#   ./scripts/run.sh [--build] [--foreground] [--verbose]

set -euo pipefail

SCRIPT_DIR="$(dirname "$0")"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

readonly COMPOSE_FILE="docker-compose.yml"

show_usage() {
    cat << EOF
Start the OpenUTM Verification GUI in Docker.

Usage: $0 [OPTIONS]

Options:
    -b, --build         Rebuild the image before starting
    -f, --foreground    Run in the foreground (stream logs); default is detached
    -v, --verbose       Verbose docker compose output
    -h, --help          Show this help message

The GUI is served at http://localhost:8989.
EOF
}

main() {
    local build_first="false"
    local foreground="false"
    local verbose="false"

    while [[ $# -gt 0 ]]; do
        case $1 in
            -b|--build) build_first="true"; shift ;;
            -f|--foreground) foreground="true"; shift ;;
            -v|--verbose) verbose="true"; shift ;;
            -h|--help) show_usage; exit 0 ;;
            *) log_error "Unknown option: $1"; show_usage; exit 1 ;;
        esac
    done

    check_dependencies

    if [[ ! -f "${COMPOSE_FILE}" ]]; then
        log_error "Compose file '${COMPOSE_FILE}' not found"
        exit 1
    fi

    mkdir -p reports

    local compose_opts=()
    [[ "${verbose}" == "true" ]] && compose_opts+=(--verbose)

    local up_opts=()
    [[ "${build_first}" == "true" ]] && up_opts+=(--build)
    [[ "${foreground}" == "false" ]] && up_opts+=(-d)

    log_info "Starting GUI via docker compose..."
    DOCKER_BUILDKIT=1 docker compose ${compose_opts[@]+"${compose_opts[@]}"} \
        -f "${COMPOSE_FILE}" up ${up_opts[@]+"${up_opts[@]}"}

    if [[ "${foreground}" == "false" ]]; then
        log_success "GUI running at http://localhost:8989 (detached)"
        log_info "Logs:  docker compose logs -f"
        log_info "Stop:  docker compose down  (or ./scripts/cleanup.sh)"
    fi
}

main "$@"
