#!/usr/bin/env bash
set -euo pipefail

# Requires the existing owner-controlled deployment channel and independently
# verified available capacity. This helper does not establish a zero-cost budget.
# It never configures authentication, defaults, IAM, secrets or new resources.
SOURCE_REPO="https://github.com/tncommerce/commerce-agents.git"
PROJECT="" REGION="" SERVICE="" IMAGE_REPO="" EXPECTED_ORIGIN="" SHA=""
EXISTING_IMAGE="" EXPECTED_RUNTIME_DIGEST="" BUILD_EVIDENCE=""

usage() {
  echo "usage: $0 --project PROJECT_ID --region REGION --service SERVICE --image-repository LOCATION-docker.pkg.dev/PROJECT/REPOSITORY/IMAGE --expected-origin https://SERVICE.run.app [--existing-image IMAGE@sha256:DIGEST --expected-runtime-digest sha256:DIGEST --build-evidence OWNER_BUILD_RECORD.json] <40-char commit sha>" >&2
  exit 2
}
die() { echo "refusing deploy: $1" >&2; exit 3; }

while (( $# )); do
  case "$1" in
    --project) [[ $# -ge 2 && -z "$PROJECT" ]] || usage; PROJECT="$2"; shift 2 ;;
    --region) [[ $# -ge 2 && -z "$REGION" ]] || usage; REGION="$2"; shift 2 ;;
    --service) [[ $# -ge 2 && -z "$SERVICE" ]] || usage; SERVICE="$2"; shift 2 ;;
    --image-repository) [[ $# -ge 2 && -z "$IMAGE_REPO" ]] || usage; IMAGE_REPO="$2"; shift 2 ;;
    --expected-origin) [[ $# -ge 2 && -z "$EXPECTED_ORIGIN" ]] || usage; EXPECTED_ORIGIN="$2"; shift 2 ;;
    --existing-image) [[ $# -ge 2 && -z "$EXISTING_IMAGE" ]] || usage; EXISTING_IMAGE="$2"; shift 2 ;;
    --expected-runtime-digest) [[ $# -ge 2 && -z "$EXPECTED_RUNTIME_DIGEST" ]] || usage; EXPECTED_RUNTIME_DIGEST="$2"; shift 2 ;;
    --build-evidence) [[ $# -ge 2 && -z "$BUILD_EVIDENCE" ]] || usage; BUILD_EVIDENCE="$2"; shift 2 ;;
    --*) usage ;;
    *) [[ -z "$SHA" ]] || usage; SHA="$1"; shift ;;
  esac
done
[[ "$SHA" =~ ^[a-f0-9]{40}$ ]] || usage
[[ "$PROJECT" =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]$ ]] || usage
[[ "$REGION" =~ ^[a-z][a-z0-9-]{1,62}$ ]] || usage
[[ "$SERVICE" =~ ^[a-z]([a-z0-9-]{0,61}[a-z0-9])?$ ]] || usage
[[ "$EXPECTED_ORIGIN" =~ ^https://[a-z0-9]([a-z0-9.-]*[a-z0-9])?\.run\.app$ ]] || usage
[[ "$IMAGE_REPO" =~ ^([a-z][a-z0-9-]*)-docker\.pkg\.dev/([a-z][a-z0-9-]*)/([a-z][a-z0-9_-]*)/([a-z0-9][a-z0-9._-]*)$ ]] || usage
REGISTRY_LOCATION="${BASH_REMATCH[1]}"
[[ "${BASH_REMATCH[2]}" == "$PROJECT" ]] || die "registry project does not match the explicit project"
REGISTRY_REPOSITORY="${BASH_REMATCH[3]}"
IMAGE="${IMAGE_REPO}:${SHA}"
RESUME=0
if [[ -n "$EXISTING_IMAGE$EXPECTED_RUNTIME_DIGEST$BUILD_EVIDENCE" ]]; then
  [[ -n "$EXISTING_IMAGE" && -n "$EXPECTED_RUNTIME_DIGEST" && -n "$BUILD_EVIDENCE" ]] || usage
  [[ "$EXISTING_IMAGE" == "$IMAGE_REPO@"* ]] || die "existing image is outside the bound repository"
  [[ "${EXISTING_IMAGE#"$IMAGE_REPO@"}" =~ ^sha256:[0-9a-f]{64}$ ]] || usage
  [[ "$EXPECTED_RUNTIME_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]] || usage
  RESUME=1
fi
EXECUTABLES=(gcloud docker python3)
if (( ! RESUME )); then EXECUTABLES+=(git); fi
for executable in "${EXECUTABLES[@]}"; do
  command -v "$executable" >/dev/null || die "required local CLI is unavailable"
done
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

# Parse bounded, projected non-secret JSON. Both bare and qualified SHA-256
# digests must resolve to the exact bound image repository; never trim a foreign
# URI down to its otherwise matching hash.
cat > "$WORKDIR/verify.py" <<'PY'
import json
import hashlib
import re
import subprocess
import sys
from pathlib import Path

stage, root, project, region, service, image_repo, origin, registry_location, repository, source_sha, existing_image, expected_runtime, build_evidence = sys.argv[1:]
root = Path(root)

def fail(reason):
    raise ValueError(reason)

def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            fail("ambiguous JSON metadata")
        result[key] = value
    return result

def load(name):
    source = root / name
    if not 1 <= source.stat().st_size <= 262144:
        fail("metadata size rejected")
    value = json.loads(source.read_text(), object_pairs_hook=unique)
    if not isinstance(value, dict):
        fail("metadata object required")
    return value

def digest(value):
    if not isinstance(value, str):
        fail("image digest missing")
    if value.startswith(image_repo + "@"):
        value = value[len(image_repo) + 1:]
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        fail("image digest or repository rejected")
    return value

def artifact_digest(name):
    summary = load(name)["image_summary"]
    resolved = digest(summary.get("digest"))
    if summary.get("fully_qualified_digest") != image_repo + "@" + resolved:
        fail("registry digest is not bound to the requested image")
    return resolved

def runtime_digest(root_digest):
    # Cloud Run executes the linux/amd64 child of an OCI index/manifest list.
    # Resolve only a digest-bound image in the already verified repository;
    # Docker uses the owner's existing registry credentials, never a new login.
    try:
        result = subprocess.run(
            ["docker", "buildx", "imagetools", "inspect", image_repo + "@" + root_digest,
             "--format", "{{json .Manifest}}"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        fail("bound registry manifest could not be read")
    if result.returncode or not 1 <= len(result.stdout) <= 262144:
        fail("bound registry manifest could not be read")
    manifest = json.loads(result.stdout, object_pairs_hook=unique)
    if not isinstance(manifest, dict) or manifest.get("digest") != root_digest:
        fail("registry manifest is not bound to the requested digest")
    image_types = {"application/vnd.oci.image.manifest.v1+json",
                   "application/vnd.docker.distribution.manifest.v2+json"}
    index_types = {"application/vnd.oci.image.index.v1+json",
                   "application/vnd.docker.distribution.manifest.list.v2+json"}
    if manifest.get("mediaType") in image_types and "manifests" not in manifest:
        # Buildx emits a descriptor (mediaType/digest/size) for a direct image;
        # schemaVersion belongs to the full index, not that descriptor.
        if "schemaVersion" in manifest and (type(manifest["schemaVersion"]) is not int or manifest["schemaVersion"] != 2):
            fail("registry image schema rejected")
        return root_digest
    descriptors = manifest.get("manifests")
    if manifest.get("mediaType") not in index_types or type(manifest.get("schemaVersion")) is not int or manifest["schemaVersion"] != 2 or not isinstance(descriptors, list) or not 1 <= len(descriptors) <= 1000:
        fail("registry manifest type or descriptors rejected")
    candidates, seen = [], set()
    for descriptor in descriptors:
        if not isinstance(descriptor, dict):
            fail("registry manifest descriptor rejected")
        child = descriptor.get("digest")
        if not isinstance(child, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", child) or child in seen:
            fail("registry manifest child digest rejected")
        seen.add(child)
        platform = descriptor.get("platform")
        if not isinstance(platform, dict):
            fail("registry manifest platform missing")
        if platform.get("os") == "linux" and platform.get("architecture") == "amd64":
            if descriptor.get("mediaType") not in image_types or platform.keys() - {"os", "architecture", "variant"} or platform.get("variant") not in {None, ""}:
                fail("registry runtime platform rejected")
            if descriptor.get("annotations", {}).get("vnd.docker.reference.type") == "attestation-manifest":
                fail("registry attestation is not a runtime image")
            candidates.append(child)
    if len(candidates) != 1:
        fail("registry manifest must select exactly one linux/amd64 image")
    return candidates[0]

def ready(status, metadata):
    generation, observed = metadata.get("generation"), status.get("observedGeneration")
    if type(generation) is not int or generation < 1 or type(observed) is not int or observed != generation:
        fail("resource reconciliation is incomplete")
    conditions = status.get("conditions")
    if not isinstance(conditions, list):
        fail("Ready condition missing")
    matches = [row for row in conditions if isinstance(row, dict) and row.get("type") == "Ready"]
    if len(matches) != 1 or matches[0].get("status") != "True":
        fail("resource is not Ready")

def service_state(name):
    value = load(name)
    metadata, status = value["metadata"], value["status"]
    project_info = load("project.json")
    if project_info.get("projectId") != project or project_info.get("lifecycleState") != "ACTIVE":
        fail("project identity or lifecycle mismatch")
    number = project_info.get("projectNumber")
    if not isinstance(number, str) or not re.fullmatch(r"[1-9][0-9]{0,19}", number):
        fail("project number missing")
    if metadata.get("name") != service or metadata.get("namespace") not in {project, number}:
        fail("service identity mismatch")
    if metadata.get("labels", {}).get("cloud.googleapis.com/location") != region:
        fail("service region mismatch")
    if status.get("url") != origin:
        fail("service origin mismatch")
    uid, version = metadata.get("uid"), metadata.get("resourceVersion")
    if not isinstance(uid, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{8,128}", uid):
        fail("service UID missing")
    if not isinstance(version, str) or not 1 <= len(version) <= 256:
        fail("service version missing")
    ready(status, metadata)
    revision = status.get("latestReadyRevisionName")
    if not isinstance(revision, str) or not re.fullmatch(re.escape(service) + r"-[a-z0-9-]+", revision):
        fail("ready revision identity missing")
    if revision != status.get("latestCreatedRevisionName"):
        fail("latest revision is not ready")
    traffic = status.get("traffic")
    if not isinstance(traffic, list) or not traffic or len(traffic) > 100:
        fail("traffic evidence missing")
    total = 0
    for row in traffic:
        if not isinstance(row, dict):
            fail("traffic evidence malformed")
        percent = row.get("percent", 0)
        if type(percent) is not int or not 0 <= percent <= 100:
            fail("traffic percentage malformed")
        if percent and row.get("revisionName") != revision:
            fail("traffic is not bound to the ready revision")
        total += percent
    if total != 100:
        fail("ready revision does not receive 100 percent traffic")
    routing = value["spec"].get("traffic")
    if not isinstance(routing, list) or len(routing) != 1 or routing[0].get("latestRevision") is not True or routing[0].get("revisionName") or type(routing[0].get("percent")) is not int or routing[0]["percent"] != 100:
        fail("image-only update requires existing latest-revision traffic policy")
    containers = value["spec"]["template"]["spec"]["containers"]
    if not isinstance(containers, list) or len(containers) != 1:
        fail("expected one broker container")
    image = containers[0].get("image")
    if not isinstance(image, str) or not re.fullmatch(re.escape(image_repo) + r"(?::[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}|@sha256:[0-9a-f]{64})", image):
        fail("current service image is outside the bound repository")
    return {"uid": uid, "resource_version": version, "generation": metadata["generation"],
            "revision": revision, "image": image, "namespace": metadata["namespace"]}

try:
    if stage == "build-evidence":
        # This is an explicitly supplied owner build record, not an invented
        # source attestation. A SHA-shaped tag or argument alone proves no origin.
        record = load(str(Path(build_evidence).resolve()))
        expected = {
            "version": 1,
            "source_repository": "https://github.com/tncommerce/commerce-agents.git",
            "source_sha": source_sha,
            "image": existing_image,
            "runtime_digest": expected_runtime,
        }
        if type(record.get("version")) is not int or any(record.get(k) != v for k, v in expected.items()):
            fail("owner build evidence does not bind the requested source and image")
        ref = record.get("evidence_ref")
        if not isinstance(ref, str) or not 1 <= len(ref) <= 1024 or any(ord(c) < 32 for c in ref) or not ref.strip():
            fail("owner build evidence reference missing or malformed")
        if record.keys() != expected.keys() | {"evidence_ref"}:
            fail("owner build evidence schema rejected")
        # Keep the exact validated record private and stable for this invocation.
        encoded = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
        (root / "owner-build-record.json").write_bytes(encoded)
        (root / "owner-build-record.sha256").write_text(hashlib.sha256(encoded).hexdigest())
    elif stage == "preflight":
        state = service_state("service.json")
        repo = load("repository.json")
        number = load("project.json")["projectNumber"]
        names = {f"projects/{p}/locations/{registry_location}/repositories/{repository}" for p in (project, number)}
        if repo.get("name") not in names or repo.get("format") != "DOCKER" or repo.get("mode") != "STANDARD_REPOSITORY":
            fail("registry repository identity, format or mode mismatch")
        (root / "preflight.json").write_text(json.dumps(state, sort_keys=True))
        print(state["revision"])
    elif stage == "unchanged":
        if service_state("service-current.json") != load("preflight.json"):
            fail("service changed since preflight; no image update performed")
    elif stage == "artifact":
        resolved = artifact_digest("artifact.json")
        if existing_image:
            if image_repo + "@" + resolved != existing_image:
                fail("published image does not match the explicit existing digest")
            if artifact_digest("artifact-tag.json") != resolved:
                fail("source-SHA tag does not resolve to the explicit existing digest")
        selected_runtime = runtime_digest(resolved)
        if existing_image and selected_runtime != expected_runtime:
            fail("registry runtime child does not match the owner build evidence")
        (root / "expected-runtime-digest").write_text(selected_runtime)
        print(resolved)
    elif stage in {"revision-before", "revision-after"}:
        state = load("preflight.json") if stage == "revision-before" else service_state("service-after.json")
        revision = load("revision.json")
        metadata, status = revision["metadata"], revision["status"]
        if metadata.get("name") != state["revision"] or metadata.get("namespace") != state["namespace"]:
            fail("revision identity mismatch")
        if metadata.get("labels", {}).get("serving.knative.dev/service") != service:
            fail("revision belongs to another service")
        ready(status, metadata)
        resolved = digest(status.get("imageDigest"))
        if stage == "revision-before":
            if "@" in state["image"] and digest(state["image"]) != resolved and runtime_digest(digest(state["image"])) != resolved:
                fail("current image and ready revision disagree")
        else:
            initial = load("preflight.json")
            expected = (root / "expected-digest").read_text().strip()
            expected_runtime = (root / "expected-runtime-digest").read_text().strip()
            if state["uid"] != initial["uid"] or state["namespace"] != initial["namespace"]:
                fail("service identity changed during deployment")
            if resolved != expected_runtime or state["image"] != image_repo + "@" + expected:
                fail("ready revision digest mismatch")
            print(state["revision"])
    elif stage == "final-service":
        print(service_state("service-after.json")["revision"])
    else:
        fail("unknown verification stage")
except (KeyError, TypeError, ValueError, OSError, AttributeError, IndexError, RecursionError) as exc:
    message = str(exc) if type(exc) is ValueError else "metadata validation failed"
    print("refusing deploy: " + message, file=sys.stderr)
    sys.exit(3)
PY

verify() {
  python3 "$WORKDIR/verify.py" "$1" "$WORKDIR" "$PROJECT" "$REGION" "$SERVICE" \
    "$IMAGE_REPO" "$EXPECTED_ORIGIN" "$REGISTRY_LOCATION" "$REGISTRY_REPOSITORY" \
    "$SHA" "$EXISTING_IMAGE" "$EXPECTED_RUNTIME_DIGEST" "$BUILD_EVIDENCE"
}

if (( RESUME )); then verify build-evidence; fi
docker buildx version > "$WORKDIR/cli-result" 2> "$WORKDIR/cli-error" \
  || die "required local Docker buildx is unavailable"

# Read-only target checks precede clone/build/push. Every gcloud command has an
# explicit project; the user's current default project is neither read nor set.
gcloud projects describe "$PROJECT" --project="$PROJECT" \
  --format='json(projectId,projectNumber,lifecycleState)' --quiet > "$WORKDIR/project.json" 2> "$WORKDIR/cli-error" \
  || die "existing project could not be read"
gcloud artifacts repositories describe "$REGISTRY_REPOSITORY" --project="$PROJECT" --location="$REGISTRY_LOCATION" \
  --format='json(name,format,mode)' --quiet > "$WORKDIR/repository.json" 2> "$WORKDIR/cli-error" \
  || die "existing registry repository could not be read"

describe_service() {
  gcloud run services describe "$SERVICE" --project="$PROJECT" --region="$REGION" \
    --format='json(metadata.name,metadata.namespace,metadata.uid,metadata.resourceVersion,metadata.generation,metadata.labels,status.observedGeneration,status.conditions,status.url,status.latestReadyRevisionName,status.latestCreatedRevisionName,status.traffic,spec.traffic,spec.template.spec.containers[].image)' \
    --quiet > "$1" 2> "$WORKDIR/cli-error" || die "existing service could not be read"
}
describe_revision() {
  gcloud run revisions describe "$1" --project="$PROJECT" --region="$REGION" \
    --format='json(metadata.name,metadata.namespace,metadata.generation,metadata.labels,status.observedGeneration,status.conditions,status.imageDigest)' \
    --quiet > "$WORKDIR/revision.json" 2> "$WORKDIR/cli-error" || die "revision could not be read"
}

describe_service "$WORKDIR/service.json"
PREVIOUS_REVISION="$(verify preflight)"
describe_revision "$PREVIOUS_REVISION"
verify revision-before
echo "verified_target=$PROJECT/$REGION/$SERVICE"
echo "verified_origin=$EXPECTED_ORIGIN"

if (( RESUME )); then
  # No clone, build or upload: the owner already published this immutable image.
  # Check both its explicit digest and the source-SHA tag; deploy only the digest.
  gcloud artifacts docker images describe "$EXISTING_IMAGE" --project="$PROJECT" \
    --format='json(image_summary.digest,image_summary.fully_qualified_digest)' --quiet \
    > "$WORKDIR/artifact.json" 2> "$WORKDIR/cli-error" || die "existing image digest could not be read"
  gcloud artifacts docker images describe "$IMAGE" --project="$PROJECT" \
    --format='json(image_summary.digest,image_summary.fully_qualified_digest)' --quiet \
    > "$WORKDIR/artifact-tag.json" 2> "$WORKDIR/cli-error" || die "source-SHA image tag could not be read"
else
  git clone --quiet --filter=blob:none --no-checkout "$SOURCE_REPO" "$WORKDIR/repo"
  git -C "$WORKDIR/repo" fetch --quiet --depth=1 origin "$SHA"
  git -C "$WORKDIR/repo" checkout --quiet --detach FETCH_HEAD
  ACTUAL_SHA="$(git -C "$WORKDIR/repo" rev-parse HEAD)"
  [[ "$ACTUAL_SHA" == "$SHA" ]] || die "checked out sha does not match requested sha"

  # Docker registry authentication must already exist in the owner environment.
  docker build -f "$WORKDIR/repo/private_broker/Dockerfile" -t "$IMAGE" "$WORKDIR/repo"
  describe_service "$WORKDIR/service-current.json"
  verify unchanged
  docker push "$IMAGE"
  gcloud artifacts docker images describe "$IMAGE" --project="$PROJECT" \
    --format='json(image_summary.digest,image_summary.fully_qualified_digest)' --quiet \
    > "$WORKDIR/artifact.json" 2> "$WORKDIR/cli-error" || die "pushed image digest could not be read"
fi
DIGEST="$(verify artifact)"
PINNED_IMAGE="${IMAGE_REPO}@${DIGEST}"
printf '%s\n' "$DIGEST" > "$WORKDIR/expected-digest"

# Do not overwrite another rollout that occurred during build/push. This is a
# readback guard, not an atomic lock against a concurrent owner deployment.
describe_service "$WORKDIR/service-current.json"
verify unchanged
gcloud run services update "$SERVICE" --project="$PROJECT" --region="$REGION" \
  --image="$PINNED_IMAGE" --quiet > "$WORKDIR/update-result" 2> "$WORKDIR/cli-error" \
  || die "image-only service update failed"

describe_service "$WORKDIR/service-after.json"
READY_REVISION="$(verify final-service)"
describe_revision "$READY_REVISION"
verify revision-after >/dev/null
echo "verified_revision=$READY_REVISION"
echo "verified_image=$PINNED_IMAGE"
echo "verified_runtime_image=${IMAGE_REPO}@$(cat "$WORKDIR/expected-runtime-digest")"
if (( RESUME )); then
  echo "verified_owner_build_record_sha256=$(cat "$WORKDIR/owner-build-record.sha256")"
fi
echo "verified_traffic=100"
