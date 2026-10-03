#!/usr/bin/env bash
set -euo pipefail

PROJECT="dufynd-private-broker-01"
REGION="europe-west3"
SERVICE="dufynd-private-observer"
REGISTRY="europe-west3-docker.pkg.dev"
IMAGE_REPO="${REGISTRY}/${PROJECT}/broker/runtime"
SOURCE_REPO="https://github.com/tncommerce/commerce-agents.git"

usage() {
  echo "usage: $0 <40-char scentai-mvp commit sha>" >&2
  exit 2
}

SHA="${1:-}"
[[ "$SHA" =~ ^[a-f0-9]{40}$ ]] || usage
TAG="${SHA:0:8}"
IMAGE="${IMAGE_REPO}:${TAG}"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

echo "DUFYND private broker owner deploy"
echo "project=$PROJECT region=$REGION service=$SERVICE"
echo "commit=$SHA"
echo "image=$IMAGE"

gcloud config set project "$PROJECT" >/dev/null

git clone --quiet --filter=blob:none --no-checkout "$SOURCE_REPO" "$WORKDIR/repo"
git -C "$WORKDIR/repo" fetch --quiet --depth=1 origin "$SHA"
git -C "$WORKDIR/repo" checkout --quiet --detach FETCH_HEAD

ACTUAL_SHA="$(git -C "$WORKDIR/repo" rev-parse HEAD)"
if [[ "$ACTUAL_SHA" != "$SHA" ]]; then
  echo "refusing deploy: checked out sha does not match requested sha" >&2
  exit 3
fi

gcloud auth configure-docker "$REGISTRY" --quiet >/dev/null

docker build \
  -f "$WORKDIR/repo/private_broker/Dockerfile" \
  -t "$IMAGE" \
  "$WORKDIR/repo"

docker push "$IMAGE"

gcloud run services update "$SERVICE" \
  --project="$PROJECT" \
  --region="$REGION" \
  --image="$IMAGE" \
  --quiet

READY_REVISION="$(
  gcloud run services describe "$SERVICE" \
    --project="$PROJECT" \
    --region="$REGION" \
    --format='value(status.latestReadyRevisionName)'
)"
LATEST_REVISION="$(
  gcloud run services describe "$SERVICE" \
    --project="$PROJECT" \
    --region="$REGION" \
    --format='value(status.latestCreatedRevisionName)'
)"
DEPLOYED_IMAGE="$(
  gcloud run services describe "$SERVICE" \
    --project="$PROJECT" \
    --region="$REGION" \
    --format='value(spec.template.spec.containers[0].image)'
)"
LATEST_TRAFFIC="$(
  gcloud run services describe "$SERVICE" \
    --project="$PROJECT" \
    --region="$REGION" \
    --format='value(status.traffic[0].percent)'
)"

if [[ -z "$READY_REVISION" || "$READY_REVISION" != "$LATEST_REVISION" ]]; then
  echo "deploy verification failed: latest revision is not ready" >&2
  exit 4
fi
if [[ "$DEPLOYED_IMAGE" != "$IMAGE" ]]; then
  echo "deploy verification failed: service image mismatch" >&2
  exit 5
fi
if [[ "$LATEST_TRAFFIC" != "100" ]]; then
  echo "deploy verification failed: latest traffic is not 100 percent" >&2
  exit 6
fi

echo "verified_revision=$READY_REVISION"
echo "verified_image=$DEPLOYED_IMAGE"
echo "verified_traffic=100"
