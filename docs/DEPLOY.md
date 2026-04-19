# Deployment And CI/CD

This project uses two GitHub Actions pipelines:

1. Model pipeline: publish versioned model artifacts to GCS.
2. Code pipeline: run quality gates and deploy Cloud Run services.

## Workflow Files

- `.github/workflows/model-release.yml`
- `.github/workflows/deploy.yml`

## Required CLI Tools

Install GitHub CLI (`gh`):

- macOS (Homebrew): `brew install gh`
- Linux / Windows and other methods: [GitHub CLI install docs](https://github.com/cli/cli#installation)

Install Google Cloud CLI (`gcloud`):

- macOS (Homebrew): `brew install --cask google-cloud-sdk`
- Linux / Windows and other methods: [Google Cloud CLI install docs](https://cloud.google.com/sdk/docs/install)

Verify both are available:

```bash
gh --version
gcloud --version
```

## Single Source Of Truth For Naming

Local deploy scripts read naming from `.env`:

- `GCP_PROJECT_ID=secsuite-phishing-mail-api`
- `GCP_REGION=europe-west1`
- `SERVICE_NAME=secsuite-phishing-mail-api`
- `STAGING_SERVICE_NAME=secsuite-phishing-mail-api-staging`
- `AR_REPO=secsuite-phishing-mail-api`
- `IMAGE_NAME=secsuite-phishing-mail-api`
- `MODEL_BUCKET=secsuite-phishing-mail-api-models-bucket`
- `MODEL_ARTIFACTS_PREFIX=secsuite-phishing-mail-api-models`
- `GHA_SA_NAME=gha-${GCP_PROJECT_ID}`
- `REPO_SLUG=secsuite/phishing-mail-api`

GitHub Actions cannot read local `.env`, so define the same values as repository variables.

## One-Time Bootstrap

### 1. Create project, billing, and APIs

If your GCP project does not exist yet:

```bash
set -a; source .env; set +a
gcloud auth login
gcloud projects create "$GCP_PROJECT_ID" --name="$GCP_PROJECT_ID"
gcloud billing accounts list
gcloud billing projects link "$GCP_PROJECT_ID" --billing-account="$(gcloud billing accounts list --filter='open=true' --format='value(ACCOUNT_ID)' --limit=1)"
```

Always run project and API setup:

```bash
set -a; source .env; set +a
gcloud config set project "$GCP_PROJECT_ID"
gcloud auth application-default set-quota-project "$GCP_PROJECT_ID"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com iamcredentials.googleapis.com sts.googleapis.com
```

### 2. Create model bucket and upload bootstrap artifacts

```bash
set -a; source .env; set +a
gcloud storage buckets create "gs://${MODEL_BUCKET}" --location="${GCP_REGION}"
gcloud storage rsync -r app/ml/models "gs://${MODEL_BUCKET}/${MODEL_ARTIFACTS_PREFIX}/bootstrap"
```

If `gcloud storage rsync` fails with `403 ... does not have storage.objects.get access`:

```bash
set -a; source .env; set +a
ACCOUNT="$(gcloud config get-value account)"
gcloud storage buckets add-iam-policy-binding "gs://${MODEL_BUCKET}" \
  --member="user:${ACCOUNT}" \
  --role="roles/storage.objectAdmin"
gcloud storage rsync -r app/ml/models "gs://${MODEL_BUCKET}/${MODEL_ARTIFACTS_PREFIX}/bootstrap"
```

If bucket IAM binding is denied, ask a project owner to grant your user
`roles/storage.objectAdmin` on `gs://${MODEL_BUCKET}` (or `roles/storage.admin` at project level).

### 3. Create runtime secret used by Cloud Run

```bash
grep '^PHISHING_MAIL_API_KEY=' .env | cut -d= -f2- | tr -d '\r' | gcloud secrets create PHISHING_MAIL_API_KEY --data-file=-
```

If secret exists already:

```bash
grep '^PHISHING_MAIL_API_KEY=' .env | cut -d= -f2- | tr -d '\r' | gcloud secrets versions add PHISHING_MAIL_API_KEY --data-file=-
```

### 4. Create GitHub Actions deploy service account and grant roles

```bash
set -a; source .env; set +a
PROJECT_ID="$GCP_PROJECT_ID"
GHA_SA_NAME="${GHA_SA_NAME:-gha-${PROJECT_ID}}"
GHA_SA_EMAIL="${GHA_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud iam service-accounts create "$GHA_SA_NAME" --display-name="GitHub Actions deployer"

gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:${GHA_SA_EMAIL}" --role="roles/cloudbuild.builds.editor"
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:${GHA_SA_EMAIL}" --role="roles/artifactregistry.admin"
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:${GHA_SA_EMAIL}" --role="roles/storage.admin"
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:${GHA_SA_EMAIL}" --role="roles/run.admin"
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:${GHA_SA_EMAIL}" --role="roles/iam.serviceAccountUser"
```

### 5. Configure Workload Identity Federation for GitHub OIDC

```bash
set -a; source .env; set +a
PROJECT_ID="$GCP_PROJECT_ID"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
POOL_ID=github
PROVIDER_ID=github-provider
GHA_SA_NAME="${GHA_SA_NAME:-gha-${PROJECT_ID}}"
GHA_SA_EMAIL="${GHA_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
REPO_SLUG="${REPO_SLUG:-secsuite/phishing-mail-api}"

gcloud iam workload-identity-pools create "$POOL_ID" \
  --project="$PROJECT_ID" \
  --location="global" \
  --display-name="GitHub pool"

gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_ID" \
  --display-name="GitHub provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository == '${REPO_SLUG}'"

gcloud iam service-accounts add-iam-policy-binding "$GHA_SA_EMAIL" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${REPO_SLUG}"

gcloud iam service-accounts add-iam-policy-binding "$GHA_SA_EMAIL" \
  --project="$PROJECT_ID" \
  --role="roles/iam.serviceAccountTokenCreator" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${REPO_SLUG}"
```

### 6. Grant Cloud Build and runtime service accounts required permissions

Cloud Build service account:

```bash
set -a; source .env; set +a
PROJECT_ID="$GCP_PROJECT_ID"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
CB_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:${CB_SA}" --role="roles/storage.objectViewer"
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:${CB_SA}" --role="roles/run.admin"
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:${CB_SA}" --role="roles/iam.serviceAccountUser"
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:${CB_SA}" --role="roles/secretmanager.secretAccessor"
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:${CB_SA}" --role="roles/artifactregistry.writer"
```

Cloud Run runtime service account:

```bash
set -a; source .env; set +a
PROJECT_ID="$GCP_PROJECT_ID"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/secretmanager.secretAccessor"
```

## GitHub Repository Configuration

### Required GitHub variables

- `GCP_PROJECT_ID`
- `GCP_REGION`
- `MODEL_BUCKET`
- `MODEL_ARTIFACTS_PREFIX`
- `SERVICE_NAME`
- `STAGING_SERVICE_NAME`
- `AR_REPO`
- `IMAGE_NAME`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT`

Set all required variables from `.env`:

```bash
set -a; source .env; set +a
PROJECT_NUMBER="$(gcloud projects describe "$GCP_PROJECT_ID" --format='value(projectNumber)')"
GHA_SA_NAME="${GHA_SA_NAME:-gha-${GCP_PROJECT_ID}}"
GHA_SA_EMAIL="${GHA_SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

gh variable set GCP_PROJECT_ID --body "$GCP_PROJECT_ID"
gh variable set GCP_REGION --body "$GCP_REGION"
gh variable set MODEL_BUCKET --body "$MODEL_BUCKET"
gh variable set MODEL_ARTIFACTS_PREFIX --body "$MODEL_ARTIFACTS_PREFIX"
gh variable set SERVICE_NAME --body "$SERVICE_NAME"
gh variable set STAGING_SERVICE_NAME --body "$STAGING_SERVICE_NAME"
gh variable set AR_REPO --body "$AR_REPO"
gh variable set IMAGE_NAME --body "$IMAGE_NAME"
gh variable set GCP_WORKLOAD_IDENTITY_PROVIDER --body "projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github/providers/github-provider"
gh variable set GCP_SERVICE_ACCOUNT --body "${GHA_SA_EMAIL}"
```

Recommended GitHub environments:

- `staging`
- `production` (add required reviewers)

## Pipeline Usage

First-time order:

1. Upload/prepare models in GCS.
2. Run `Model Release`.
3. Run `Deploy`.

### A. Model pipeline

Workflow: `Model Release`

```bash
set -a; source .env; set +a
gh workflow run "Model Release" \
  -f source_uri="gs://${MODEL_BUCKET}/${MODEL_ARTIFACTS_PREFIX}/bootstrap" \
  -f update_latest=true
```

### B. Code pipeline

Workflow: `Deploy`

- Push to `master` triggers staging deploy automatically.
- Manual staging run:

```bash
gh workflow run "Deploy" -f environment=staging
```

- Manual production run:

```bash
gh workflow run "Deploy" -f environment=production
```

## CI/CD Behavior

### Pull request to `master`

- Runs `Quality Gates` job.
- `make quality` is executed.

### Merge/push to `master`

- Does not rerun `Quality Gates`.
- Deploys automatically to staging.
- Makes staging service publicly invokable (`roles/run.invoker` for `allUsers`).
- Runs `/health` smoke check.

### Production deploy

- Manual only via `workflow_dispatch` with `environment=production`.
- Uses latest model pointer or explicit `model_artifacts_uri` input.
- Makes production service publicly invokable automatically.
- Runs `/health` smoke check.

## Model Release Flow

`model-release.yml` publishes versioned artifacts to:

- `gs://${MODEL_BUCKET}/${MODEL_ARTIFACTS_PREFIX}/<version>`

It writes:

- `manifest.json`
- `latest.txt` (when `update_latest=true`)

## Local Deploy Command

```bash
set -a; source .env; set +a
./deploy/cloudbuild-deploy.sh
```

## Post-Deploy

Get service URLs:

```bash
set -a; source .env; set +a
gcloud run services describe "$STAGING_SERVICE_NAME" --region="$GCP_REGION" --format='value(status.url)'
gcloud run services describe "$SERVICE_NAME" --region="$GCP_REGION" --format='value(status.url)'
```

Smoke endpoints:

- `https://<service-url>/health`
- `https://<service-url>/docs`

Public invoker policy is handled automatically in GitHub deploy workflow.
