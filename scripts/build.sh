#!/usr/bin/env bash

# OpenUTM Verification Docker Build Script
# This script builds the Docker image with proper error handling and logging

set -euo pipefail

# Configuration
readonly NAMESPACE="${NAMESPACE:-openutm}"
readonly APP="${APP:-verification}"
readonly TIMESTAMP="$(date +%s)"
readonly IMAGE="${APP}:${TIMESTAMP}"
readonly IMAGE_LATEST="${APP}:latest"
readonly IMAGE_DEV="${APP}:dev"

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

# Cleanup function
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Build failed with exit code $exit_code"
        # Optionally cleanup dangling images
        # docker image prune -f
    fi
    exit $exit_code
}

# Set trap for cleanup
trap cleanup EXIT

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

# Build production image
build_production() {
    log_info "Building production Docker image: ${NAMESPACE}/${IMAGE_LATEST}"

    # Enable Docker BuildKit for better performance
    export DOCKER_BUILDKIT=1

    local build_args=()
    if [[ "${force_rebuild}" == "true" ]]; then
        build_args+=(--no-cache)
        log_info "Force rebuild enabled - skipping cache"
    fi

    if [[ "${verbose}" == "true" ]]; then
        build_args+=(--progress=plain)
        log_info "Verbose output enabled"
    fi

    # Build with build args
    docker build \
        --target production \
        --build-arg UV_COMPILE_BYTECODE=1 \
        --build-arg UV_LINK_MODE=copy \
        "${build_args[@]}" \
        -t "${NAMESPACE}/${IMAGE}" \
        -t "${NAMESPACE}/${IMAGE_LATEST}" \
        .

    log_success "Production image built successfully"
}

# Build development image
build_development() {
    log_info "Building development Docker image: ${NAMESPACE}/${IMAGE_DEV}"

    export DOCKER_BUILDKIT=1

    local build_args=()
    if [[ "${force_rebuild}" == "true" ]]; then
        build_args+=(--no-cache)
        log_info "Force rebuild enabled - skipping cache"
    fi

    if [[ "${verbose}" == "true" ]]; then
        build_args+=(--progress=plain)
        log_info "Verbose output enabled"
    fi

    docker build \
        -f Dockerfile.dev \
        --target development \
        --build-arg UV_COMPILE_BYTECODE=0 \
        "${build_args[@]}" \
        -t "${NAMESPACE}/${IMAGE_DEV}" \
        .

    log_success "Development image built successfully"
}

# Show build information
show_build_info() {
    log_info "Build completed successfully!"
    echo "Production image: ${NAMESPACE}/${IMAGE_LATEST}"
    echo "Development image: ${NAMESPACE}/${IMAGE_DEV}"
    echo "Timestamp: ${TIMESTAMP}"
}

# Show usage information
show_usage() {
    cat << EOF
OpenUTM Verification Docker Build Script

Usage: $0 [OPTIONS] [BUILD_TYPE]

Build Docker images for OpenUTM Verification

Arguments:
    BUILD_TYPE          Type of build to perform
                        production, prod    Build production image only
                        development, dev    Build development image only
                        all                 Build both images (default)

Options:
    -f, --force         Force rebuild even if images exist
    -v, --verbose       Enable verbose output
    -h, --help          Show this help message

Examples:
    $0                   # Build all images
    $0 production        # Build production image only
    $0 --force all       # Force rebuild all images
    $0 -v development    # Build development image with verbose output

EOF
}

# Main execution
main() {
    local build_type="all"
    local force_rebuild="false"
    local verbose="false"
    local args=()

    # Parse options
    while [[ $# -gt 0 ]]; do
        case $1 in
            -f|--force)
                force_rebuild="true"
                shift
                ;;
            -v|--verbose)
                verbose="true"
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            -*)
                log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
            *)
                # Collect positional arguments
                args+=("$1")
                shift
                ;;
        esac
    done

    # Set build type from the first positional argument, if provided
    if [[ ${#args[@]} -gt 0 ]]; then
        build_type="${args[0]}"
    fi

    log_info "Starting Docker build process..."
    check_dependencies

    case "${build_type}" in
        "production"|"prod")
            build_production
            ;;
        "development"|"dev")
            build_development
            ;;
        "all")
            build_production
            build_development
            ;;
        *)
            log_error "Invalid build type: '${build_type}'"
            echo "Usage: $0 [OPTIONS] [production|development|all]"
            echo "Try '$0 --help' for more information."
            exit 1
            ;;
    esac

    show_build_info
}

# Run main function with all arguments
main "$@"
