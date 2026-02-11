#!/bin/bash
# Wrapper script to add Juju RPC tracing to all juju commands
# Called by Jubilant via cli_binary parameter

# Create log directory (redirect to stderr to avoid polluting stdout)
LOG_DIR="/tmp/juju-wrapper-logs"
mkdir -p "${LOG_DIR}" 2>&1 >&2

# Generate unique log file names with timestamp and PID
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_PREFIX="${LOG_DIR}/juju-${TIMESTAMP}-$$"
STDOUT_LOG="${LOG_PREFIX}-stdout.log"
STDERR_LOG="${LOG_PREFIX}-stderr.log"

# Log the command being executed (to stderr for debugging)
echo "WRAPPER: juju --show-log --logging-config=\"juju.rpc=TRACE\" $* >> ${STDOUT_LOG} 2>> ${STDERR_LOG}" >&2

# Execute juju with logging, duplicating stdout and stderr to files
# - stdout goes to stdout AND to the stdout log file
# - stderr goes to stderr AND to the stderr log file
/snap/juju/current/bin/juju --show-log --logging-config="juju.rpc=TRACE" "$@" \
    > >(tee "${STDOUT_LOG}") \
    2> >(tee "${STDERR_LOG}" >&2)
