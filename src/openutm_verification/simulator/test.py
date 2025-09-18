import shapely
from pyproj import Geod, Proj, Transformer

if __name__ == "__main__":
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "coordinates": [
                        [
                            [7.471958949151656, 46.9799127188804],
                            [7.48377058671727, 46.9799127188804],
                            [7.48377058671727, 46.986538963424294],
                            [7.471958949151656, 46.986538963424294],
                            [7.471958949151656, 46.9799127188804],
                        ]
                    ],
                    "type": "Polygon",
                },
            }
        ],
    }
    # get the bounds fo the geojson
    polygon = shapely.geometry.shape(geojson["features"][0]["geometry"])
    bounds = polygon.bounds
    print(bounds)  # (minx, miny, maxx, maxy)
    minx, miny, maxx, maxy = bounds
    print(f"minx: {minx}, miny: {miny}, maxx: {maxx}, maxy: {maxy}")
    # get the diagonal length of the bounds in meters
    geod = Geod(ellps="WGS84")
    diagonal_length = geod.inv(minx, miny, maxx, maxy)[2]
    print(f"Diagonal length: {diagonal_length} meters")

    # compute the area in m2
    box = shapely.geometry.box(minx, miny, maxx, maxy)
    area = abs(geod.geometry_area_perimeter(box)[0])
    print(f"Area: {area} m²")

    # reduce the box so that the area is 250000 m2
    target_area = 250000  # 500m x 500m
    scale_factor = (target_area / area) ** 0.5
    print(f"Scale factor: {scale_factor}")
    center_x = (minx + maxx) / 2
    center_y = (miny + maxy) / 2
    width = (maxx - minx) * scale_factor
    height = (maxy - miny) * scale_factor
    minx = center_x - width / 2
    maxx = center_x + width / 2
    miny = center_y - height / 2
    maxy = center_y + height / 2
    print(f"New bounds: minx: {minx}, miny: {miny}, maxx: {maxx}, maxy: {maxy}")
    box = shapely.geometry.box(minx, miny, maxx, maxy)
    area = abs(geod.geometry_area_perimeter(box)[0])
    print(f"New area: {area} m²")
    diagonal_length = geod.inv(minx, miny, maxx, maxy)[2]
    print(f"New diagonal length: {diagonal_length} meters")
