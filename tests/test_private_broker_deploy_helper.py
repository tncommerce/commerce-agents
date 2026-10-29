from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from subprocess import run

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/deploy_dufynd_private_broker.sh"
PROJECT = "dufynd-private-broker"
NUMBER = "592985661274"
REGION = "europe-west3"
SERVICE = "dufynd-private-observer"
ORIGIN = f"https://{SERVICE}-{NUMBER}.{REGION}.run.app"
REPO = f"{REGION}-docker.pkg.dev/{PROJECT}/broker/runtime"
SHA = "a" * 40
OLD_DIGEST = "sha256:" + "1" * 64
DIGEST = "sha256:" + "2" * 64
OLD_RUNTIME_DIGEST = "sha256:" + "3" * 64
RUNTIME_DIGEST = "sha256:" + "4" * 64
OLD_REVISION = SERVICE + "-00004-old"
REVISION = SERVICE + "-00005-new"
ARGS = [
    "--project",
    PROJECT,
    "--region",
    REGION,
    "--service",
    SERVICE,
    "--image-repository",
    REPO,
    "--expected-origin",
    ORIGIN,
    SHA,
]


def service(*, after=False):
    revision = REVISION if after else OLD_REVISION
    generation = 5 if after else 4
    return {
        "metadata": {
            "name": SERVICE,
            "namespace": NUMBER,
            "uid": "service-uid-12345678",
            "resourceVersion": f"version-{generation}",
            "generation": generation,
            "labels": {"cloud.googleapis.com/location": REGION},
        },
        "spec": {
            "traffic": [{"latestRevision": True, "percent": 100}],
            "template": {
                "spec": {"containers": [{"image": REPO + "@" + (DIGEST if after else OLD_DIGEST)}]}
            },
        },
        "status": {
            "observedGeneration": generation,
            "conditions": [{"type": "Ready", "status": "True"}],
            "url": ORIGIN,
            "latestReadyRevisionName": revision,
            "latestCreatedRevisionName": revision,
            "traffic": [{"revisionName": revision, "latestRevision": True, "percent": 100}],
        },
    }


def revision(*, after=False):
    return {
        "metadata": {
            "name": REVISION if after else OLD_REVISION,
            "namespace": NUMBER,
            "generation": 1,
            "labels": {"serving.knative.dev/service": SERVICE},
        },
        "status": {
            "observedGeneration": 1,
            "conditions": [{"type": "Ready", "status": "True"}],
            "imageDigest": REPO + "@" + (DIGEST if after else OLD_DIGEST),
        },
    }


MOCK_CLI = r"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

root = Path(os.environ["DUFYND_DEPLOY_FIXTURE"])
config = json.loads((root / "config.json").read_text())
state_path = root / "state.json"
state = json.loads(state_path.read_text()) if state_path.exists() else {}
tool, args = Path(sys.argv[0]).name, sys.argv[1:]
with (root / "calls.jsonl").open("a") as log:
    log.write(json.dumps([tool, *args]) + "\n")

def fail():
    print("private-provider-diagnostic-canary", file=sys.stderr)
    sys.exit(19)

def output(key):
    if config.get("fail") == key:
        fail()
    raw = config.get("raw", {}).get(key)
    print(raw if raw is not None else json.dumps(config[key]))

