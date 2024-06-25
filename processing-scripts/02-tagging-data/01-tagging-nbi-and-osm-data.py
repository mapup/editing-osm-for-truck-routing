import csv
import sys

from qgis.analysis import QgsNativeAlgorithms
from qgis.core import (
    QgsApplication,
    QgsProcessingFeedback,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)

# Initialize QGIS application
QgsApplication.setPrefixPath("/Applications/QGIS-LTR.app/Contents/MacOS", True)
qgs = QgsApplication([], False)
qgs.initQgis()

# Add QGIS plugin path
sys.path.append("/Applications/QGIS-LTR.app/Contents/Resources/python/plugins")

import processing
from processing.core.Processing import Processing

# Initialize QGIS processing
Processing.initialize()
QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
feedback = QgsProcessingFeedback()


def create_buffer(vector_layer, radius):
    """
    Create a buffer around a vector layer
    """
    buffered = processing.run(
        "native:buffer",
        {
            "DISSOLVE": False,
            "DISTANCE": radius,
            "END_CAP_STYLE": 0,
            "INPUT": vector_layer,
            "JOIN_STYLE": 0,
            "MITER_LIMIT": 2,
            "OUTPUT": "memory:",
            "SEGMENTS": 5,
        },
    )["OUTPUT"]
    return buffered


def filter_osm_data(vector_layer, filter_expression):
    """
    Apply a filter expression to a vector layer
    """
    vector_layer.setSubsetString(filter_expression)
    return vector_layer


def explode_osm_data(vector_layer):
    """
    Explode the 'other_tags' field in OSM data
    """
    exploded = processing.run(
        "native:explodehstorefield",
        {
            "EXPECTED_FIELDS": "",
            "FIELD": "other_tags",
            "INPUT": vector_layer,
            "OUTPUT": "memory:",
        },
    )["OUTPUT"]
    return exploded


def join_by_location(input_layer, join_layer, join_fields):
    """
    Join attributes by location
    """
    joined_layer = processing.run(
        "native:joinattributesbylocation",
        {
            "DISCARD_NONMATCHING": False,
            "INPUT": input_layer,
            "JOIN": join_layer,
            "JOIN_FIELDS": join_fields,
            "METHOD": 0,
            "OUTPUT": "memory:",
            "PREDICATE": [0, 1, 3, 4, 6],
            "PREFIX": "",
        },
    )["OUTPUT"]
    return joined_layer


def vl_to_csv_filter(vector_layer, csv_path, keep_fields):
    """
    Export vector layer to CSV with selected columns
    """
    fields = vector_layer.fields()
    with open(csv_path, mode="w", newline="", encoding="utf-8") as file:
        csv_writer = csv.writer(file)
        header = [field.name() for field in fields if field.name() in keep_fields]
        csv_writer.writerow(header)
        for feature in vector_layer.getFeatures():
            row = [
                feature[field.name()] for field in fields if field.name() in keep_fields
            ]
            csv_writer.writerow(row)


def vl_to_csv(vector_layer, csv_path):
    """
    Export vector layer to CSV with WKT geometry column
    """
    QgsVectorFileWriter.writeAsVectorFormat(
        vector_layer,
        csv_path,
        "utf-8",
        vector_layer.crs(),
        "CSV",
        layerOptions=["GEOMETRY=AS_WKT"],
    )


def get_nearby_bridge_ids_from_csv(csv_file_path):
    """
    Extract nearby bridge IDs from CSV file
    """
    nearby_bridge_ids = []

    with open(csv_file_path, mode="r") as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            if row["STRUCTURE_NUMBER_008"] != row["STRUCTURE_NUMBER_008_2"]:
                nearby_bridge_ids.append(row["STRUCTURE_NUMBER_008"])
                nearby_bridge_ids.append(row["STRUCTURE_NUMBER_008_2"])
    nearby_bridge_ids = list(set(nearby_bridge_ids))

    return nearby_bridge_ids


def get_bridge_ids_from_csv(csv_file_path):
    """
    Extract bridge IDs from CSV file
    """
    bridge_ids = []
    with open(csv_file_path, mode="r") as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            bridge_id = row["STRUCTURE_NUMBER_008"]
            if bridge_id:
                bridge_ids.append(bridge_id)
    return bridge_ids


