"""Exactly what helmo would ask kubectl to do.

These are the destructive paths -- creating and deleting secrets and
namespaces, switching contexts.  Asserting the argv that *would* be executed
covers them without ever pointing a real cluster at a delete command, which is
the only way to test "it did not delete anything" safely.
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


# --- context switching ---------------------------------------------------


def test_switch_context_is_a_noop_when_already_current(monkeypatch, recorder):
    """kubectl terminates its output with a newline; the comparison must strip it.

    Without stripping, the current context never compares equal and helmo
    issues a redundant ``use-context`` on every single call.
    """
    rec = recorder(stdout="k3d-helmo-test\n")
    monkeypatch.setattr(runtime_k8s, "execute_subprocess", rec)

    runtime_k8s.switch_context("k3d-helmo-test")

    assert rec.calls == [["kubectl", "config", "current-context"]]


def test_switch_context_switches_when_a_different_context_is_current(
    monkeypatch, recorder
):
    rec = recorder(stdout="some-other-cluster\n")
    monkeypatch.setattr(runtime_k8s, "execute_subprocess", rec)

    runtime_k8s.switch_context("k3d-helmo-test")

    assert rec.calls[-1] == [
        "kubectl",
        "config",
        "use-context",
        "k3d-helmo-test",
    ]


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
        ["kubectl", "delete", "namespace", "cert-manager"]
    ]


def test_delete_namespace_ignores_an_empty_namespace(
    monkeypatch, recorder, always_exists
):
    rec = recorder()
    monkeypatch.setattr(runtime_k8s, "execute_subprocess", rec)

    runtime_k8s.delete_namespace("", context="k3d-helmo-test")

    assert rec.calls == []


# --- manifest apply ------------------------------------------------------


def test_resource_apply_switches_context_before_applying(
    monkeypatch, recorder, tmp_path
):
    rec = recorder(stdout="some-other-cluster\n")
    monkeypatch.setattr(runtime_k8s, "execute_subprocess", rec)
    manifest = tmp_path / "cluster-issuer.yaml"
    manifest.write_text("{}")

    runtime_k8s.resource_apply(str(manifest), context="k3d-helmo-test")

    assert [
        "kubectl",
        "config",
        "use-context",
        "k3d-helmo-test",
    ] in rec.calls
    assert rec.calls[-1] == ["kubectl", "apply", "-f", str(manifest)]


def test_resource_apply_without_a_context_uses_the_current_one(
    monkeypatch, recorder, tmp_path
):
    rec = recorder()
    monkeypatch.setattr(runtime_k8s, "execute_subprocess", rec)
    manifest = tmp_path / "cluster-issuer.yaml"
    manifest.write_text("{}")

    runtime_k8s.resource_apply(str(manifest))

    assert rec.calls == [["kubectl", "apply", "-f", str(manifest)]]
