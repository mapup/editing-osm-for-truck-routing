import geojson
from shapely.geometry import LineString, Point
from shapely.ops import nearest_points, transform
import pyproj
import pandas as pd
from utils import csv_to_nested_dict

# Function to load GeoJSON data from a file
def load_geojson(file_path):
    with open(file_path, 'r') as f:
        data = geojson.load(f)
    return data

# Function to find the nearest point on a line to a given point
def find_nearest_point_on_line(line, point):
    nearest_geoms = nearest_points(line, point)
    return nearest_geoms[0]

# Function to calculate forward and backward points on the line from the nearest point
def calculate_points_on_way(line, nearest_point, distance):
    nearest_distance = line.project(nearest_point)
    forward_distance = nearest_distance + distance
    backward_distance = nearest_distance - distance
    forward_point = line.interpolate(forward_distance)
    backward_point = line.interpolate(backward_distance)
    return forward_point, backward_point

# Function to process multiple input coordinates
def process_input_coordinates(input_coordinates, line, distance, project, inverse_project):
    results = []
    line_utm = transform(project, line)  # Transform the line to UTM
    for input_coordinate in input_coordinates:
        point = Point(input_coordinate[0])  # Create a point from input coordinate
        point_utm = transform(project, point)  # Transform the point to UTM
        specific_dist = input_coordinate[1]  # Specific distance for this input coordinate
        
        # Find the nearest point on the line
        nearest_point_utm = find_nearest_point_on_line(line_utm, point_utm)
        
        # Calculate forward and backward points
        forward_point_utm, backward_point_utm = calculate_points_on_way(line_utm, nearest_point_utm, specific_dist)
        forward_point = transform(inverse_project, forward_point_utm)  # Transform forward point back to WGS84
        backward_point = transform(inverse_project, backward_point_utm)  # Transform backward point back to WGS84
        
        # Append results
        results.append({
            "input_coordinate": input_coordinate,
            "nearest_point": (nearest_point_utm.x, nearest_point_utm.y),
            "forward_point": (forward_point.x, forward_point.y),
            "backward_point": (backward_point.x, backward_point.y),
            "actual_forward_distance": point_utm.distance(forward_point_utm),
            "actual_backward_distance": point_utm.distance(backward_point_utm)
        })
    return results

# Function to get split points for a given input coordinate and bridge length
def get_split_points(input_coordinates, bridge_length):
    # Load the GeoJSON file
    geojson_file_path = '/Users/nitinkhandagale/Desktop/test-2.geojson'
    geojson_data = load_geojson(geojson_file_path)
    
    # Assuming the GeoJSON contains a LineString under 'geometry'
    line_coords = geojson_data['features'][0]['geometry']['coordinates']
    line = LineString(line_coords)

    split_distance = bridge_length / 2  # Calculate split distance as half the bridge length
    
    # List of input coordinates with their specific distances
    bridge_location = [
        [input_coordinates, split_distance]  # Add the input coordinate and split distance
    ]
    
    # Define projection transformations
    wgs84 = pyproj.CRS('EPSG:4326')
    utm_zone = pyproj.CRS('EPSG:32616')  # UTM zone for your input coordinates
    project = pyproj.Transformer.from_crs(wgs84, utm_zone, always_xy=True).transform
    inverse_project = pyproj.Transformer.from_crs(utm_zone, wgs84, always_xy=True).transform
    
    # Process each input coordinate
    results = process_input_coordinates(bridge_location, line, split_distance, project, inverse_project)

    # Save results to CSV
    df = pd.DataFrame(results)
    df.to_csv("bridge_splits.csv", index=False)
    
    # Collect and print the split points
    splits = []
    for result in results:
        splits.append(list(result["forward_point"]))
        splits.append(list(result["backward_point"]))

    return splits


# Define input coordinates and bridge length
input_coordinates = (-85.9069943619548, 36.9879919499241)
bridge_length = 20 # In meters

# Get the split points
split_point_coordinates = get_split_points(input_coordinates=input_coordinates, 
                 bridge_length=bridge_length)

# Print the split point coordinates
print(split_point_coordinates)

