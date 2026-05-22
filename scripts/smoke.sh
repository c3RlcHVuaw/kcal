#!/usr/bin/env sh
set -eu

base_url="${1:-${PUBLIC_API_URL:-http://127.0.0.1:3100}}"
base_url="${base_url%/}"

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required for smoke checks but was not found." >&2
  exit 1
fi

echo "Checking $base_url/health"
curl --fail --silent --show-error "$base_url/health"
echo

echo "Checking $base_url/health/ready"
curl --fail --silent --show-error "$base_url/health/ready"
echo
