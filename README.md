# OpenUTM Verification Toolkit

A repository to host verification tools for Flight Blender and OpenUTM products.

## Overview

This toolkit provides a configuration-driven framework for running automated conformance and integration test scenarios against a Flight Blender instance. It is designed to be run as a standalone tool or within a Docker container.

## Running with Docker (Recommended)

The easiest way to run the verification tool is by using Docker and the provided scripts.

### Prerequisites

* Docker
* Docker Compose

### 1. Build the Docker Image

First, build the Docker image using the build script. This packages the application and all its dependencies.

```bash
./scripts/build.sh
```

### 2. Run the Verification Scenarios

Once the image is built, you can execute the verification tool using the run script.

**To run with the default configuration (`config/default.yaml`):**

```bash
./scripts/run.sh
```

**To specify a different configuration file:**

You can pass arguments to the `run.sh` script, which will be forwarded to the script inside the container.

```bash
./scripts/run.sh --config config/your_scenario_config.yaml
```

**To enable debug mode:**

```bash
./scripts/run.sh --debug
```

Reports will be generated in the `reports/` directory on your local machine.
