from implicitdict import ImplicitDict, StringBasedDateTime
from pydantic import BaseModel, Field
from uas_standards.astm.f3411.v22a.api import RIDAircraftState, RIDFlightDetails

DEFAULT_REFERENCE_TIME = "2022-01-01T00:00:00Z"


class FlightObservationSchema(BaseModel):
    lat_dd: float
    lon_dd: float
    altitude_mm: float
    traffic_source: int
    source_type: int
    icao_address: str
    timestamp: int
    metadata: dict = Field(default_factory=dict)


class FullFlightRecord(ImplicitDict):
    reference_time: StringBasedDateTime
    """The reference time of this flight (usually the time of first telemetry)"""

    states: list[RIDAircraftState]
    """All telemetry that will be/was received for this flight"""

    flight_details: RIDFlightDetails
    """Details of this flight, as would be reported at the ASTM /details endpoint"""

    aircraft_type: str
    """Type of aircraft, as per RIDFlight.aircraft_type"""


class FlightRecordCollection(ImplicitDict):
    flights: list[FullFlightRecord]


class AdjacentCircularFlightsSimulatorConfiguration(ImplicitDict):
    reference_time: StringBasedDateTime = StringBasedDateTime(DEFAULT_REFERENCE_TIME)
    """The reference time relative to which flight data should be generated.

    The time should be irrelevant in real-world use as times are adjusted to be
    relative to a time close to the time of test.
    """

    random_seed: int | None = 12345
    """Pseudorandom seed that should be used, or specify None to use default Random."""

    minx: float = 7.4735784530639648
    """Western edge of bounding box (degrees longitude)"""

    miny: float = 46.9746744128218410
    """Southern edge of bounding box (degrees latitude)"""

    maxx: float = 7.4786210060119620
    """Eastern edge of bounding box (degrees longitude)"""

    maxy: float = 46.9776318195799121
    """Northern edge of bounding box (degrees latitude)"""

    utm_zone: int = 32
    """UTM Zone integer for the location, see https://en.wikipedia.org/wiki/Universal_Transverse_Mercator_coordinate_system
     to identify the zone for the location."""

    altitude_of_ground_level_wgs_84 = 570
    """Height of the geoid above the WGS84 ellipsoid (using EGM 96) for Bern, rom https://geographiclib.sourceforge.io/cgi-bin/GeoidEval?input=46%B056%26%238242%3B53%26%238243%3BN+7%B026%26%238242%3B51%26%238243%3BE&option=Submit"""

    flight_start_shift: int = 0
    """Delay generated flight starts from the reference time to spread flights over time. Expressed in seconds. Use 0 to disable."""


class GeoJSONFlightsSimulatorConfiguration(ImplicitDict):
    reference_time: StringBasedDateTime = StringBasedDateTime(DEFAULT_REFERENCE_TIME)
    """The reference time relative to which flight data should be generated.

    The time should be irrelevant in real-world use as times are adjusted to be
    relative to a time close to the time of test.
    """

    random_seed: int | None = 12345
    """Pseudorandom seed that should be used, or specify None to use default Random."""
    geojson: dict
    utm_zone: int = 32
    """UTM Zone integer for the location, see https://en.wikipedia.org/wiki/Universal_Transverse_Mercator_coordinate_system
     to identify the zone for the location."""

    altitude_of_ground_level_wgs_84 = 570
    """Height of the geoid above the WGS84 ellipsoid (using EGM 96) for Bern, rom https://geographiclib.sourceforge.io/cgi-bin/GeoidEval?input=46%B056%26%238242%3B53%26%238243%3BN+7%B026%26%238242%3B51%26%238243%3BE&option=Submit"""

    flight_start_shift: int = 0
    """Delay generated flight starts from the reference time to spread flights over time. Expressed in seconds. Use 0 to disable."""


class AirTrafficGeneratorConfiguration(ImplicitDict):
    reference_time: StringBasedDateTime = StringBasedDateTime(DEFAULT_REFERENCE_TIME)
    """The reference time relative to which flight data should be generated.

    The time should be irrelevant in real-world use as times are adjusted to be
    relative to a time close to the time of test.
    """

    random_seed: int | None = 12345
    """Pseudorandom seed that should be used, or specify None to use default Random."""
    geojson: dict
    utm_zone: int = 32
    """UTM Zone integer for the location, see https://en.wikipedia.org/wiki/Universal_Transverse_Mercator_coordinate_system
    to identify the zone for the location."""

    altitude_of_ground_level_wgs_84 = 570
    """Height of the geoid above the WGS84 ellipsoid (using EGM 96) for Bern, rom https://geographiclib.sourceforge.io/cgi-bin/GeoidEval?input=46%B056%26%238242%3B53%26%238243%3BN+7%B026%26%238242%3B51%26%238243%3BE&option=Submit"""

    flight_start_shift: int = 0
    """Delay generated flight starts from the reference time to spread flights over time. Expressed in seconds. Use 0 to disable."""
