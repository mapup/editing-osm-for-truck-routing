from org.openstreetmap.josm.data.osm import *
from org.openstreetmap.josm.data.coor import LatLon
from org.openstreetmap.josm.data.osm import Node, Way, OsmPrimitiveType, RelationMember
from org.openstreetmap.josm.gui import MainApplication
from java.util import ArrayList
from javax.swing import JOptionPane
import math
# Function to calculate the distance from a point to a line segment
def distance_to_segment(point, start, end):
    # Round coordinates to ensure consistent precision
    x, y = point.lon(), point.lat()
    x1, y1 = start.lon(), start.lat()
    x2, y2 = end.lon(), end.lat()

    # Calculate vector components
    dx, dy = x2 - x1, y2 - y1
    dx_point, dy_point = x - x1, y - y1

    # Handle cases where the segment has zero length
    if dx == dy == 0:
        return math.sqrt(dx_point ** 2 + dy_point ** 2)

    # Calculate parametric value
    param = (dx_point * dx + dy_point * dy) / (dx * dx + dy * dy)

    # Clamp parametric value to segment bounds
    param = max(0, min(1, param))

    # Calculate nearest point on the segment
    xx = x1 + param * dx
    yy = y1 + param * dy

    # Calculate distance between point and nearest point on the segment
    dx_nearest, dy_nearest = x - xx, y - yy
    distance = math.sqrt(dx_nearest ** 2 + dy_nearest ** 2)

    return distance

# Function to interpolate a point given a start point, direction, and distance
def interpolate_point(start, end, distance):
    segment_length = start.greatCircleDistance(end)
    factor = distance / segment_length

    lat1 = math.radians(start.lat())
    lon1 = math.radians(start.lon())
    lat2 = math.radians(end.lat())
    lon2 = math.radians(end.lon())

    d = segment_length / 6371000  # Earth's radius in meters
    a = math.sin((1 - factor) * d) / math.sin(d)
    b = math.sin(factor * d) / math.sin(d)
    
    x = a * math.cos(lat1) * math.cos(lon1) + b * math.cos(lat2) * math.cos(lon2)
    y = a * math.cos(lat1) * math.sin(lon1) + b * math.cos(lat2) * math.sin(lon2)
    z = a * math.sin(lat1) + b * math.sin(lat2)
    
    lat = math.atan2(z, math.sqrt(x * x + y * y))
    lon = math.atan2(y, x)
    
    return LatLon(math.degrees(lat), math.degrees(lon))
# Function to find the index of the closest node in a way to a given coordinate
def find_closest_node(way, coord):
    min_distance = float('inf')
    closest_node_index = -1
    
    for i in range(len(way.nodes)):
        node = way.getNode(i)
        distance = coord.greatCircleDistance(node.getCoor())
        if distance < min_distance:
            min_distance = distance
            closest_node_index = i
    return closest_node_index
# Function to process a bridge point on a way and create new nodes for the bridge
def process_bridge_point(way, coord, bridge_length):
    closest_node_index = find_closest_node(way, coord)
    if closest_node_index == -1:
        print("No nodes found in the way.")
        return None

    segments = []
    if closest_node_index > 0:
        segments.append((closest_node_index - 1, closest_node_index))
    if closest_node_index < len(way.nodes) - 1:
        segments.append((closest_node_index, closest_node_index + 1))

    best_segment = None
    min_distance = float('inf')

    for (start_idx, end_idx) in segments:
        segment_start = way.getNode(start_idx).getCoor()
        segment_end = way.getNode(end_idx).getCoor()
        distance = distance_to_segment(coord, segment_start, segment_end)
        
        if distance < min_distance:
            min_distance = distance
            best_segment = (start_idx, end_idx)

    if best_segment is None:
        print("No valid segment found.")
        return None

    half_bridge_length = bridge_length / 2

    start_segment_index = best_segment[0]
    segment_start = way.getNode(start_segment_index).getCoor()
    segment_end = way.getNode(start_segment_index + 1).getCoor()
    distance_to_start = coord.greatCircleDistance(segment_start)

    while distance_to_start < half_bridge_length and start_segment_index > 0:
        half_bridge_length -= distance_to_start
        start_segment_index -= 1
        segment_start = way.getNode(start_segment_index).getCoor()
        segment_end = way.getNode(start_segment_index + 1).getCoor()
        distance_to_start = segment_start.greatCircleDistance(segment_end)

    if start_segment_index == best_segment[0]:
        interpolated_start = interpolate_point(coord, segment_start, half_bridge_length)
    else:
        interpolated_start = interpolate_point(segment_end, segment_start, half_bridge_length)

    half_bridge_length = bridge_length / 2

    end_segment_index = best_segment[1]
    segment_start = way.getNode(end_segment_index - 1).getCoor()
    segment_end = way.getNode(end_segment_index).getCoor()
    distance_to_end = coord.greatCircleDistance(segment_end)

    while distance_to_end < half_bridge_length and end_segment_index < len(way.nodes) - 2:
        half_bridge_length -= distance_to_end
        end_segment_index += 1
        segment_start = way.getNode(end_segment_index - 1).getCoor()
        segment_end = way.getNode(end_segment_index).getCoor()
        distance_to_end = segment_start.greatCircleDistance(segment_end)

    if end_segment_index == best_segment[1]:
        interpolated_end = interpolate_point(coord, segment_end, half_bridge_length)
    else:
        interpolated_end = interpolate_point(segment_start, segment_end, half_bridge_length)

    new_node_start = Node(interpolated_start)
    new_node_end = Node(interpolated_end)

    return (new_node_start, new_node_end, start_segment_index, end_segment_index)

