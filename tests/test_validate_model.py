"""Schema validation for the two file formats helmo reads.

``<release>.helmo`` drives a single deployment; ``releases.yaml`` drives a
serial one.  Both are user-authored, so a bad field must fail loudly before any
cluster call is made.
"""

import pytest
from pydantic import ValidationError

from helmo.validate import (
    HelmoReleasesYamlItemModel,
    ensure_helmo_init_file_format,
    safe_load_helmo_releases_yaml_file,
)


def test_valid_init_file_parses_every_field(helmo_file):
    settings = ensure_helmo_init_file_format(helmo_file)
    assert settings.REPOSITORY_NAME == "jetstack"
    assert settings.CHART_NAME == "cert-manager"
    assert settings.CHART_VERSION == "v1.19.2"
    assert settings.NAMESPACE == "cert-manager"
    assert settings.TEST_CONTEXT == "colima-helmo-test"
    assert settings.PROD_CONTEXT == "k3d-helmo-prod"


def test_init_file_missing_a_required_field_is_rejected(helmo_file, tmp_path):
    incomplete = tmp_path / "broken.helmo"
    incomplete.write_text(
        helmo_file.read_text().replace("NAMESPACE=cert-manager\n", "")
    )
    with pytest.raises(ValidationError):
        ensure_helmo_init_file_format(incomplete)


def test_init_file_with_a_malformed_repo_url_is_rejected(helmo_file, tmp_path):
    bad_url = tmp_path / "badurl.helmo"
    bad_url.write_text(
        helmo_file.read_text().replace(
            "REPO_URL=https://charts.jetstack.io", "REPO_URL=not-a-url"
        )
    )
    with pytest.raises(ValidationError):
        ensure_helmo_init_file_format(bad_url)


def test_release_item_requires_a_helmo_init_file():
    with pytest.raises(ValidationError):
        HelmoReleasesYamlItemModel(initFile="cert-manager.txt", environment="test")


def test_release_item_rejects_a_non_yaml_resource_manifest():
    with pytest.raises(ValidationError):
        HelmoReleasesYamlItemModel(
            initFile="cert-manager.helmo",
            environment="test",
            resourceManifestNames=["issuer.json"],
        )


def test_release_item_rejects_an_unknown_environment():
    with pytest.raises(ValidationError):
        HelmoReleasesYamlItemModel(
            initFile="cert-manager.helmo", environment="qa"
        )


def test_release_item_rejects_the_staging_environment():
    """staging has no STAGING_CONTEXT counterpart in the .helmo init file."""
    with pytest.raises(ValidationError):
        HelmoReleasesYamlItemModel(
            initFile="cert-manager.helmo", environment="staging"
        )


def test_release_item_defaults_optional_lists_to_empty():
    item = HelmoReleasesYamlItemModel(
        initFile="cert-manager.helmo", environment="prod"
    )
    assert item.secretFileNames == []
    assert item.resourceManifestNames == []
    assert item.additionalValuesNames == []


def test_releases_yaml_file_round_trips(tmp_path):
    releases = tmp_path / "releases.yaml"
    releases.write_text(
        """
releases:
  - initFile: cert-manager.helmo
    environment: test
    secretFileNames:
      - registry.dockerconfigjson
    resourceManifestNames:
      - cluster-issuer.yaml
  - initFile: ingress-nginx.helmo
    environment: prod
"""
    )
    parsed = safe_load_helmo_releases_yaml_file(releases)
    assert [r.initFile for r in parsed.releases] == [
        "cert-manager.helmo",
        "ingress-nginx.helmo",
    ]
    assert parsed.releases[0].resourceManifestNames == ["cluster-issuer.yaml"]
    assert parsed.releases[1].secretFileNames == []
