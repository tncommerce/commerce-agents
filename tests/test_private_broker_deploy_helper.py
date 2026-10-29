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
        output("artifact")
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
elif tool == "docker" and args[0] in {"build", "push"}:
    if config.get("fail") == args[0]:
        fail()
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
    assert all(call[0] == "gcloud" and "describe" in call and not is_update(call) for call in calls)


def test_helper_has_valid_bash_syntax():
    result = run(["bash", "-n", str(SCRIPT)], check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("bare_digest", [False, True])
def test_bound_existing_target_deploys_only_image_and_verifies_exact_ready_traffic(
    owner_cli, bare_digest
):
    config, execute = owner_cli
    if bare_digest:
        config["revision"]["status"]["imageDigest"] = OLD_DIGEST
        config["revision_after"]["status"]["imageDigest"] = DIGEST
    result, calls = execute(config)
    assert result.returncode == 0, result.stderr
    assert f"verified_revision={REVISION}" in result.stdout
    assert f"verified_image={REPO}@{DIGEST}" in result.stdout
    assert "verified_traffic=100" in result.stdout
    first_clone = next(i for i, call in enumerate(calls) if call[:2] == ["git", "clone"])
    assert_no_build_or_remote_write(calls[:first_clone])
    assert len(calls[:first_clone]) == 4
    assert len([call for call in calls if is_update(call)]) == 1
    assert [call[:2] for call in calls if call[0] == "docker"] == [
        ["docker", "build"],
        ["docker", "push"],
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


@pytest.mark.parametrize("failed", ["project", "repository", "service", "revision"])
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
    assert not any(call[0] == "docker" or is_update(call) for call in calls)


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