def filter_nbi_layer(vector_layer, exclusion_ids):
    """
    Filter NBI layer by excluding certain IDs
    """
    # Create a memory layer to store filtered features
    filtered_layer = QgsVectorLayer("Point?crs=EPSG:4326", "filtered_layer", "memory")
    provider = filtered_layer.dataProvider()

    # Add fields from the original layer to the filtered layer
    provider.addAttributes(vector_layer.fields())
    filtered_layer.updateFields()

    # Iterate through the features and filter them
    for feature in vector_layer.getFeatures():
        if feature["STRUCTURE_NUMBER_008"] not in exclusion_ids:
            provider.addFeature(feature)

    return filtered_layer


def get_line_intersections(filtered_osm_gl, rivers_gl):
    """
    Get intersections between OSM lines and rivers
    """
    intersections = processing.run(
        "native:lineintersections",
        {
            "INPUT": filtered_osm_gl,
            "INPUT_FIELDS": [],
            "INTERSECT": rivers_gl,
            "INTERSECT_FIELDS": [
                "OBJECTID",
                "permanent_identifier",
                "gnis_id",
                "gnis_name",
                "fcode_description",
            ],
            "INTERSECT_FIELDS_PREFIX": "",
            "OUTPUT": "memory:",
        },
    )["OUTPUT"]
    return intersections


def load_layers(nbi_points_fp, osm_fp):
    """
    Load required layers
    """
    nbi_points_gl = QgsVectorLayer(nbi_points_fp, "nbi-points", "ogr")
    if not nbi_points_gl.isValid():
        print("NBI points layer failed to load!")
        sys.exit(1)

    osm_gl = QgsVectorLayer(osm_fp, "filtered", "ogr")
    if not osm_gl.isValid():
        print("OSM ways layer failed to load!")
        sys.exit(1)

    return nbi_points_gl, osm_gl


def process_bridge(nbi_points_gl, exploded_osm_gl):
    """
    Process bridges: filter and join NBI data with OSM data
    """
    filter_expression = "bridge is not null or man_made='bridge'"

    filtered_osm_gl = filter_osm_data(exploded_osm_gl, filter_expression)

    buffer_80 = create_buffer(filtered_osm_gl, 0.0008)

    osm_bridge_yes_nbi_join = join_by_location(
        buffer_80,
        nbi_points_gl,
        [
            "STRUCTURE_NUMBER_008",
        ],
    )

    join_csv_path = "output-data/csv-files/OSM-Bridge-Yes-NBI-Join.csv"

    vl_to_csv(osm_bridge_yes_nbi_join, join_csv_path)

    exclusion_ids = get_bridge_ids_from_csv(join_csv_path)

    filtered_layer = filter_nbi_layer(nbi_points_gl, exclusion_ids)

    output_path = "output-data/gpkg-files/NBI-Filtered-Yes-Manmade-Bridges.gpkg"

    QgsVectorFileWriter.writeAsVectorFormat(
        filtered_layer, output_path, "utf-8", filtered_layer.crs(), "GPKG"
    )

    print(f"\nOutput file: {output_path} has been created successfully!")

    QgsProject.instance().removeMapLayer(filtered_osm_gl.id())
    QgsProject.instance().removeMapLayer(buffer_80.id())
    QgsProject.instance().removeMapLayer(osm_bridge_yes_nbi_join.id())

    return filtered_layer


