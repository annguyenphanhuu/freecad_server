#!/bin/bash
set -e

export REDIS_URL=${REDIS_URL:-redis://localhost:6379/0}
export QUEUE_NAME=${QUEUE_NAME:-freecad_jobs}
export STORAGE_PATH=${STORAGE_PATH:-/app/storage}
export API_HOST=${API_HOST:-0.0.0.0}
export API_PORT=${API_PORT:-8080}
# Job timeout in seconds for both API enqueue and worker execution (default 1 hour)
export JOB_TIMEOUT=${JOB_TIMEOUT:-3600}
# Propagate timeout to RQ workers (respected by rq.worker)
export RQ_JOB_TIMEOUT=${RQ_JOB_TIMEOUT:-$JOB_TIMEOUT}
# MQTT_BROKER should point to external MQTT container
# Default: mqtt://mqtt:1883 (if using docker network) or mqtt://localhost:1883 (if same host)
export MQTT_BROKER=${MQTT_BROKER:-mqtt://mqtt:1883}
export NUM_WORKERS=${NUM_WORKERS:-3}

worker_pids=()
api_pid=""

cleanup() {
    exit_code=${1:-0}
    echo "🛑 Shutting down services..."
    if [ -n "$redis_pid" ]; then
        kill -TERM "$redis_pid" 2>/dev/null || true
    fi
    for pid in "${worker_pids[@]}"; do
        kill -TERM "$pid" 2>/dev/null || true
    done
    kill -TERM "$api_pid" 2>/dev/null || true
    wait || true
    exit "$exit_code"
}
trap 'cleanup $?' SIGTERM SIGINT ERR

# Start Redis (only if not already running)
echo "🔴 Checking Redis..."
if ! redis-cli -h localhost -p 6379 ping >/dev/null 2>&1; then
    echo "  → Starting Redis server..."
    redis-server --bind 0.0.0.0 --daemonize no &
    redis_pid=$!
    sleep 2
else
    echo "  → Redis already running on host, using existing instance"
    redis_pid=""
fi

# Note: MQTT broker runs in separate container
echo "📡 MQTT broker: ${MQTT_BROKER} (external container)"

# Start RQ workers (using conda base environment where FreeCAD is installed)
echo "👥 Starting ${NUM_WORKERS} worker(s)..."
worker_pids=()
for i in $(seq 1 $NUM_WORKERS); do
    worker_name="worker-${i}"
    echo "  → Starting ${worker_name} (timeout ${RQ_JOB_TIMEOUT}s)..."
    env RQ_JOB_TIMEOUT=${RQ_JOB_TIMEOUT} conda run -n base rq worker --url "${REDIS_URL}" "${QUEUE_NAME}" --name "${worker_name}" &
    worker_pids+=("$!")
done
sleep 2

# Start API (using conda base environment)
echo "🌐 Starting API on port ${API_PORT}..."
conda run -n base python app.py &
api_pid=$!

# Wait for any process to exit, then trigger cleanup
set +e
if [ -n "$redis_pid" ]; then
    wait -n "$api_pid" "$redis_pid" "${worker_pids[@]}"
else
    wait -n "$api_pid" "${worker_pids[@]}"
fi
exit_code=$?
set -e
cleanup "$exit_code"

