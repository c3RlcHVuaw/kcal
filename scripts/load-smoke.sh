#!/usr/bin/env sh
set -eu

base_url="${1:-${PUBLIC_API_URL:-http://127.0.0.1:3100}}"
base_url="${base_url%/}"
total_requests="${LOAD_SMOKE_REQUESTS:-120}"
concurrency="${LOAD_SMOKE_CONCURRENCY:-8}"
max_p95_ms="${LOAD_SMOKE_MAX_P95_MS:-1500}"
endpoints="${LOAD_SMOKE_ENDPOINTS:-/health /health/ready / /landing/static/styles.css /landing/static/tracker.js}"

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required for load smoke checks but was not found." >&2
  exit 1
fi

case "$total_requests" in
  ''|*[!0-9]*)
    echo "LOAD_SMOKE_REQUESTS must be a positive integer." >&2
    exit 1
    ;;
esac

case "$concurrency" in
  ''|*[!0-9]*)
    echo "LOAD_SMOKE_CONCURRENCY must be a positive integer." >&2
    exit 1
    ;;
esac

case "$max_p95_ms" in
  ''|*[!0-9]*)
    echo "LOAD_SMOKE_MAX_P95_MS must be a positive integer." >&2
    exit 1
    ;;
esac

if [ "$total_requests" -lt 1 ] || [ "$concurrency" -lt 1 ]; then
  echo "LOAD_SMOKE_REQUESTS and LOAD_SMOKE_CONCURRENCY must be >= 1." >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT INT TERM

endpoint_file="$tmp_dir/endpoints"
result_file="$tmp_dir/results"
request_file="$tmp_dir/requests"

printf "%s\n" $endpoints > "$endpoint_file"
endpoint_count="$(wc -l < "$endpoint_file" | tr -d ' ')"
if [ "$endpoint_count" -lt 1 ]; then
  echo "No load-smoke endpoints configured." >&2
  exit 1
fi

awk -v total="$total_requests" -v count="$endpoint_count" '
  BEGIN {
    for (i = 1; i <= total; i += 1) {
      print ((i - 1) % count) + 1
    }
  }
' > "$request_file"

echo "Load smoke: $total_requests requests, concurrency $concurrency, p95 <= ${max_p95_ms}ms"
echo "Target: $base_url"

xargs -n 1 -P "$concurrency" sh -c '
  base_url="$1"
  endpoint_file="$2"
  index="$3"
  endpoint="$(sed -n "${index}p" "$endpoint_file")"
  url="${base_url}${endpoint}"
  line="$(curl --silent --show-error --output /dev/null \
    --connect-timeout 3 --max-time 10 \
    --write-out "%{http_code} %{time_total}" "$url" 2>/dev/null || true)"
  if [ -z "$line" ]; then
    line="000 10.000"
  fi
  printf "%s %s\n" "$line" "$endpoint"
' sh "$base_url" "$endpoint_file" < "$request_file" > "$result_file"

awk -v max_p95_ms="$max_p95_ms" '
  {
    status = $1 + 0
    ms = int(($2 * 1000) + 0.5)
    endpoint = $3
    count += 1
    sum += ms
    times[count] = ms
    endpoint_count[endpoint] += 1
    endpoint_sum[endpoint] += ms
    if (ms > endpoint_max[endpoint]) endpoint_max[endpoint] = ms
    if (status < 200 || status >= 400) {
      errors += 1
      error_status[status] += 1
      error_endpoint[endpoint] += 1
    }
  }
  END {
    if (count == 0) {
      print "No load-smoke results were produced." > "/dev/stderr"
      exit 1
    }
    errors += 0
    for (i = 1; i <= count; i += 1) {
      for (j = i + 1; j <= count; j += 1) {
        if (times[j] < times[i]) {
          tmp = times[i]
          times[i] = times[j]
          times[j] = tmp
        }
      }
    }
    p95_index = int(count * 0.95)
    if (p95_index < 1) p95_index = 1
    if (p95_index > count) p95_index = count
    p95 = times[p95_index]
    average = int((sum / count) + 0.5)
    print "Requests: " count
    print "Average: " average "ms"
    print "p95: " p95 "ms"
    print "Max: " times[count] "ms"
    print "Errors: " errors
    print ""
    print "By endpoint:"
    for (endpoint in endpoint_count) {
      endpoint_average = int((endpoint_sum[endpoint] / endpoint_count[endpoint]) + 0.5)
      print "  " endpoint ": count=" endpoint_count[endpoint] \
        " avg=" endpoint_average "ms max=" endpoint_max[endpoint] "ms errors=" error_endpoint[endpoint] + 0
    }
    if (errors > 0) {
      print "Load smoke failed: HTTP/network errors detected." > "/dev/stderr"
      for (status in error_status) {
        print "  status " status ": " error_status[status] > "/dev/stderr"
      }
      exit 1
    }
    if (p95 > max_p95_ms) {
      print "Load smoke failed: p95 " p95 "ms exceeds " max_p95_ms "ms." > "/dev/stderr"
      exit 1
    }
  }
' "$result_file"
