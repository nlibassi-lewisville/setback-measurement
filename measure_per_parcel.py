import os
import math
import arcpy
import time
import pandas as pd
import numpy as np
from shared import set_environment


def calculate_angle(geometry):
    """
    Calculate the angle (bearing) of a line geometry in degrees, accounting for bidirectional lines.
    :param geometry: The geometry object of the line.
    :return: Angle in degrees (0-360).
    """
    start = geometry.firstPoint
    end = geometry.lastPoint
    dx = end.X - start.X
    dy = end.Y - start.Y
    angle = math.degrees(math.atan2(dy, dx))
    # Normalize to 0-360 degrees
    angle = angle % 360
    # Normalize the angle to the range 0-180 (to account for bidirectional lines)
    if angle > 180:
        angle -= 180
    return angle


def is_parallel(angle1, angle2, tolerance=10):
    """
    Check if two angles are roughly parallel within a given tolerance.
    :param angle1: Angle of the first line in degrees.
    :param angle2: Angle of the second line in degrees.
    :param tolerance: Tolerance in degrees for determining parallelism.
    :return: True if angles are roughly parallel, False otherwise.
    """
    diff = abs(angle1 - angle2)
    return diff <= tolerance


def clip_streets_near_parcel(parcel_fc, parcel_id, street_fc, output_street_fc, buffer_ft=30):
    """
    Clip streets near a parcel to avoid measuring distances to distant streets.
    :param parcel_fc: Path to the parcel feature class.
    :param parcel_id: The OBJECTID of the parcel to clip streets near.
    :param street_fc: Path to the street feature class.
    :param output_street_fc: Path to the output street feature class.
    :param buffer_ft: Distance in feet to buffer around the parcel.
    """
    print(f"Attempting to clip streets near parcel {parcel_id}...")
    arcpy.management.Delete("current_parcel")
    # Isolate the current parcel
    parcel_layer = "current_parcel"
    arcpy.management.MakeFeatureLayer(parcel_fc, parcel_layer, f"OBJECTID = {parcel_id}")
    
    # TODO - ask for permission to delete output feature class?
    arcpy.management.Delete(output_street_fc)
    arcpy.management.Delete("parcel_buffer")
    print("output_street_fc and parcel_buffer deleted")
    #arcpy.management.SelectLayerByAttribute(parcel_fc, "NEW_SELECTION", f"OBJECTID = {parcel_id}")

    parcel_buffer = "parcel_buffer"

    # TODO - create buffer in memory or delete when finished
    arcpy.analysis.Buffer(
    in_features=parcel_layer,
    out_feature_class=parcel_buffer,
    buffer_distance_or_field=f"{buffer_ft} Feet",
    line_side="FULL",
    line_end_type="ROUND",
    dissolve_option="NONE",
    dissolve_field=None,
    method="PLANAR"
    )
    print("Buffer created")
    # Buffer the parcel to clip streets
    #buffer_layer = "parcel_buffer"
    #arcpy.analysis.Buffer(parcel_layer, buffer_layer, f"{buffer_ft} Feet")

    # Clip streets near the parcel - returns almost all streets (but because the buffer created was too large - may be able to return to this)
    arcpy.analysis.Clip(street_fc, parcel_buffer, output_street_fc)


    # TODO - find faster solution for this?
    #arcpy.gapro.ClipLayer(
    #    input_layer=street_fc,
    #    clip_layer=parcel_buffer,
    #    out_feature_class=output_street_fc,
    #    )



