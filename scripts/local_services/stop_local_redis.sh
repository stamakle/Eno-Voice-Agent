#!/usr/bin/env bash
set -euo pipefail
/home/aseda/.local/opt/english_tech/redis/redis-cli -h 127.0.0.1 -p 6379 shutdown || true
