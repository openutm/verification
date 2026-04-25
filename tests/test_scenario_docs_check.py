"""Tests for scenario documentation check (issue #101)."""

from unittest.mock import MagicMock, patch

import pytest

from openutm_verification.core.execution.dependencies import get_scenario_docs, scenarios


class TestGetScenarioDocs:
    """Tests for get_scenario_docs with recursive subdirectory search."""

    def test_returns_content_for_existing_flat_doc(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        doc_file = docs_dir / "my_scenario.md"
        doc_file.write_text("# My Scenario\nSome content.", encoding="utf-8")

        with patch("openutm_verification.core.execution.dependencies.get_docs_directory", return_value=docs_dir):
            result = get_scenario_docs("my_scenario")

        assert result == "# My Scenario\nSome content."

    def test_returns_content_for_doc_in_subdirectory(self, tmp_path):
        docs_dir = tmp_path / "docs"
        sub_dir = docs_dir / "standard-scenarios"
        sub_dir.mkdir(parents=True)
        doc_file = sub_dir / "F1_happy_path.md"
        doc_file.write_text("# F1 Happy Path", encoding="utf-8")

        with patch("openutm_verification.core.execution.dependencies.get_docs_directory", return_value=docs_dir):
            result = get_scenario_docs("F1_happy_path")

        assert result == "# F1 Happy Path"

    def test_returns_none_when_no_docs_exist(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        with patch("openutm_verification.core.execution.dependencies.get_docs_directory", return_value=docs_dir):
            result = get_scenario_docs("nonexistent_scenario")

        assert result is None

    def test_returns_none_when_docs_dir_is_none(self):
        with patch("openutm_verification.core.execution.dependencies.get_docs_directory", return_value=None):
            result = get_scenario_docs("any_scenario")

        assert result is None

    def test_returns_none_for_multiple_matches(self, tmp_path):
        docs_dir = tmp_path / "docs"
        dir1 = docs_dir / "subdir1"
        dir2 = docs_dir / "subdir2"
        dir1.mkdir(parents=True)
        dir2.mkdir(parents=True)
        (dir1 / "ambiguous.md").write_text("A", encoding="utf-8")
        (dir2 / "ambiguous.md").write_text("B", encoding="utf-8")

        with patch("openutm_verification.core.execution.dependencies.get_docs_directory", return_value=docs_dir):
            with patch("openutm_verification.core.execution.dependencies.logger") as mock_logger:
                result = get_scenario_docs("ambiguous")

        assert result is None
        warning_calls = " ".join(str(c) for c in mock_logger.warning.call_args_list)
        assert "Multiple documentation files found" in warning_calls

    def test_returns_none_when_docs_dir_does_not_exist(self, tmp_path):
        missing_dir = tmp_path / "nonexistent"

        with patch("openutm_verification.core.execution.dependencies.get_docs_directory", return_value=missing_dir):
            with patch("openutm_verification.core.execution.dependencies.logger") as mock_logger:
                result = get_scenario_docs("any_scenario")

        assert result is None
        warning_calls = " ".join(str(c) for c in mock_logger.warning.call_args_list)
        assert "does not exist or is not a directory" in warning_calls


class TestScenariosDocsCheck:
    """Tests for documentation warnings/errors in the scenarios() generator."""

    def _make_config(self, scenario_docs="warn", scenario_names=None):
        """Create a mock config proxy with the given scenario_docs mode."""
        if scenario_names is None:
            scenario_names = ["test_scenario"]

        suite_scenarios = []
        for name in scenario_names:
            ss = MagicMock()
            ss.name = name
            suite_scenarios.append(ss)

        mock_suite = MagicMock()
        mock_suite.scenarios = suite_scenarios

        suites_dict = {"default_suite": mock_suite}

        mock_config = MagicMock()
        mock_config.scenario_docs = scenario_docs
        mock_config.target_suites = []
        mock_config.suites = suites_dict

        return mock_config

    @patch("openutm_verification.core.execution.dependencies.get_docs_directory")
    @patch("openutm_verification.core.execution.dependencies.get_scenario_docs")
    @patch("openutm_verification.core.execution.dependencies.get_settings")
    def test_warn_mode_logs_warning_for_missing_docs(self, mock_get_settings, mock_get_docs, mock_docs_dir, capfd, tmp_path):
        mock_get_settings.return_value = self._make_config(scenario_docs="warn")
        mock_get_docs.return_value = None
        mock_docs_dir.return_value = tmp_path / "docs"

        with patch("openutm_verification.core.execution.dependencies.logger") as mock_logger:
            list(scenarios())
            warning_calls = " ".join(str(c) for c in mock_logger.warning.call_args_list)
            assert "test_scenario" in warning_calls
            assert "has no documentation" in warning_calls

    @patch("openutm_verification.core.execution.dependencies.get_scenario_docs")
    @patch("openutm_verification.core.execution.dependencies.get_settings")
    def test_required_mode_raises_for_missing_docs(self, mock_get_settings, mock_get_docs):
        mock_get_settings.return_value = self._make_config(scenario_docs="required")
        mock_get_docs.return_value = None

        with patch("openutm_verification.core.execution.dependencies.logger"):
            with pytest.raises(FileNotFoundError, match="Missing documentation for scenario 'test_scenario'"):
                list(scenarios())

    @patch("openutm_verification.core.execution.dependencies.get_scenario_docs")
    @patch("openutm_verification.core.execution.dependencies.get_settings")
    def test_ignore_mode_no_warning_for_missing_docs(self, mock_get_settings, mock_get_docs):
        mock_get_settings.return_value = self._make_config(scenario_docs="ignore")
        mock_get_docs.return_value = None

        with patch("openutm_verification.core.execution.dependencies.logger") as mock_logger:
            list(scenarios())
            # Should not have any warning or error about docs
            for call in mock_logger.warning.call_args_list:
                assert "has no documentation" not in str(call)
            for call in mock_logger.error.call_args_list:
                assert "has no documentation" not in str(call)

    @patch("openutm_verification.core.execution.dependencies.get_scenario_docs")
    @patch("openutm_verification.core.execution.dependencies.get_settings")
    def test_no_warning_when_docs_exist(self, mock_get_settings, mock_get_docs):
        mock_get_settings.return_value = self._make_config(scenario_docs="warn")
        mock_get_docs.return_value = "# Some Documentation"

        with patch("openutm_verification.core.execution.dependencies.logger") as mock_logger:
            list(scenarios())
            for call in mock_logger.warning.call_args_list:
                assert "has no documentation" not in str(call)

    @patch("openutm_verification.core.execution.dependencies.get_scenario_docs")
    @patch("openutm_verification.core.execution.dependencies.get_settings")
    def test_required_mode_no_error_when_docs_exist(self, mock_get_settings, mock_get_docs):
        mock_get_settings.return_value = self._make_config(scenario_docs="required")
        mock_get_docs.return_value = "# Documented Scenario"

        with patch("openutm_verification.core.execution.dependencies.logger"):
            result = list(scenarios())
            assert result == ["test_scenario"]