if tool == "gcloud":
    if "--project=" + config["project"]["projectId_expected"] not in args:
        sys.exit(98)
    if args[:2] == ["projects", "describe"]:
        output("project")
    elif args[:3] == ["artifacts", "repositories", "describe"]:
        if "--location=europe-west3" not in args:
            sys.exit(98)
        output("repository")
    elif args[:3] == ["run", "services", "describe"]:
        if "--region=europe-west3" not in args:
            sys.exit(98)
        # The official SDK structured JSON projector requires an array slice;
        # the unindexed containers.image path does not retain container objects.
        formats = [arg for arg in args if arg.startswith("--format=")]
        if len(formats) != 1 or "spec.template.spec.containers[].image)" not in formats[0]:
            sys.exit(98)
        state["service_reads"] = state.get("service_reads", 0) + 1
        if state.get("updated"):
            output("service_after")
        elif state["service_reads"] == config.get("drift_read"):
            output("service_drift")
        else:
            output("service")
    elif args[:3] == ["run", "revisions", "describe"]:
        if "--region=europe-west3" not in args:
            sys.exit(98)
        output("revision_after" if args[3] == config["revision_after"]["metadata"]["name_expected"] else "revision")
    elif args[:4] == ["artifacts", "docker", "images", "describe"]:
        source_tag = config["image_repository"] + ":" + "a" * 40
        output("artifact_tag" if args[4] == source_tag and "artifact_tag" in config else "artifact")
    elif args[:3] == ["run", "services", "update"]:
        # No incidental auth, IAM, traffic, scaling, environment or secret flags.
        expected = ["run", "services", "update", "dufynd-private-observer",
                    "--project=dufynd-private-broker", "--region=europe-west3",
                    "--image=" + config["expected_image"], "--quiet"]
        if args != expected:
            sys.exit(98)
        if config.get("fail") == "update":
            fail()
        state["updated"] = True
    else:
        sys.exit(99)
elif tool == "git":
    if args[0] == "clone":
        Path(args[-1]).mkdir()
    elif args[0] == "-C" and args[2] in {"fetch", "checkout"}:
        pass
    elif args[0] == "-C" and args[2:] == ["rev-parse", "HEAD"]:
        print(config.get("checkout_sha", "a" * 40))
    else:
        sys.exit(99)
elif tool == "docker" and args == ["buildx", "version"]:
    if config.get("fail") == "buildx":
        fail()
elif tool == "docker" and args[0] in {"build", "push"}:
    if config.get("fail") == args[0]:
        fail()
elif tool == "docker" and args[:3] == ["buildx", "imagetools", "inspect"]:
    if len(args) != 6 or args[4:] != ["--format", "{{json .Manifest}}"]:
        sys.exit(98)
    if not args[3].startswith(config["image_repository"] + "@"):
        sys.exit(98)
    image_digest = args[3].split("@", 1)[1]
    if config.get("fail") == "manifest":
        fail()
    raw = config.get("raw", {}).get("manifest")
    print(raw if raw is not None else json.dumps(config["manifests"][image_digest]))
else:
    sys.exit(99)
