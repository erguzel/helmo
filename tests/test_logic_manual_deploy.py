"""``helmo manual`` -- the argv handed to helm, per action.

``manual -a uninstall`` used to build the install argv whatever the action was,
so helm rejected the flags and uninstall only ever worked through ``serial``.
The argv is asserted here instead of the effect: a real uninstall would need a
real release to destroy, while the command line says everything that matters.
"""

import pytest

import helmo.runtime as runtime
from helmo.logic import manual_deploy_logic

FAKE_CHART_VALUES = "replicaCount: 1\n"


@pytest.fixture
def initialised_release(monkeypatch, recorder, helmo_file, tmp_path):
    """A release whose ``helmo init`` step has already run.

    The init file is moved into its namespace folder and the environment
    manifests sit next to it, which is the state ``manual`` expects.
    """
    namespace_dir = tmp_path / "cert-manager"
    namespace_dir.mkdir()
    release_file = namespace_dir / "cert-manager.helmo"
    release_file.write_text(helmo_file.read_text())
    helmo_file.unlink()
    for environment in ("prod", "test", "default"):
        (namespace_dir / f"cert-manager_{environment}_v1.19.2.yaml").write_text(
            FAKE_CHART_VALUES
        )
    return release_file


def _patch_runtime(monkeypatch, recorder):
    rec = recorder(stdout=FAKE_CHART_VALUES)
    monkeypatch.setattr(runtime, "execute_subprocess", rec)
    monkeypatch.setattr(runtime, "switch_context", lambda *a, **kw: None)
    monkeypatch.setattr(runtime, "resource_exists", lambda *a, **kw: True)
    return rec


def _helm_calls(rec):
    return [call for call in rec.calls if call[0] == "helm"]


def test_manual_install_passes_the_chart_and_the_environment_manifest(
    monkeypatch, recorder, initialised_release
):
    rec = _patch_runtime(monkeypatch, recorder)

    manual_deploy_logic(
        release_file=initialised_release,
        environment="test",
        helm_action="install",
        additional_values=[],
        wait="2m",
        quiet=True,
    )

    install = _helm_calls(rec)[-1]
    assert install[:5] == [
        "helm",
        "install",
        "cert-manager",
        "jetstack/cert-manager",
        "--namespace",
    ]
    assert "--create-namespace" in install
    assert ["--version", "v1.19.2"] == install[
        install.index("--version") : install.index("--version") + 2
    ]
    assert str(
        initialised_release.parent / "cert-manager_test_v1.19.2.yaml"
    ) in install


def test_manual_uninstall_builds_a_helm_uninstall(
    monkeypatch, recorder, initialised_release
):
    rec = _patch_runtime(monkeypatch, recorder)

    manual_deploy_logic(
        release_file=initialised_release,
        environment="test",
        helm_action="uninstall",
        additional_values=[],
        wait="3m",
        quiet=True,
    )

    assert _helm_calls(rec) == [
        [
            "helm",
            "uninstall",
            "cert-manager",
            "-n",
            "cert-manager",
            "--wait",
            "--timeout",
            "3m",
        ]
    ]


@pytest.mark.parametrize(
    "rejected_flag",
    ["--create-namespace", "--version", "--values", "jetstack/cert-manager"],
)
def test_manual_uninstall_omits_the_flags_helm_rejects(
    monkeypatch, recorder, initialised_release, rejected_flag
):
    rec = _patch_runtime(monkeypatch, recorder)

    manual_deploy_logic(
        release_file=initialised_release,
        environment="test",
        helm_action="uninstall",
        additional_values=[],
        wait="2m",
        quiet=True,
    )

    assert rejected_flag not in _helm_calls(rec)[0]


def test_manual_uninstall_does_not_regenerate_manifests(
    monkeypatch, recorder, initialised_release
):
    """Uninstall must not run the init step: there is nothing to initialise."""
    rec = _patch_runtime(monkeypatch, recorder)

    manual_deploy_logic(
        release_file=initialised_release,
        environment="test",
        helm_action="uninstall",
        additional_values=[],
        wait="2m",
        quiet=True,
    )

    assert not [call for call in rec.calls if call[:3] == ["helm", "show", "values"]]
    archived = list(initialised_release.parent.glob("*_v1.19.2_*.yaml"))
    assert archived == []


def test_manual_uninstall_needs_no_environment_manifest(
    monkeypatch, recorder, initialised_release
):
    """A release can be removed after its generated manifests are gone."""
    rec = _patch_runtime(monkeypatch, recorder)
    for manifest in initialised_release.parent.glob("*.yaml"):
        manifest.unlink()

    manual_deploy_logic(
        release_file=initialised_release,
        environment="test",
        helm_action="uninstall",
        additional_values=[],
        wait="2m",
        quiet=True,
    )

    assert _helm_calls(rec)[0][:2] == ["helm", "uninstall"]


def test_manual_dry_run_runs_no_helm_action(
    monkeypatch, recorder, initialised_release
):
    """``manual -d`` used to reach the cluster through its init step.

    The helm action itself was guarded, but ``init_logic`` was called
    unguarded, so a dry run created the namespace and wrote a manifest set.
    """
    rec = _patch_runtime(monkeypatch, recorder)

    manual_deploy_logic(
        release_file=initialised_release,
        environment="test",
        helm_action="install",
        additional_values=[],
        wait="2m",
        quiet=True,
        dryrun=True,
    )

    assert not [call for call in rec.calls if call[:2] == ["helm", "install"]]
    assert not [call for call in rec.calls if call[:2] == ["kubectl", "create"]]


def test_manual_dry_run_writes_no_manifests(
    monkeypatch, recorder, initialised_release
):
    _patch_runtime(monkeypatch, recorder)
    before = sorted(path.name for path in initialised_release.parent.iterdir())

    manual_deploy_logic(
        release_file=initialised_release,
        environment="test",
        helm_action="install",
        additional_values=[],
        wait="2m",
        quiet=True,
        dryrun=True,
    )

    assert sorted(path.name for path in initialised_release.parent.iterdir()) == before


def test_manual_dry_run_uninstall_runs_no_helm_action(
    monkeypatch, recorder, initialised_release
):
    rec = _patch_runtime(monkeypatch, recorder)

    manual_deploy_logic(
        release_file=initialised_release,
        environment="test",
        helm_action="uninstall",
        additional_values=[],
        wait="2m",
        quiet=True,
        dryrun=True,
    )

    assert _helm_calls(rec) == []
