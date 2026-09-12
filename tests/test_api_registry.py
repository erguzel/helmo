"""Docker Registry v2 client, driven through a mock transport.

No registry is contacted.  The conftest fixture redirects HOME, so the netrc
fallback reads a throwaway file rather than the developer's credentials.
"""

import httpx
import pytest

from helmo.api import RegistryClient
from helmo.validate import HelmoApiError

REGISTRY = "https://registry.example.com:5000"


def make_client(handler):
    """A RegistryClient whose transport is mocked, with explicit credentials."""
    client = RegistryClient(REGISTRY, username="user", password="pass")
    client.client.close()
    client.client = httpx.Client(transport=httpx.MockTransport(handler))
    return client


def test_trailing_slash_is_stripped_from_the_registry_url():
    client = RegistryClient(f"{REGISTRY}/", username="user", password="pass")
    try:
        assert client.registry_url == REGISTRY
    finally:
        client.client.close()


def test_client_does_not_follow_redirects():
    """Credentials must not be replayed to whatever a redirect points at."""
    client = RegistryClient(REGISTRY, username="user", password="pass")
    try:
        assert client.client.follow_redirects is False
    finally:
        client.client.close()


def test_explicit_credentials_are_used_verbatim():
    client = RegistryClient(REGISTRY, username="user", password="pass")
    try:
        assert isinstance(client.client.auth, httpx.BasicAuth)
    finally:
        client.client.close()


def test_falls_back_to_netrc_when_no_credentials_are_given(
    isolated_environment,
):
    netrc = isolated_environment / ".netrc"
    netrc.write_text("machine registry.example.com login user password pass\n")
    netrc.chmod(0o600)

    client = RegistryClient(REGISTRY)
    try:
        assert isinstance(client.client.auth, httpx.NetRCAuth)
    finally:
        client.client.close()


def test_get_digest_returns_the_content_digest_header():
    digest = "sha256:" + "ab" * 32

    def handler(request):
        assert request.method == "HEAD"
        assert request.url.path == "/v2/myapp/manifests/v1.0.0"
        assert "application/vnd.oci.image.manifest.v1+json" in request.headers[
            "Accept"
        ]
        return httpx.Response(200, headers={"docker-content-digest": digest})

    client = make_client(handler)
    with client:
        assert client.get_digest("myapp", "v1.0.0") == digest


def test_get_digest_raises_when_the_digest_header_is_absent():
    client = make_client(lambda request: httpx.Response(200))
    with client:
        with pytest.raises(HelmoApiError) as excinfo:
            client.get_digest("myapp", "v1.0.0")
    assert excinfo.value.data == {"image": "myapp", "tag": "v1.0.0"}


def test_get_digest_raises_for_an_error_status():
    client = make_client(lambda request: httpx.Response(401))
    with client:
        with pytest.raises(httpx.HTTPStatusError):
            client.get_digest("myapp", "v1.0.0")


def test_list_catalog_returns_the_repositories():
    client = make_client(
        lambda request: httpx.Response(200, json={"repositories": ["a", "b"]})
    )
    with client:
        assert client.list_catalog() == ["a", "b"]


def test_list_catalog_tolerates_an_empty_registry():
    client = make_client(lambda request: httpx.Response(200, json={}))
    with client:
        assert client.list_catalog() == []


def test_list_tags_returns_the_tags():
    client = make_client(
        lambda request: httpx.Response(200, json={"tags": ["v1", "v2"]})
    )
    with client:
        assert client.list_tags("myapp") == ["v1", "v2"]


@pytest.mark.parametrize(
    "status,expected", [(202, True), (404, True), (500, False)]
)
def test_delete_manifest_reports_success_for_accepted_and_absent(
    status, expected
):
    """404 counts as deleted -- the manifest is gone either way."""
    client = make_client(lambda request: httpx.Response(status))
    with client:
        assert client.delete_manifest("myapp", "sha256:dead") is expected


def test_delete_tag_resolves_the_digest_before_deleting():
    digest = "sha256:" + "cd" * 32
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path))
        if request.method == "HEAD":
            return httpx.Response(
                200, headers={"docker-content-digest": digest}
            )
        return httpx.Response(202)

    client = make_client(handler)
    with client:
        assert client.delete_tag("myapp", "v1.0.0") is True

    assert seen == [
        ("HEAD", "/v2/myapp/manifests/v1.0.0"),
        ("DELETE", f"/v2/myapp/manifests/{digest}"),
    ]


def test_delete_all_tags_records_a_failure_without_aborting_the_rest():
    digest = "sha256:" + "ef" * 32

    def handler(request):
        if request.url.path.endswith("/tags/list"):
            return httpx.Response(200, json={"tags": ["good", "bad"]})
        if request.method == "HEAD":
            if request.url.path.endswith("/bad"):
                return httpx.Response(404, json={"errors": ["not found"]})
            return httpx.Response(
                200, headers={"docker-content-digest": digest}
            )
        return httpx.Response(202)

    client = make_client(handler)
    with client:
        result = client.delete_all_tags("myapp")

    assert result["good"] is True
    assert result["bad"]["status_code"] == 404


def test_context_manager_closes_the_transport():
    client = make_client(lambda request: httpx.Response(200, json={}))
    with client:
        pass
    assert client.client.is_closed
