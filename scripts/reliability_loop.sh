#!/usr/bin/env bash
set -euo pipefail

STAGES=(
  "execution"
  "deterministic_validation"
  "human_reports"
  "cursor_rules"
  "corrections"
  "integration_summary"
)

FROM_STAGE=""
UNTIL_STAGE=""
RUN_ID="${RUN_ID:-$(date +%Y%m%d_%H%M%S)}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${REPO_ROOT}/runs/${RUN_ID}"
LOG_DIR="${RUN_DIR}/logs"
ARTIFACT_DIR="${RUN_DIR}/artifacts"

usage() {
  cat <<EOF
Usage: $0 [--from stage] [--until stage] [--run-id id]

Stages:
  execution
  deterministic_validation
  human_reports
  cursor_rules
  corrections
  integration_summary
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from)
      FROM_STAGE="${2:-}"
      shift 2
      ;;
    --until)
      UNTIL_STAGE="${2:-}"
      shift 2
      ;;
    --run-id)
      RUN_ID="${2:-}"
      RUN_DIR="${REPO_ROOT}/runs/${RUN_ID}"
      LOG_DIR="${RUN_DIR}/logs"
      ARTIFACT_DIR="${RUN_DIR}/artifacts"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

mkdir -p "${LOG_DIR}" "${ARTIFACT_DIR}" "${REPO_ROOT}/validation_out/rules" "${REPO_ROOT}/validation_out/reports/${RUN_ID}" "${RUN_DIR}/corrections"

index_of() {
  local needle="$1"
  local i
  for i in "${!STAGES[@]}"; do
    if [[ "${STAGES[$i]}" == "${needle}" ]]; then
      echo "$i"
      return 0
    fi
  done
  echo "-1"
}

FROM_INDEX=0
UNTIL_INDEX=$((${#STAGES[@]} - 1))
if [[ -n "${FROM_STAGE}" ]]; then
  FROM_INDEX=$(index_of "${FROM_STAGE}")
fi
if [[ -n "${UNTIL_STAGE}" ]]; then
  UNTIL_INDEX=$(index_of "${UNTIL_STAGE}")
fi
if [[ "${FROM_INDEX}" -lt 0 || "${UNTIL_INDEX}" -lt 0 || "${FROM_INDEX}" -gt "${UNTIL_INDEX}" ]]; then
  echo "Invalid stage bounds: from=${FROM_STAGE:-start}, until=${UNTIL_STAGE:-end}"
  exit 2
fi

run_stage() {
  local stage="$1"
  local log_file="${LOG_DIR}/${stage}.log"
  echo "[reliability-loop] stage=${stage} run_id=${RUN_ID}" | tee -a "${log_file}"
  case "${stage}" in
    execution)
      python "${REPO_ROOT}/scripts/write_observed_values.py" \
        --reference "${REPO_ROOT}/configs/reference_values_2016.yaml" \
        --output "${ARTIFACT_DIR}/observed_values.json" >>"${log_file}" 2>&1
      ;;
    deterministic_validation)
      python "${REPO_ROOT}/validation/check_published_values.py" \
        --reference "${REPO_ROOT}/configs/reference_values_2016.yaml" \
        --observed "${ARTIFACT_DIR}/observed_values.json" \
        --output "${REPO_ROOT}/validation_out/checks.json" >>"${log_file}" 2>&1
      ;;
    human_reports)
      python "${REPO_ROOT}/scripts/generate_report_bundle.py" \
        --checks "${REPO_ROOT}/validation_out/checks.json" \
        --run-id "${RUN_ID}" \
        --output-dir "${REPO_ROOT}/validation_out/reports/${RUN_ID}" >>"${log_file}" 2>&1
      ;;
    cursor_rules)
      python "${REPO_ROOT}/scripts/write_smoke_results.py" \
        --config "${REPO_ROOT}/configs/cursor_rules_tests.yaml" \
        --output "${ARTIFACT_DIR}/cursor_rules_smoke.json" >>"${log_file}" 2>&1
      python "${REPO_ROOT}/validation/check_cursor_rules.py" \
        --config "${REPO_ROOT}/configs/cursor_rules_tests.yaml" \
        --smoke "${ARTIFACT_DIR}/cursor_rules_smoke.json" \
        --output "${REPO_ROOT}/validation_out/rules/${RUN_ID}.json" >>"${log_file}" 2>&1
      ;;
    corrections)
      python "${REPO_ROOT}/corrections/apply_corrections.py" \
        --registry "${REPO_ROOT}/corrections/correction_registry.yaml" \
        --input "${REPO_ROOT}/validation_out/checks.json" \
        --output-dir "${RUN_DIR}/corrections" \
        --run-id "${RUN_ID}" >>"${log_file}" 2>&1
      ;;
    integration_summary)
      python "${REPO_ROOT}/scripts/summarize_run.py" \
        --run-id "${RUN_ID}" \
        --repo-root "${REPO_ROOT}" \
        --output "${RUN_DIR}/summary.json" >>"${log_file}" 2>&1
      ;;
    *)
      echo "Unsupported stage: ${stage}" >>"${log_file}" 2>&1
      return 3
      ;;
  esac
}

for i in "${!STAGES[@]}"; do
  if [[ "$i" -lt "${FROM_INDEX}" || "$i" -gt "${UNTIL_INDEX}" ]]; then
    continue
  fi
  run_stage "${STAGES[$i]}"
done

echo "[reliability-loop] complete run_id=${RUN_ID}"