def process_layer_tag(nbi_points_gl, exploded_osm_gl):
    """
    Process layer tags: filter and join NBI data with OSM data based on layer tag
    """
    filter_expression = "layer>0"

    filtered_osm_gl = filter_osm_data(exploded_osm_gl, filter_expression)

    buffer_30 = create_buffer(filtered_osm_gl, 0.0003)

    osm_bridge_yes_nbi_join = join_by_location(
        buffer_30,
        nbi_points_gl,
        [
            "STRUCTURE_NUMBER_008",
        ],
    )

    join_csv_path = (
        "output-data/csv-files/OSM-NBI-Manmade-Bridge-Layer-Filtered-Join.csv"
    )

    vl_to_csv(osm_bridge_yes_nbi_join, join_csv_path)

    exclusion_ids = get_bridge_ids_from_csv(join_csv_path)

    filtered_layer = filter_nbi_layer(nbi_points_gl, exclusion_ids)

    output_path = "output-data/gpkg-files/NBI-Filtered-Yes-Manmade-Layer-Bridges.gpkg"

    QgsVectorFileWriter.writeAsVectorFormat(
        filtered_layer, output_path, "utf-8", filtered_layer.crs(), "GPKG"
    )

    print(f"\nOutput file: {output_path} has been created successfully!")

    QgsProject.instance().removeMapLayer(filtered_osm_gl.id())
    QgsProject.instance().removeMapLayer(buffer_30.id())
    QgsProject.instance().removeMapLayer(osm_bridge_yes_nbi_join.id())

    return filtered_layer


def process_parallel_bridges(nbi_points_gl, exploded_osm_gl):
    """
    Process parallel bridges: identify and filter parallel bridges
    """
    filter_expression = "highway IN ('motorway_link', 'primary', 'primary_link', 'trunk', 'motorway', 'trunk_link') AND oneway = 'yes' AND bridge is null"

    filtered_osm_gl = filter_osm_data(exploded_osm_gl, filter_expression)

    buffer_30 = create_buffer(filtered_osm_gl, 0.0003)

    osm_oneway_yes_osm_join = join_by_location(
        buffer_30,
        filtered_osm_gl,
        [
            "osm_id",
        ],
    )

    osm_oneway_yes_osm_bridge_join = join_by_location(
        osm_oneway_yes_osm_join,
        nbi_points_gl,
        ["STRUCTURE_NUMBER_008"],
    )

    join_csv_path = "output-data/csv-files/OSM-Oneways-NBI-Join.csv"
    keep_fields = ["osm_id", "osm_id_2", "STRUCTURE_NUMBER_008"]
    vl_to_csv_filter(osm_oneway_yes_osm_bridge_join, join_csv_path, keep_fields)

    parallel_bridge_ids = get_bridge_ids_from_csv(join_csv_path)
    filtered_layer = filter_nbi_layer(
        vector_layer=nbi_points_gl, exclusion_ids=parallel_bridge_ids
    )

    output_path = "output-data/gpkg-files/Filtered-NBI-Bridges.gpkg"

    QgsVectorFileWriter.writeAsVectorFormat(
        filtered_layer, output_path, "utf-8", filtered_layer.crs(), "GPKG"
    )

    print(f"\nOutput file: {output_path} has been created successfully!")

    QgsProject.instance().removeMapLayer(filtered_osm_gl.id())
    QgsProject.instance().removeMapLayer(buffer_30.id())
    QgsProject.instance().removeMapLayer(osm_oneway_yes_osm_join.id())
    QgsProject.instance().removeMapLayer(osm_oneway_yes_osm_bridge_join.id())

    return filtered_layer


def process_nearby_bridges(nbi_points_gl):
    """
    Process nearby bridges: identify and filter nearby bridges
    """
    buffer_10 = create_buffer(nbi_points_gl, 0.0001)

    nbi_10_nbi_join = join_by_location(
        buffer_10,
        nbi_points_gl,
        [
            "STRUCTURE_NUMBER_008",
        ],
    )

    join_csv_path = "output-data/csv-files/NBI-10-NBI-Join.csv"
    keep_fields = ["STRUCTURE_NUMBER_008", "STRUCTURE_NUMBER_008_2"]
    vl_to_csv_filter(nbi_10_nbi_join, join_csv_path, keep_fields)

    nearby_bridge_ids = get_nearby_bridge_ids_from_csv(join_csv_path)
    filtered_layer = filter_nbi_layer(
        vector_layer=nbi_points_gl, exclusion_ids=nearby_bridge_ids
    )

    output_path = "output-data/gpkg-files/Final-filtered-NBI-Bridges.gpkg"
    QgsVectorFileWriter.writeAsVectorFormat(
        filtered_layer, output_path, "utf-8", filtered_layer.crs(), "GPKG"
    )

    print(f"\nOutput file: {output_path} has been created successfully!")

    QgsProject.instance().removeMapLayer(buffer_10.id())
    QgsProject.instance().removeMapLayer(nbi_10_nbi_join.id())

    return filtered_layer


