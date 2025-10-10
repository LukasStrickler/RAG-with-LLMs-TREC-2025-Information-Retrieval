#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "Using repository root: ${ROOT_DIR}" >&2

# Copy environment files if missing and track missing keys
env_targets=(
  "backend/api"
  "backend/embeddings"
  "backend/eval"
  "frontend"
)

missing_templates=()
missing_keys=()

copy_env_if_missing() {
  local template_path="$1"
  local env_path="$2"
  local rel_env_path="${env_path#"${ROOT_DIR}/"}"
  local rel_template_path="${template_path#"${ROOT_DIR}/"}"

  if [ -f "${template_path}" ]; then
    if [ ! -f "${env_path}" ]; then
      echo "[info] Creating ${rel_env_path} from template" >&2
      cp "${template_path}" "${env_path}"
    else
      echo "[info] ${rel_env_path} already present" >&2
    fi
  else
    echo "[warn] Missing template ${rel_template_path}" >&2
    missing_templates+=("${rel_template_path}")
  fi
}

check_env_keys() {
  local template_path="$1"
  local env_path="$2"
  local rel_env_path="${env_path#"${ROOT_DIR}/"}"

  if [ ! -f "${template_path}" ] || [ ! -f "${env_path}" ]; then
    return
  fi

  while IFS='=' read -r key _; do
    if [ -z "${key}" ]; then
      continue
    fi
    if ! grep -q "^${key}=" "${env_path}"; then
      missing_keys+=("${rel_env_path}:${key}")
    fi
  done < <(grep -E '^[A-Z0-9_]+=' "${template_path}" | sed 's/[[:space:]]//g')
}

for target in "${env_targets[@]}"; do
  template="${ROOT_DIR}/${target}/.env.example"
  env_file="${ROOT_DIR}/${target}/.env"
  copy_env_if_missing "${template}" "${env_file}"
  check_env_keys "${template}" "${env_file}"
done

if ! command -v poetry >/dev/null 2>&1; then
  echo "[warn] Poetry not found. Skipping backend dependency installation." >&2
else
  services=(backend/api backend/embeddings backend/eval)
  for service in "${services[@]}"; do
    project_dir="${ROOT_DIR}/${service}"
    if [ -f "${project_dir}/pyproject.toml" ]; then
      echo "[info] Installing dependencies for ${service}" >&2
      (cd "${project_dir}" && poetry install --no-root)
    else
      echo "[warn] Skipping ${service} (pyproject.toml not found)" >&2
    fi
  done
fi

if ! command -v deno >/dev/null 2>&1; then
  echo "[warn] Deno not found. Skipping frontend dependency installation." >&2
else
  frontend_dir="${ROOT_DIR}/frontend"
  if [ -f "${frontend_dir}/deno.json" ]; then
    echo "[info] Installing frontend dependencies" >&2
    (cd "${frontend_dir}" && deno install --allow-scripts=npm:sharp)
  else
    echo "[warn] Skipping frontend (deno.json not found)" >&2
  fi
fi

if [ ${#missing_templates[@]} -gt 0 ]; then
  echo "[warn] Missing env templates:" >&2
  printf '  - %s\n' "${missing_templates[@]}" >&2
fi

if [ ${#missing_keys[@]} -gt 0 ]; then
  echo "[warn] Missing keys in env files:" >&2
  printf '  - %s\n' "${missing_keys[@]}" >&2
fi

echo "[done] Dependency installation complete." >&2

