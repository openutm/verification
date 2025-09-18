from dataclasses import dataclass


@dataclass
class DefaultScenarioData:
    "Default data for Bern, using them minx, miny, maxx, maxy to define the bounding box that is the flight declaration geojson and use the geojson to generate the flight tracks using the GeoJSON simulator."

    minx: float = 7.488001888664087
    miny: float = 46.98348913137784
    maxx: float = 7.49349250821345
    maxy: float = 46.98687385609128
    f1_flow_flight_track_geojson: dict = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "coordinates": [
                        [7.489374543551406, 46.983606185954244],
                        [7.489303051109118, 46.98410366504382],
                        [7.491447824371534, 46.986210583981915],
                    ],
                    "type": "LineString",
                },
            }
        ],
    }
    f2_flow_flight_track_geojson: dict = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "coordinates": [
                        [7.489946483087635, 46.98364520408907],
                        [7.489946483087635, 46.984298753619186],
                        [7.4893316480862495, 46.98490352367844],
                    ],
                    "type": "LineString",
                },
            }
        ],
    }
    f3_flow_flight_track_geojson: dict = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "coordinates": [
                        [7.493120747515036, 46.98368422219579],
                        [7.4930778520499075, 46.98423047269873],
                        [7.493749881005499, 46.984874260768606],
                        [7.493964358331311, 46.98506934653176],
                        [7.4943790144949105, 46.98533271118271],
                    ],
                    "type": "LineString",
                },
            }
        ],
    }
    f4_flow_flight_track_geojson: dict = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "coordinates": [
                        [7.493220836934455, 46.98377201283182],
                        [7.493163642980221, 46.984220718274315],
                        [7.493621194610029, 46.984493841482504],
                        [7.4943075220537025, 46.98490352367844],
                        [7.494121641703913, 46.98544976172238],
                        [7.493792776470684, 46.9857228786513],
                        [7.4930349565846655, 46.98585943659248],
                        [7.492463017048493, 46.98592771543221],
                    ],
                    "type": "LineString",
                },
            }
        ],
    }
    f5_flow_flight_track_geojson: dict = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "coordinates": [
                        [7.492491614025596, 46.98367446767202],
                        [7.492806180769776, 46.98411341948963],
                        [7.493292329375663, 46.984347525651884],
                        [7.493892865889023, 46.98458163078902],
                        [7.4947650736824585, 46.984952295159445],
                        [7.495451401126132, 46.98517664339812],
                        [7.4957802663593895, 46.985313202734716],
                    ],
                    "type": "LineString",
                },
            }
        ],
    }
