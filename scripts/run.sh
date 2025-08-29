#!/usr/bin/env bash

# OpenUTM Verification Docker Run Script
# This script runs the verification tool using Docker Compose with enhanced error handling

set -euo pipefail

# Configuration
readonly COMPOSE_FILE="docker-compose.yml"
readonly SERVICE_NAME="verification-tool"
readonly DEV_SERVICE_NAME="verification-dev"

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" >&2
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" >&2
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Check if Docker and Docker Compose are available
check_dependencies() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi

    if ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not available"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi
}

# Check if required files exist
check_files() {
    if [[ ! -f "${COMPOSE_FILE}" ]]; then
        log_error "Docker Compose file '${COMPOSE_FILE}' not found"
        exit 1
    fi

    if [[ ! -f "config/default.yaml" ]]; then
        log_warning "Default config file 'config/default.yaml' not found"
    fi
}

# Show usage information
show_usage() {
    cat << EOF
OpenUTM Verification Tool Runner

Usage: $0 [OPTIONS] [ARGS...]

Options:
    -d, --dev          Run in development mode with hot reload
    -p, --production   Run in production mode (default)
    -b, --build        Build images before running
    --clean            Clean up containers and images after run
    -v, --verbose      Enable verbose output
    -h, --help         Show this help message

Arguments:
    All additional arguments are passed to the verification tool

Examples:
    $0                                   # Run with default config
    $0 --config config/custom.yaml       # Run with custom config
    $0 --debug                           # Run with debug logging
    $0 --dev --build                     # Build and run in development mode
    $0 --clean --config config/test.yaml # Clean up after run
    $0 -v --build                        # Run with verbose output and build first

EOF
}

# Run in production mode
run_production() {
    log_info "Running verification tool in production mode..."

    local build_opts=()
    if [[ "${VERBOSE}" == "true" ]]; then
        log_info "Verbose mode enabled - additional logging will be shown"
        build_opts+=("-v")
    fi

    if [[ "${BUILD_FIRST}" == "true" ]]; then
        log_info "Building production image first..."
        ./scripts/build.sh "${build_opts[@]}" production
    fi

    local compose_opts=()
    if [[ "${VERBOSE}" == "true" ]]; then
        log_info "Starting container with verbose output..."
        compose_opts+=("--verbose")
    fi

    docker compose "${compose_opts[@]}" --file "${COMPOSE_FILE}" run --rm "${SERVICE_NAME}" "$@"
}

# Run in development mode
run_development() {
    log_info "Running verification tool in development mode..."

    local build_opts=()
    if [[ "${VERBOSE}" == "true" ]]; then
        log_info "Verbose mode enabled - additional logging will be shown"
        build_opts+=("-v")
    fi

    if [[ "${BUILD_FIRST}" == "true" ]]; then
        log_info "Building development image first..."
        ./scripts/build.sh "${build_opts[@]}" development
    fi

    local compose_opts=()
    if [[ "${VERBOSE}" == "true" ]]; then
        compose_opts+=("--verbose")
    fi

    docker compose "${compose_opts[@]}" --profile dev run --rm "${DEV_SERVICE_NAME}" "$@"
}

# Cleanup function for run script
run_cleanup() {
    if [[ "${CLEANUP_AFTER:-false}" == "true" ]]; then
        log_info "Cleaning up containers and images after run..."
        ./scripts/cleanup.sh -a -f
    fi
}

# Main execution
main() {
    local RUN_MODE="production"
    local BUILD_FIRST="false"
    local CLEANUP_AFTER="false"
    local VERBOSE="false"

    # Parse options
    while [[ $# -gt 0 ]]; do
        case $1 in
            -d|--dev)
                RUN_MODE="development"
                shift
                ;;
            -p|--production)
                RUN_MODE="production"
                shift
                ;;
            -b|--build)
                BUILD_FIRST="true"
                shift
                ;;
            --clean)
                CLEANUP_AFTER="true"
                shift
                ;;
            -v|--verbose)
                VERBOSE="true"
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                # Break on first non-option argument
                break
                ;;
        esac
    done

    log_info "Starting OpenUTM Verification Tool..."
    check_dependencies
    check_files

    # Set up cleanup trap
    trap 'run_cleanup' EXIT

    case "${RUN_MODE}" in
        "production")
            run_production "$@"
            ;;
        "development")
            run_development "$@"
            ;;
        *)
            log_error "Invalid run mode: ${RUN_MODE}"
            exit 1
            ;;
    esac

    log_success "Verification run completed successfully"
}

# Run main function with all arguments
main "$@"
