import geopandas as gpd

# Load the layers
points_gdf = gpd.read_file(
    "data/NBI-Bridge-data-renamed.gpkg"
)
lines_gdf = gpd.read_file(
    "data/OSM-NBI-joined-layer.gpkg"
)
output_path = "data/nearest-point-to-way-ID.gpkg"

# Ensure the coordinate reference systems (CRS) match
if points_gdf.crs != lines_gdf.crs:
    lines_gdf = lines_gdf.to_crs(points_gdf.crs)

# Function to find the nearest point on a line
def nearest_point_on_line(point, line):
    return line.interpolate(line.project(point))

# Prepare a list to collect results
results = []

# Iterate through points
for _, point_row in points_gdf.iterrows():
    point = point_row.geometry
    bridge_id = point_row["BRIDGE_ID"]

    # Filter lines with the same BRIDGE_ID
    matching_lines = lines_gdf[lines_gdf["BRIDGE_ID"] == bridge_id]

    if matching_lines.empty:
        continue

    # Find the nearest point on the matching lines
    nearest_point = None
    min_dist = float("inf")

    for _, line_row in matching_lines.iterrows():
        line = line_row.geometry
        candidate_point = nearest_point_on_line(point, line)
        dist = point.distance(candidate_point)

        if dist < min_dist:
            min_dist = dist
            nearest_point = candidate_point

    print(line_row,line, bridge_id,nearest_point)

    # Collect the result
    if nearest_point:
        results.append({"geometry": nearest_point, "BRIDGE_ID": bridge_id})

# Create a GeoDataFrame from the results
results_gdf = gpd.GeoDataFrame(results, crs=points_gdf.crs)

# Save the results to a new GeoPackage
results_gdf.to_file(output_path, driver="GPKG", layer="nearest_points")

print("Processing complete. Output saved to:", output_path)
