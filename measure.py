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


def remove_exact_duplicates(feature_class, output_fc):
    """
    Remove exact duplicates from a feature class by comparing geometries using WKT.
    :param feature_class: Path to the input feature class.
    :param output_fc: Path to the output feature class without duplicates.
    """
    print("Removing exact duplicates by geometry comparison...")
    unique_geometries = set()
    output_rows = []

    # Use a search cursor to iterate over features
    with arcpy.da.SearchCursor(feature_class, ["SHAPE@", "OBJECTID"]) as cursor:
        for row in cursor:
            geom_wkt = row[0].WKT  # Convert geometry to WKT for comparison
            if geom_wkt not in unique_geometries:
                unique_geometries.add(geom_wkt)  # Add WKT to the set
                output_rows.append(row)

    # Create an empty output feature class with the same schema as the input
    arcpy.management.CreateFeatureclass(
        os.path.dirname(output_fc), os.path.basename(output_fc), "POLYLINE", spatial_reference=feature_class
    )
    #arcpy.management.AddField(output_fc, "OBJECTID", "LONG")

    # Use an insert cursor to write unique features to the output
    with arcpy.da.InsertCursor(output_fc, ["SHAPE@", "OBJECTID"]) as cursor:
        for row in output_rows:
            cursor.insertRow(row)

    print(f"Duplicates removed. Output saved to {output_fc}.")



# TODO use closest_count again if necessary
def calculate_nearest_distances(building_lines_fc, parcel_lines_fc, near_table_path, search_radius=100, distance_unit="Feet"):
    """
    Calculate the nearest distance between building lines and parcel lines.
    :param building_lines_fc - string: Path to the building lines feature class.
    :param parcel_lines_fc - string: Path to the parcel lines feature class.
    :param near_table_path - string: Path for the output near table.
    :param search_radius - int: The radius that will be used to search for near features (parcel lines near buildings) using the specified distance unit.
    :param distance_unit - string: Unit of measurement for distance.
    """
    print("Calculating nearest distances...")
    # Generate near table with 15 closest parcel boundaries to each building side - TODO: modify closest_count if necessary
    arcpy.analysis.GenerateNearTable(building_lines_fc, parcel_lines_fc, near_table_path, 
                                     method="PLANAR", closest="ALL", search_radius=f"{search_radius} Feet", distance_unit=distance_unit)
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
    # have not yet run with DeleteIdentical() here
    arcpy.management.DeleteIdentical(parcel_lines, "Shape")
    calculate_nearest_distances(building_lines, parcel_lines, near_table_path)

    simplified_near_table_path = simplify_near_table(gdb_path, near_table_name, max_rank=8)
    transformed_near_table_path = transform_near_table(gdb_path, simplified_near_table_path)

    join_near_distances(building_lines, transformed_near_table_path)
    modify_out_table_fields(building_lines)
    elapsed_minutes = (time.time() - start_time) / 60
    print(f"Setback distance calculation complete in {round(elapsed_minutes, 2)} minutes.")


