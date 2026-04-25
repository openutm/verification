import asyncio
import shutil
from pathlib import Path
from typing import Any, Type, TypeVar

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse, RedirectResponse

from openutm_verification.core.execution.definitions import ScenarioDefinition, StepDefinition
from openutm_verification.core.execution.scenario_loader import load_yaml_scenario_definition
from openutm_verification.utils.paths import get_docs_directory, get_scenarios_directory

T = TypeVar("T")

scenario_router = APIRouter()

# Serialise concurrent Allure HTML generations: the underlying ``allure
# generate`` command rewrites ``allure-report/`` in place, so concurrent
# invocations would race and produce a corrupt report directory.
_allure_generate_lock = asyncio.Lock()


def get_runner(request: Request) -> Any:
    return request.app.state.runner


def get_dependency(dep_type: Type[T]):
    async def dependency(runner: Any = Depends(get_runner)) -> T:
        # Ensure session is initialized
        if not runner.session_resolver:
            await runner.initialize_session()
        return await runner.session_resolver.resolve(dep_type)

    return dependency


@scenario_router.post("/api/step")
async def execute_step(step: StepDefinition, runner: Any = Depends(get_runner)):
    return await runner.execute_single_step(step)


@scenario_router.get("/api/scenarios")
async def list_scenarios():
    """List all available scenarios, including those in sub-folders."""
    path = get_scenarios_directory()
    if not path.exists():
        return []
    return [f.relative_to(path).with_suffix("").as_posix() for f in sorted(path.rglob("*.yaml"))]


@scenario_router.get("/api/suites")
async def list_suites(runner: Any = Depends(get_runner)):
    """Return suite-to-scenario mapping, resolving bare names to subfolder-relative paths."""
    scenarios_path = get_scenarios_directory()
    # Build a mapping from stem to all matching scenario IDs to detect ambiguities.
    stem_to_ids: dict[str, list[str]] = {}
    for f in scenarios_path.rglob("*.yaml"):
        stem = f.stem
        scenario_id = f.relative_to(scenarios_path).with_suffix("").as_posix()
        stem_to_ids.setdefault(stem, []).append(scenario_id)

    def resolve_scenario_name(name: str) -> str:
        """Resolve a bare scenario name to its ID if unambiguous.

        If there are no scenarios with the given stem, or if multiple scenarios
        share the same stem, return the name unchanged so callers can use a
        fully-qualified ID instead.
        """
        ids = stem_to_ids.get(name)
        if not ids:
            # No matching stem; leave as-is.
            return name
        if len(ids) == 1:
            # Unique stem; safe to auto-resolve.
            return ids[0]
        # Ambiguous stem; do not auto-resolve to avoid silently picking one.
        return name

    config = runner.config
    result: dict[str, list[str]] = {}
    for suite_name, suite_config in config.suites.items():
        if suite_config.scenarios:
            result[suite_name] = [resolve_scenario_name(s.name) for s in suite_config.scenarios]
        else:
            result[suite_name] = []
    return result


@scenario_router.get("/api/scenarios/{scenario:path}/docs")
async def get_scenario_docs(scenario: str):
    """Get the documentation for a specific scenario."""
    docs_dir = get_docs_directory()
    file_path = (docs_dir / scenario).with_suffix(".md").resolve()
    if not file_path.is_relative_to(docs_dir.resolve()):
        raise HTTPException(status_code=404, detail="Documentation not found")
    if not file_path.exists():
        # Fallback: search by stem for flat doc files not yet reorganised into subfolders
        stem = Path(scenario).stem
        matches = list(docs_dir.rglob(f"{stem}.md"))
        if len(matches) == 1:
            file_path = matches[0]
        else:
            raise HTTPException(status_code=404, detail="Documentation not found")

    with open(file_path, "r", encoding="utf-8") as f:
        return PlainTextResponse(f.read())


@scenario_router.get("/api/scenarios/{scenario:path}")
async def get_scenario(scenario: str):
    """Get the content of a specific scenario."""
    try:
        scenario_def = load_yaml_scenario_definition(scenario)
        return scenario_def.model_dump()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Scenario not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Invalid YAML: {e}")


@scenario_router.post("/api/scenarios/{name:path}")
async def save_scenario(name: str, scenario: ScenarioDefinition):
    """Save a scenario to a YAML file."""
    base_dir = get_scenarios_directory().resolve()

    # Reject absolute paths in the name to prevent writing outside the scenarios directory
    if Path(name).is_absolute():
        raise HTTPException(status_code=400, detail="Invalid scenario name")

    # Normalize and validate the target path to prevent directory traversal
    file_path = (base_dir / name).with_suffix(".yaml").resolve()
    if not file_path.is_relative_to(base_dir):
        raise HTTPException(status_code=400, detail="Invalid scenario name")

    # Ensure directory exists (including any sub-folder)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Convert Pydantic model to dict, excluding None values to keep YAML clean
        data = scenario.model_dump(exclude_none=True, exclude_defaults=True)

        with open(file_path, "w") as f:
            yaml.dump(data, f, sort_keys=False, default_flow_style=False)

        return {"message": f"Scenario saved to {file_path.name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save scenario: {e}")


