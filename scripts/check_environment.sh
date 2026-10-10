#!/usr/bin/env bash

set -u

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
failures=0

pass() {
  printf 'PASS  %-20s %s\n' "$1" "$2"
}

fail() {
  printf 'FAIL  %-20s %s\n' "$1" "$2" >&2
  failures=$((failures + 1))
}

if [[ -s "${NVM_DIR:-$HOME/.nvm}/nvm.sh" ]]; then
  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  # shellcheck source=/dev/null
  . "$NVM_DIR/nvm.sh"
  if nvm use --silent "$(<"$project_root/.nvmrc")" >/dev/null; then
    node_version="$(node --version)"
    if [[ "$node_version" == v22.* ]]; then
      pass "Node.js" "$node_version via NVM"
    else
      fail "Node.js" "expected v22.x, got $node_version"
    fi
    pass "npm" "$(npm --version)"
  else
    fail "Node.js" "version from .nvmrc is not installed"
  fi
else
  fail "NVM" "${NVM_DIR:-$HOME/.nvm}/nvm.sh not found"
fi

venv_python="$project_root/.venv/bin/python"
if [[ -x "$venv_python" ]]; then
  python_version="$($venv_python --version 2>&1)"
  if [[ "$python_version" == "Python 3.12"* ]]; then
    pass "Python venv" "$python_version"
  else
    fail "Python venv" "expected Python 3.12.x, got $python_version"
  fi
  if "$venv_python" -m pip --version >/dev/null 2>&1; then
    pass "pip" "$($venv_python -m pip --version)"
  else
    fail "pip" "not installed in .venv"
  fi
else
  fail "Python venv" "$venv_python not found"
fi

if command -v docker >/dev/null 2>&1; then
  pass "Docker CLI" "$(docker --version)"
  if docker compose version >/dev/null 2>&1; then
    pass "Docker Compose" "$(docker compose version)"
  else
    fail "Docker Compose" "docker compose is unavailable"
  fi
  if docker info >/dev/null 2>&1; then
    pass "Docker daemon" "reachable"
  else
    fail "Docker daemon" "not reachable or current user lacks permission"
  fi
else
  fail "Docker CLI" "not installed"
  fail "Docker Compose" "not installed"
  fail "Docker daemon" "not available"
fi

if command -v psql >/dev/null 2>&1; then
  pass "PostgreSQL client" "$(psql --version)"
else
  fail "PostgreSQL client" "psql not installed"
fi

if ((failures > 0)); then
  printf '\nEnvironment check failed with %d issue(s).\n' "$failures" >&2
  exit 1
fi

printf '\nEnvironment check passed.\n'
