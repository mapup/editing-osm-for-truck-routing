import csv
import json
import logging
from multiprocessing import Pool, cpu_count

import pyproj
from shapely.geometry import LineString, Point
from shapely.ops import nearest_points, transform


def setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler("debug.log"), logging.StreamHandler()],
    )


def load_geojson(file_path):
    with open(file_path, "r") as f:
        data = json.load(f)
    return data


def load_csv(file_path):
    bridge_data = []
    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row_number, row in enumerate(reader, start=1):
            osm_id = row["final_osm_id"]
            bridge_id = row["STRUCTURE_NUMBER_008"]
            bridge_length = float(row["bridge_length"])
            bridge_coordinate = (float(row["final_lat"]), float(row["final_long"]))
            bridge_data.append(
                {
                    "index": row_number,
                    "osm_id": osm_id,
                    "bridge_id": bridge_id,
                    "bridge_length": bridge_length,
                    "bridge_coordinate": bridge_coordinate,
                }
            )
    return bridge_data


def find_nearest_point_on_line(line, point):
    nearest_geoms = nearest_points(line, point)
    return nearest_geoms[0]


def find_way_id_for_point(point, all_lines_with_ids):
    for line, way_id in all_lines_with_ids:
        if line.distance(point) < 1e-6:
            return way_id
    return None


def calculate_points_on_way(line, nearest_point, half_distance, all_lines_with_ids):
    nearest_distance = line.project(nearest_point)
    forward_distance = nearest_distance + half_distance
    backward_distance = nearest_distance - half_distance

    forward_point = (
        line.interpolate(forward_distance) if forward_distance <= line.length else None
    )
    backward_point = (
        line.interpolate(backward_distance) if backward_distance >= 0 else None
    )

    forward_way_id = None
    backward_way_id = None

    if forward_point is None:
        forward_point, forward_way_id = extend_along_connected_way(
            line, forward_distance - line.length, all_lines_with_ids
        )
    else:
        forward_way_id = find_way_id_for_point(forward_point, all_lines_with_ids)

    if backward_point is None:
        backward_point, backward_way_id = extend_along_connected_way(
            line, -backward_distance, all_lines_with_ids, reverse=True
        )
    else:
        backward_way_id = find_way_id_for_point(backward_point, all_lines_with_ids)

    return forward_point, forward_way_id, backward_point, backward_way_id


def extend_along_connected_way(
    current_line, remaining_distance, all_lines_with_ids, reverse=False, visited=None
):
    if visited is None:
        visited = set()

    start_or_end = 0 if reverse else -1
    print("start_or_end",start_or_end)
    connection_point = Point(current_line.coords[start_or_end])
    current_line_way_id = None
    possible_next_lines = []

    for line, way_id in all_lines_with_ids:
        if line.equals(current_line):
            print("visited",visited)
            current_line_way_id = way_id
            print("current_line_way_id",current_line_way_id)
            continue
        if way_id in visited:
            continue
        if connection_point.equals(Point(line.coords[0])) or connection_point.equals(Point(line.coords[-1])):
            possible_next_lines.append((line, way_id))

    if len(possible_next_lines) > 1:
        print(f"Split detected at point {connection_point}. Stopping.")
        #find the way_id of the current line
        print("returning1", current_line_way_id)
        return None, current_line_way_id

    if len(possible_next_lines) == 1:
        next_line, way_id = possible_next_lines[0]
        if remaining_distance <= next_line.length:
            next_point = next_line.interpolate(remaining_distance)
            print("returning2", way_id)
            return next_point, way_id
        else:
            visited.add(way_id)
            return_point, return_wayid =extend_along_connected_way(
                next_line, 
                remaining_distance - next_line.length, 
                all_lines_with_ids, 
                reverse, 
                visited
            )
            print("returning3", return_wayid)
            return return_point, return_wayid

    print(f"No connected line found at point {connection_point}. Stopping.")
    return None, current_line_way_id
