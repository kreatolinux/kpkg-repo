#!/bin/sh
set -eu

config=${1:-.github/alloy/kpkg-telemetry.alloy}

assert_hint_actions() {
  hint=$1
  value=$2

  actions=$(awk -v hint="$hint" '
    /^[[:space:]]*action[[:space:]]*\{/ {
      in_action = 1
      key = op = val = ""
      next
    }
    in_action && /^[[:space:]]*key[[:space:]]*=/ {
      key = $3
      gsub(/"/, "", key)
      next
    }
    in_action && /^[[:space:]]*action[[:space:]]*=/ {
      op = $3
      gsub(/"/, "", op)
      next
    }
    in_action && /^[[:space:]]*value[[:space:]]*=/ {
      val = $3
      gsub(/"/, "", val)
      next
    }
    in_action && /^[[:space:]]*\}/ {
      if (key == hint) {
        print op "=" val
      }
      in_action = 0
    }
  ' "$config")

  test "$actions" = "delete=
insert=$value"
}

assert_hint_actions "loki.resource.labels" "service.name"
assert_hint_actions "loki.attribute.labels" "span_name,status,package_name,run3_stage"
! grep -Eq 'trace(_id|\.id)|span(_id|\.id)' "$config"
grep -F 'otelcol.exporter.loki "grafana_cloud" {' "$config"
