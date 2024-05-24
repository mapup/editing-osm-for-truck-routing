# Edit OSM using JOSM add missing bridges for truck routing

## Introduction
This repository contains the code to identify and add missing bridges in the USA to OpenStreetMap (OSM) using [National Bridge Inventory (NBI)](https://geodata.bts.gov/datasets/national-bridge-inventory/about) data. This includes finding the nearest point to line geometry, determining splitting coordinates based on bridge length, logically splitting OSM ways, and adding bridge-related tags to the split ways. The NBI data, being in the public domain, allows unrestricted public use and is compatible with OSM. The next phase of this project will focus on adding truck restriction information to the bridge data.

## OSM Bridge Integration

This repository contains two approaches for integrating and accurately representing bridge locations in OpenStreetMap (OSM) data. It also contains some additional Python scripts that handle finding the nearest point to line geometry and finding OSM way-splitting coordinates based on a bridge's length.
- To find the nearest point on the OSM way: [find_nearest_point.py](find_nearest_point.py)
- To get the split points: [calculate_osm_split_points.py](calculate_osm_split_points.py) 

### Approach 1

This approach [[JOSM Approach 1 - split way in place](JOSM_1_split_way_in_place.js)] uses the GraalJS scripting engine of the JOSM Scripting Plugin. It inserts new nodes at the closest points along existing ways to the provided bridge coordinates, splits the ways at these new nodes, and tags the identified way segment connecting the bridge start and end nodes as a "bridge" by adding the (`bridge=yes`) tag.

### Approach 2

This approach [[JOSM Approach 2 - split way and remove old way.py](JOSM_2_split_way_remove_old_way.py)]  utilizes the Jython engine of the JOSM scripting plugin. It retrieves the active data layer and edit dataset from JOSM, then splits existing ways at bridge locations, adds bridge tags (`bridge=yes`), and removes the old way. It accurately represents missing bridges by interpolating the start and end points of the bridge segments along the existing way segments.