def populate_parallel_field(parcel_street_join_fc, parcel_lines_fc, street_name_field, parallel_field, street_fc):
    """
    Populate a field in the parcel-street join table with info on whether or not each segment is parallel to the street.
    :param parcel_street_join_fc: Path to the feature class resulting from the spatial join between parcel boundary segments and streets.
    :param parcel_lines_fc: Path to the parcel line feature class.
    :param street_name_field: Name of the field in the parcel_street_join_fc that contains the street name associated with each parcel boundary segment feature.
    :param parallel_field: Name of the field to populate with parallelism info.
    :param street_fc: Path to the street feature class.
    """
    print("Attempting to populate parallel field...")

    parcel_lines_fc = "parcel_lines"

    # TODO - move spatial join and addition of "is_parallel_to_street" to separate function!!

    #Pre-compute spatial relationships between parcel lines and streets
    #parcel_street_join = os.path.join(gdb_path, "parcel_street_join")
    if arcpy.Exists(parcel_street_join_fc):
        arcpy.management.Delete(parcel_street_join_fc)

    print("Performing spatial join between parcel lines and streets...")

    #TODO: # Use a search radius that is appropriate for the data
    # value of join_type may not matter when join_operation is JOIN_ONE_TO_MANY
    arcpy.analysis.SpatialJoin(parcel_lines_fc, street_fc, parcel_street_join_fc, join_operation="JOIN_ONE_TO_MANY", join_type="KEEP_COMMON", 
        match_option="WITHIN_A_DISTANCE", search_radius="50 Feet")
    
    # TODO - may be able to remove fields list and if statement after testing
    join_fields = arcpy.ListFields(parcel_street_join_fc)
    if not any(field.name == "is_parallel_to_street" for field in join_fields):
        arcpy.management.AddField(parcel_street_join_fc, "is_parallel_to_street", "TEXT", field_length=10)

    # TODO - remove TARGET_FID if not needed - only included for testing/logging
    with arcpy.da.UpdateCursor(parcel_street_join_fc, ["SHAPE@", street_name_field, parallel_field, "TARGET_FID"]) as cursor:
        for row in cursor:
            parcel_geom = row[0]
            street_name = row[1]
            parcel_segment_id = row[3]
            
            # Get the angle of the parcel segment
            parcel_angle = calculate_angle(parcel_geom)
            
            # Use a cursor to find the associated street geometry
            street_angle = None
            with arcpy.da.SearchCursor(street_fc, ["SHAPE@", "StFULLName"]) as street_cursor:
                for street_row in street_cursor:
                    if street_row[1] == street_name:
                        street_angle = calculate_angle(street_row[0])
                        break
            
            # Check if the angles are parallel
            if street_angle is not None:
                row[2] = "Yes" if is_parallel(parcel_angle, street_angle, tolerance=10) else "No"
            else:
                row[2] = "No Match"
            
            cursor.updateRow(row)

    # from Copilot - remove if not needed
    # Load the join table into a pandas DataFrame
    #join_array = arcpy.da.TableToNumPyArray(parcel_street_join_fc, ["TARGET_FID", "StFULLName", "Angle"])
    #join_df = pd.DataFrame(join_array)
    #join_df = join_df.rename(columns={"TARGET_FID": "PB_FID", "StFULLName": "STREET_NAME", "Angle": "STREET_ANGLE"})
    ## Load the street feature class into a pandas DataFrame
    #street_array = arcpy.da.FeatureClassToNumPyArray(street_fc, ["OBJECTID", "Angle"])
    #street_df = pd.DataFrame(street_array)
    #street_df = street_df.rename(columns={"OBJECTID": "STREET_FID", "Angle": "STREET_ANGLE"})
    ## Merge the join table with the street table to get street angles
    #merged_df = join_df.merge(street_df, left_on="PB_FID", right_on="STREET_FID", how="left")
    ## Populate the parallel field based on angle comparison
    #merged_df[parallel_field] = merged_df.apply(
    #    lambda row: is_parallel(row["STREET_ANGLE"], row["STREET_ANGLE"]), axis=1
    #)
    ## Convert output to a NumPy structured array and write to the table
    #output_array = np.array([tuple(row) for row in merged_df.to_records(index=False)])
    #arcpy.da.NumPyArrayToTable(output_array, parcel_street_join_fc)


