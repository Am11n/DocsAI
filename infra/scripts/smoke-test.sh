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

if [[ -n "${AUTH_TOKEN:-}" ]]; then
  echo "Authenticated endpoint checks"
  curl -fsS -H "Authorization: Bearer ${AUTH_TOKEN}" "${API_BASE_URL}/documents" >/dev/null
else
  echo "Skipping authenticated checks (set AUTH_TOKEN to enable)"
fi

echo "Smoke checks passed"
