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


def get_significant_vertices(line_fc, angle_threshold=80):
    """Get points at significant angle changes along lines in a feature class."""
    significant_points = "significant_points"
    #arcpy.CreateFeatureclass_management("in_memory", significant_points, "POINT", spatial_reference=line_fc)
    workspace = os.getenv("FEATURE_DATASET")
    arcpy.management.CreateFeatureclass(workspace, significant_points, "POINT", spatial_reference=line_fc)
    
    with arcpy.da.InsertCursor(significant_points, ["SHAPE@"]) as insert_cursor:
        with arcpy.da.SearchCursor(line_fc, ["SHAPE@"]) as search_cursor:
            for row in search_cursor:
                part = row[0]  # The geometry of the line
                previous_angle = None
                for i in range(len(part) - 1):
                    # Get angle between consecutive segments
                    x1, y1 = part[i].X, part[i].Y
                    x2, y2 = part[i + 1].X, part[i + 1].Y
                    angle = calculate_angle(x1, y1, x2, y2)
                    
                    if previous_angle is not None:
                        # Check if angle change is above threshold
                        angle_change = abs(angle - previous_angle)
                        if angle_change >= angle_threshold:
                            # Add point at this vertex
                            insert_cursor.insertRow([arcpy.Point(x1, y1)])
                    
                    previous_angle = angle

    return significant_points


def split_lines_at_significant_points(line_fc, output_split_lines_fc, angle_threshold=80):
    """
    Split lines at significant angle changes.
    :param line_fc: Input line feature class.
    :param output_split_lines_fc: Output feature class for split lines.
    :param angle_threshold: Minimum angle change (in degrees) to consider a significant turn.
    """
    # Step 1: Identify significant vertices based on angle threshold
    significant_points = get_significant_vertices(line_fc, angle_threshold)

    # Step 2: Split lines at significant points
    arcpy.management.SplitLineAtPoint(line_fc, significant_points, output_split_lines_fc, search_radius="1 Feet")

    # Clean up in-memory feature class
    arcpy.management.Delete(significant_points)

    print("Lines have been split at significant angle changes.")    


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

    split_parcel_lines = "minimized_split_parcel_lines"
    split_lines_at_significant_points(parcel_lines, split_parcel_lines, angle_threshold=40)

    # Calculate nearest distances and join results to building lines
    #calculate_nearest_distances(building_lines, parcel_lines, near_table)
    calculate_nearest_distances(building_lines, split_parcel_lines, near_table)
    join_near_distances(building_lines, near_table)
    elapsed_minutes = (time.time() - start_time) / 60
    print(f"Setback distance calculation complete in {round(elapsed_minutes, 2)} minutes.")


# Run the script
run()
