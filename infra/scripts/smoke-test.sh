#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${API_BASE_URL:-}" ]]; then
  echo "Set API_BASE_URL, e.g. http://localhost:8000"
  exit 1
fi

echo "Health checks"
curl -fsS "${API_BASE_URL}/health/live" >/dev/null
curl -fsS "${API_BASE_URL}/health/ready" >/dev/null
curl -fsS "${API_BASE_URL}/metrics" >/dev/null

echo "Smoke checks passed"
