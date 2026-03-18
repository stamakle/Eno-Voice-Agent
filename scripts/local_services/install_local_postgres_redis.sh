#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/aseda/.local/opt/english_tech
PKGROOT=/home/aseda/.local/opt/english_tech_pkgs
SRCDIR=/home/aseda/.local/src
VARDIR=/home/aseda/.local/var/english_tech
mkdir -p "$ROOT/bin" "$PKGROOT" "$SRCDIR" "$VARDIR/log" "$VARDIR/run" "$VARDIR/postgres" "$VARDIR/redis"

cat > "$ROOT/bin/pg-env" <<'ENVEOF'
export ET_PKGROOT=/home/aseda/.local/opt/english_tech_pkgs/extracted
export PATH="$ET_PKGROOT/postgresql-client-17_17.9-0ubuntu0.25.10.1_amd64/usr/lib/postgresql/17/bin:$ET_PKGROOT/postgresql-17_17.9-0ubuntu0.25.10.1_amd64/usr/lib/postgresql/17/bin:$PATH"
export LD_LIBRARY_PATH="$ET_PKGROOT/libpq5_17.9-0ubuntu0.25.10.1_amd64/usr/lib/x86_64-linux-gnu:$ET_PKGROOT/libllvm20_1%3a20.1.8-0ubuntu4_amd64/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export PGDATA=/home/aseda/.local/var/english_tech/postgres/data
export PGHOST=/home/aseda/.local/var/english_tech/run
export PGPORT=5432
export PGPASSWORD=english_tech
ENVEOF
chmod +x "$ROOT/bin/pg-env"

cd "$PKGROOT"
apt-get download postgresql-17 postgresql-client-17 postgresql-client-common postgresql-common libpq5 libllvm20 >/dev/null
mkdir -p extracted
for pkg in *.deb; do
  dir=${pkg%.deb}
  mkdir -p "extracted/$dir"
  dpkg-deb -x "$pkg" "extracted/$dir"
done

. "$ROOT/bin/pg-env"
if [ ! -f "$PGDATA/PG_VERSION" ]; then
  initdb -D "$PGDATA" --auth=scram-sha-256 --username=english_tech --pwfile=<(printf 'english_tech\n')
fi
if ! grep -q "^listen_addresses = '127.0.0.1'" "$PGDATA/postgresql.conf"; then
  printf "\nlisten_addresses = '127.0.0.1'\nport = 5432\nunix_socket_directories = '%s'\n" "$PGHOST" >> "$PGDATA/postgresql.conf"
fi
if ! grep -q '^host all all 127.0.0.1/32 scram-sha-256' "$PGDATA/pg_hba.conf"; then
  printf "\nhost all all 127.0.0.1/32 scram-sha-256\nhost all all ::1/128 scram-sha-256\n" >> "$PGDATA/pg_hba.conf"
fi

cd "$SRCDIR"
if [ ! -d redis-8.0.2 ]; then
  curl -L https://download.redis.io/releases/redis-8.0.2.tar.gz -o redis-8.0.2.tar.gz
  tar -xzf redis-8.0.2.tar.gz
fi
cd redis-8.0.2
make -j"$(nproc)" BUILD_TLS=no
mkdir -p "$ROOT/redis"
cp src/redis-server src/redis-cli src/redis-benchmark src/redis-check-aof src/redis-check-rdb "$ROOT/redis/"
cat > "$VARDIR/redis/redis.conf" <<'REDISEOF'
bind 127.0.0.1
port 6379
daemonize yes
pidfile /home/aseda/.local/var/english_tech/redis/redis.pid
dir /home/aseda/.local/var/english_tech/redis
dbfilename dump.rdb
appendonly yes
appendfilename appendonly.aof
logfile /home/aseda/.local/var/english_tech/log/redis.log
REDISEOF
