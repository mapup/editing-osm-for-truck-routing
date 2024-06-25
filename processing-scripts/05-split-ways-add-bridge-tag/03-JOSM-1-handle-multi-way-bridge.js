import * as console from "josm/scriptingconsole";

const LatLon = Java.type("org.openstreetmap.josm.data.coor.LatLon");
const Node = Java.type("org.openstreetmap.josm.data.osm.Node");
const Way = Java.type("org.openstreetmap.josm.data.osm.Way");
const MainApplication = Java.type("org.openstreetmap.josm.gui.MainApplication");
const SplitWayAction = Java.type("org.openstreetmap.josm.actions.SplitWayAction");
const AddCommand = Java.type("org.openstreetmap.josm.command.AddCommand");
const ChangeCommand = Java.type("org.openstreetmap.josm.command.ChangeCommand");
const Geometry = Java.type("org.openstreetmap.josm.tools.Geometry");
const ProjectionRegistry = Java.type("org.openstreetmap.josm.data.projection.ProjectionRegistry");
const UndoRedoHandler = Java.type("org.openstreetmap.josm.data.UndoRedoHandler");
const OsmPrimitiveType = Java.type("org.openstreetmap.josm.data.osm.OsmPrimitiveType");

console.clear();

// Constants
const BRIDGE_TAG = "bridge";
const BRIDGE_VALUE = "yes";

// Improved coordinate list structure
const coordinatesList = [
  {
    points: [
      { latitude: 37.9340811, longitude: -87.5476108, wayId: 17561921 },
      { latitude: 37.9363173, longitude: -87.5462384, wayId: 97759371 },
    ],
    additionalBridgeWayIds: [17563421]
  }
];

function getDataSet() {
  return MainApplication.getLayerManager().getEditDataSet();
}

function addNodeToWay(way, latLon, isFirstPoint, preExistingNodeId) {
  const dataSet = getDataSet();
  const projection = ProjectionRegistry.getProjection();
  const wayNodes = way.getNodes();
  let closestIndex = -1;
  let closestDistance = Infinity;
  let closestLatLon = latLon;

  for (let i = 0; i < wayNodes.size() - 1; i++) {
    const segmentStart = projection.latlon2eastNorth(wayNodes.get(i).getCoor());
    const segmentEnd = projection.latlon2eastNorth(wayNodes.get(i + 1).getCoor());
    const point = Geometry.closestPointToSegment(
      segmentStart,
      segmentEnd,
      projection.latlon2eastNorth(latLon)
    );
    const pointLatLon = projection.eastNorth2latlon(point);
    const distance = latLon.greatCircleDistance(pointLatLon);
    if (distance < closestDistance) {
      closestDistance = distance;
      closestIndex = i;
      closestLatLon = pointLatLon;
    }
  }

  if (closestIndex !== -1) {
    const closestNode = new Node(closestLatLon);
    const newWayNodes = new java.util.ArrayList(wayNodes);
    newWayNodes.add(closestIndex + 1, closestNode);

    const newWay = new Way(way);
    newWay.setNodes(newWayNodes);

    UndoRedoHandler.getInstance().add(new AddCommand(dataSet, closestNode));
    UndoRedoHandler.getInstance().add(new ChangeCommand(way, newWay));

    dataSet.setSelected(closestNode);
    SplitWayAction.runOn(dataSet);

    console.println(`Node added at latitude: ${latLon.lat()}, longitude: ${latLon.lon()} and Node ID: ${closestNode.getId()}`);

    // Tag the appropriate way as a bridge
    const selectedWays = dataSet.getSelectedWays();
    for (const selectedWay of selectedWays) {
      const selectedWayNodes = selectedWay.getNodes();
      let isBridgeWay = false;

      if (isFirstPoint) {
        isBridgeWay = selectedWayNodes.get(0).getId() === closestNode.getId() &&
                      selectedWayNodes.get(selectedWayNodes.size() - 1).getId() === preExistingNodeId;
      } else {
        isBridgeWay = selectedWayNodes.get(0).getId() === preExistingNodeId &&
                      selectedWayNodes.get(selectedWayNodes.size() - 1).getId() === closestNode.getId();
      }

      if (isBridgeWay) {
        selectedWay.put(BRIDGE_TAG, BRIDGE_VALUE);
        UndoRedoHandler.getInstance().add(new ChangeCommand(selectedWay, selectedWay));
        console.println(`Bridge way ${selectedWay.getId()} tagged successfully.`);
        break;
      }
    }

    return closestNode;
  } else {
    console.println("Failed to find a suitable segment to insert the node.");
    return null;
  }
}

function tagAdditionalBridgeWays(additionalBridgeWayIds) {
  const dataSet = getDataSet();
  for (const wayId of additionalBridgeWayIds) {
    const way = dataSet.getPrimitiveById(wayId, OsmPrimitiveType.WAY);
    if (way) {
      way.put(BRIDGE_TAG, BRIDGE_VALUE);
      UndoRedoHandler.getInstance().add(new ChangeCommand(way, way));
      console.println(`Additional bridge way ${wayId} tagged successfully.`);
    } else {
      console.println(`Additional bridge way ${wayId} not found.`);
    }
  }
}

function processCoordinateSet(coordinateSet) {
  const dataSet = getDataSet();
  if (!dataSet) {
    console.println("No active data set found.");
    return;
  }

  const { points, additionalBridgeWayIds } = coordinateSet;

  for (let i = 0; i < points.length - 1; i++) {
    const currentPoint = points[i];
    const nextPoint = points[i + 1];

    const currentWay = dataSet.getPrimitiveById(currentPoint.wayId, OsmPrimitiveType.WAY);
    const nextWay = dataSet.getPrimitiveById(nextPoint.wayId, OsmPrimitiveType.WAY);

    if (!currentWay || !nextWay) {
      console.println(`Way not found for point ${i} or ${i + 1}`);
      continue;
    }

    const isFirstPoint = i === 0;
    const currentNode = addNodeToWay(currentWay, new LatLon(currentPoint.latitude, currentPoint.longitude), isFirstPoint, currentWay.getNodes().get(currentWay.getNodes().size() - 1).getId());
    
    if (i === points.length - 2) {
      addNodeToWay(nextWay, new LatLon(nextPoint.latitude, nextPoint.longitude), false, nextWay.getNodes().get(0).getId());
    }
  }

  tagAdditionalBridgeWays(additionalBridgeWayIds);

  MainApplication.getMap().mapView.repaint();
}

// Main execution
try {
  for (const coordinateSet of coordinatesList) {
    processCoordinateSet(coordinateSet);
  }
} catch (error) {
  console.println(`An error occurred: ${error.message}`);
}