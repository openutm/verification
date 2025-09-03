#!/usr/bin/env bash

# OpenUTM Verification Docker Cleanup Script
# This script cleans up Docker resources related to the verification tool

set -euo pipefail

# Source common functions
SCRIPT_DIR="$(dirname "$0")"
source "$SCRIPT_DIR/common.sh"

# Configuration
readonly PROJECT_NAME="${COMPOSE_PROJECT_NAME:-openutm-verification}"
readonly IMAGE_PREFIX="openutm/verification"

# Cleanup function specific to cleanup script
cleanup_cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Script failed with exit code $exit_code"
    fi
    exit $exit_code
}

# Set trap for cleanup
trap cleanup_cleanup EXIT

# Show usage
show_usage() {
    cat << EOF
OpenUTM Verification Docker Cleanup Script

Usage: $0 [OPTIONS]

Options:
    -a, --all          Clean all Docker resources (containers, images, volumes, networks)
    -c, --containers   Clean containers only
    -i, --images       Clean images only
    -v, --volumes      Clean volumes only
    -n, --networks     Clean networks only
    -d, --dangling     Clean dangling resources only
    -f, --force        Force cleanup without confirmation
    -V, --verbose      Enable verbose output
    -h, --help         Show this help message

Examples:
    $0 --all           # Clean all resources
    $0 --containers    # Clean containers only
    $0 --dangling      # Clean dangling resources
    $0 -f --all        # Force clean all without confirmation

EOF
}

# Confirm action
confirm() {
    local message="$1"
    if [[ "${FORCE_CLEANUP:-false}" == "true" ]]; then
        return 0
    fi

    read -p "$message (y/N): " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]]
}

# Clean containers
clean_containers() {
    if [[ "${VERBOSE}" == "true" ]]; then
        log_info "Verbose mode enabled - showing detailed container information"
    fi

    log_info "Cleaning containers..."

    local containers
    containers=$(docker ps -a --filter "label=project=openutm-verification" --format "{{.ID}}")

    if [[ -z "$containers" ]]; then
        log_info "No containers found to clean"
        return 0
    fi

    if [[ "${VERBOSE}" == "true" ]]; then
        log_info "Found containers:"
        docker ps -a --filter "label=project=openutm-verification" --format "table {{.ID}}\t{{.Image}}\t{{.Status}}\t{{.Names}}"
    else
        log_info "Containers found: $containers"
    fi

    if confirm "Remove $(echo "$containers" | wc -l) container(s)?"; then
        echo "$containers" | xargs docker rm -f
        log_success "Containers cleaned"
    fi
}

# Clean images
clean_images() {
    log_info "Cleaning images..."

    local images
    images=$(docker images "${IMAGE_PREFIX}" --format "{{.Repository}}:{{.Tag}}")

    if [[ -z "$images" ]]; then
        log_info "No images found to clean"
        return 0
    fi

    log_info "Images found: $images"
    if confirm "Remove $(echo "$images" | wc -l) image(s)?"; then
        echo "$images" | xargs docker rmi -f
        log_success "Images cleaned"
    fi
}

# Clean volumes
clean_volumes() {
    log_info "Cleaning volumes..."

    local volumes
    volumes=$(docker volume ls --filter "label=com.docker.compose.project=${PROJECT_NAME}" --format "{{.Name}}")

    if [[ -z "$volumes" ]]; then
        log_info "No volumes found to clean"
        return 0
    fi

    log_info "Volumes found: $volumes"
    if confirm "Remove $(echo "$volumes" | wc -l) volume(s)?"; then
        echo "$volumes" | xargs docker volume rm -f
        log_success "Volumes cleaned"
    fi
}

# Clean networks
clean_networks() {
    log_info "Cleaning networks..."

    local networks
    networks=$(docker network ls --filter "label=com.docker.compose.project=${PROJECT_NAME}" --format "{{.Name}}")

    if [[ -z "$networks" ]]; then
        log_info "No networks found to clean"
        return 0
    fi

    log_info "Networks found: $networks"
    if confirm "Remove $(echo "$networks" | wc -l) network(s)?"; then
        echo "$networks" | xargs docker network rm
        log_success "Networks cleaned"
    fi
}

# Clean dangling resources
clean_dangling() {
    log_info "Cleaning dangling resources..."

    # Remove dangling images
    local dangling_images
    dangling_images=$(docker images -f "dangling=true" -q)
    if [[ -n "$dangling_images" ]]; then
        echo "$dangling_images" | xargs docker rmi -f
        log_success "Dangling images cleaned"
    fi

    # Remove unused volumes
    docker volume prune -f
    log_success "Unused volumes cleaned"

    # Remove unused networks
    docker network prune -f
    log_success "Unused networks cleaned"
}

# Clean all resources
clean_all() {
    log_info "Cleaning all Docker resources for OpenUTM Verification..."

    if confirm "This will remove ALL containers, images, volumes, and networks for the project. Continue?"; then
        # Stop and remove containers
        docker compose down --rmi all --volumes --remove-orphans

        # Clean dangling resources
        clean_dangling

        log_success "All resources cleaned"
    fi
}

# Main execution
main() {
    local CLEAN_CONTAINERS="false"
    local CLEAN_IMAGES="false"
    local CLEAN_VOLUMES="false"
    local CLEAN_NETWORKS="false"
    local CLEAN_DANGLING="false"
    local FORCE_CLEANUP="false"
    local VERBOSE="false"

    # Parse options
    while [[ $# -gt 0 ]]; do
        case $1 in
            -a|--all)
                clean_all
                exit 0
                ;;
            -c|--containers)
                CLEAN_CONTAINERS="true"
                shift
                ;;
            -i|--images)
                CLEAN_IMAGES="true"
                shift
                ;;
            -v|--volumes)
                CLEAN_VOLUMES="true"
                shift
                ;;
            -V|--verbose)
                VERBOSE="true"
                shift
                ;;
            -n|--networks)
                CLEAN_NETWORKS="true"
                shift
                ;;
            -d|--dangling)
                CLEAN_DANGLING="true"
                shift
                ;;
            -f|--force)
                FORCE_CLEANUP="true"
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    # If no specific options provided, show usage
    if [[ "$CLEAN_CONTAINERS" == "false" && "$CLEAN_IMAGES" == "false" && \
          "$CLEAN_VOLUMES" == "false" && "$CLEAN_NETWORKS" == "false" && \
          "$CLEAN_DANGLING" == "false" ]]; then
        show_usage
        exit 0
    fi

    log_info "Starting cleanup process..."
    check_dependencies

    # Execute cleanup actions
    if [[ "$CLEAN_CONTAINERS" == "true" ]]; then
        clean_containers
    fi

    if [[ "$CLEAN_IMAGES" == "true" ]]; then
        clean_images
    fi

    if [[ "$CLEAN_VOLUMES" == "true" ]]; then
        clean_volumes
    fi

    if [[ "$CLEAN_NETWORKS" == "true" ]]; then
        clean_networks
    fi

    if [[ "$CLEAN_DANGLING" == "true" ]]; then
        clean_dangling
    fi

    log_success "Cleanup completed"
}

# Run main function with all arguments
main "$@"
