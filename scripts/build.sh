#!/usr/bin/env bash

export DOCKER_BUILDKIT=1

NAMESPACE=openutm
APP=verification
TIMESTAMP=$(date +%s)
IMAGE=$APP:$TIMESTAMP
IMAGE_LATEST=$APP:latest

set -e

echo "Building Docker image: $NAMESPACE/$IMAGE_LATEST"

docker build -t "$NAMESPACE/$IMAGE" .
docker tag "$NAMESPACE/$IMAGE" $NAMESPACE/$IMAGE_LATEST