# Updating all the relations which are related to old_way
def update_relation_membership(data_set, old_way, new_ways):
    for relation in data_set.getRelations():
        if old_way in [member.getMember() for member in relation.getMembers()]:
            new_members = []
            for member in relation.getMembers():
                if member.getMember() == old_way:
                    for new_way in new_ways:
                        new_members.append(RelationMember(member.getRole(), new_way))
                else:
                    new_members.append(member)
            relation.setMembers(new_members)
            relation.setModified(True)

# Access the active data layer
layer = MainApplication.getLayerManager().getEditLayer()
if layer is None:
    print("No active data layer found.")
    exit()

data_set = layer.getDataSet()
# List of way IDs and bridge points (coordinate and length)
bridgedata = [(108707726, [(LatLon(36.9905395374629, -85.9021257060234), 30.2)]), (16082992, [(LatLon(36.9879919499241, -85.9069943619548), 23.2)])]

for way_id, bridge_points in bridgedata:
    way = data_set.getPrimitiveById(way_id, OsmPrimitiveType.WAY)
    if way is None:
        print("Way not found.")
        exit()

    all_segments = []
    way_nodes = ArrayList(way.nodes)

    # Sort bridge points based on their position along the way
    sorted_bridge_points = sorted(bridge_points, key=lambda bp: find_closest_node(way, bp[0]))

    for coord, bridge_length in sorted_bridge_points:
        bridge_result = process_bridge_point(way, coord, bridge_length)
        if bridge_result is None:
            continue
    
        new_node_start, new_node_end, start_segment_index, end_segment_index = bridge_result
    
        data_set.addPrimitive(new_node_start)
        data_set.addPrimitive(new_node_end)
    
        start_index = way_nodes.indexOf(way.getNode(start_segment_index)) + 1
        end_index = way_nodes.indexOf(way.getNode(end_segment_index)) + 1
    
        way_nodes.add(start_index, new_node_start)
        way_nodes.add(end_index, new_node_end)
    
        all_segments.append((start_index, end_index, new_node_start, new_node_end))

    new_ways = []
    previous_end_index = 0

    for start_index, end_index, new_node_start, new_node_end in all_segments:
        part1_nodes = way_nodes.subList(previous_end_index, start_index + 1)
        part2_nodes = way_nodes.subList(start_index, end_index + 1)
        previous_end_index = end_index
    
        part1 = Way()
        part1.setNodes(part1_nodes)
        new_ways.append(part1)
    
        part2 = Way()
        part2.setNodes(part2_nodes)
        part2.put("bridge", "yes")
        part2.put("layer", "1")
        new_ways.append(part2)

    if previous_end_index < len(way_nodes):
        part3_nodes = way_nodes.subList(previous_end_index, len(way_nodes))
        part3 = Way()
        part3.setNodes(part3_nodes)
        new_ways.append(part3)

    for tag in way.getKeys().keySet():
        for new_way in new_ways:
            new_way.put(tag, way.get(tag))

    for new_way in new_ways:
        data_set.addPrimitive(new_way)

    update_relation_membership(data_set, way, new_ways)

    way.setDeleted(True)