@scenario_router.get("/api/reports/latest")
async def get_latest_report(request: Request, scenario: str | None = None):
    """Redirect to the latest generated report. Optionally filter by scenario name."""
    runner = request.app.state.runner
    output_dir = Path(runner.config.reporting.output_dir)

    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="Reports directory not found")

    # Get all subdirectories that might contain reports
    runs = [d for d in output_dir.iterdir() if d.is_dir()]
    if not runs:
        raise HTTPException(status_code=404, detail="No reports found")

    if scenario:
        runs = [d for d in runs if (d / scenario).exists()]
        if not runs:
            raise HTTPException(status_code=404, detail=f"No reports found for scenario '{scenario}'")

    # Sort by directory name (timestamp) to find the latest
    latest_run = sorted(runs, key=lambda d: d.name)[-1]

    report_file = latest_run / "report.html"
    if not report_file.exists():
        raise HTTPException(status_code=404, detail="Report file not found in latest run")

    # Construct URL relative to the mounted /reports path
    relative_path = report_file.relative_to(output_dir)
    url = f"/reports/{relative_path}"

    return RedirectResponse(url=url)


@scenario_router.post("/api/allure/generate")
async def generate_allure_report(request: Request):
    """Run ``allure generate`` to build HTML from allure-results.

    Results are read from the active run directory
    (``<output_dir>/<timestamp>/<results_dir>``) and HTML is written next to
    them as ``allure-report/``. Concurrent calls are serialised with an
    ``asyncio.Lock`` because the CLI rewrites the output directory in place.
    """
    runner = request.app.state.runner
    allure_cfg = runner.config.reporting.allure

    if not allure_cfg.enabled:
        raise HTTPException(status_code=400, detail="Allure reporting is not enabled in config")

    output_dir = Path(runner.config.reporting.output_dir).resolve()
    results_dir = _resolve_run_allure_results_dir(runner).resolve()

    if not results_dir.exists() or not any(results_dir.iterdir()):
        raise HTTPException(status_code=404, detail="No Allure results found. Run a scenario first.")

    report_dir = (results_dir.parent / "allure-report").resolve()

    # The report path is exposed via the /reports static mount, which serves
    # files from ``output_dir``. Refuse to generate outside that tree to
    # prevent path traversal and to keep ``/api/allure/report`` deterministic.
    try:
        report_dir.relative_to(output_dir)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Allure report directory {report_dir} is outside the configured "
                f"reporting output directory {output_dir}. Adjust reporting.allure.results_dir."
            ),
        ) from exc

    # Prefer a locally installed Allure CLI. Fall back to npx with the
    # explicit ``allure-commandline`` package and ``-y`` so it never prompts.
    allure_cmd = shutil.which("allure")
    if allure_cmd:
        cmd = [allure_cmd, "generate", str(results_dir), "--clean", "--output", str(report_dir)]
    elif shutil.which("npx"):
        cmd = ["npx", "-y", "allure-commandline@latest", "generate", str(results_dir), "--clean", "--output", str(report_dir)]
    else:
        raise HTTPException(
            status_code=500,
            detail="Allure CLI not found. Install with `brew install allure` or ensure `npx` is on PATH.",
        )

    async with _allure_generate_lock:
        # Clean previous report so stale files don't linger. The CLI's --clean
        # flag covers this too, but doing it ourselves catches the case where
        # the directory exists but the CLI fails before writing.
        if report_dir.exists():
            shutil.rmtree(report_dir)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=500,
                detail="Allure CLI not found. Install with `brew install allure`.",
            ) from exc
        except asyncio.TimeoutError as exc:
            raise HTTPException(status_code=500, detail="Allure generate timed out after 120s") from exc

        if proc.returncode != 0:
            detail = stderr.decode(errors="replace").strip() or stdout.decode(errors="replace").strip()
            raise HTTPException(status_code=500, detail=f"allure generate failed: {detail}")

    relative_path = report_dir.relative_to(output_dir)
    return {
        "status": "success",
        "report_url": f"/reports/{relative_path}/index.html",
    }


@scenario_router.get("/api/allure/report")
async def get_allure_report(request: Request):
    """Redirect to the generated Allure HTML report for the current run."""
    runner = request.app.state.runner
    allure_cfg = runner.config.reporting.allure
    if not allure_cfg.enabled:
        raise HTTPException(status_code=400, detail="Allure reporting is not enabled in config")

    output_dir = Path(runner.config.reporting.output_dir).resolve()
    results_dir = _resolve_run_allure_results_dir(runner).resolve()
    report_index = (results_dir.parent / "allure-report" / "index.html").resolve()

    if not report_index.exists():
        raise HTTPException(
            status_code=404,
            detail="Allure report not generated yet. Call POST /api/allure/generate first.",
        )

    try:
        relative_path = report_index.relative_to(output_dir)
    except ValueError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Allure report at {report_index} is not under reporting.output_dir {output_dir}",
        ) from exc
    return RedirectResponse(url=f"/reports/{relative_path}")


def _resolve_run_allure_results_dir(runner: Any) -> Path:
    """Compute the active-run Allure results directory.

    Mirrors :func:`openutm_verification.core.execution.execution._resolve_allure_results_dir`
    but pulls the timestamp from the live ``SessionManager`` so the latest
    server-driven run is always targeted.
    """
    cfg = runner.config
    p = Path(cfg.reporting.allure.results_dir)
    if p.is_absolute():
        return p
    timestamp = runner.current_timestamp_str or cfg.reporting.timestamp_subdir
    base = Path(cfg.reporting.output_dir)
    if timestamp:
        return base / timestamp / p
    return base / p
