#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-secsuite/phishing-mail-api}"

gh api --method PUT \
  -H "Accept: application/vnd.github+json" \
  "/repos/${REPO}/branches/master/protection" \
  -f required_status_checks.strict=true \
  -f required_status_checks.contexts[]='Quality Gates' \
  -f enforce_admins=true \
  -f required_pull_request_reviews.required_approving_review_count=0 \
  -f required_linear_history=true \
  -F restrictions='null' \
  -F allow_force_pushes=false \
  -F allow_deletions=false