def process_parcel(parcel_id, all_parcel_polygons_fc, building_fc, initial_near_table, output_near_table, output_lines_fc, max_side_fields=4):
    """
    Process a single parcel: convert to lines, measure distances, and generate a near table.
    :param parcel_id: The OBJECTID of the parcel being processed.
    :param all_parcel_polygons_fc: Path to the polygon feature class holding all parcels.
    :param building_fc: Path to the building polygon feature class.
    TODO remove if not needed  
    :param parcel_lines_fc: Path to the temporary parcel line feature class.

    :param output_near_table: Path to the temporary output near table.
    :param output_lines_fc: Path to the combined output parcel line feature class.
    """
    # TODO - clean up naming
    #arcpy.management.Delete("current_parcel2")
    ## Isolate the current parcel
    #parcel_layer = "current_parcel_test"
    print(f"all_parcel_polygons_fc: {all_parcel_polygons_fc}")
    arcpy.management.MakeFeatureLayer(all_parcel_polygons_fc, "parcel_polygon_layer", f"OBJECTID = {parcel_id}")

    parcel_lines_fc = f"parcel_lines_{parcel_id}"
    # Convert parcel polygon to lines
    arcpy.management.PolygonToLine("parcel_polygon_layer", parcel_lines_fc)
    # Add a field to store the polygon parcel ID
    arcpy.management.AddField(parcel_lines_fc, "PARCEL_POLYGON_OID", "LONG")
    arcpy.management.CalculateField(parcel_lines_fc, "PARCEL_POLYGON_OID", f"{parcel_id}")
    # TODO - uncomment and fix after processing single parcel
    #arcpy.management.Append(parcel_lines_fc, output_lines_fc, "NO_TEST")

    parcel_points_fc = f"parcel_points_{parcel_id}"

    # original - before refactoring
    #arcpy.management.FeatureVerticesToPoints(parcel_lines_fc, parcel_points_fc, "ALL")
    arcpy.management.FeatureVerticesToPoints("parcel_polygon_layer", parcel_points_fc, "ALL")
    #arcpy.management.SplitLineAtPoint(parcel_lines_fc, parcel_points_fc, split_parcel_lines_fc)
    split_parcel_lines_fc = f"split_parcel_lines_{parcel_id}"
    # TODO - adjust search radius if necessary
    # original - before refactoring
    #arcpy.management.SplitLineAtPoint(parcel_lines_fc, parcel_points_fc, split_parcel_lines_fc, search_radius="500 Feet")
    arcpy.management.SplitLineAtPoint(parcel_lines_fc, parcel_points_fc, split_parcel_lines_fc, search_radius="500 Feet")

    # Select buildings inside the parcel
    #building_layer = "building_layer"
    arcpy.management.MakeFeatureLayer(building_fc, "building_layer")
    print(f"Selecting building(s) inside parcel {parcel_id}...")
    print(f"building_fc: {building_fc}")
    #with arcpy.da.SearchCursor(building_fc, ["OBJECTID"]) as cursor:
    #    for row in cursor:
    #        print(row)
    #print(f"parcel_layer: {parcel_layer}")
    #print(f"number of features in parcel_layer: {arcpy.management.GetCount(parcel_layer)}")
    #with arcpy.da.SearchCursor(parcel_layer, ["OBJECTID"]) as cursor:
    #    for row in cursor:
    #        print(row)
    #arcpy.management.SelectLayerByLocation(building_layer, "WITHIN", parcel_layer)
    #arcpy.management.SelectLayerByLocation("building_layer", "WITHIN", "parcel_layer")
    arcpy.management.SelectLayerByLocation("building_layer", "WITHIN", "parcel_polygon_layer")

    # ok to have multiple buildings in a parcel 
    #count = arcpy.management.GetCount(building_fc)
    #count_result = int(count.getOutput(0))
    #if count_result != "1":
    #    print(f"WARNING: {count_result} buildings found inside parcel {parcel_id}.")
    building_polygon_ids = []
    with arcpy.da.SearchCursor(building_fc, ["OBJECTID"]) as cursor:
        for row in cursor:
            building_polygon_ids.append(row[0])

    string_ids = ", ".join(str(id) for id in building_polygon_ids)
    query = f"OBJECTID in ({string_ids})"
    building_layer = f"buildings_in_parcel_{parcel_id}"
    arcpy.management.MakeFeatureLayer(building_fc, building_layer, query)

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


def transform_near_table_with_street_info(gdb_path, near_table_name, parcel_street_join, street_fc, parcel_lines_fc):
    """
    Transform near table to include info on adjacent street(s) and other side(s).
    :param gdb_path: Path to the geodatabase.
    :param near_table_name: Name of the near table.
    :param street_fc: Path to feature class resulting from join of parcel line feature class with streets feature class.

    :param street_fc: Path to the street feature class.
    :param parcel_lines_fc: Path to the parcel line feature class.
    :return: Path to the transformed near table.
    """
    print("Transforming near table to include info on adjacent street(s) and other side(s)...")


    # Load spatial join results into a pandas DataFrame
    join_array = arcpy.da.TableToNumPyArray(parcel_street_join, ["TARGET_FID", "StFULLName"])
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
    print("merged_df:")
    print(merged_df)
    merged_df["is_facing_street"] = merged_df["STREET_NAME"].notna()
    merged_df = merged_df.drop_duplicates(subset=["NEAR_DIST", "PARCEL_COMBO_FID", "STREET_NAME"])
    print("merged_df after adding is_facing_street and dropping duplicates:")
    print(merged_df)

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
    # TODO - update or remove parcel id from name
    transformed_table_path = os.path.join(gdb_path, "transformed_near_table_with_street_info_parcel_62")
    if arcpy.Exists(transformed_table_path):
        arcpy.management.Delete(transformed_table_path)

    arcpy.da.NumPyArrayToTable(output_array, transformed_table_path)
    print(f"Transformed near table written to: {transformed_table_path}")
    return transformed_table_path


