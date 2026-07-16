#!/bin/sh
set -eu

config=${1:-.github/alloy/kpkg-telemetry.alloy}

test "$(grep -c 'key    = "loki.resource.labels"' "$config")" -eq 2
test "$(grep -c 'key    = "loki.attribute.labels"' "$config")" -eq 2
test "$(grep -c 'action = "delete"' "$config")" -eq 2
grep -F 'value  = "service.name"' "$config"
grep -F 'value  = "span_name,status,package_name,run3_stage"' "$config"
! grep -Eq 'trace(_id|\.id)|span(_id|\.id)' "$config"
grep -F 'otelcol.exporter.loki "grafana_cloud" {' "$config"
