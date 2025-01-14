import os
import arcpy
import time
import pandas as pd
import numpy as np
from shared import set_environment


def process_parcel(parcel_id, parcel_fc, building_fc, parcel_lines_fc, initial_near_table, output_near_table, output_lines_fc, max_side_fields=4):
    """
    Process a single parcel: convert to lines, measure distances, and generate a near table.
    :param parcel_id: The OBJECTID of the parcel being processed.
    :param parcel_fc: Path to the parcel polygon feature class.
    :param building_fc: Path to the building polygon feature class.
    :param parcel_lines_fc: Path to the temporary parcel line feature class.
    :param output_near_table: Path to the temporary output near table.
    :param output_lines_fc: Path to the combined output parcel line feature class.
    """
    # Isolate the current parcel
    parcel_layer = "current_parcel"
    arcpy.management.MakeFeatureLayer(parcel_fc, parcel_layer, f"OBJECTID = {parcel_id}")

    # Convert parcel polygon to lines
    arcpy.management.PolygonToLine(parcel_layer, parcel_lines_fc)
    # Add a field to store the polygon parcel ID
    arcpy.management.AddField(parcel_lines_fc, "PARCEL_POLYGON_OID", "LONG")
    arcpy.management.CalculateField(parcel_lines_fc, "PARCEL_POLYGON_OID", f"{parcel_id}")
    # TODO - uncomment and fix after processing single parcel
    #arcpy.management.Append(parcel_lines_fc, output_lines_fc, "NO_TEST")

    parcel_points_fc = f"parcel_points_{parcel_id}"

    split_parcel_lines_fc = f"split_parcel_lines_{parcel_id}"

    arcpy.management.FeatureVerticesToPoints(parcel_lines_fc, parcel_points_fc, "ALL")
    #arcpy.management.SplitLineAtPoint(parcel_lines_fc, parcel_points_fc, split_parcel_lines_fc)
    # TODO - adjust search radius if necessary
    arcpy.management.SplitLineAtPoint(parcel_lines_fc, parcel_points_fc, split_parcel_lines_fc, search_radius="500 Feet")

    # Select buildings inside the parcel
    building_layer = f"buildings_in_parcel_{parcel_id}"
    arcpy.management.MakeFeatureLayer(building_fc, building_layer)
    print(f"Selecting building(s) inside parcel {parcel_id}...")
    arcpy.management.SelectLayerByLocation(building_layer, "WITHIN", parcel_layer)

    # TODO - uncomment and fix after processing single parcel
    # Generate near table
    #near_table = f"in_memory/near_table_{parcel_id}"

    print(f"Generating near table for parcel {parcel_id}...")
    arcpy.analysis.GenerateNearTable(
        building_layer, split_parcel_lines_fc, initial_near_table, method="PLANAR", closest="ALL", search_radius="150 Feet"
    )

    side_field_count = 0
    print(f"Adding fields with side info to near table for parcel {parcel_id}...")
    while side_field_count < max_side_fields:
        # Add facing street and other side fields
        side_field_count += 1
        arcpy.management.AddField(initial_near_table, f"FACING_STREET_{side_field_count}", "TEXT")
        arcpy.management.AddField(initial_near_table, f"FACING_STREET_{side_field_count}_DIST_FT", "FLOAT")
        arcpy.management.AddField(initial_near_table, f"OTHER_SIDE_{side_field_count}_PB_FID", "LONG")
        arcpy.management.AddField(initial_near_table, f"OTHER_SIDE_{side_field_count}_DIST_FT", "FLOAT")

    # TODO - add logic for populating these fields here or elsewhere

    # In a new field, hold the parcel polygon ID followed by parcel line ID in format 64-1, 64-2, etc.
    arcpy.management.AddField(initial_near_table, f"PARCEL_COMBO_FID", "TEXT")
    arcpy.management.CalculateField(initial_near_table, "PARCEL_COMBO_FID", f"'{parcel_id}-' + str(!NEAR_FID!)", "PYTHON3")
    #arcpy.management.CalculateField("initial_near_table_64", "PARCEL_COMBO_FID", "'64-' + str(!NEAR_FID!)")
    

    # TODO - uncomment and fix after processing single parcel
    # Append the near table to the output table
    #print(f"Appending near table to output table for parcel {parcel_id}...")
    #arcpy.management.Append(initial_near_table, output_near_table, "NO_TEST")
    #arcpy.management.Delete(initial_near_table)  # Clean up in-memory table


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
    print("join_df head:")
    print(join_df.head())

    # Step 2: Load the near table into a pandas DataFrame
    near_table_path = os.path.join(gdb_path, near_table_name)
    print(f"Near table path: {near_table_path}")
    print(f"near table exists: {arcpy.Exists(near_table_path)}")
    # "*" as second arg should return all fields
    #near_array = arcpy.da.TableToNumPyArray(near_table_path, "*")
    #near_table_fields = [field.name for field in arcpy.ListFields(near_table_path)]

    # TODO - modify field list after creating dataframe or add placeholder? - passing empty fields here resulted in TypeError: int() argument must be a string, a bytes-like object or a real number, not 'NoneType'
    near_table_fields = ['IN_FID', 'NEAR_FID', 'NEAR_DIST', 'NEAR_RANK', 'PARCEL_COMBO_FID']
    print(f"Near table fields: {near_table_fields}")
    near_array = arcpy.da.TableToNumPyArray(near_table_path, near_table_fields)
    near_df = pd.DataFrame(near_array)
    print("near_df head:")
    print(near_df.head())

    # TODO - fix issue below
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