def run(building_source_date, parcel_id, all_parcel_lines_fc):
    """
    Run the process to measure distances between buildings and parcels.
    :param building_source_date - string: date of imagery used to extract building footprints in format YYYYMMDD e.g. "20240107"
    :param parcel_id - int: OBJECTID of the parcel to process
    :param all_parcel_lines_fc - string: path to the feature class holding all parcel lines
    """
    start_time = time.time()
    print(f"Starting setback distance calculation with fields holding info on adjacent streets {time.ctime(start_time)}")
    # set environment to feature dataset
    set_environment()
    input_streets = "streets_20241030"
    gdb = os.getenv("GEODATABASE")
    feature_dataset = os.getenv("FEATURE_DATASET")
    # Paths to input data
    # TODO - pass these as arguments to run() after testing
    building_fc = f"extracted_footprints_nearmap_{building_source_date}_in_aoi_and_zones_r_th_otmu_li_ao"
    parcel_polygon_fc = "parcels_in_zones_r_th_otmu_li_ao"

    # TODO - modify after test or keep in memory only if possible
    # Temporary outputs
    initial_near_table_name = f"initial_near_table_{parcel_id}"
    initial_near_table = os.path.join(gdb, initial_near_table_name)
    temp_parcel_lines = f"temp_parcel_lines_{parcel_id}"

    # TODO - ensure that temp_parcel_lines is created...

    # Final outputs
    output_near_table = f"test_output_near_table_{building_source_date}_parcel_polygon_{parcel_id}"
    output_combined_lines_fc = "temp_combined_parcel_lines"

    # Initialize outputs
    arcpy.management.CreateTable(gdb, output_near_table)
    arcpy.management.CreateFeatureclass(
        gdb, output_combined_lines_fc, "POLYLINE", spatial_reference=parcel_polygon_fc
    )

    # TODO - remove hardcoded parcel id after testing
    clipped_street_fc = f"clipped_streets_near_parcel_{parcel_id}"
    clip_streets_near_parcel(parcel_polygon_fc, parcel_id, input_streets, clipped_street_fc, buffer_ft=30)
    parcel_street_join_path = os.path.join(gdb, "parcel_street_join")
    # TODO - add argument for 'all_parcel_lines_fc' to run() - comes from create_parcel_line_fc() in prep_data.py
    populate_parallel_field(parcel_street_join_path, all_parcel_lines_fc, "StFULLName", "is_parallel_to_street", street_fc=clipped_street_fc)

    # parcels tried so far: 64, 62
    #process_parcel(62, parcel_polygon_fc, building_fc, temp_parcel_lines, initial_near_table, output_near_table, output_combined_lines_fc, max_side_fields=4)
    process_parcel(parcel_id, parcel_polygon_fc, building_fc, initial_near_table, output_near_table, output_combined_lines_fc, max_side_fields=4)

    #transform_near_table_with_street_info(gdb, initial_near_table_name, input_streets, temp_parcel_lines)
    # TODO pass the correct split parcel lines fc in a cleaner way after testing
    split_parcel_lines_fc = os.path.join(feature_dataset, f"split_parcel_lines_{parcel_id}")
    arcpy.Delete_management(split_parcel_lines_fc)
    transform_near_table_with_street_info(gdb, initial_near_table_name, parcel_street_join_path, input_streets, split_parcel_lines_fc)
    ## Iterate over each parcel
    #with arcpy.da.SearchCursor(parcel_polygon_fc, ["OBJECTID"]) as cursor:
    #    for row in cursor:
    #        parcel_id = row[0]
    #        print(f"Processing parcel {parcel_id}...")
    #        process_parcel(parcel_id, parcel_polygon_fc, building_fc, temp_parcel_lines, output_near_table, output_combined_lines_fc, max_side_fields=4)
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
    # TODO - remove lines below after testing parallel field population
    #set_environment()
    #street_fc = "streets_20241030"
    #clipped_street_fc = "clipped_streets_near_parcel_62"
    #clip_streets_near_parcel("parcels_in_zones_r_th_otmu_li_ao", 62, street_fc, clipped_street_fc, buffer_ft=30)
    #gdb = os.getenv("GEODATABASE")
    #parcel_street_join_path = os.path.join(gdb, "parcel_street_join")
    #populate_parallel_field(parcel_street_join_path, "StFULLName", "is_parallel_to_street", street_fc=clipped_street_fc)
    run("20240107", 62, "parcel_lines_from_polygons_TEST")
