#!/usr/bin/env bash
# Owner browser session (ephemeral Development/Test stack on a CI runner): give the web app and the API a public https address.
#
# Two account-less Cloudflare quick tunnels (one per port). The binary is pinned by version AND SHA-256: a different file stops the
# run. The addresses are random, valid only while this job runs, and protected by Clerk sign-in; nothing persistent is created.
# Writes OWNER_SESSION_WEB_URL / OWNER_SESSION_API_URL to $GITHUB_ENV. Usage: owner_session_tunnels.sh <web-port> <api-port>
set -euo pipefail

VERSION="2026.10.7"
SHA256="1f99fb518b83dec2ba8d870a7cc991d82a77e6196295a3d2754ba17ab9f91872"
WEB_PORT="${1:?web port}"
API_PORT="${2:?api port}"
BIN="${RUNNER_TEMP:?}/cloudflared"

curl -fsSL --retry 3 -o "$BIN" "https://github.com/cloudflare/cloudflared/releases/download/${VERSION}/cloudflared-linux-amd64"
echo "${SHA256}  ${BIN}" | sha256sum -c -
chmod +x "$BIN"

start_tunnel() {
  local name="$1"
  local port="$2"
  local log="${RUNNER_TEMP}/cf-${name}.log"
  nohup "$BIN" tunnel --no-autoupdate --url "http://localhost:${port}" > "$log" 2>&1 &
  echo $! > "${RUNNER_TEMP}/cf-${name}.pid"
  for _ in $(seq 1 60); do
    url="$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$log" | head -1 || true)"
    if [ -n "$url" ]; then echo "$url"; return 0; fi
    sleep 1
  done
  echo "::error::the ${name} tunnel did not come up within 60 s" >&2
  cat "$log" >&2
  return 1
}

WEB_URL="$(start_tunnel web "$WEB_PORT")"
API_URL="$(start_tunnel api "$API_PORT")"
echo "OWNER_SESSION_WEB_URL=${WEB_URL}" >> "$GITHUB_ENV"
echo "OWNER_SESSION_API_URL=${API_URL}" >> "$GITHUB_ENV"
echo "tunnels up: web=${WEB_URL} api=${API_URL}"