state_path.write_text(json.dumps(state))
"""


@pytest.fixture
def owner_cli(tmp_path):
    binaries = tmp_path / "bin"
    binaries.mkdir()
    for name in ("gcloud", "docker", "git"):
        executable = binaries / name
        executable.write_text(MOCK_CLI)
        executable.chmod(0o755)
    baseline = {
        "project": {
            "projectId": PROJECT,
            "projectId_expected": PROJECT,
            "projectNumber": NUMBER,
            "lifecycleState": "ACTIVE",
        },
        "repository": {
            "name": f"projects/{PROJECT}/locations/{REGION}/repositories/broker",
            "format": "DOCKER",
            "mode": "STANDARD_REPOSITORY",
        },
        "service": service(),
        "service_after": service(after=True),
        "revision": revision(),
        "revision_after": revision(after=True),
        "artifact": {
            "image_summary": {"digest": DIGEST, "fully_qualified_digest": REPO + "@" + DIGEST}
        },
        "expected_image": REPO + "@" + DIGEST,
        "image_repository": REPO,
        "manifests": {
            image_digest: {
                "schemaVersion": 2,
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "digest": image_digest,
            }
            for image_digest in (OLD_DIGEST, DIGEST)
        },
    }
    baseline["revision_after"]["metadata"]["name_expected"] = REVISION

    def execute(config=None, args=None):
        (tmp_path / "config.json").write_text(json.dumps(config or baseline))
        environment = dict(
            os.environ,
            PATH=str(binaries) + os.pathsep + os.environ["PATH"],
            DUFYND_DEPLOY_FIXTURE=str(tmp_path),
            CLOUDSDK_CORE_PROJECT="unrelated-user-default",
        )
        result = run(
            ["bash", str(SCRIPT), *(ARGS if args is None else args)],
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        log = tmp_path / "calls.jsonl"
        calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
        return result, calls

    return baseline, execute


def is_update(call):
    return call[:4] == ["gcloud", "run", "services", "update"]


def assert_no_build_or_remote_write(calls):
    assert all(
        (call[0] == "gcloud" and "describe" in call and not is_update(call))
        or call[:4] == ["docker", "buildx", "imagetools", "inspect"]
        or call == ["docker", "buildx", "version"]
        for call in calls
    )


def test_helper_has_valid_bash_syntax():
    result = run(["bash", "-n", str(SCRIPT)], check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("bare_digest", [False, True])
@pytest.mark.parametrize("descriptor_only", [False, True])
def test_bound_existing_target_deploys_only_image_and_verifies_exact_ready_traffic(
    owner_cli, bare_digest, descriptor_only
):
    config, execute = owner_cli
    if bare_digest:
        config["revision"]["status"]["imageDigest"] = OLD_DIGEST
        config["revision_after"]["status"]["imageDigest"] = DIGEST
    if descriptor_only:
        del config["manifests"][DIGEST]["schemaVersion"]
    result, calls = execute(config)
    assert result.returncode == 0, result.stderr
    assert f"verified_revision={REVISION}" in result.stdout
    assert f"verified_image={REPO}@{DIGEST}" in result.stdout
    assert "verified_traffic=100" in result.stdout
    first_clone = next(i for i, call in enumerate(calls) if call[:2] == ["git", "clone"])
    assert_no_build_or_remote_write(calls[:first_clone])
    assert len(calls[:first_clone]) == 5
    assert len([call for call in calls if is_update(call)]) == 1
    assert [call[:2] for call in calls if call[0] == "docker"] == [
        ["docker", "buildx"],
        ["docker", "build"],
        ["docker", "push"],
        ["docker", "buildx"],
    ]
    for call in calls:
        if call[0] == "gcloud":
            assert f"--project={PROJECT}" in call
            assert not any("env" in item or "secret" in item for item in call[1:])
            assert call[1] not in {"config", "auth", "services", "billing", "iam"}


@pytest.mark.parametrize(
    "args",
    [
        [SHA],
        ARGS[:-1] + ["bad-sha"],
        ARGS + ["--project", PROJECT],
        ["--project", "foreign-project", *ARGS[2:]],
        [*ARGS[:9], "https://foreign.invalid", SHA],
        [*ARGS[:7], REPO + ":latest", *ARGS[8:]],
    ],
)
def test_missing_or_conflicting_explicit_arguments_stop_before_any_cli(owner_cli, args):
    _, execute = owner_cli
    result, calls = execute(args=args)
    assert result.returncode != 0
    assert calls == []


@pytest.mark.parametrize(
    "path,value",
    [
        (("project", "projectId"), "dufynd-private-broker-01"),
        (("project", "lifecycleState"), "DELETE_REQUESTED"),
        (("project", "projectNumber"), 592985661274),
        (
            ("repository", "name"),
            "projects/foreign-project/locations/europe-west3/repositories/broker",
        ),
        (("repository", "name"), f"projects/{PROJECT}/locations/us-east1/repositories/broker"),
        (("repository", "format"), "MAVEN"),
        (("repository", "mode"), "REMOTE_REPOSITORY"),
        (("service", "metadata", "name"), "other-service"),
        (("service", "metadata", "namespace"), "123456789"),
        (("service", "metadata", "uid"), None),
        (("service", "metadata", "resourceVersion"), None),
        (("service", "metadata", "labels", "cloud.googleapis.com/location"), "us-east1"),
        (("service", "status", "url"), "https://another-broker.run.app"),
        (("service", "status", "latestCreatedRevisionName"), SERVICE + "-00005-pending"),
        (("service", "status", "observedGeneration"), 3),
        (("service", "status", "conditions"), [{"type": "Ready", "status": "False"}]),
        (
            ("service", "status", "traffic"),
            [{"revisionName": SERVICE + "-00001-foreign", "percent": 100}],
        ),
        (("service", "status", "traffic"), [{"latestRevision": True, "percent": 100}]),
        (("service", "status", "traffic"), [{"revisionName": OLD_REVISION, "percent": "100"}]),
        (("service", "status", "traffic"), [{"revisionName": OLD_REVISION, "percent": 50}]),
        (("service", "spec", "traffic"), [{"revisionName": OLD_REVISION, "percent": 100}]),
        (
            ("service", "spec", "template", "spec", "containers"),
            [{"image": "us-docker.pkg.dev/foreign-project/broker/runtime:latest"}],
        ),
        (("service", "spec", "template", "spec", "containers"), [{"image": REPO + "@sha256:bad"}]),
        (("revision", "metadata", "name"), SERVICE + "-00001-foreign"),
        (("revision", "metadata", "labels", "serving.knative.dev/service"), "foreign-service"),
        (("revision", "status", "conditions"), [{"type": "Ready", "status": "Unknown"}]),
        (("revision", "status", "imageDigest"), "sha256:bad"),
        (("revision", "status", "imageDigest"), DIGEST),
        (
            ("revision", "status", "imageDigest"),
            "us-docker.pkg.dev/foreign-project/broker/runtime@" + OLD_DIGEST,
        ),
    ],
)
def test_read_only_preflight_rejects_wrong_or_unready_target_before_clone_build_push(
    owner_cli, path, value
):
    config, execute = owner_cli
    target = config
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    result, calls = execute(config)
    assert result.returncode != 0
    assert "refusing deploy:" in result.stderr
    assert_no_build_or_remote_write(calls)


@pytest.mark.parametrize("failed", ["buildx", "project", "repository", "service", "revision"])
def test_existing_access_failures_stop_without_auth_or_resource_setup(owner_cli, failed):
    config, execute = owner_cli
    config["fail"] = failed
    result, calls = execute(config)
    assert result.returncode != 0
    assert "private-provider-diagnostic-canary" not in result.stderr + result.stdout
    assert_no_build_or_remote_write(calls)


@pytest.mark.parametrize(
    "raw",
    ["not JSON", "[]", '{"metadata":null}', '{"metadata":{},"metadata":{}}', " " * 262145],
    ids=["malformed_json", "wrong_type", "null_metadata", "duplicate_keys", "oversized"],
)
def test_invalid_or_oversized_preflight_metadata_is_rejected_without_traceback(owner_cli, raw):
    config, execute = owner_cli
    config["raw"] = {"service": raw}
    result, calls = execute(config)
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert_no_build_or_remote_write(calls)


def test_checkout_identity_failure_prevents_any_image_build(owner_cli):
    config, execute = owner_cli
    config["checkout_sha"] = "b" * 40
    result, calls = execute(config)
    assert result.returncode != 0
    assert not any(
        call[:2] in (["docker", "build"], ["docker", "push"]) or is_update(call) for call in calls
    )


@pytest.mark.parametrize("read_number,pushed", [(2, False), (3, True)])
def test_concurrent_target_change_is_not_overwritten(owner_cli, read_number, pushed):
    config, execute = owner_cli
    config["drift_read"] = read_number
    config["service_drift"] = copy.deepcopy(config["service"])
    config["service_drift"]["metadata"]["resourceVersion"] = "another-owner-version"
    result, calls = execute(config)
    assert result.returncode != 0
    assert not any(is_update(call) for call in calls)
    assert any(call[:2] == ["docker", "push"] for call in calls) is pushed


@pytest.mark.parametrize(
    "digest,qualified",
    [
        ("sha256:bad", REPO + "@sha256:bad"),
        (DIGEST, "us-docker.pkg.dev/foreign-project/broker/runtime@" + DIGEST),
        (DIGEST, REPO + "@" + OLD_DIGEST),
        (None, REPO + "@" + DIGEST),
    ],
)
def test_new_registry_digest_must_be_bound_before_any_cloud_run_update(
    owner_cli, digest, qualified
):
    config, execute = owner_cli
    config["artifact"]["image_summary"] = {"digest": digest, "fully_qualified_digest": qualified}
    result, calls = execute(config)
    assert result.returncode != 0
    assert any(call[:2] == ["docker", "push"] for call in calls)
    assert not any(is_update(call) for call in calls)


@pytest.mark.parametrize(
    "path,value",
    [
        (("service_after", "status", "traffic"), [{"revisionName": OLD_REVISION, "percent": 100}]),
        (("service_after", "status", "traffic"), [{"latestRevision": True, "percent": 100}]),
        (("service_after", "status", "latestReadyRevisionName"), OLD_REVISION),
        (("service_after", "metadata", "uid"), "replacement-service-uid"),
        (("revision_after", "status", "imageDigest"), OLD_DIGEST),
        (
            ("revision_after", "status", "imageDigest"),
            "us-docker.pkg.dev/foreign-project/broker/runtime@" + DIGEST,
        ),
    ],
)
def test_post_update_verification_never_claims_unbound_success_or_rolls_back_automatically(
    owner_cli, path, value
):
    config, execute = owner_cli
    target = config
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    result, calls = execute(config)
    assert result.returncode != 0
    assert len([call for call in calls if is_update(call)]) == 1
    assert "verified_traffic=100" not in result.stdout


@pytest.mark.parametrize("failed", ["build", "push", "artifact", "update"])
def test_cli_stage_failure_has_no_followup_mutation_or_success_claim(owner_cli, failed):
    config, execute = owner_cli
    config["fail"] = failed
    result, calls = execute(config)
    assert result.returncode != 0
    assert "verified_traffic=100" not in result.stdout
    assert len([call for call in calls if is_update(call)]) == (1 if failed == "update" else 0)
    if failed == "build":
        assert not any(call[:2] == ["docker", "push"] for call in calls)


def image_index(root_digest, child_digest, *, docker=False):
    return {
        "schemaVersion": 2,
        "digest": root_digest,
        "mediaType": (
            "application/vnd.docker.distribution.manifest.list.v2+json"
            if docker
            else "application/vnd.oci.image.index.v1+json"
        ),
        "manifests": [
            {
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "digest": child_digest,
                "platform": {"os": "linux", "architecture": "amd64"},
            },
            {
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "digest": "sha256:" + "5" * 64,
                "platform": {"os": "unknown", "architecture": "unknown"},
                "annotations": {"vnd.docker.reference.type": "attestation-manifest"},
            },
        ],
    }


@pytest.mark.parametrize("docker", [False, True], ids=["oci_index", "docker_manifest_list"])
def test_index_deploy_keeps_root_pin_and_verifies_selected_runtime_digest(owner_cli, docker):
    config, execute = owner_cli
    config["manifests"][OLD_DIGEST] = image_index(OLD_DIGEST, OLD_RUNTIME_DIGEST, docker=docker)
    config["manifests"][DIGEST] = image_index(DIGEST, RUNTIME_DIGEST, docker=docker)
    config["revision"]["status"]["imageDigest"] = REPO + "@" + OLD_RUNTIME_DIGEST
    config["revision_after"]["status"]["imageDigest"] = REPO + "@" + RUNTIME_DIGEST
    result, calls = execute(config)
    assert result.returncode == 0, result.stderr
    assert f"verified_image={REPO}@{DIGEST}" in result.stdout
    assert f"verified_runtime_image={REPO}@{RUNTIME_DIGEST}" in result.stdout
    assert len([call for call in calls if is_update(call)]) == 1
    first_clone = next(i for i, call in enumerate(calls) if call[:2] == ["git", "clone"])
    assert_no_build_or_remote_write(calls[:first_clone])
    manifest_reads = [
        call[4] for call in calls if call[:4] == ["docker", "buildx", "imagetools", "inspect"]
    ]
    assert manifest_reads == [REPO + "@" + OLD_DIGEST, REPO + "@" + DIGEST]


@pytest.mark.parametrize("stage", ["before", "after_build"])
@pytest.mark.parametrize(
    "fault",
    [
        "foreign_root",
        "wrong_schema",
        "wrong_type",
        "missing_platform",
        "wrong_architecture",
        "duplicate_platform",
        "duplicate_digest",
        "foreign_child",
        "invalid_child",
        "nested_index",
        "attestation_runtime",
        "unsupported_variant",
        "platform_requirements",
        "missing_manifests",
        "empty_manifests",
        "wrong_runtime_child",
        "unreadable",
    ],
)
def test_unproven_index_binding_fails_before_next_mutation(owner_cli, stage, fault):
    config, execute = owner_cli
    root_digest = OLD_DIGEST if stage == "before" else DIGEST
    child_digest = OLD_RUNTIME_DIGEST if stage == "before" else RUNTIME_DIGEST
    manifest = image_index(root_digest, child_digest)
    config["manifests"][root_digest] = manifest
    if stage == "before":
        config["revision"]["status"]["imageDigest"] = child_digest
    else:
        config["revision_after"]["status"]["imageDigest"] = child_digest
    selected = manifest["manifests"][0]
    if fault == "foreign_root":
        manifest["digest"] = "foreign.example/runtime@" + root_digest
    elif fault == "wrong_schema":
        manifest["schemaVersion"] = True
    elif fault == "wrong_type":
        manifest["mediaType"] = "application/unknown"
    elif fault == "missing_platform":
        del selected["platform"]
    elif fault == "wrong_architecture":
        selected["platform"]["architecture"] = "arm64"
    elif fault == "duplicate_platform":
        manifest["manifests"][1]["platform"] = dict(selected["platform"])
    elif fault == "duplicate_digest":
        manifest["manifests"][1]["digest"] = child_digest
    elif fault == "foreign_child":
        selected["digest"] = "foreign.example/runtime@" + child_digest
    elif fault == "invalid_child":
        selected["digest"] = "sha256:invalid"
    elif fault == "nested_index":
        selected["mediaType"] = "application/vnd.oci.image.index.v1+json"
    elif fault == "attestation_runtime":
        selected["annotations"] = {"vnd.docker.reference.type": "attestation-manifest"}
    elif fault == "unsupported_variant":
        selected["platform"]["variant"] = "v4"
    elif fault == "platform_requirements":
        selected["platform"]["os.features"] = ["unsupported"]
    elif fault == "missing_manifests":
        del manifest["manifests"]
    elif fault == "empty_manifests":
        manifest["manifests"] = []
    elif fault == "wrong_runtime_child":
        selected["digest"] = "sha256:" + "6" * 64
    elif fault == "unreadable":
        config["fail"] = "manifest"
    result, calls = execute(config)
    assert result.returncode != 0
    assert "verified_traffic=100" not in result.stdout
    assert "private-provider-diagnostic-canary" not in result.stdout + result.stderr
    if stage == "before":
        assert_no_build_or_remote_write(calls)
    elif fault == "wrong_runtime_child":
        # A well-formed registry graph can only be compared with Cloud Run after
        # the update. An unbound ready digest must never claim success.
        assert len([call for call in calls if is_update(call)]) == 1
    else:
        assert not any(is_update(call) for call in calls)


@pytest.mark.parametrize(
    "raw",
    ["[]", "not JSON", '{"digest":1,"digest":2}', " " * 262145],
    ids=["wrong_type", "malformed_json", "duplicate_keys", "oversized"],
)
def test_malformed_index_evidence_is_bounded_and_never_ignored(owner_cli, raw):
    config, execute = owner_cli
    config["revision"]["status"]["imageDigest"] = OLD_RUNTIME_DIGEST
    config["raw"] = {"manifest": raw}
    result, calls = execute(config)
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert_no_build_or_remote_write(calls)


def owner_build_record(*, runtime_digest=DIGEST):
    return {
        "version": 1,
        "source_repository": "https://github.com/tncommerce/commerce-agents.git",
        "source_sha": SHA,
        "image": REPO + "@" + DIGEST,
        "runtime_digest": runtime_digest,
        "evidence_ref": "ops.dufynd_monitoring_release_20261029/verified_owner_build",
    }


def resume_args(tmp_path, *, record=None, runtime_digest=DIGEST, raw=None):
    evidence = tmp_path / "private-owner-build-record.json"
    evidence.write_text(raw if raw is not None else json.dumps(
        owner_build_record(runtime_digest=runtime_digest) if record is None else record
    ))
    return [*ARGS[:-1], "--existing-image", REPO + "@" + DIGEST,
            "--expected-runtime-digest", runtime_digest,
            "--build-evidence", str(evidence), SHA]


@pytest.mark.parametrize("is_index", [False, True], ids=["direct_image", "oci_index"])
def test_resume_published_image_keeps_guards_and_never_clones_builds_or_pushes(
    owner_cli, tmp_path, is_index
):
    config, execute = owner_cli
    config["artifact_tag"] = copy.deepcopy(config["artifact"])
    child = RUNTIME_DIGEST if is_index else DIGEST
    if is_index:
        config["manifests"][OLD_DIGEST] = image_index(OLD_DIGEST, OLD_RUNTIME_DIGEST)
        config["manifests"][DIGEST] = image_index(DIGEST, child)
        config["revision"]["status"]["imageDigest"] = OLD_RUNTIME_DIGEST
        config["revision_after"]["status"]["imageDigest"] = child
    result, calls = execute(config, args=resume_args(tmp_path, runtime_digest=child))
    assert result.returncode == 0, result.stderr
    assert f"verified_image={REPO}@{DIGEST}" in result.stdout
    assert f"verified_runtime_image={REPO}@{child}" in result.stdout
    assert "verified_owner_build_record_sha256=" in result.stdout
    assert "verified_traffic=100" in result.stdout
    assert len([call for call in calls if is_update(call)]) == 1
    assert_no_build_or_remote_write([call for call in calls if not is_update(call)])
    artifact_reads = [call[5] for call in calls
                      if call[:5] == ["gcloud", "artifacts", "docker", "images", "describe"]]
    assert artifact_reads == [REPO + "@" + DIGEST, REPO + ":" + SHA]


@pytest.mark.parametrize("fault", ["missing_image", "missing_child", "missing_evidence",
                                  "mutable_tag", "bare_digest", "foreign_repo", "invalid_child"])
def test_resume_requires_complete_explicit_immutable_arguments_before_any_cli(
    owner_cli, tmp_path, fault
):
    _, execute = owner_cli
    args = resume_args(tmp_path)
    if fault.startswith("missing_"):
        flag = {"missing_image": "--existing-image", "missing_child": "--expected-runtime-digest",
                "missing_evidence": "--build-evidence"}[fault]
        at = args.index(flag)
        del args[at:at + 2]
    elif fault == "mutable_tag":
        args[args.index("--existing-image") + 1] = REPO + ":" + SHA
    elif fault == "bare_digest":
        args[args.index("--existing-image") + 1] = DIGEST
    elif fault == "foreign_repo":
        args[args.index("--existing-image") + 1] = "foreign.example/broker/runtime@" + DIGEST
    elif fault == "invalid_child":
        args[args.index("--expected-runtime-digest") + 1] = "sha256:invalid"
    result, calls = execute(args=args)
    assert result.returncode != 0
    assert calls == []


def test_resume_resolves_an_explicit_relative_owner_record_from_the_callers_directory(
    owner_cli, tmp_path
):
    _, execute = owner_cli
    args = resume_args(tmp_path)
    at = args.index("--build-evidence") + 1
    args[at] = os.path.relpath(args[at], Path.cwd())
    result, calls = execute(args=args)
    assert result.returncode == 0, result.stderr
    assert len([call for call in calls if is_update(call)]) == 1
    assert_no_build_or_remote_write([call for call in calls if not is_update(call)])


def test_resume_missing_owner_record_stops_before_any_cli(owner_cli, tmp_path):
    _, execute = owner_cli
    args = resume_args(tmp_path)
    Path(args[args.index("--build-evidence") + 1]).unlink()
    result, calls = execute(args=args)
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert calls == []


@pytest.mark.parametrize("key,value", [
    ("version", True),
    ("source_repository", "https://github.com/foreign/repo.git"),
    ("source_sha", "b" * 40),
    ("image", REPO + "@" + OLD_DIGEST),
    ("runtime_digest", OLD_RUNTIME_DIGEST),
    ("evidence_ref", ""),
    ("evidence_ref", "   "),
    ("evidence_ref", "record\nforged-output"),
    ("evidence_ref", "x" * 1025),
    ("unexpected", "ignored-metadata"),
])
def test_resume_owner_record_must_bind_exact_source_root_and_child_before_any_cli(
    owner_cli, tmp_path, key, value
):
    _, execute = owner_cli
    record = owner_build_record()
    record[key] = value
    result, calls = execute(args=resume_args(tmp_path, record=record))
    assert result.returncode != 0
    assert "refusing deploy:" in result.stderr
    assert "Traceback" not in result.stderr
    assert calls == []


@pytest.mark.parametrize(
    "raw", ["[]", "not JSON", '{"version":1,"version":1}', " " * 262145],
    ids=["wrong_type", "malformed_json", "duplicate_keys", "oversized"],
)
def test_resume_rejects_ambiguous_or_unbounded_owner_record(owner_cli, tmp_path, raw):
    _, execute = owner_cli
    result, calls = execute(args=resume_args(tmp_path, raw=raw))
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert calls == []


@pytest.mark.parametrize("fault", ["wrong_published_root", "retargeted_sha_tag", "foreign_sha_tag",
                                  "wrong_runtime_child", "tag_read_failure", "manifest_read_failure"])
def test_resume_registry_binding_failures_stop_before_any_service_update(owner_cli, tmp_path, fault):
    config, execute = owner_cli
    config["artifact_tag"] = copy.deepcopy(config["artifact"])
    config["manifests"][DIGEST] = image_index(DIGEST, RUNTIME_DIGEST)
    config["revision_after"]["status"]["imageDigest"] = RUNTIME_DIGEST
    if fault == "wrong_published_root":
        config["artifact"]["image_summary"] = {"digest": OLD_DIGEST, "fully_qualified_digest": REPO + "@" + OLD_DIGEST}
    elif fault == "retargeted_sha_tag":
        config["artifact_tag"]["image_summary"] = {"digest": OLD_DIGEST, "fully_qualified_digest": REPO + "@" + OLD_DIGEST}
    elif fault == "foreign_sha_tag":
        config["artifact_tag"]["image_summary"]["fully_qualified_digest"] = "foreign.example/image@" + DIGEST
    elif fault == "wrong_runtime_child":
        config["manifests"][DIGEST]["manifests"][0]["digest"] = OLD_RUNTIME_DIGEST
    elif fault == "tag_read_failure":
        config["fail"] = "artifact_tag"
    elif fault == "manifest_read_failure":
        config["fail"] = "manifest"
    result, calls = execute(config, args=resume_args(tmp_path, runtime_digest=RUNTIME_DIGEST))
    assert result.returncode != 0
    assert "verified_traffic=100" not in result.stdout
    assert "private-provider-diagnostic-canary" not in result.stdout + result.stderr
    assert_no_build_or_remote_write(calls)


def test_resume_does_not_overwrite_service_change_during_registry_reads(owner_cli, tmp_path):
    config, execute = owner_cli
    config["drift_read"] = 2
    config["service_drift"] = copy.deepcopy(config["service"])
    config["service_drift"]["metadata"]["resourceVersion"] = "another-owner-rollout"
    result, calls = execute(config, args=resume_args(tmp_path))
    assert result.returncode != 0
    assert "service changed since preflight" in result.stderr
    assert_no_build_or_remote_write(calls)


def test_resume_reuses_target_preflight_and_never_updates_an_unready_broker(owner_cli, tmp_path):
    config, execute = owner_cli
    config["service"]["status"]["latestCreatedRevisionName"] = SERVICE + "-pending"
    result, calls = execute(config, args=resume_args(tmp_path))
    assert result.returncode != 0
    assert_no_build_or_remote_write(calls)
    assert not any(call[:5] == ["gcloud", "artifacts", "docker", "images", "describe"] for call in calls)


def test_resume_post_update_mismatch_never_claims_success_or_rolls_back(owner_cli, tmp_path):
    config, execute = owner_cli
    config["revision_after"]["status"]["imageDigest"] = OLD_DIGEST
    result, calls = execute(config, args=resume_args(tmp_path))
    assert result.returncode != 0
    assert "verified_traffic=100" not in result.stdout
    assert "verified_owner_build_record_sha256=" not in result.stdout
    assert len([call for call in calls if is_update(call)]) == 1
    assert_no_build_or_remote_write([call for call in calls if not is_update(call)])
