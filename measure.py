import os
import arcpy
from dotenv import load_dotenv
import pathlib
import time
import pandas as pd
import numpy as np


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


def simplify_near_table(gdb_path, near_table_name, max_rank=6):
    """
    Simplify the near table by filtering out records with NEAR_RANK greater than max_rank.
    :param gdb_path - string: path to the geodatabase containing the near table
    :param near_table_name - string: name of near table
    :param max_rank - int: maximum NEAR_RANK value to retain
    :return out_table_path - string: path to the simplified near table
    """
    print("Simplifying near table...")
    out_table_name = f"{near_table_name}_{max_rank}_or_less"
    out_table_path = os.path.join(gdb_path, out_table_name)
    near_table_path = os.path.join(gdb_path, near_table_name)
    arcpy.management.SelectLayerByAttribute(near_table_path, "NEW_SELECTION", f"NEAR_RANK <= {max_rank}")
    arcpy.management.CopyFeatures(near_table_path, out_table_path)
    print(f"Near table simplified to records with NEAR_RANK <= {max_rank}.")
    return out_table_path


def transform_near_table(gdb_path, near_table_name):
    """
    Transform the near table to a format that can be joined with the input building (line or polygon) layer.
    :param gdb_path - string: path to the geodatabase containing the near table generated by GenerateNearTable()
    :param near_table_name - string: name of the near table to be transformed
    :return out_table_path - string: path to the transformed near table
    """
    in_table_path = os.path.join(gdb_path, near_table_name)
    in_array = arcpy.da.TableToNumPyArray(in_table_path, "*")
    df = pd.DataFrame(in_array)

    #out_df = pd.DataFrame()
    output_data = []

    # Iterate through each unique IN_FID
    for in_fid in df['IN_FID'].unique():
        subset = df[df['IN_FID'] == in_fid]
        row = {'IN_FID': in_fid}
    
        # Populate the pbX_fid and pbX_distance columns based on NEAR_RANK
        for _, item in subset.iterrows():
            rank = int(item['NEAR_RANK'])
            row[f'pb{rank}_fid'] = item['NEAR_FID']
            row[f'pb{rank}_distance'] = item['NEAR_DIST']
    
        # Append the row to the output DataFrame
        #out_df = pd.concat([out_df, pd.DataFrame([row])], ignore_index=True)
        output_data.append(row)

    out_df = pd.DataFrame(output_data)

    out_array = np.array([tuple(row) for row in out_df.to_records(index=False)], 
                         dtype=[(name, 'f8' if 'distance' in name else 'i4') for name in out_df.columns]
    )

    out_table_path = os.path.join(gdb_path, "transformed_near_table")
    arcpy.da.NumPyArrayToTable(out_array, out_table_path)
    print(f"Transformed near table has been written to {out_table_path}")
    return out_table_path


def join_near_distances(building_lines, near_table):
    """
    TODO: modify this function to join the transformed near table to the building lines layer.
    Join the NEAR_DIST values to the building lines layer.
    :param building_lines - string: path to the building lines feature class
    :param near_table - string: path to the near table containing the NEAR_DIST values
    """
    print("Joining distance results to building lines...")
    # may need to use [*] as fifth argument to join all fields
    arcpy.management.JoinField(building_lines, "OBJECTID", near_table, "IN_FID")
    print("Join operation complete.")    


def run():
    start_time = time.time()
    print(f"Starting setback distance calculation {time.ctime(start_time)}")
    set_environment()
    
    # Define input feature classes and output paths
    input_parcels = "parcels_in_zones_r_th_otmu_li_ao"
    input_buildings = "osm_na_buildings_in_zones_r_th_otmu_li_ao_non_intersecting"
    input_streets = "streets_20241030"
    parcel_lines = "parcel_lines"
    building_lines = "building_lines"
    gdb_path = os.getenv("GEODATABASE")
    near_table_name = "near_table"
    near_table_path = os.path.join(gdb_path, near_table_name)
    
    # Clear any existing outputs - not necessary if overwriting is enabled
    out_items = [parcel_lines, building_lines, near_table_path]
    clear_existing_outputs(out_items)

    # Select parcels that intersect streets and convert to line features
    select_parcels_near_streets(input_parcels, input_streets)
    create_line_features(input_parcels, input_buildings, parcel_lines, building_lines)

    print(f"near_table exists (pre-calculation): {arcpy.Exists(near_table_path)}")
    # Calculate nearest distances and join results to building lines
    calculate_nearest_distances(building_lines, parcel_lines, near_table_path)
    print(f"near_table exists (post-calculation): {arcpy.Exists(near_table_path)}")

    simplified_near_table = simplify_near_table(gdb_path, near_table_name, max_rank=8)
    transformed_near_table = transform_near_table(gdb_path, simplified_near_table)

    join_near_distances(building_lines, transformed_near_table)
    elapsed_minutes = (time.time() - start_time) / 60
    print(f"Setback distance calculation complete in {round(elapsed_minutes, 2)} minutes.")


def test():
    set_environment()
    gdb_path = os.getenv("GEODATABASE")
    transform_near_table(gdb_path, "near_table_07_near_rank_6_or_less")


# Run the script
run()

#test()
