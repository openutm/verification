import pytest


@pytest.fixture(autouse=True)
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _isolate_run_artifacts(tmp_path, monkeypatch):
    """Prevent ``SessionManager.run_scenario()`` from writing a timestamped
    ``reports/<timestamp>/report.log`` (and its parent dir) into the project
    tree during tests.

    Many tests instantiate a real ``SessionManager`` and call ``run_scenario``,
    which unconditionally creates ``<reporting.output_dir>/<timestamp>/`` and
    sets up file logging there. Without isolation, every test run would
    pollute the actual ``reports/`` directory (which is gitignored, so the
    leak is silent).

    This autouse fixture:
    1. No-ops ``setup_logging`` in the runner module (no log file is opened).
    2. Patches ``SessionManager.__init__`` so every instance's
       ``config.reporting.output_dir`` points at the per-test ``tmp_path``.
    """
    from openutm_verification.server import runner as runner_module

    monkeypatch.setattr(runner_module, "setup_logging", lambda *_args, **_kwargs: None)

    original_init = runner_module.SessionManager.__init__

    def _patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        # Redirect any per-run artefact directories into the test's tmp_path
        # so they don't end up under the project's real reports/ folder.
        self.config.reporting.output_dir = str(tmp_path)

    monkeypatch.setattr(runner_module.SessionManager, "__init__", _patched_init)
