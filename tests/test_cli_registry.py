"""Registry group parsing.

``helmo registry <subcommand> --help`` used to fail without ``~/.netrc``: the
url was read in the group callback, which Click runs before it reaches the
subcommand, so reading the help text demanded a credential file.  The url is a
lazy option default now, and these tests pin that down.  ``HOME`` points at an
empty directory through the autouse ``isolated_environment`` fixture, so no
real ``~/.netrc`` can satisfy them.
"""

import pytest
from click.testing import CliRunner
from click.exceptions import UsageError

from helmo.cli import cli, registry_url_from_netrc

REGISTRY_SUBCOMMANDS = [
    "catalog",
    "tags",
    "get-digest",
    "delete-digest",
    "delete-tags",
    "delete-all",
    "gc-collect",
]


@pytest.fixture
def runner():
    return CliRunner()


def test_registry_group_help_needs_no_netrc(runner):
    result = runner.invoke(cli, ["registry", "--help"])
    assert result.exit_code == 0
    assert "Registry commands" in result.output


@pytest.mark.parametrize("subcommand", REGISTRY_SUBCOMMANDS)
def test_registry_subcommand_help_needs_no_netrc(runner, subcommand):
    result = runner.invoke(cli, ["registry", subcommand, "--help"])
    assert result.exit_code == 0
    assert "--help" in result.output


def test_missing_netrc_reports_a_usage_error(runner):
    """The failure is a usage error, not a traceback out of the path layer."""
    result = runner.invoke(cli, ["registry", "catalog"])
    assert result.exit_code != 0
    assert "--registryurl" in result.output
    assert "HELMO_REGISTRY_URL" in result.output


def test_registry_url_default_raises_usage_error_without_netrc():
    with pytest.raises(UsageError):
        registry_url_from_netrc()


def test_netrc_machine_becomes_the_default_registry_url(isolated_environment):
    netrc = isolated_environment / ".netrc"
    netrc.write_text("machine registry.example.com login someone password secret\n")
    netrc.chmod(0o600)
    assert registry_url_from_netrc() == "registry.example.com"
