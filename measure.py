import os
import arcpy
from dotenv import load_dotenv
import pathlib
import time


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


def run():
    start_time = time.time()
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
    
    # Calculate nearest distances and join results to building lines
    calculate_nearest_distances(building_lines, parcel_lines, near_table)
    join_near_distances(building_lines, near_table)
    elapsed_minutes = (time.time() - start_time) / 60
    print(f"Setback distance calculation complete in {elapsed_minutes}.")


# Run the script
run()
