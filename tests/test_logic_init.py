"""``helmo init`` -- manifest generation and versioning of previous manifests.

This is the only logic that rearranges the user's own files (it *moves* the
init file into a namespace folder), so its filesystem effects are pinned down
here.  The helm and kubectl calls are intercepted; nothing leaves the tmp dir.
"""

import helmo.runtime as runtime
from helmo.logic import init_logic

FAKE_CHART_VALUES = "replicaCount: 1\nimage:\n  tag: v1.19.2\n"


def _patch_runtime(monkeypatch, recorder, namespace_present=True):
    rec = recorder(stdout=FAKE_CHART_VALUES)
    monkeypatch.setattr(runtime, "execute_subprocess", rec)
    monkeypatch.setattr(
        runtime, "resource_exists", lambda *a, **kw: namespace_present
    )
    return rec


def test_init_asks_helm_for_the_pinned_chart_version(
    monkeypatch, recorder, helmo_file
):
    rec = _patch_runtime(monkeypatch, recorder)

    init_logic(helmo_file, suffix="", env="test", quiet=True)

    assert rec.calls[0] == [
        "helm",
        "show",
        "values",
        "jetstack/cert-manager",
        "--version",
        "v1.19.2",
    ]


def test_init_writes_a_manifest_per_environment(
    monkeypatch, recorder, helmo_file, tmp_path
):
    _patch_runtime(monkeypatch, recorder)

    init_logic(helmo_file, suffix="", env="test", quiet=True)

    namespace_dir = tmp_path / "cert-manager"
    for environment in ("prod", "test", "default"):
        manifest = namespace_dir / f"cert-manager_{environment}_v1.19.2.yaml"
        assert manifest.read_text() == FAKE_CHART_VALUES


def test_init_moves_the_release_file_into_the_namespace_folder(
    monkeypatch, recorder, helmo_file, tmp_path
):
    _patch_runtime(monkeypatch, recorder)

    init_logic(helmo_file, suffix="", env="test", quiet=True)

    assert not helmo_file.exists()
    assert (tmp_path / "cert-manager" / "cert-manager.helmo").exists()


def test_init_creates_the_per_release_config_directory(
    monkeypatch, recorder, helmo_file, tmp_path
):
    _patch_runtime(monkeypatch, recorder)

    init_logic(helmo_file, suffix="", env="test", quiet=True)

    assert (tmp_path / "cert-manager" / "config" / "cert-manager").is_dir()


def test_init_creates_the_namespace_when_it_is_missing(
    monkeypatch, recorder, helmo_file
):
    rec = _patch_runtime(monkeypatch, recorder, namespace_present=False)

    init_logic(helmo_file, suffix="", env="test", quiet=True)

    assert [
        "kubectl",
        "create",
        "namespace",
        "cert-manager",
    ] in rec.calls


def test_init_archives_previous_environment_manifests(
    monkeypatch, recorder, helmo_file, tmp_path
):
    """A second init keeps the earlier prod/test manifests under a timestamp.

    Hand-edited environment overrides live in these files, so they are copied
    aside rather than overwritten; only the ``default`` manifest is refreshed
    from the chart.
    """
    _patch_runtime(monkeypatch, recorder)
    namespace_dir = tmp_path / "cert-manager"

    init_logic(helmo_file, suffix="", env="test", quiet=True)
    edited = namespace_dir / "cert-manager_prod_v1.19.2.yaml"
    edited.write_text("replicaCount: 3\n")

    init_logic(
        namespace_dir / "cert-manager.helmo",
        suffix="",
        env="test",
        quiet=True,
    )

    archived = list(namespace_dir.glob("cert-manager_prod_v1.19.2_*.yaml"))
    assert len(archived) == 1
    assert archived[0].read_text() == "replicaCount: 3\n"
    assert edited.read_text() == "replicaCount: 3\n"


def test_init_refreshes_the_default_manifest_from_the_chart(
    monkeypatch, recorder, helmo_file, tmp_path
):
    _patch_runtime(monkeypatch, recorder)
    namespace_dir = tmp_path / "cert-manager"

    init_logic(helmo_file, suffix="", env="test", quiet=True)
    default_manifest = namespace_dir / "cert-manager_default_v1.19.2.yaml"
    default_manifest.write_text("stale\n")

    init_logic(
        namespace_dir / "cert-manager.helmo",
        suffix="",
        env="test",
        quiet=True,
    )

    assert default_manifest.read_text() == FAKE_CHART_VALUES


def test_init_dry_run_creates_nothing(
    monkeypatch, recorder, helmo_file, tmp_path
):
    """A dry run reports; it does not write.

    It used to write a full manifest set and archive the previous one under a
    ``dryrun.`` prefix, which left the caller to clean up after a command whose
    point was to change nothing.
    """
    _patch_runtime(monkeypatch, recorder, namespace_present=False)

    init_logic(helmo_file, suffix="", env="test", quiet=True, dryrun=True)

    assert helmo_file.exists(), "the release file must stay where it was"
    assert not (tmp_path / "cert-manager").exists()
    assert list(tmp_path.glob("*.yaml")) == []


def test_init_dry_run_creates_no_namespace(
    monkeypatch, recorder, helmo_file
):
    """No kubectl call may mutate the cluster during a dry run."""
    rec = _patch_runtime(monkeypatch, recorder, namespace_present=False)

    init_logic(helmo_file, suffix="", env="test", quiet=True, dryrun=True)

    assert not [call for call in rec.calls if call[:2] == ["kubectl", "create"]]


def test_init_dry_run_still_resolves_the_chart(
    monkeypatch, recorder, helmo_file
):
    """Reading the chart values is the read-only part and stays: it proves the
    pinned chart version resolves before a real run is attempted."""
    rec = _patch_runtime(monkeypatch, recorder)

    init_logic(helmo_file, suffix="", env="test", quiet=True, dryrun=True)

    assert rec.calls[0][:3] == ["helm", "show", "values"]
