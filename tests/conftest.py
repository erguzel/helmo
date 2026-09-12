"""Shared fixtures and suite-wide safety guards.

Every test here runs without a Kubernetes cluster: kubectl and helm invocations
are intercepted before reaching ``subprocess``, and HTTP traffic goes through a
mock transport.  The guards below make that a property of the suite rather than
a convention, so an integration test added later cannot quietly reach a real
cluster or pick up real credentials.
"""

import os
from types import SimpleNamespace

import pytest

from helmo.validate import HelmoRuntimeError

#: Contexts an integration test is permitted to talk to.  The naming
#: convention is <tool>-helmo-test, which only a cluster created for this
#: suite carries -- never a context that might be a real environment.
SANDBOX_CONTEXTS = frozenset(
    {"colima-helmo-test", "k3d-helmo-test", "kind-helmo-test"}
)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: needs a disposable cluster; skipped unless HELMO_TEST_CLUSTER is set",
    )


def pytest_collection_modifyitems(config, items):
    """Skip integration tests unless a sandbox cluster is explicitly offered."""
    if os.environ.get("HELMO_TEST_CLUSTER") in SANDBOX_CONTEXTS:
        return
    skip = pytest.mark.skip(
        reason="set HELMO_TEST_CLUSTER to a sandbox context "
        f"({', '.join(sorted(SANDBOX_CONTEXTS))}) to run integration tests"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch):
    """Redirect HOME and KUBECONFIG at throwaway locations.

    ``api.RegistryClient`` falls back to ``httpx.NetRCAuth()``, which reads
    ``~/.netrc``.  Without this fixture a test could authenticate with the
    developer's real registry credentials.  KUBECONFIG is pointed at a path
    that does not exist so that an accidental real kubectl call cannot resolve
    a context.
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("KUBECONFIG", str(home / "kubeconfig-does-not-exist"))
    for leaked in ("HELMO_SERIAL_RELEASES_YAML", "HELMO_REGISTRY_URL"):
        monkeypatch.delenv(leaked, raising=False)
    return home


class CommandRecorder:
    """Stand-in for ``execute_subprocess`` that records argv instead of running it.

    Destructive kubectl and helm calls are asserted through this: the test
    checks what *would* have been executed, so the dangerous paths are covered
    without ever needing a cluster to be destructive against.
    """

    def __init__(self, stdout="", fail=False):
        self.calls = []
        self.stdout = stdout
        self.fail = fail

    def __call__(self, *args):
        cmd = [arg for arg in args if arg]
        self.calls.append(cmd)
        if self.fail:
            raise HelmoRuntimeError("Subprocess returned nonzero status").add_data(
                command=cmd, stderr=""
            )
        return SimpleNamespace(stdout=self.stdout, stderr="", returncode=0)


@pytest.fixture
def recorder():
    return CommandRecorder


HELMO_FILE_TEMPLATE = """\
TEST_CONTEXT=colima-helmo-test
PROD_CONTEXT=k3d-helmo-prod
CHART_VERSION=v1.19.2
APP_VERSION=v1.19.2
REPO_URL=https://charts.jetstack.io
REPOSITORY_NAME=jetstack
CHART_NAME=cert-manager
NAMESPACE=cert-manager
"""


@pytest.fixture
def helmo_file(tmp_path):
    """A valid ``<release>.helmo`` init file on disk."""
    path = tmp_path / "cert-manager.helmo"
    path.write_text(HELMO_FILE_TEMPLATE)
    return path
