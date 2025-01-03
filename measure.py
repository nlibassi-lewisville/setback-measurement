import os
import arcpy
import time
import pandas as pd
import numpy as np
from shared import set_environment


def clear_existing_outputs(output_items):
    """
    Delete existing outputs if they already exist.
    :param output_items - list: List of output items to delete if they exist.
    """
    for item in output_items:
        if arcpy.Exists(item):
            arcpy.management.Delete(item)


def create_line_features(parcel_polygon_fc, building_polygon_fc, parcel_line_fc, building_line_fc):
    """
    Convert parcel and building polygons to line features.
    :param parcel_polygon_fc - string: Path to the parcel polygon feature class.
    :param building_polygon_fc - string: Path to the building polygon feature class.
    :param parcel_line_fc - string: Path for the output parcel line feature class.
    :param building_line_fc - string: Path for the output building line feature class.
    """
    print("Converting polygons to lines...")
    arcpy.management.PolygonToLine(parcel_polygon_fc, parcel_line_fc)
    arcpy.management.PolygonToLine(building_polygon_fc, building_line_fc)
    print("Line features created.")


def select_parcels_near_streets(parcel_fc, street_fc):
    """
    Select parcels that are near streets.
    :param parcel_fc - string: Path to the parcel feature class.
    :param street_fc - string: Path to the street feature class.
    """
    print("Selecting parcels that intersect streets...")
    arcpy.management.SelectLayerByLocation(parcel_fc, "INTERSECT", street_fc)
    print("Parcels near streets selected.")


def calculate_nearest_distances(building_lines_fc, parcel_lines_fc, near_table_path, distance_unit="Feet"):
    """
    Calculate the nearest distance between building lines and parcel lines.
    :param building_lines_fc - string: Path to the building lines feature class.
    :param parcel_lines_fc - string: Path to the parcel lines feature class.
    :param near_table_path - string: Path for the output near table.
    :param distance_unit - string: Unit of measurement for distance.
    """
    print("Calculating nearest distances...")
    arcpy.analysis.GenerateNearTable(building_lines_fc, parcel_lines_fc, near_table_path, 
                                     method="PLANAR", closest="ALL", distance_unit=distance_unit)
    print("Nearest distances calculated.")


def simplify_near_table(gdb_path, near_table_name, max_rank=6):
    """
    Simplify the near table by filtering out records with NEAR_RANK greater than max_rank.
    :param gdb_path - string: Path to the geodatabase.
    :param near_table_name - string: Name of the near table.
    :param max_rank - int: Maximum 'near rank' to retain in the table. (NEAR_RANK value of 1 is closest parcel boundary to a building side)
    :return out_table_path - string: Path of the simplified near table.
    """
    print("Simplifying near table...")
    out_table_name = f"{near_table_name}_max_rank_{max_rank}_or_less"
    out_table_path = os.path.join(gdb_path, out_table_name)
    near_table_path = os.path.join(gdb_path, near_table_name)
    arcpy.analysis.TableSelect(near_table_path, out_table_path, f"NEAR_RANK <= {max_rank}")
    print(f"Number of records with NEAR_RANK <= {max_rank}: {arcpy.GetCount_management(out_table_path).getOutput(0)}.")
    print(f"Near table simplified to records with NEAR_RANK <= {max_rank}.")
    return out_table_path


def transform_near_table(gdb_path, near_table_name):
    """
    Transform the near table to a format that can be joined with the input building layer.
    :param gdb_path - string: Path to the geodatabase.
    :param near_table_name - string: Name of the near table to transform.
    :return transformed_table_path - string: Path of the transformed near table.
    """
    print("Transforming near table...")
    near_table_path = os.path.join(gdb_path, near_table_name)
    table_array = arcpy.da.TableToNumPyArray(near_table_path, "*")
    df = pd.DataFrame(table_array)

    output_data = []
    for in_fid in df['IN_FID'].unique():
        subset = df[df['IN_FID'] == in_fid]
        row = {'IN_FID': in_fid}
    
        for _, item in subset.iterrows():
            rank = int(item['NEAR_RANK'])
            row[f'PB_{rank}_FID'] = item['NEAR_FID']
            row[f'PB_{rank}_DIST_FT'] = item['NEAR_DIST']
    
        output_data.append(row)

    transformed_df = pd.DataFrame(output_data)
    transformed_df.fillna(-1, inplace=True)
    out_table_array = np.array([tuple(row) for row in transformed_df.to_records(index=False)], 
                               dtype=[(name, 'f8' if 'DIST' in name else 'i4') for name in transformed_df.columns])

    transformed_table_path = os.path.join(gdb_path, "transformed_near_table")
    arcpy.da.NumPyArrayToTable(out_table_array, transformed_table_path)
    #print(f"Transformed near table has been written to {transformed_table_path}")
    return transformed_table_path


def join_near_distances(building_lines_fc, transformed_near_table_path):
    """
    Join the transformed near table to the building lines layer.
    :param building_lines_fc - string: Path to the building lines feature class.
    :param transformed_near_table_path - string: Path to the transformed near table.
    """
    print("Joining distance results to building lines...")
    arcpy.management.JoinField(building_lines_fc, "OBJECTID", transformed_near_table_path, "IN_FID")
    print("Join operation complete.")


def modify_out_table_fields(out_layer_path):
    """
    Add and remove fields in the near table.
    :param out_layer_path - string: Path to output layer (building feature class containing near distances).
    """
    print("Modifying near table fields...")
    fields = arcpy.ListFields(out_layer_path)
    to_delete = ["LEFT_FID", "RIGHT_FID"]
    for field in fields:    
        if field.name in to_delete:
            arcpy.management.DeleteField(out_layer_path, field.name)
    new_fields = [("HEIGHT_FT", "FLOAT"), ("AREA_FT", "FLOAT"), ("CONDITION", "TEXT")]
    for field in new_fields:
        arcpy.management.AddField(out_layer_path, field[0], field[1])
    print("Fields of output table modified.")    


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
    output_items = [parcel_lines, building_lines, near_table_path]
    clear_existing_outputs(output_items)

    # Select parcels that intersect streets and convert to line features
    select_parcels_near_streets(input_parcels, input_streets)
    create_line_features(input_parcels, input_buildings, parcel_lines, building_lines)
    calculate_nearest_distances(building_lines, parcel_lines, near_table_path)

    simplified_near_table_path = simplify_near_table(gdb_path, near_table_name, max_rank=8)
    transformed_near_table_path = transform_near_table(gdb_path, simplified_near_table_path)

    join_near_distances(building_lines, transformed_near_table_path)
    modify_out_table_fields(building_lines)
    elapsed_minutes = (time.time() - start_time) / 60
    print(f"Setback distance calculation complete in {round(elapsed_minutes, 2)} minutes.")


# Run the script
if __name__ == "__main__":
    run()