def run(building_source_date):
    """
    Run the process to measure distances between buildings and parcels.
    :param building_source_date - string: date of imagery used to extract building footprints in format YYYYMMDD e.g. "20240107"
    """
    start_time = time.time()
    print(f"Starting setback distance calculation with fields holding info on adjacent streets {time.ctime(start_time)}")
    # set environment to feature dataset
    set_environment()
    input_streets = "streets_20241030"
    gdb = os.getenv("GEODATABASE")
    # Paths to input data
    building_fc = f"extracted_footprints_nearmap_{building_source_date}_in_aoi_and_zones_r_th_otmu_li_ao"
    parcel_fc = "parcels_in_zones_r_th_otmu_li_ao"

    # TODO - modify after test or keep in memory only if possible
    # Temporary outputs
    initial_near_table_name = "initial_near_table_64"
    initial_near_table = os.path.join(gdb, initial_near_table_name)
    temp_parcel_lines = "temp_parcel_lines_64"

    # Final outputs
    output_near_table = f"test_output_near_table_{building_source_date}_parcel_polygon_64"
    output_combined_lines_fc = "temp_combined_parcel_lines"

    
    # Initialize outputs
    arcpy.management.CreateTable(gdb, output_near_table)
    arcpy.management.CreateFeatureclass(
        gdb, output_combined_lines_fc, "POLYLINE", spatial_reference=parcel_fc
    )

    process_parcel(64, parcel_fc, building_fc, temp_parcel_lines, initial_near_table, output_near_table, output_combined_lines_fc, max_side_fields=4)

    transform_near_table_with_street_info(gdb, initial_near_table_name, input_streets, temp_parcel_lines)
    ## Iterate over each parcel
    #with arcpy.da.SearchCursor(parcel_fc, ["OBJECTID"]) as cursor:
    #    for row in cursor:
    #        parcel_id = row[0]
    #        print(f"Processing parcel {parcel_id}...")
    #        process_parcel(parcel_id, parcel_fc, building_fc, temp_parcel_lines, output_near_table, output_combined_lines_fc, max_side_fields=4)
    ## Join the near table back to building polygons
    #print("Joining near table to building polygons...")
    #arcpy.management.JoinField(building_fc, "OBJECTID", output_near_table, "IN_FID")
    ## Save final outputs
    #arcpy.management.CopyFeatures(output_combined_lines_fc, "path_to_final_parcel_lines")
    #arcpy.management.CopyRows(output_near_table, "path_to_final_near_table")
    elapsed_minutes = (time.time() - start_time) / 60
    print(f"Setback distance calculation with street info fields complete in {round(elapsed_minutes, 2)} minutes.")


# Run the script
if __name__ == "__main__":
    run("20240107")
