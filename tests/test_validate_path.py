"""Path and suffix validation.

These are the guards every CLI command runs before touching the filesystem, so
their edge cases are worth pinning down.
"""

import pytest

from helmo.validate import (
    HelmoPathError,
    directory_exists,
    ensure_file,
    file_exists,
    is_file,
    is_path,
    is_path_or_file,
    path_resolver,
    suffix_exists,
)


def test_path_resolver_expands_home(isolated_environment):
    assert path_resolver("~/values.yaml") == isolated_environment / "values.yaml"


def test_path_resolver_returns_absolute_path(tmp_path):
    resolved = path_resolver(tmp_path / "sub" / ".." / "values.yaml")
    assert resolved.is_absolute()
    assert resolved == tmp_path / "values.yaml"


def test_file_exists_reports_presence(tmp_path):
    present = tmp_path / "present.yaml"
    present.write_text("{}")
    assert file_exists(present) is True
    assert file_exists(tmp_path / "absent.yaml") is False


def test_file_exists_raises_when_ensure_is_set(tmp_path):
    with pytest.raises(HelmoPathError):
        file_exists(tmp_path / "absent.yaml", ensure=True)


def test_directory_exists_distinguishes_files_from_directories(tmp_path):
    a_file = tmp_path / "a.yaml"
    a_file.write_text("{}")
    assert directory_exists(tmp_path) is True
    assert directory_exists(a_file) is False


def test_ensure_file_returns_resolved_path(tmp_path):
    target = tmp_path / "release.helmo"
    target.write_text("")
    assert ensure_file(target, ".helmo") == target


def test_ensure_file_raises_for_missing_file(tmp_path):
    with pytest.raises(HelmoPathError):
        ensure_file(tmp_path / "missing.helmo", ".helmo")


def test_ensure_file_rejects_unexpected_suffix(tmp_path):
    target = tmp_path / "release.txt"
    target.write_text("")
    with pytest.raises(HelmoPathError):
        ensure_file(target, ".helmo")


def test_suffix_exists_accepts_an_allowed_suffix(tmp_path):
    assert suffix_exists(tmp_path / "values.yaml", ".yaml", ".yml") is True
    assert suffix_exists(tmp_path / "values.yml", ".yaml", ".yml") is True


def test_suffix_exists_rejects_a_disallowed_suffix(tmp_path):
    assert suffix_exists(tmp_path / "values.json", ".yaml", ".yml") is False


def test_suffix_exists_rejects_compound_suffixes(tmp_path):
    """Archived manifests carry a versioning suffix and must not pass as input.

    ``init`` writes files such as ``release_prod_v1.2.3_20260101120000.yaml``;
    only single-suffix names are accepted so an archived copy is never mistaken
    for a live manifest.
    """
    assert suffix_exists(tmp_path / "values.backup.yaml", ".yaml") is False


def test_suffix_exists_handles_dotfiles(tmp_path):
    assert suffix_exists(tmp_path / ".helmo", ".helmo") is True


def test_is_path_detects_multi_part_names():
    assert is_path("charts/cert-manager") is True
    assert is_path("cert-manager") is False


def test_is_file_detects_a_suffix():
    assert is_file("cert-manager.helmo") is True
    assert is_file("cert-manager") is False


def test_is_path_or_file_rejects_anything_that_is_not_a_bare_name():
    """Release names given as CLI arguments must be bare names, not paths."""
    assert is_path_or_file("cert-manager") is False
    assert is_path_or_file("cert-manager.helmo") is True
    assert is_path_or_file("deploy/cert-manager") is True
