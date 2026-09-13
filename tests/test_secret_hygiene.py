"""Nothing helmo prints may carry a credential.

Two leaks were found by running the tool, and both are pinned here.

``netrc.NetrcParseError`` quotes the token it choked on, and in a malformed
entry that token is the password.  loguru's ``backtrace``/``diagnose`` default
to True, which annotates every frame of a failure with the values appearing in
its source line -- and on the registry path those are netrc credentials.

The canary below is what a real password would look like in that output.  It
must not appear.
"""

import sys

import pytest
from click.testing import CliRunner
from loguru import logger

from helmo.cli import cli, setup_logging
from helmo.validate import HelmoError, load_validated_netrc

CANARY = "canary-password-must-not-be-printed"


@pytest.fixture
def malformed_netrc(isolated_environment):
    """A netrc whose password sits where the parser expects a token."""
    netrc = isolated_environment / ".netrc"
    netrc.write_text(f"machine registry.example.com\nlogin\npassword {CANARY}\n")
    netrc.chmod(0o600)
    return netrc


def test_malformed_netrc_raises_a_helmo_error_without_the_token(malformed_netrc):
    with pytest.raises(HelmoError) as excinfo:
        load_validated_netrc(str(malformed_netrc))
    rendered = str(excinfo.value) + "".join(getattr(excinfo.value, "__notes__", []))
    assert CANARY not in rendered
    assert "could not be parsed" in rendered


def test_malformed_netrc_suppresses_the_original_cause(malformed_netrc):
    """``from None`` matters: a chained cause would print the token anyway."""
    with pytest.raises(HelmoError) as excinfo:
        load_validated_netrc(str(malformed_netrc))
    assert excinfo.value.__cause__ is None
    assert excinfo.value.__suppress_context__ is True


def test_cli_does_not_print_the_token_of_a_malformed_netrc(malformed_netrc):
    result = CliRunner().invoke(cli, ["registry", "catalog"])
    assert result.exit_code != 0
    assert CANARY not in result.output


def _explode(credential):
    raise RuntimeError("failed")


def _crash_carrying_a_credential():
    """The frame loguru would annotate: the value is named on the failing line."""

    @logger.catch(reraise=False)
    def boom():
        password = CANARY
        _explode(password)

    boom()


def test_default_logging_does_not_annotate_frames_with_values(capsys):
    setup_logging()
    _crash_carrying_a_credential()
    logger.remove()
    assert CANARY not in capsys.readouterr().err


def test_helmo_debug_restores_the_annotated_traceback(capsys, monkeypatch):
    """The escape hatch still works -- and shows exactly what it costs."""
    monkeypatch.setenv("HELMO_DEBUG", "1")
    setup_logging()
    _crash_carrying_a_credential()
    logger.remove()
    assert CANARY in capsys.readouterr().err


@pytest.fixture(autouse=True)
def restore_logging():
    """Leave the root logger the way the rest of the suite expects it."""
    yield
    logger.remove()
    logger.add(sys.stderr)
