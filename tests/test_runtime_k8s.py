"""Exactly what helmo would ask kubectl to do.

These are the destructive paths -- creating and deleting secrets and
namespaces.  Asserting the argv that *would* be executed covers them without
ever pointing a real cluster at a delete command, which is the only way to
test "it did not delete anything" safely.

The context is part of that argv.  helmo used to reach the right cluster by
running ``kubectl config use-context``, which rewrites the user's global
kubeconfig and was never restored; every command carries ``--context`` now, so
the argv is the only place the target cluster is decided.
"""

import pytest

from helmo.runtime import k8s as runtime_k8s
from helmo.validate import HelmoRuntimeError


@pytest.fixture
def never_exists(monkeypatch):
    monkeypatch.setattr(runtime_k8s, "resource_exists", lambda *a, **kw: False)


@pytest.fixture
def always_exists(monkeypatch):
    monkeypatch.setattr(runtime_k8s, "resource_exists", lambda *a, **kw: True)


# --- the global kubeconfig is never touched -------------------------------


def test_no_command_rewrites_the_users_kubeconfig(monkeypatch, recorder, tmp_path):
    """``kubectl config use-context`` must not appear anywhere.

    It is a global mutation of a file helmo does not own, and helmo never put
    it back.  It also made two commands out of one logical step, so a crash
    between them left the user pointed at a cluster they did not choose.
    """
    rec = recorder(stdout="secret/tls\n")
    monkeypatch.setattr(runtime_k8s, "execute_subprocess", rec)
    manifest = tmp_path / "cluster-issuer.yaml"
    manifest.write_text("{}")

    runtime_k8s.resource_exists("secret", "tls", context="k3d-helmo-test")
    runtime_k8s.resource_apply(str(manifest), context="k3d-helmo-test")
    runtime_k8s.delete_namespace("cert-manager", context="k3d-helmo-test")

    assert not [call for call in rec.calls if call[:2] == ["kubectl", "config"]]


def test_switch_context_is_gone():
    """The helper is removed rather than kept as an unused side door."""
    assert not hasattr(runtime_k8s, "switch_context")


# --- resource lookup -----------------------------------------------------


def test_resource_exists_is_false_when_kubectl_names_nothing(
    monkeypatch, recorder
):
    """--ignore-not-found reports absence as a zero exit with no output."""
    rec = recorder(stdout="")
    monkeypatch.setattr(runtime_k8s, "execute_subprocess", rec)

    assert runtime_k8s.resource_exists("secret", "tls") is False


def test_resource_exists_is_true_when_kubectl_names_the_resource(
    monkeypatch, recorder
):
    rec = recorder(stdout="secret/tls\n")
    monkeypatch.setattr(runtime_k8s, "execute_subprocess", rec)

    assert runtime_k8s.resource_exists("secret", "tls") is True


def test_resource_exists_raises_when_kubectl_fails(monkeypatch, recorder):
    """A nonzero exit is a real failure, never an answer of "absent".

    An unreachable cluster or a rejected credential reported as absence would
    send the caller on to create namespaces and secrets against a cluster it
    never reached.
    """
    rec = recorder(fail=True)
    monkeypatch.setattr(runtime_k8s, "execute_subprocess", rec)

    with pytest.raises(HelmoRuntimeError):
        runtime_k8s.resource_exists("secret", "tls")


def test_resource_exists_does_not_swallow_unexpected_failures(monkeypatch):
    """A missing kubectl binary must surface too, not read as absence."""

    def kubectl_is_missing(*args):
        raise FileNotFoundError("kubectl")

    monkeypatch.setattr(runtime_k8s, "execute_subprocess", kubectl_is_missing)

    with pytest.raises(FileNotFoundError):
        runtime_k8s.resource_exists("secret", "tls")


def test_resource_exists_omits_the_namespace_flag_when_no_namespace_given(
    monkeypatch, recorder
):
    rec = recorder()
    monkeypatch.setattr(runtime_k8s, "execute_subprocess", rec)

    runtime_k8s.resource_exists("namespace", "cert-manager")

    assert rec.calls == [
        [
            "kubectl", "get", "namespace", "cert-manager",
            "--ignore-not-found", "-o", "name",
        ]
    ]


def test_resource_exists_passes_the_context_flag_when_given(
    monkeypatch, recorder
):
    rec = recorder()
    monkeypatch.setattr(runtime_k8s, "execute_subprocess", rec)

    runtime_k8s.resource_exists(
        "namespace", "cert-manager", context="k3d-helmo-test"
    )

    assert rec.calls == [
        [
            "kubectl", "--context", "k3d-helmo-test",
            "get", "namespace", "cert-manager",
            "--ignore-not-found", "-o", "name",
        ]
    ]


def test_resource_exists_passes_the_namespace_flag_when_given(
    monkeypatch, recorder
):
    rec = recorder()
    monkeypatch.setattr(runtime_k8s, "execute_subprocess", rec)

    runtime_k8s.resource_exists("secret", "tls", namespace="cert-manager")

    assert rec.calls == [
        [
            "kubectl", "get", "secret", "tls", "-n", "cert-manager",
            "--ignore-not-found", "-o", "name",
        ]
    ]


# --- secret creation -----------------------------------------------------


def test_create_file_secret_uses_from_file_for_a_plain_file(
    monkeypatch, recorder, tmp_path, never_exists
):
    rec = recorder()
    monkeypatch.setattr(runtime_k8s, "execute_subprocess", rec)
    secret = tmp_path / "tls.crt"
    secret.write_text("certificate")

    runtime_k8s.create_file_secret("tls", secret)

    argv = rec.calls[-1]
    assert argv[:5] == ["kubectl", "create", "secret", "generic", "tls"]
    assert f"--from-file=tls.crt={secret}" in argv
    assert "--type=Opaque" in argv