def process_buffer_join(nbi_points_gl, osm_gl, exploded_osm_gl):
    """
    Process buffer join: join NBI data with OSM and river data
    """
    rivers_fp = (
        "input-data/NHD-Kentucky-Streams-Flowline.gpkg|layername=NHD-Kentucky-Flowline"
    )
    rivers_gl = QgsVectorLayer(rivers_fp, "rivers", "ogr")
    if not rivers_gl.isValid():
        print("Rivers layer failed to load!")
        sys.exit(1)
        
    filter_expression = "highway not in ('abandoned','bridleway','construction','corridor','crossing','cycleway','elevator','escape','footway','living_street','path','pedestrian','planned','proposed','raceway','rest_area','steps') AND bridge IS NULL AND layer IS NULL"
    exploded_osm_gl = filter_osm_data(exploded_osm_gl, filter_expression)

    intersections = get_line_intersections(exploded_osm_gl, rivers_gl)

    output_path = "output-data/csv-files/OSM-NHD-Intersections.csv"
    vl_to_csv(
        intersections,
        output_path,
    )
    print(f"\nOutput file: {output_path} has been created successfully!")

    osm_river_join = join_by_location(
        osm_gl,
        rivers_gl,
        [
            "OBJECTID",
            "permanent_identifier",
            "gnis_id",
            "gnis_name",
            "fcode_description",
        ],
    )

    output_path = "output-data/csv-files/OSM-NHD-Join.csv"
    vl_to_csv(
        osm_river_join,
        "output-data/csv-files/OSM-NHD-Join.csv",
    )
    print(f"\nOutput file: {output_path} has been created successfully!")

    buffer_10 = create_buffer(nbi_points_gl, 0.0001)
    buffer_30 = create_buffer(nbi_points_gl, 0.0003)

    nbi_10_river_join = join_by_location(
        buffer_10,
        rivers_gl,
        [
            "OBJECTID",
            "permanent_identifier",
            "gnis_id",
            "gnis_name",
            "fcode_description",
        ],
    )

    keep_fields = [
        "STRUCTURE_NUMBER_008",
        "permanent_identifier",
    ]

    output_path = "output-data/csv-files/NBI-10-NHD-Join.csv"

    vl_to_csv_filter(
        nbi_10_river_join,
        output_path,
        keep_fields,
    )
    print(f"\nOutput file: {output_path} has been created successfully!")

    nbi_30_osm_river_join = join_by_location(
        buffer_30,
        osm_river_join,
        [],
    )

    keep_fields = [
        "OBJECTID",
        "STATE_CODE_001",
        "STRUCTURE_NUMBER_008",
        "LATDD",
        "LONGDD",
        "osm_id",
        "name",
        "highway",
        "OBJECTID_2",
        "permanent_identifier",
    ]

    output_path = "output-data/csv-files/NBI-30-OSM-NHD-Join.csv"
    vl_to_csv_filter(
        nbi_30_osm_river_join,
        output_path,
        keep_fields,
    )
    print(f"\nOutput file: {output_path} has been created successfully!")


def main():
    nbi_points_fp = "output-data/gpkg-files/NBI-Kentucky-Bridge-Data.gpkg|layername=NBI-Kentucky-Bridge-Data"
    osm_fp = "output-data/gpkg-files/kentucky-filtered-highways.gpkg|layername=lines"
    nbi_points_gl, osm_gl = load_layers(nbi_points_fp, osm_fp)
    exploded_osm_gl = explode_osm_data(osm_gl)
    output_layer1 = process_bridge(nbi_points_gl, exploded_osm_gl)
    output_layer2 = process_layer_tag(output_layer1, exploded_osm_gl)
    output_layer3 = process_parallel_bridges(output_layer2, exploded_osm_gl)
    output_layer4 = process_nearby_bridges(output_layer3)
    process_buffer_join(output_layer4, osm_gl, exploded_osm_gl)


if __name__ == "__main__":
    main()