def transform_near_table_with_street_info(gdb_path, near_table_name, street_fc, parcel_lines_fc):
    """
    Transform near table to include info on adjacent street(s) and other side(s).
    :param gdb_path: Path to the geodatabase.
    :param near_table_name: Name of the near table.
    :param street_fc: Path to the street feature class.
    :param parcel_lines_fc: Path to the parcel line feature class.
    :return: Path to the transformed near table.
    """
    print("Transforming near table to include info on adjacent street(s) and other side(s)...")

    # Step 1: Pre-compute spatial relationships between parcel lines and streets
    street_parcel_join = os.path.join(gdb_path, "street_parcel_join")
    if arcpy.Exists(street_parcel_join):
        arcpy.management.Delete(street_parcel_join)
    
    print("Performing spatial join between parcel lines and streets...")
    #TODO: # Use a search radius that is appropriate for the data
    arcpy.analysis.SpatialJoin(parcel_lines_fc, street_fc, street_parcel_join, join_type="KEEP_COMMON", 
        match_option="WITHIN_A_DISTANCE", search_radius="50 Feet")

    # Load spatial join results into a pandas DataFrame
    join_array = arcpy.da.TableToNumPyArray(street_parcel_join, ["TARGET_FID", "StFULLName"])
    join_df = pd.DataFrame(join_array)
    join_df = join_df.rename(columns={"TARGET_FID": "PB_FID", "StFULLName": "STREET_NAME"})

    # Step 2: Load the near table into a pandas DataFrame
    near_table_path = os.path.join(gdb_path, near_table_name)
    near_array = arcpy.da.TableToNumPyArray(near_table_path, "*")
    near_df = pd.DataFrame(near_array)

    # Merge the near table with the spatial join results to identify adjacent streets
    merged_df = near_df.merge(join_df, left_on="NEAR_FID", right_on="PB_FID", how="left")
    merged_df["is_facing_street"] = merged_df["STREET_NAME"].notna()

    # Step 3: Populate fields for adjacent streets and other sides
    output_data = []
    for in_fid, group in merged_df.groupby("IN_FID"):
        row = {"IN_FID": in_fid}
        facing_count, other_count = 1, 1

        for _, record in group.iterrows():
            near_fid = record["NEAR_FID"]
            distance = record["NEAR_DIST"]

            if record["is_facing_street"]:
                if facing_count <= 4:  # Limit to 4 adjacent streets
                    row[f"FACING_STREET_{facing_count}"] = record["STREET_NAME"]
                    row[f"FACING_STREET_{facing_count}_PB_FID"] = near_fid
                    row[f"FACING_STREET_{facing_count}_DIST_FT"] = distance
                    facing_count += 1
            else:
                if other_count <= 4:  # Limit to 4 other sides
                    row[f"OTHER_SIDE_{other_count}_PB_FID"] = near_fid
                    row[f"OTHER_SIDE_{other_count}_DIST_FT"] = distance
                    other_count += 1

        output_data.append(row)

    # Step 4: Convert output to a NumPy structured array and write to a table
    output_df = pd.DataFrame(output_data)
    print(output_df.head())
    output_df.fillna(-1, inplace=True)
    output_fields = [(col, "f8" if "DIST" in col else ("i4" if output_df[col].dtype.kind in 'i' else "<U50")) for col in output_df.columns]
    print(f'Output fields: {output_fields}')
    output_array = np.array([tuple(row) for row in output_df.to_records(index=False)], dtype=output_fields)

    #transformed_table_path = os.path.join(gdb_path, "transformed_near_table_with_facing_optimized")
    transformed_table_path = os.path.join(gdb_path, "transformed_near_table_with_street_info")
    if arcpy.Exists(transformed_table_path):
        arcpy.management.Delete(transformed_table_path)

    arcpy.da.NumPyArrayToTable(output_array, transformed_table_path)
    print(f"Transformed near table written to: {transformed_table_path}")
    return transformed_table_path


def run_with_street_info():
    start_time = time.time()
    print(f"Starting setback distance calculation with fields holding info on adjacent streets {time.ctime(start_time)}")
    set_environment()

    # Define input feature classes and output paths (inputs are in feature dataset)
    input_parcels = "parcels_in_zones_r_th_otmu_li_ao"
    input_buildings = "extracted_footprints_nearmap_20240107_in_aoi_and_zones_r_th_otmu_li_ao"
    input_streets = "streets_20241030"
    parcel_lines = "parcel_lines"
    unique_parcel_lines = "unique_parcel_lines"
    building_lines = "building_lines_nearmap_20240107"
    gdb_path = os.getenv("GEODATABASE")
    near_table_name = "near_table"
    near_table_path = os.path.join(gdb_path, near_table_name)

    # Clear any existing outputs
    output_items = [parcel_lines, building_lines, near_table_path]
    clear_existing_outputs(output_items)

    # Process and calculate distances
    select_parcels_near_streets(input_parcels, input_streets)
    create_line_features(input_parcels, input_buildings, parcel_lines, building_lines)
    parcel_line_count = arcpy.management.GetCount(parcel_lines).getOutput(0)
    print(f"number of parcel line features before deleting identical: {parcel_line_count}")
    #arcpy.management.DeleteIdentical(parcel_lines, "Shape")
    #count = arcpy.management.GetCount(parcel_lines).getOutput(0)
    #print(f"number of parcel line features after deleting identical: {count}")

    remove_exact_duplicates("parcel_lines", "unique_parcel_lines")
    parcel_line_count = arcpy.management.GetCount(unique_parcel_lines).getOutput(0)
    print(f"number of parcel line features after deleting identical: {parcel_line_count}")
    calculate_nearest_distances(building_lines, unique_parcel_lines, near_table_path)

    # Transform near table with street info and other side fields
    transformed_near_table_path = transform_near_table_with_street_info(gdb_path, near_table_name, input_streets, parcel_lines)
    join_near_distances(building_lines, transformed_near_table_path)

    elapsed_minutes = (time.time() - start_time) / 60
    print(f"Setback distance calculation with street info fields complete in {round(elapsed_minutes, 2)} minutes.")


# Run the script
if __name__ == "__main__":
    #run()
    run_with_street_info()

