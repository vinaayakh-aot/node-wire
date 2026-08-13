#!/usr/bin/env bash
##
## SPDX-FileCopyrightText: 2026 AOT Technologies
## SPDX-License-Identifier: Apache-2.0
##
# Decide whether a PR touched files matching a POSIX ERE.
#
# Non-pull_request events always print run=true (push/schedule/dispatch).
# Pull requests list changed files via the GitHub API (paginated) and match
# PATH_REGEX. Writes run=true|false to GITHUB_OUTPUT so required jobs still
# report a status when analysis is skipped.
#
# Required env: GH_TOKEN, GITHUB_OUTPUT
# Optional env: EVENT_NAME (default github.event_name), REPO, PR_NUMBER
# Usage: bash .github/scripts/ci-pr-relevant.sh '<posix-ere>' [output-key]
# Default output key is "run".

set -euo pipefail

PATH_REGEX="${1:?usage: ci-pr-relevant.sh '<posix-ere>' [output-key]}"
OUTPUT_KEY="${2:-run}"
EVENT_NAME="${EVENT_NAME:-}"
REPO="${REPO:-}"
PR_NUMBER="${PR_NUMBER:-}"

if [[ -z "${GITHUB_OUTPUT:-}" ]]; then
  echo "ERROR: GITHUB_OUTPUT is not set" >&2
  exit 1
fi

if [[ "${EVENT_NAME}" != "pull_request" ]]; then
  echo "${OUTPUT_KEY}=true" >> "${GITHUB_OUTPUT}"
  echo "Non-PR event (${EVENT_NAME:-unset}): ${OUTPUT_KEY}=true"
  exit 0
fi

if [[ -z "${GH_TOKEN:-}" ]]; then
  echo "ERROR: GH_TOKEN is required to list pull request files" >&2
  exit 1
fi
if [[ -z "${REPO}" || -z "${PR_NUMBER}" ]]; then
  echo "ERROR: REPO and PR_NUMBER are required for pull_request events" >&2
  exit 1
fi

files="$(gh api --paginate "repos/${REPO}/pulls/${PR_NUMBER}/files" --jq '.[].filename')"
if [[ -z "${files}" ]]; then
  echo "${OUTPUT_KEY}=false" >> "${GITHUB_OUTPUT}"
  echo "No changed files on PR #${PR_NUMBER}; ${OUTPUT_KEY}=false"
  exit 0
fi

echo "Changed files:"
echo "${files}"

if echo "${files}" | grep -Eq "${PATH_REGEX}"; then
  echo "${OUTPUT_KEY}=true" >> "${GITHUB_OUTPUT}"
  echo "Relevant path change detected; ${OUTPUT_KEY}=true"
else
  echo "${OUTPUT_KEY}=false" >> "${GITHUB_OUTPUT}"
  echo "No paths matching /${PATH_REGEX}/; ${OUTPUT_KEY}=false"
fi
