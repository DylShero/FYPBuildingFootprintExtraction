import json
from shapely.geometry import Polygon, shape, mapping

input_filename = "31310121.geojson"
output_filename = "convex_fixed.geojson"

with open(input_filename, "r") as f:
    geojson_obj = json.load(f)

valid_features = []
invalid_count = 0
converted_count = 0

for i, feature in enumerate(geojson_obj.get("features", [])):
    geometry = feature.get("geometry", {})
    if geometry.get("type") != "Polygon":
        print(f"Feature {i} skipped: not a Polygon.")
        invalid_count += 1
        continue

    try:
        # Convert to Shapely shape
        polygon = shape(geometry)

        if not polygon.is_valid:
            print(f"Feature {i} skipped: invalid polygon.")
            invalid_count += 1
            continue

        # Create convex hull
        convex = polygon.convex_hull

        # Convert back to GeoJSON format
        feature["geometry"] = mapping(convex)
        valid_features.append(feature)
        converted_count += 1

    except Exception as e:
        print(f"Feature {i} skipped due to error: {e}")
        invalid_count += 1

# Save new GeoJSON with convexified polygons
output_obj = {
    "type": "FeatureCollection",
    "features": valid_features
}

with open(output_filename, "w") as out:
    json.dump(output_obj, out, indent=2)

print(f"\n Convex hull conversion complete.")
print(f"{converted_count} features converted.")
print(f" {invalid_count} features skipped.")
print(f" Output written to: {output_filename}")