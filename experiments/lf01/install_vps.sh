#!/usr/bin/env bash
# LF-01 isolated Langflow pilot installer. RUN WITH: sudo bash install_vps.sh
# No C2Pro checkout, Railway, Vercel, or existing DB is touched.
set -euo pipefail
test "$(id -u)" -eq 0 || { echo 'Requires root for initial podman install'; exit 1; }
export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends podman uidmap >/dev/null
if ! id lf01lab >/dev/null 2>&1; then
  useradd --create-home --user-group --shell /usr/sbin/nologin lf01lab
fi
LAB_UID="$(id -u lf01lab)"
install -d -m 700 -o lf01lab -g lf01lab "/run/user/${LAB_UID}" \
  /home/lf01lab/lf01-data /home/lf01lab/lf01-config /home/lf01lab/lf01-evidence
ENVFILE=/home/lf01lab/lf01-config/.env
if test ! -f "$ENVFILE"; then
  export LF01_ENV_TARGET="$ENVFILE"
  python3 - <<'PY'
import os, secrets, base64
from pathlib import Path
p=Path(os.environ["LF01_ENV_TARGET"])
fkey=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
lines=[
'LANGFLOW_AUTO_LOGIN=false','LANGFLOW_SUPERUSER=lf01lab',
'LANGFLOW_SUPERUSER_PASSWORD='+secrets.token_hex(28),
'LANGFLOW_SECRET_KEY='+fkey,
'LANGFLOW_CONFIG_DIR=/app/langflow','LANGFLOW_SAVE_DB_IN_CONFIG_DIR=true',
'LANGFLOW_HOST=0.0.0.0','LANGFLOW_PORT=7860','LANGFLOW_WORKERS=1',
'LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false','LANGFLOW_BLOCK_CODE_INTERPRETER_COMPONENTS=true',
'LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS=true','LANGFLOW_ALLOW_PUBLIC_CUSTOM_COMPONENTS=false',
'LANGFLOW_WEBHOOK_AUTH_ENABLE=true','LANGFLOW_MCP_SERVER_DOCKER_HARDENING=true',
'LANGFLOW_TWEAKS_POLICY=off','LANGFLOW_FALLBACK_TO_ENV_VAR=false',
'LANGFLOW_STORE_ENVIRONMENT_VARIABLES=false',
'LANGCHAIN_TRACING_V2=false','LANGSMITH_TRACING=false','DO_NOT_TRACK=true']
fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as out: out.write('\n'.join(lines)+'\n')
PY
  chown lf01lab:lf01lab "$ENVFILE"
fi
chmod 600 "$ENVFILE"
P=(runuser -u lf01lab -- env "XDG_RUNTIME_DIR=/run/user/${LAB_UID}" HOME=/home/lf01lab podman --cgroup-manager=cgroupfs)
"${P[@]}" pull docker.io/langflowai/langflow:1.13.3
if ! "${P[@]}" container exists c2pro-lf01; then
  "${P[@]}" create --name c2pro-lf01 --pull=never \
    --security-opt=no-new-privileges --cap-drop=all \
    --pids-limit=256 --memory=4g --cpus=2 \
    --env-file "$ENVFILE" -p 127.0.0.1:17860:7860 \
    --volume /home/lf01lab/lf01-data:/app/langflow:rw,U \
    docker.io/langflowai/langflow:1.13.3 >/dev/null
fi

# A rootless podman --memory flag alone is not enough without cgroup delegation.
# Place the container process inside a separately capped root-managed systemd
# unit. Never attach it to the AI-GEN Ops service's cgroup.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="${SCRIPT_DIR}/lf01-langflow.service.in"
test -f "$TEMPLATE" || { echo "Missing $TEMPLATE"; exit 1; }
SERVICE_PATH=/etc/systemd/system/lf01-langflow.service
if ! test -f "$SERVICE_PATH"; then
  if systemctl is-active --quiet lf01-langflow.service; then
    echo 'LF01 uses a transient unit; refusing to overwrite a running unit automatically.'
    exit 1
  fi
  sed "s/__LF01_UID__/${LAB_UID}/g" "$TEMPLATE" > "$SERVICE_PATH"
  chmod 0644 "$SERVICE_PATH"
  systemctl daemon-reload
fi
systemctl enable --now lf01-langflow.service >/dev/null
systemctl show lf01-langflow.service -p ActiveState -p MemoryMax -p CPUQuotaPerSecUSec --no-pager
echo 'LF01 service installed with systemd cgroup 4 GiB / 2 CPU max.'
echo 'Only 127.0.0.1:17860 is bound. Use an SSH tunnel; never expose publicly.'
echo 'Credentials stored at /home/lf01lab/lf01-config/.env (0600), never in Git.'