def test_create_file_secret_uses_from_env_file_for_dotenv(
    monkeypatch, recorder, tmp_path, never_exists
):
    rec = recorder()
    monkeypatch.setattr(runtime_k8s, "execute_subprocess", rec)
    secret = tmp_path / "app.env"
    secret.write_text("TOKEN=x")

    runtime_k8s.create_file_secret("app", secret)

    assert f"--from-env-file={secret}" in rec.calls[-1]


def test_create_file_secret_sets_the_docker_config_type(
    monkeypatch, recorder, tmp_path, never_exists
):
    rec = recorder()
    monkeypatch.setattr(runtime_k8s, "execute_subprocess", rec)
    secret = tmp_path / "regcred.dockerconfigjson"
    secret.write_text("{}")

    runtime_k8s.create_file_secret("regcred", secret)

    assert "--type=kubernetes.io/dockerconfigjson" in rec.calls[-1]


def test_create_file_secret_leaves_an_existing_secret_alone_without_override(
    monkeypatch, recorder, tmp_path, always_exists
):
    """No delete, no create -- the existing secret is untouched."""
    rec = recorder()
    monkeypatch.setattr(runtime_k8s, "execute_subprocess", rec)
    secret = tmp_path / "tls.crt"
    secret.write_text("certificate")

    runtime_k8s.create_file_secret("tls", secret, override=False)

    assert rec.calls == []


def test_create_file_secret_replaces_an_existing_secret_with_override(
    monkeypatch, recorder, tmp_path, always_exists
):
    rec = recorder()
    monkeypatch.setattr(runtime_k8s, "execute_subprocess", rec)
    secret = tmp_path / "tls.crt"
    secret.write_text("certificate")

    runtime_k8s.create_file_secret(
        "tls", secret, namespace="cert-manager", override=True
    )

    assert rec.calls[0][:4] == ["kubectl", "delete", "secret", "tls"]
    assert rec.calls[1][:4] == ["kubectl", "create", "secret", "generic"]


def test_create_file_secret_creates_a_missing_namespace(
    monkeypatch, recorder, tmp_path, never_exists
):
    rec = recorder()
    monkeypatch.setattr(runtime_k8s, "execute_subprocess", rec)
    secret = tmp_path / "tls.crt"
    secret.write_text("certificate")

    runtime_k8s.create_file_secret("tls", secret, namespace="cert-manager")

    assert rec.calls[0] == [
        "kubectl",
        "create",
        "namespace",
        "cert-manager",
    ]


def test_create_file_secret_passes_the_context_to_every_command(
    monkeypatch, recorder, tmp_path, never_exists
):
    """Namespace creation and secret creation must land in the same cluster."""
    rec = recorder()
    monkeypatch.setattr(runtime_k8s, "execute_subprocess", rec)
    secret = tmp_path / "tls.crt"
    secret.write_text("certificate")

    runtime_k8s.create_file_secret(
        "tls", secret, context="k3d-helmo-test", namespace="cert-manager"
    )

    assert rec.calls
    for call in rec.calls:
        assert call[:3] == ["kubectl", "--context", "k3d-helmo-test"]


# --- namespace deletion --------------------------------------------------


def test_delete_namespace_does_nothing_when_the_namespace_is_absent(
    monkeypatch, recorder, never_exists
):
    rec = recorder()
    monkeypatch.setattr(runtime_k8s, "execute_subprocess", rec)

    runtime_k8s.delete_namespace("cert-manager", context="k3d-helmo-test")

    assert rec.calls == []


def test_delete_namespace_deletes_when_present(
    monkeypatch, recorder, always_exists
):
    rec = recorder()
    monkeypatch.setattr(runtime_k8s, "execute_subprocess", rec)

    runtime_k8s.delete_namespace("cert-manager", context="k3d-helmo-test")

    assert rec.calls == [
        [
            "kubectl", "--context", "k3d-helmo-test",
            "delete", "namespace", "cert-manager",
        ]
    ]


def test_delete_namespace_ignores_an_empty_namespace(
    monkeypatch, recorder, always_exists
):
    rec = recorder()
    monkeypatch.setattr(runtime_k8s, "execute_subprocess", rec)

    runtime_k8s.delete_namespace("", context="k3d-helmo-test")

    assert rec.calls == []


# --- manifest apply ------------------------------------------------------


def test_resource_apply_names_the_context_on_the_apply_itself(
    monkeypatch, recorder, tmp_path
):
    """One command, one cluster: no separate switch step to get out of sync."""
    rec = recorder()
    monkeypatch.setattr(runtime_k8s, "execute_subprocess", rec)
    manifest = tmp_path / "cluster-issuer.yaml"
    manifest.write_text("{}")

    runtime_k8s.resource_apply(str(manifest), context="k3d-helmo-test")

    assert rec.calls == [
        [
            "kubectl", "--context", "k3d-helmo-test",
            "apply", "-f", str(manifest),
        ]
    ]


def test_resource_apply_without_a_context_uses_the_current_one(
    monkeypatch, recorder, tmp_path
):
    rec = recorder()
    monkeypatch.setattr(runtime_k8s, "execute_subprocess", rec)
    manifest = tmp_path / "cluster-issuer.yaml"
    manifest.write_text("{}")

    runtime_k8s.resource_apply(str(manifest))

    assert rec.calls == [["kubectl", "apply", "-f", str(manifest)]]
