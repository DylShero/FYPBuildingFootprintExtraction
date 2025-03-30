import json
import math
from shapely.geometry import Polygon, shape, LineString
from pyproj import Transformer

#Config

input_filename = "31310121.geojson"
output_res_filename = "letterkenny_test.res"
open_path_filename = "open_path.txt"

#Transformer to change from lon/lat to metres
transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)

#  Load and Process GeoJSON 

with open(input_filename, "r") as f:
    geojson_obj = json.load(f)

valid_features = []
building_polygons = []

invalid_count = 0
converted_count = 0

for i, feature in enumerate(geojson_obj.get("features", [])):
    geometry = feature.get("geometry", {})
    if geometry.get("type") != "Polygon":
        print(f"Feature {i} skipped: not a Polygon.")
        invalid_count += 1
        continue

    try:
        polygon = shape(geometry)
        if not polygon.is_valid:
            print(f"Feature {i} skipped: invalid polygon.")
            invalid_count += 1
            continue

        # Convert to convex hull
        convex = polygon.convex_hull
        coords = list(convex.exterior.coords)

        # Ensure closure
        if coords[0] != coords[-1]:
            coords.append(coords[0])

        # Update feature with convex geometry
        feature["geometry"] = {
            "type": "Polygon",
            "coordinates": [list(map(list, coords))]
        }

        valid_features.append(feature)
        building_polygons.append(convex)
        converted_count += 1

    except Exception as e:
        print(f"Feature {i} skipped due to error: {e}")
        invalid_count += 1

print(f"\n GeoJSON validation complete.")
print(f" {converted_count} convex polygons processed.")
print(f" {invalid_count} skipped due to errors.")

#Calculate Local Origin 

# Get bounding box for centre search
all_coords = [pt for poly in building_polygons for pt in poly.exterior.coords]
xs, ys = zip(*all_coords)
min_x, max_x = min(xs), max(xs)
min_y, max_y = min(ys), max(ys)
centre_point = ((min_x + max_x) / 2, (min_y + max_y) / 2)

# Convert centre_point (lon, lat) to metres for local origin offset
origin_x, origin_y = transformer.transform(centre_point[0], centre_point[1])

# Order Buildings by Distance from Origin

buildings_with_distance = []

for feature, polygon in zip(valid_features, building_polygons):
    centroid_lonlat = polygon.centroid.x, polygon.centroid.y
    centroid_x, centroid_y = transformer.transform(*centroid_lonlat)
    dx = centroid_x - origin_x
    dy = centroid_y - origin_y
    distance = math.hypot(dx, dy)
    buildings_with_distance.append((distance, feature, polygon))

# Sort by distance to origin
buildings_with_distance.sort(key=lambda x: x[0])

# Write Edges to .res File 

with open(output_res_filename, "w", encoding="utf-8") as res_file:
    

    total_edges = 0

    for building_number, (_, feature, polygon) in enumerate(buildings_with_distance, start=1):
        # Extract height
        height = feature.get("properties", {}).get("properties", {}).get("height", 1.0)
        coords = list(polygon.exterior.coords)

        # Convert coords to metres and offset by origin
        metre_coords = [
            (
                transformer.transform(x, y)[0] - origin_x,
                transformer.transform(x, y)[1] - origin_y
            )
            for x, y in coords
        ]

        num_edges = len(metre_coords)
        for j in range(num_edges - 1):
            x1, y1 = metre_coords[j]
            x2, y2 = metre_coords[j + 1]

            total_edges += 1
            res_file.write(f"{x1} {y1} {x2} {y2} {height} {building_number} 1 {total_edges}\n")

print(f" Edge data saved to: {output_res_filename}")

# Open Path Finder

def is_clear_path(start, end, buildings):
    path = LineString([start, end])
    return not any(path.intersects(b) for b in buildings)

def find_open_path(grid_spacing=1, min_length=1):
    search_radius = (max_x - min_x) / 3
    grid_start_x = centre_point[0] - search_radius
    grid_end_x = centre_point[0] + search_radius
    grid_start_y = centre_point[1] - search_radius
    grid_end_y = centre_point[1] + search_radius

    # Create grid points (1m spacing)
    x = grid_start_x
    while x < grid_end_x:
        y = grid_start_y
        while y < grid_end_y:
            directions = [
                (x + min_length, y),  # right
                (x, y + min_length),  # up
                (x - min_length, y),  # left
                (x, y - min_length)   # down
            ]
            for end in directions:
                if is_clear_path((x, y), end, building_polygons):
                    return (x, y), end
            y += grid_spacing
        x += grid_spacing

    return None, None

start, end = find_open_path()

if start and end:
    with open(open_path_filename, "w", encoding="utf-8") as f:
        f.write(f"Open path near centre (>=1m):\nStart: {start}\nEnd: {end}\n")
    print(f" Open path written to: {open_path_filename}")
    print(f"Start: {start}, End: {end}")
else:
    print(" No open path found after grid scan.")
