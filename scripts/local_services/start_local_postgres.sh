#!/usr/bin/env bash
set -euo pipefail
. /home/aseda/.local/opt/english_tech/bin/pg-env
pg_ctl -D "$PGDATA" -l /home/aseda/.local/var/english_tech/log/postgres.log -o "-k $PGHOST -p $PGPORT" start
createdb -h 127.0.0.1 -p 5432 -U english_tech english_tech 2>/dev/null || true
