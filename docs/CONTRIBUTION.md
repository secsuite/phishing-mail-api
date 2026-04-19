# Contribution Guide

## Branch Strategy

- `master` is protected.
- No direct pushes to `master`.
- Every change must go through a pull request.
- Self-merge is allowed when required checks pass.

## Local Quality Gates

Install local tooling and hooks:

```bash
make install-runtime
```

Pre-push runs automatically and blocks push on failures:

- `make quality` = format check + lint + mypy + fast tests.
- Integration tests are excluded from local pre-push by default.

Run commands directly when needed:

```bash
make quality
make quality-fix
make test-fast
make test-integration
```

## Unit vs Integration Tests

- Unit/fast: `pytest -m "not integration"` (default local quality gate).
- Integration: `pytest -m "integration"` (real model/runtime path, optional external deps).
- Integration tests that require secrets must use explicit markers and env guards.

## PR and Merge Expectations

1. Create branch from `master`.
2. Commit normally (lightweight pre-commit checks).
3. Push branch (pre-push runs `make quality`).
4. Open PR to `master`.
5. Wait for `Quality Gates` in GitHub Actions (includes integration tests in CI).
6. Merge only after required checks pass.

## Branch Protection (Automated with gh)

Apply once (repo admin):

```bash
export REPO="secsuite/phishing-mail-api"
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
```
