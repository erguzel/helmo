"""The subprocess wrapper every kubectl and helm call goes through."""

import sys

import pytest

from helmo.runtime import execute_subprocess
from helmo.validate import HelmoRuntimeError


def test_returns_completed_process_on_success():
    result = execute_subprocess(sys.executable, "-c", "print('hello')")
    assert result.returncode == 0
    assert result.stdout.strip() == "hello"


def test_drops_empty_arguments():
    """Callers pass optional flags as '' when unset; those must not reach argv.

    ``runtime.k8s`` builds commands like ``[..., '-n' if ns else '', ns or '']``
    and relies on this filtering, otherwise kubectl would receive empty
    positional arguments.
    """
    result = execute_subprocess(sys.executable, "", "-c", "", "print('ok')")
    assert result.stdout.strip() == "ok"


def test_raises_with_command_and_stderr_on_failure():
    with pytest.raises(HelmoRuntimeError) as excinfo:
        execute_subprocess(
            sys.executable,
            "-c",
            "import sys; sys.stderr.write('boom'); sys.exit(2)",
        )
    error = excinfo.value
    assert error.data["command"][0] == sys.executable
    assert "boom" in error.data["stderr"]


def test_error_serialises_for_logging():
    with pytest.raises(HelmoRuntimeError) as excinfo:
        execute_subprocess(sys.executable, "-c", "raise SystemExit(3)")
    payload = excinfo.value.to_dict()
    assert payload["error"] == "HelmoRuntimeError"
    assert "command" in payload["data"]
