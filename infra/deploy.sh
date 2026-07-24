#!/usr/bin/env bash
# Build, push, and deploy the container-image Lambda. Run from anywhere.
set -euo pipefail

cd "$(dirname "$0")"

REGION="us-east-1"
REPO_URL="$(terraform output -raw ecr_repository_url)"

# The tag identifies the commit, plus a marker when the working tree is dirty,
# so a tag never claims to be a clean commit that it isn't.
TAG="$(git rev-parse --short HEAD)"
if ! git diff-index --quiet HEAD --; then
  TAG="${TAG}-dirty-$(date +%Y%m%d%H%M%S)"
fi

echo "==> deploying tag: ${TAG}"

aws ecr get-login-password --region "${REGION}" \
  | docker login --username AWS --password-stdin "${REPO_URL%%/*}"

# --provenance and --sbom off on purpose: buildx otherwise tags an OCI image
# index bundling the image with attestations, which Lambda cannot resolve. It
# fails at CreateFunction with "media type ... is not supported", not at build
# or push, so the cause is far from the symptom.
docker build \
  --platform linux/amd64 \
  --provenance=false \
  --sbom=false \
  -f ../Dockerfile.lambda \
  -t "${REPO_URL}:${TAG}" \
  ..

docker push "${REPO_URL}:${TAG}"

terraform apply -var="image_tag=${TAG}"

echo
echo "==> live at: $(terraform output -raw api_base_url)"