def process_single_bridge(bridge, lines_utm_with_ids, project, inverse_project):
    try:
        print(f"{bridge['index']}/6599")
        osm_id = bridge["osm_id"]
        bridge_length = bridge["bridge_length"]
        input_coordinate = bridge["bridge_coordinate"]
        half_distance = bridge_length / 2

        point = Point(input_coordinate)
        point_utm = transform(project, point)

        for line_utm, way_id in lines_utm_with_ids:
            if way_id != osm_id:
                continue

            nearest_point_utm = find_nearest_point_on_line(line_utm, point_utm)
            if line_utm.distance(point_utm) < 1:
                (
                    forward_point_utm,
                    forward_way_id,
                    backward_point_utm,
                    backward_way_id,
                ) = calculate_points_on_way(
                    line_utm, nearest_point_utm, half_distance, lines_utm_with_ids
                )
                
                # Initialize forward and backward points
                forward_point = Point(-1, -1)
                backward_point = Point(-1, -1)
                if forward_point_utm is not None:
                    forward_point = transform(inverse_project, forward_point_utm)
                if backward_point_utm is not None:
                    backward_point = transform(inverse_project, backward_point_utm)

                print ("aaa",forward_way_id, backward_way_id)
                result = {
                    "original_osm_id": osm_id,
                    "bridge_length": bridge_length,
                    "bridge_coordinate": input_coordinate,
                    "input_coordinate": input_coordinate,
                    "nearest_point": (nearest_point_utm.x, nearest_point_utm.y),
                    "forward_point": (forward_point.x, forward_point.y),
                    "backward_point": (backward_point.x, backward_point.y),
                    "forward_way_id": forward_way_id if forward_way_id is not None else -1,
                    "backward_way_id": backward_way_id if backward_way_id is not None else -1,
                    "actual_forward_distance": point_utm.distance(forward_point_utm),
                    "actual_backward_distance": point_utm.distance(backward_point_utm),
                }

                # Write the result immediately to the CSV file
                with open("bridge-osm-association-with-split-coords.csv", "a", encoding="utf-8-sig") as rf:
                    writer = csv.writer(rf)
                    writer.writerow(
                        [
                            result["original_osm_id"],
                            result["bridge_coordinate"],
                            result["bridge_length"],
                            result["forward_point"][1],
                            result["forward_point"][0],
                            result["forward_way_id"],
                            result["backward_point"][1],
                            result["backward_point"][0],
                            result["backward_way_id"],
                        ]
                    )

                return result
    except Exception as e:
        logging.error(f"Error processing bridge {bridge['osm_id']}: {e}")
    return None

def process_bridge_data_parallel(bridge_data, lines_with_ids, project, inverse_project):
    lines_utm_with_ids = [
        (transform(project, line), way_id) for way_id, line in lines_with_ids.items()
    ]
    pool = Pool(cpu_count())
    results = pool.starmap(
        process_single_bridge,
        [
            (bridge, lines_utm_with_ids, project, inverse_project)
            for bridge in bridge_data
        ],
    )
    pool.close()
    pool.join()
    return [result for result in results if result is not None]


def main():
    setup_logging()
    logging.info("Starting processing...")

    try:
        # Load the GeoJSON file
        geojson_file_path = (
            "/Users/tanishqsharma/Downloads/kentucky-multi-bridge.geojson"
        )
        geojson_data = load_geojson(geojson_file_path)
        print("Reading OSM data completed......!")

        # Load the CSV file containing bridge data
        csv_file_path = (
            "/Users/tanishqsharma/Downloads/bridge-osm-association-with-lengths (1).csv"
        )
        bridge_data = load_csv(csv_file_path)
        print("Reading bridge data completed......!")

        lines_with_ids = {
            feature["properties"]["osm_id"]: LineString(
                feature["geometry"]["coordinates"]
            )
            for feature in geojson_data["features"]
        }
        print("Consolidated lines with IDs......!")
        # Define projection transformations
        wgs84 = pyproj.CRS("EPSG:4326")
        utm_zone = pyproj.CRS("EPSG:32616")  # UTM zone for your input coordinates
        project = pyproj.Transformer.from_crs(wgs84, utm_zone, always_xy=True).transform
        inverse_project = pyproj.Transformer.from_crs(
            utm_zone, wgs84, always_xy=True
        ).transform

        # Initialize the results CSV file with headers
        with open(
            "bridge-osm-association-with-split-coords.csv", "w", encoding="utf-8-sig"
        ) as rf:
            writer = csv.writer(rf)
            writer.writerow(
                [
                    "osm_id",
                    "bridge_coordinate",
                    "bridge_length",
                    "first_split_point_lat",
                    "first_split_point_lon",
                    "osm_id_for_first_split_point",
                    "second_split_point_lat",
                    "second_split_point_lon",
                    "osm_id_for_second_split_point",
                ]
            )

        # Process each bridge entry in parallel
        process_bridge_data_parallel(
            bridge_data, lines_with_ids, project, inverse_project
        )

        logging.info("Processing completed successfully.")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")


if __name__ == "__main__":
    main()
