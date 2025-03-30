import pandas as pd
import geopandas as gpd
import json
import math
from shapely.geometry import Polygon, shape, LineString
from pyproj import Transformer

# Configuration

location = 'Ireland'
output_res_filename = "output_edges.res"
open_path_filename = "open_path.txt"
max_files = 5  # Set the maximum number of GeoJSON files to generate

transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)

#  Download GeoJSON 

def download_geojson(location, max_files=None):
    dataset_links = pd.read_csv("https://minedbuildings.z5.web.core.windows.net/global-buildings/dataset-links.csv")
    location_links = dataset_links[dataset_links.Location == location]
    geojson_files = []

    for i, (_, row) in enumerate(location_links.iterrows()):
        if max_files is not None and i >= max_files:
            break
        df = pd.read_json(row.Url, lines=True)
        df['geometry'] = df['geometry'].apply(shape)
        gdf = gpd.GeoDataFrame(df, crs=4326)
        filename = f"{row.QuadKey}.geojson"
        gdf.to_file(filename, driver="GeoJSON")
        geojson_files.append(filename)

    return geojson_files

# Process GeoJSON

def process_geojson(file):
    with open(file, "r") as f:
        geojson_obj = json.load(f)

    valid_features = []
    building_polygons = []

    for i, feature in enumerate(geojson_obj.get("features", [])):
        geometry = feature.get("geometry", {})
        if geometry.get("type") != "Polygon":
            continue

        polygon = shape(geometry)
        if not polygon.is_valid:
            continue

        convex = polygon.convex_hull
        coords = list(convex.exterior.coords)
        if coords[0] != coords[-1]:
            coords.append(coords[0])

        feature["geometry"] = {
            "type": "Polygon",
            "coordinates": [list(map(list, coords))]
        }

        valid_features.append(feature)
        building_polygons.append(convex)

    return valid_features, building_polygons

# Calculate Edges and Origin

def calculate_edges(valid_features, building_polygons, output_filename):
    all_coords = [pt for poly in building_polygons for pt in poly.exterior.coords]
    xs, ys = zip(*all_coords)
    centre_point = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    origin_x, origin_y = transformer.transform(*centre_point)

    buildings_with_distance = []

    for feature, polygon in zip(valid_features, building_polygons):
        centroid_x, centroid_y = transformer.transform(polygon.centroid.x, polygon.centroid.y)
        distance = math.hypot(centroid_x - origin_x, centroid_y - origin_y)
        buildings_with_distance.append((distance, feature, polygon))

    buildings_with_distance.sort(key=lambda x: x[0])

    with open(output_filename, "w", encoding="utf-8") as res_file:
        total_edges = 0

        for building_number, (_, feature, polygon) in enumerate(buildings_with_distance, start=1):
            height = feature.get("properties", {}).get("properties", {}).get("height", 1.0)
            coords = list(polygon.exterior.coords)

            metre_coords = [
                (
                    transformer.transform(x, y)[0] - origin_x,
                    transformer.transform(x, y)[1] - origin_y
                )
                for x, y in coords
            ]

            for j in range(len(metre_coords) - 1):
                x1, y1 = metre_coords[j]
                x2, y2 = metre_coords[j + 1]
                total_edges += 1
                res_file.write(f"{x1} {y1} {x2} {y2} {height} {building_number} 1 {total_edges}\n")

#  Main Execution 

def main():
    geojson_files = download_geojson(location, max_files=max_files)

    all_valid_features = []
    all_building_polygons = []

    for file in geojson_files:
        valid_features, building_polygons = process_geojson(file)
        all_valid_features.extend(valid_features)
        all_building_polygons.extend(building_polygons)

    calculate_edges(all_valid_features, all_building_polygons, output_res_filename)

if __name__ == "__main__":
    main()
