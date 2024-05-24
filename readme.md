# OSM Bridge Integration

This repository contains two approaches for integrating and accurately representing bridge locations in OpenStreetMap (OSM) data.

## Approach 1

This approach uses the GraalJS scripting engine of the JOSM Scripting Plugin. It inserts new nodes at the closest points along existing ways to the provided bridge coordinates, splits the ways at these new nodes, and tags the identified way segment connecting the bridge start and end nodes as a "bridge" by adding the `bridge=yes` tag.

## Approach 2

This approach utilizes the Jython engine of the JOSM scripting plugin. It retrieves the active data layer and edit dataset from JOSM, then splits existing ways at bridge locations, adds bridge tags (`bridge=yes`), and removes the old way. It accurately represents missing bridges by interpolating the start and end points of the bridge segments along the existing way segments.

Both approaches aim to enhance the accuracy and detail of bridge representations in OSM data, automating a task that would otherwise be time-consuming and prone to human error if performed manually.

## Usage

1. Clone the repository
2. Open JOSM and enable the respective scripting plugin (GraalJS or Jython)
3. Load the desired script
4. Provide the required input data (bridge coordinates, way IDs, etc.)
5. Run the script
