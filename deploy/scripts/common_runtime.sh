#!/usr/bin/env bash

resolve_service_node_bin() {
  local service_user="$1"
  local service_home
  local candidate
  local major
  local best_major=0
  local best_bin=""

  service_home="$(getent passwd "$service_user" | cut -d: -f6)"
  for candidate in "$(command -v node 2>/dev/null || true)" "$service_home"/.nvm/versions/node/*/bin/node; do
    [[ -n "$candidate" && -x "$candidate" ]] || continue
    major="$($candidate -p 'Number(process.versions.node.split(".")[0])' 2>/dev/null || true)"
    [[ "$major" =~ ^[0-9]+$ ]] || continue
    if (( major >= 18 && major > best_major )) && [[ -x "$(dirname "$candidate")/npm" ]]; then
      best_major="$major"
      best_bin="$(dirname "$candidate")"
    fi
  done

  if [[ -z "$best_bin" ]]; then
    echo "未找到 Node.js >= 18 及配套 npm；请为部署用户 $service_user 安装受支持的 Node.js。" >&2
    return 1
  fi
  printf '%s\n' "$best_bin"
}
