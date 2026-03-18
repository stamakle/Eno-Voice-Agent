#!/usr/bin/env bash
set -euo pipefail
. /home/aseda/.local/opt/english_tech/bin/pg-env
pg_ctl -D "$PGDATA" stop -m fast
