import os
import arcpy
from dotenv import load_dotenv
import pathlib
import time
import math


def set_environment():
    """Set up the environment and workspace."""
    file_path = pathlib.Path(__file__).parent.absolute()
    env_path = os.path.join(file_path, '.env')
    load_dotenv(env_path)
    workspace = os.getenv("FEATURE_DATASET")
    arcpy.env.workspace = workspace
    print(f"Workspace set to {arcpy.env.workspace}")
    arcpy.env.overwriteOutput = True


def clear_existing_outputs(out_items):
    """Delete existing outputs if they already exist."""
    for item in out_items:
        if arcpy.Exists(item):
            arcpy.management.Delete(item)


def create_line_features(parcel_poly_fc, building_poly_fc, parcel_line_fc, building_line_fc):
    """
    Convert parcel and building polygons to line features.
    :param parcel_poly_fc - string: name of input parcel polygon feature class
    :param building_poly_fc - string: name of input building polygon feature class
    :param parcel_line_fc - string: name of output parcel line feature class
    :param building_line_fc - string: name of output building line feature class
    """
    print("Converting polygons to lines...")
    arcpy.management.PolygonToLine(parcel_poly_fc, parcel_line_fc)
    arcpy.management.PolygonToLine(building_poly_fc, building_line_fc)
    print("Line features created.")


def select_parcels_near_streets(parcel_fc, streets_fc):
    """Select parcels that are near streets."""
    print("Selecting parcels that intersect streets...")
    arcpy.management.SelectLayerByLocation(parcel_fc, "INTERSECT", streets_fc)
    print("Parcels near streets selected.")


def calculate_nearest_distances(building_lines, parcel_lines, near_table, distance_unit="Feet"):
    """Calculate the nearest distance between building lines and parcel lines."""
    print("Calculating nearest distances...")
    arcpy.analysis.GenerateNearTable(building_lines, parcel_lines, near_table, 
                                     method="PLANAR", closest="ALL", distance_unit=distance_unit)
    print("Nearest distances calculated.")


def join_near_distances(building_lines, near_table):
    """Join the NEAR_DIST values to the building lines layer."""
    print("Joining distance results to building lines...")
    arcpy.management.JoinField(building_lines, "OBJECTID", near_table, "IN_FID", ["NEAR_DIST"])
    print("Join operation complete.")


def calculate_angle(x1, y1, x2, y2):
    """Calculate angle in degrees between two points."""
    angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
    return angle % 360


def classify_direction(angle):
    """Classify angle into primary directions: North-South or East-West."""
    if 45 <= angle < 135 or 225 <= angle < 315:
        return "east-west"
    else:
        return "north-south"


def get_direction_change_points(line_fc):
    """Identify points where the line changes from one primary direction to another."""
    direction_change_points = "direction_change_points"
    workspace = os.getenv("FEATURE_DATASET")
    arcpy.CreateFeatureclass_management(workspace, direction_change_points, "POINT", spatial_reference=line_fc)
    
    with arcpy.da.InsertCursor(direction_change_points, ["SHAPE@"]) as insert_cursor:
        with arcpy.da.SearchCursor(line_fc, ["SHAPE@"]) as search_cursor:
            for row in search_cursor:
                part = row[0]  # The geometry of the line
                previous_direction = None
                for i in range(len(part) - 1):
                    # Calculate angle between consecutive segments
                    x1, y1 = part[i].X, part[i].Y
                    x2, y2 = part[i + 1].X, part[i + 1].Y
                    angle = calculate_angle(x1, y1, x2, y2)
                    
                    # Classify segment direction as "north-south" or "east-west"
                    current_direction = classify_direction(angle)
                    
                    # Check for direction change
                    if previous_direction is not None and current_direction != previous_direction:
                        # Add point at this vertex if there's a change in primary direction
                        insert_cursor.insertRow([arcpy.Point(x1, y1)])
                    
                    previous_direction = current_direction

    return direction_change_points


def split_lines_at_direction_changes(line_fc, split_parcel_lines):
    """
    Split lines at points where the direction changes between primary directions.
    :param line_fc: Input line feature class.
    :param split_parcel_lines: Output feature class for split lines.
    """
    # Step 1: Identify direction change points
    direction_change_points = get_direction_change_points(line_fc)

    # Step 2: Split lines at direction change points
    arcpy.management.SplitLineAtPoint(line_fc, direction_change_points, split_parcel_lines, search_radius="1 Feet")

    # Clean up in-memory feature class
    arcpy.management.Delete(direction_change_points)

    print("Lines have been split at major direction changes.")


def run():
    start_time = time.time()
    print(f"Starting setback distance calculation {time.ctime(start_time)}")
    set_environment()
    
    # Define input feature classes and output paths
    input_parcels = "parcels_in_zones_r_th_otmu_li_ao"
    input_buildings = "osm_na_buildings_in_zones_r_th_otmu_li_ao"
    input_streets = "streets_20241030"
    parcel_lines = "parcel_lines"
    building_lines = "building_lines"
    gdb_path = os.getenv("GEODATABASE")
    near_table = os.path.join(gdb_path, "near_table")
    
    # Clear any existing outputs - not necessary if overwriting is enabled
    out_items = [parcel_lines, building_lines, near_table]
    clear_existing_outputs(out_items)

    # Select parcels that intersect streets and convert to line features
    select_parcels_near_streets(input_parcels, input_streets)
    create_line_features(input_parcels, input_buildings, parcel_lines, building_lines)

    split_parcel_lines = "direction_based_split_parcel_lines"  # Replace with your desired output feature class
    split_lines_at_direction_changes(parcel_lines, split_parcel_lines)

    # Calculate nearest distances and join results to building lines
    #calculate_nearest_distances(building_lines, parcel_lines, near_table)
    calculate_nearest_distances(building_lines, split_parcel_lines, near_table)

    join_near_distances(building_lines, near_table)
    elapsed_minutes = (time.time() - start_time) / 60
    print(f"Setback distance calculation complete in {round(elapsed_minutes, 2)} minutes.")


# Run the script
run()
