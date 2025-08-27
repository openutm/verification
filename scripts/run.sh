#!/bin/bash

# This script runs the verification tool using Docker Compose.
# It passes any command-line arguments to the container's entrypoint,
# allowing you to override the default command.
#
# Example usage:
# ./scripts/run.sh                                   # Runs with default config
# ./scripts/run.sh --config config/custom.yaml       # Runs with a custom config
# ./scripts/run.sh --debug                           # Runs with debug mode enabled

set -e

echo "Running verification tool via Docker Compose..."

docker compose run --rm verification-tool "$@"

echo "Run complete."
