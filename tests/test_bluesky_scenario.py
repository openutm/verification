"""Tests for the BlueSky YAML scenario definition feature (issue #78)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from openutm_verification.core.clients.air_traffic.bluesky_scenario import (
    BlueSkyAircraft,
    BlueSkyArea,
    BlueSkyScenarioDefinition,
    load_bluesky_scenario,
    resolve_scn_path,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_SCENARIO_DATA: dict = {
    "name": "Test Scenario",
    "aircraft": [
        {
            "callsign": "AC001",
            "type": "C172",
            "lat": 53.5200,
            "lon": -113.5500,
            "heading": 270,
            "altitude_ft": 400,
            "speed_kts": 87,
        }
    ],
}

FULL_SCENARIO_DATA: dict = {
    "name": "A1 Head-On Approach",
    "description": "ASTM F3442 Category A1 scenario",
    "display": {
        "pan": [53.5200, -113.5750],
        "trails": True,
        "reso": False,
        "rtf": 10,
    },
    "areas": [
        {
            "name": "EDM_A1_BOX",
            "color": [0, 255, 0],
            "bounds": [
                [53.5100, -113.6100],
                [53.5100, -113.5400],
                [53.5300, -113.5400],
                [53.5300, -113.6100],
            ],
        }
    ],
    "aircraft": [
        {
            "callsign": "INTA1",
            "type": "C172",
            "lat": 53.5200,
            "lon": -113.5500,
            "heading": 270,
            "altitude_ft": 400,
            "speed_kts": 87,
            "start_time": "00:00:00.00",
            "waypoints": [
                [53.5200, -113.5750],
                [53.5200, -113.6000],
            ],
        }
    ],
    "hold_time": "00:02:00.00",
}


# ---------------------------------------------------------------------------
# Model validation tests
# ---------------------------------------------------------------------------


class TestBlueSkyArea:
    def test_valid_area(self) -> None:
        area = BlueSkyArea(
            name="BOX",
            bounds=[[53.0, -113.0], [53.0, -112.0], [54.0, -112.0]],
        )
        assert area.name == "BOX"
        assert area.color == [0, 255, 0]

    def test_invalid_color_channel(self) -> None:
        with pytest.raises(ValueError, match="Color channel value"):
            BlueSkyArea(
                name="BOX",
                bounds=[[53.0, -113.0], [53.0, -112.0], [54.0, -112.0]],
                color=[0, 256, 0],
            )

    def test_too_few_bounds(self) -> None:
        with pytest.raises(ValueError):
            BlueSkyArea(name="BOX", bounds=[[53.0, -113.0], [53.0, -112.0]])


class TestBlueSkyAircraft:
    def test_callsign_uppercased(self) -> None:
        ac = BlueSkyAircraft(
            callsign="ac001",
            type="C172",
            lat=53.0,
            lon=-113.0,
            heading=270,
            altitude_ft=400,
            speed_kts=87,
        )
        assert ac.callsign == "AC001"

    def test_invalid_time_format(self) -> None:
        with pytest.raises(ValueError, match="HH:MM:SS.SS"):
            BlueSkyAircraft(
                callsign="AC001",
                type="C172",
                lat=53.0,
                lon=-113.0,
                heading=270,
                altitude_ft=400,
                speed_kts=87,
                start_time="invalid",
            )

    def test_heading_out_of_range(self) -> None:
        with pytest.raises(ValueError):
            BlueSkyAircraft(
                callsign="AC001",
                type="C172",
                lat=53.0,
                lon=-113.0,
                heading=400,  # > 360
                altitude_ft=400,
                speed_kts=87,
            )


class TestBlueSkyScenarioDefinition:
    def test_minimal_valid(self) -> None:
        scenario = BlueSkyScenarioDefinition.model_validate(MINIMAL_SCENARIO_DATA)
        assert scenario.name == "Test Scenario"
        assert len(scenario.aircraft) == 1
        assert scenario.hold_time == "00:02:00.00"

    def test_full_valid(self) -> None:
        scenario = BlueSkyScenarioDefinition.model_validate(FULL_SCENARIO_DATA)
        assert scenario.name == "A1 Head-On Approach"
        assert len(scenario.areas) == 1
        assert scenario.display.pan == [53.5200, -113.5750]

    def test_duplicate_callsigns_rejected(self) -> None:
        data = {
            "name": "Dup",
            "aircraft": [
                {"callsign": "AC001", "type": "C172", "lat": 53.0, "lon": -113.0, "heading": 0, "altitude_ft": 400, "speed_kts": 87},
                {"callsign": "AC001", "type": "B744", "lat": 54.0, "lon": -114.0, "heading": 0, "altitude_ft": 400, "speed_kts": 200},
            ],
        }
        with pytest.raises(ValueError, match="Duplicate aircraft callsign"):
            BlueSkyScenarioDefinition.model_validate(data)

    def test_no_aircraft_rejected(self) -> None:
        with pytest.raises(ValueError):
            BlueSkyScenarioDefinition.model_validate({"name": "Empty", "aircraft": []})


# ---------------------------------------------------------------------------
# SCN rendering tests
# ---------------------------------------------------------------------------


class TestToScn:
    def test_minimal_scn_contains_cre_and_hold(self) -> None:
        scenario = BlueSkyScenarioDefinition.model_validate(MINIMAL_SCENARIO_DATA)
        scn = scenario.to_scn()
        assert "CRE AC001,C172" in scn
        assert "HOLD" in scn

    def test_waypoints_rendered(self) -> None:
        scenario = BlueSkyScenarioDefinition.model_validate(FULL_SCENARIO_DATA)
        scn = scenario.to_scn()
        assert "INTA1 ADDWPT 53.52,-113.575" in scn
        assert "INTA1 ADDWPT 53.52,-113.6" in scn

    def test_poly_area_rendered(self) -> None:
        scenario = BlueSkyScenarioDefinition.model_validate(FULL_SCENARIO_DATA)
        scn = scenario.to_scn()
        assert "POLY EDM_A1_BOX" in scn
        assert "COLOR EDM_A1_BOX 0,255,0" in scn

    def test_display_settings_rendered(self) -> None:
        scenario = BlueSkyScenarioDefinition.model_validate(FULL_SCENARIO_DATA)
        scn = scenario.to_scn()
        assert "TRAILS ON" in scn
        assert "RESO OFF" in scn
        assert "RTF 10" in scn
        assert "PAN 53.52,-113.575" in scn

    def test_header_comment(self) -> None:
        scenario = BlueSkyScenarioDefinition.model_validate(FULL_SCENARIO_DATA)
        scn = scenario.to_scn()
        assert scn.startswith("# A1 Head-On Approach")

    def test_staggered_start_time(self) -> None:
        data = {
            "name": "Staggered",
            "aircraft": [
                {
                    "callsign": "INTB",
                    "type": "B206",
                    "lat": 53.52,
                    "lon": -113.55,
                    "heading": 0,
                    "altitude_ft": 492,
                    "speed_kts": 78,
                    "start_time": "00:00:20.00",
                }
            ],
        }
        scn = BlueSkyScenarioDefinition.model_validate(data).to_scn()
        assert "00:00:20.00>CRE INTB,B206" in scn

    def test_hold_time_in_scn(self) -> None:
        scenario = BlueSkyScenarioDefinition.model_validate(FULL_SCENARIO_DATA)
        scn = scenario.to_scn()
        assert "00:02:00.00>HOLD" in scn

    def test_write_scn_creates_file(self, tmp_path: Path) -> None:
        scenario = BlueSkyScenarioDefinition.model_validate(MINIMAL_SCENARIO_DATA)
        dest = tmp_path / "out.scn"
        returned = scenario.write_scn(dest)
        assert returned == dest
        assert dest.exists()
        assert "CRE AC001" in dest.read_text()

    def test_write_temp_scn(self) -> None:
        scenario = BlueSkyScenarioDefinition.model_validate(MINIMAL_SCENARIO_DATA)
        tmp = scenario.write_temp_scn()
        p = Path(tmp)
        try:
            assert p.exists()
            assert p.suffix == ".scn"
            assert "CRE AC001" in p.read_text()
        finally:
            p.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# load_bluesky_scenario tests
# ---------------------------------------------------------------------------


class TestLoadBlueSkyScenario:
    def test_load_yaml_file(self, tmp_path: Path) -> None:
        f = tmp_path / "scenario.yaml"
        f.write_text(yaml.dump(FULL_SCENARIO_DATA))
        loaded = load_bluesky_scenario(f)
        assert loaded.name == "A1 Head-On Approach"

    def test_load_yml_extension(self, tmp_path: Path) -> None:
        f = tmp_path / "scenario.yml"
        f.write_text(yaml.dump(MINIMAL_SCENARIO_DATA))
        loaded = load_bluesky_scenario(f)
        assert loaded.name == "Test Scenario"

    def test_load_json_file(self, tmp_path: Path) -> None:
        f = tmp_path / "scenario.json"
        f.write_text(json.dumps(FULL_SCENARIO_DATA))
        loaded = load_bluesky_scenario(f)
        assert loaded.name == "A1 Head-On Approach"

    def test_unsupported_extension_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "scenario.txt"
        f.write_text("content")
        with pytest.raises(ValueError, match="Unsupported file extension"):
            load_bluesky_scenario(f)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_bluesky_scenario(tmp_path / "nonexistent.yaml")


# ---------------------------------------------------------------------------
# resolve_scn_path tests
# ---------------------------------------------------------------------------


class TestResolveScnPath:
    def test_scn_file_passthrough(self, tmp_path: Path) -> None:
        f = tmp_path / "scenario.scn"
        f.write_text("00:00:00.00>CRE AC001")
        path, is_temp = resolve_scn_path(str(f))
        assert path == str(f)
        assert is_temp is False

    def test_yaml_file_creates_temp_scn(self, tmp_path: Path) -> None:
        f = tmp_path / "scenario.yaml"
        f.write_text(yaml.dump(MINIMAL_SCENARIO_DATA))
        path, is_temp = resolve_scn_path(str(f))
        p = Path(path)
        try:
            assert p.suffix == ".scn"
            assert is_temp is True
            assert p.exists()
            assert "CRE AC001" in p.read_text()
        finally:
            p.unlink(missing_ok=True)

    def test_json_file_creates_temp_scn(self, tmp_path: Path) -> None:
        f = tmp_path / "scenario.json"
        f.write_text(json.dumps(MINIMAL_SCENARIO_DATA))
        path, is_temp = resolve_scn_path(str(f))
        p = Path(path)
        try:
            assert p.suffix == ".scn"
            assert is_temp is True
        finally:
            p.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Integration: round-trip YAML -> .scn for the bundled example files
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "yaml_path",
    [
        Path(__file__).parent.parent / "config" / "edmonton" / "bluesky_a1_head_on.yaml",
        Path(__file__).parent.parent / "config" / "edmonton" / "bluesky_b2_staggered.yaml",
    ],
    ids=["a1_head_on", "b2_staggered"],
)
def test_bundled_yaml_examples_round_trip(yaml_path: Path) -> None:
    """Ensure the bundled YAML example files parse and render without errors."""
    assert yaml_path.exists(), f"Example YAML file not found: {yaml_path}"
    scenario = load_bluesky_scenario(yaml_path)
    scn_text = scenario.to_scn()
    # At minimum, every aircraft callsign must appear in the rendered file
    for ac in scenario.aircraft:
        assert ac.callsign in scn_text
    assert "HOLD" in scn_text
