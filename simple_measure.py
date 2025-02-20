import os
import time
from collections import defaultdict
import pandas as pd
import numpy as np
import arcpy
from shared import set_environment, drop_gdb_item_if_exists
from base_logger import logger


def get_near_table(building_fc, parcel_line_fc, output_near_table_suffix, max_side_fields=4):
    """
    Generate a near table for the parcel line feature class and the building feature class.
    :param building_fc - string: Path to the building feature class.
    :param parcel_line_fc - string: Path to the parcel line feature class.
    :param output_near_table_suffix - string: Suffix to append to the output near table name.
    :param parcel_building_id_field - string: Name of the field to hold the parcel polygon ID followed by building polygon ID.
    :param max_side_fields - int: Maximum number of fields to add to the near table for holding info on parcel boundary sides.
    :return: Path to the near table.
    """
    # search_radius: 300 feet is enough for most cases but accounting for some exceptions with very long parcels
    search_radius = "800 Feet"
    # closest_count: realized 2/13 that 30 is not enough
    closest_count = 50
    logger.info(f"Generating near table using nearest {closest_count} parcel lines within {search_radius} of each building feature...")
    near_table = os.path.join(os.getenv("GEODATABASE"), f"near_table_{output_near_table_suffix}")
    drop_gdb_item_if_exists(near_table)
    arcpy.analysis.GenerateNearTable(
        in_features=building_fc,
        near_features=parcel_line_fc,
        out_table=near_table,
        search_radius=search_radius,
        location="NO_LOCATION",
        angle="NO_ANGLE",
        closest="ALL",
        closest_count=closest_count,
        method="PLANAR",
        distance_unit="Feet"
    )

    logger.info(f"Adding fields with side info to near table...")
    for i in range(1, max_side_fields + 1):
        arcpy.management.AddField(near_table, f"FACING_STREET_{i}_PB_FID", "LONG")
        arcpy.management.AddField(near_table, f"FACING_STREET_{i}_DIST_FT", "FLOAT")
        arcpy.management.AddField(near_table, f"OTHER_SIDE_{i}_PB_FID", "LONG")
        arcpy.management.AddField(near_table, f"OTHER_SIDE_{i}_DIST_FT", "FLOAT")

        arcpy.management.CalculateField(near_table, f"FACING_STREET_{i}_PB_FID", -1, "PYTHON3")
        arcpy.management.CalculateField(near_table, f"FACING_STREET_{i}_DIST_FT", -1, "PYTHON3")
        arcpy.management.CalculateField(near_table, f"OTHER_SIDE_{i}_PB_FID", -1, "PYTHON3")
        arcpy.management.CalculateField(near_table, f"OTHER_SIDE_{i}_DIST_FT", -1, "PYTHON3")

    return near_table


def get_near_table_with_parcel_info(near_table, parcel_line_fc, output_table_name):
    """
    Join near table with table from parcel line feature class to get parcel line and polygon IDs as well as shared boundary info.
    :param near_table: Path to the near table.
    :param parcel_line_fc: Path to the parcel line feature class.
    :param output_table_name: Name of the output table.
    :return: Path to the near table with parcel info.
    """
    parcel_line_df = pd.DataFrame(arcpy.da.TableToNumPyArray(parcel_line_fc, ["parcel_line_OID", "shared_boundary", "parcel_polygon_OID"]))
    near_table_fields = [f.name for f in arcpy.ListFields(near_table)]
    logger.debug(f"Near table fields: {near_table_fields}")
    near_array = arcpy.da.TableToNumPyArray(near_table, near_table_fields)
    near_df = pd.DataFrame(near_array)
    logger.debug("near_df:")
    logger.debug(near_df)
    # Merge the near table with the spatial join results to identify adjacent streets
    merged_df = near_df.merge(parcel_line_df, left_on="NEAR_FID", right_on="parcel_line_OID", how="left")
    logger.debug("merged_df head:")
    logger.debug(merged_df.head())
    logger.debug("merged_df where IN_FID is 1:")
    logger.debug(merged_df[merged_df["IN_FID"] == 1])
    logger.debug("merged_df where IN_FID is 2:")
    logger.debug(merged_df[merged_df["IN_FID"] == 2])
    output_fields = [(col, "f8" if "DIST" in col else ("i4" if merged_df[col].dtype.kind in 'i' else "<U50")) for col in merged_df.columns]
    output_array = np.array([tuple(row) for row in merged_df.to_records(index=False)], dtype=output_fields)
    output_table = os.path.join(os.getenv("GEODATABASE"), output_table_name)
    drop_gdb_item_if_exists(output_table)
    arcpy.da.NumPyArrayToTable(output_array, output_table)
    return output_table


def trim_near_table(near_table, building_parcel_join_fc, parcel_id_table):
    """
    Trim the near table to include only the nearest parcel lines.
    :param near_table: Path to the near table (that includes parcel info).
    :param building_parcel_join_fc: Path to the feature class (or name if in working feature dataset) that links each building polygon ID to the ID of the parcel polygon it is contained by.
    :param parcel_id_table: Path to the table that links each parcel polygon OID to the parcel line OIDs that share a boundary with the given polygon.
    :return: Path to the trimmed near table.
    """
    logger.info("Trimming near table...")
    # Create a copy of the near table
    trimmed_near_table = os.path.join(os.getenv("GEODATABASE"), "trimmed_near_table_with_parcel_info")
    arcpy.management.CopyRows(near_table, trimmed_near_table)
    # new field must be added before creating a table view
    arcpy.management.AddField(trimmed_near_table, "intended_parcel_polygon_OID", "LONG")

    # Create views from tables and necesary layer from feature class
    trimmed_near_table_view = "trimmed_near_table_view"
    arcpy.management.MakeTableView(trimmed_near_table, trimmed_near_table_view)
    parcel_id_table_view = "parcel_id_table_view"
    arcpy.management.MakeTableView(parcel_id_table, parcel_id_table_view)
    building_parcel_join_layer = "building_parcel_join_layer"
    arcpy.management.MakeFeatureLayer(building_parcel_join_fc, building_parcel_join_layer)

    # join to get parcel ids that correspond to buildings
    # building polygon ID is: 
    #   IN_FID of near table and 
    #   TARGET_FID of buildings_with_parcel_ids
    arcpy.management.AddJoin(
        in_layer_or_view=trimmed_near_table_view,
        in_field="IN_FID",
        join_table=building_parcel_join_layer,
        join_field="TARGET_FID",
        join_type="KEEP_ALL",
        index_join_fields="NO_INDEX_JOIN_FIELDS",
        rebuild_index="NO_REBUILD_INDEX",
        join_operation=""
    )
    join_table = os.path.join(os.getenv("GEODATABASE"), "trimmed_near_table_after_first_join")
    arcpy.management.CopyRows(trimmed_near_table_view, join_table)
    join_table_fields = arcpy.ListFields(join_table)
    logger.debug(f"Fields in join_table after FIRST join: {[f.name for f in join_table_fields]}\n")
    trimmed_near_table_view_fields = arcpy.ListFields(trimmed_near_table_view)
    logger.debug(f"Fields in trimmed_near_table_view after FIRST join: {[f.name for f in trimmed_near_table_view_fields]}\n")
    expression = f"int(!{building_parcel_join_fc}.parcel_polygon_OID!)"
    logger.debug(f"expression used in CalculateField for intended_parcel_polygon_OID: {expression}")
    arcpy.management.CalculateField(
        in_table=trimmed_near_table_view,
        field="intended_parcel_polygon_OID",
        #expression="int(!buildings_with_parcel_ids.enclosing_parcel_polygon_oid!)",
        expression=expression,
        expression_type="PYTHON3",
        code_block="",
        field_type="LONG",
        enforce_domains="NO_ENFORCE_DOMAINS"
    )
    logger.debug("intended_parcel_polygon_OID field UPDATED in trimmed_near_table_view!!!!!")
    logger.debug(f"trimmed_near_table: {trimmed_near_table}")
    trimmed_near_table_name = trimmed_near_table.split("\\")[-1]
    logger.debug(f"trimmed_near_table_name: {trimmed_near_table_name}")

    fields = arcpy.ListFields(trimmed_near_table_view)
    logger.debug(f"Fields in trimmed_near_table_view after first join: {[f.name for f in fields]}")
    # TODO clean up dirty field names!!
    parcel_polygon_OID_field = 'trimmed_near_table_with_parcel_info.intended_parcel_polygon_OID'
    arcpy.management.AddJoin(
        in_layer_or_view=trimmed_near_table_view,
        in_field=parcel_polygon_OID_field,
        join_table=parcel_id_table_view,
        join_field="parcel_polygon_OID",
        join_type="KEEP_ALL",
        index_join_fields="NO_INDEX_JOIN_FIELDS",
        rebuild_index="NO_REBUILD_INDEX",
        join_operation="JOIN_ONE_TO_MANY"
    )
    fields = arcpy.ListFields(parcel_id_table_view)

    logger.debug("first row of parcel_id_table_view:")
    with arcpy.da.SearchCursor(parcel_id_table_view, [f.name for f in fields]) as cursor:
        for row in cursor:
            logger.info(row)
            break

    trimmed_near_table_2_name = "updated_trimmed_near_table_with_parcel_info"
    trimmed_near_table_2 = os.path.join(os.getenv("GEODATABASE"), trimmed_near_table_2_name)
    arcpy.management.CopyRows(trimmed_near_table_view, trimmed_near_table_2)
    #fields = arcpy.ListFields(trimmed_near_table_2)
    field_names = [f.name for f in arcpy.ListFields(trimmed_near_table_2)]
    logger.debug(f"Fields in trimmed_near_table_2 (after second join): {field_names}")
    # TODO - get full names of fields modified due to join?
    parcel_line_OID_field = f"{trimmed_near_table_name}_NEAR_FID"
    parcel_id_table_name = parcel_id_table.split("\\")[-1]
    logger.debug(f"parcel_id_table_name: {parcel_id_table_name}")
    parcel_line_OIDs_field = f"{parcel_id_table_name}_parcel_line_OIDs" 
    logger.debug(f"field used in update cursor for parcel line OIDs: {parcel_line_OIDs_field}")
    delete_count = 0
    logger.debug(f"number of rows in trimmed_near_table_2 before deletion: {arcpy.management.GetCount(trimmed_near_table_2)}")
    #iterate through the rows in the near table and remove rows where value in parcel_line_OID column is not in list in parcel_line_OIDs
    with arcpy.da.UpdateCursor(trimmed_near_table_2, [parcel_line_OID_field, parcel_line_OIDs_field]) as cursor:
        for row in cursor:
            parcel_line_OID = row[0]
            parcel_line_OIDs = row[1]
            # those with null values in parcel_line_OID should be removed as these are buildings that cross multiple parcels
            if not parcel_line_OID or not parcel_line_OIDs or str(parcel_line_OID) not in parcel_line_OIDs:
                cursor.deleteRow()
                delete_count += 1
    logger.debug(f"number of rows deleted from trimmed_near_table_2: {delete_count}")
    logger.debug(f"number of rows in trimmed_near_table_2 after deleting rows: {arcpy.management.GetCount(trimmed_near_table_2)}")
    with arcpy.da.UpdateCursor(trimmed_near_table_2, field_names) as cursor:
        for row in cursor:
            field_count = len(row)
            for i in range(0, field_count):
                # cannot use 'if not row[i]:' because 0 is a valid value in the shared_boundary field
                if row[i] is None:
                    row[i] = -1
            cursor.updateRow(row)

    logger.info(f"Check state of output trimmed near table at: {trimmed_near_table_2}")
    return trimmed_near_table_2


def transform_detailed_near_table(near_table, field_prefix, output_table_name):
    """
    Transform near table into a format that has one record per building and shows all setback values for each building side.
    :param near_table: Path to the near table that includes parcel info.
    :param field_prefix: Name of near table prior to joins.
    :param output_table_name: Name of the output transformed table.
    :return: Path to the transformed near table.
    """
    logger.info("Transforming near table to get one record per building and show all setback values for each building side...")
    fields = [f.name for f in arcpy.ListFields(near_table)]
    logger.debug(f"Near table fields in transform_detailed_near_table(): {fields}")

    in_fid_field = f"{field_prefix}_IN_FID"
    near_fid_field = f"{field_prefix}_NEAR_FID"
    near_dist_field = f"{field_prefix}_NEAR_DIST"
    shared_boundary_field = f"{field_prefix}_shared_boundary"
    
    # Fields for transformed output
    max_sides = 4  # Adjust as necessary
    facing_fields = [f"FACING_STREET_{i}_PB_FID" for i in range(1, max_sides + 1)] + \
                    [f"FACING_STREET_{i}_DIST_FT" for i in range(1, max_sides + 1)]
    other_side_fields = [f"OTHER_SIDE_{i}_PB_FID" for i in range(1, max_sides + 1)] + \
                        [f"OTHER_SIDE_{i}_DIST_FT" for i in range(1, max_sides + 1)]
    setback_fields = sorted(facing_fields + other_side_fields)
    output_fields = [in_fid_field] + setback_fields
    
    # Create a dictionary to store transformed results
    transformed_data = defaultdict(lambda: {
        field: -1 for field in output_fields  # Initialize fields with -1
    })
    
    # Read input table using SearchCursor
    with arcpy.da.SearchCursor(near_table, [in_fid_field, near_fid_field, near_dist_field, shared_boundary_field]) as cursor:
        for row in cursor:
            in_fid, near_fid, distance, shared_boundary = row
            record = transformed_data[in_fid]
            record[in_fid_field] = in_fid
            if shared_boundary == 0:
                # Facing street side
                for i in range(1, max_sides + 1):
                    if record[f"FACING_STREET_{i}_PB_FID"] == -1:
                        record[f"FACING_STREET_{i}_PB_FID"] = near_fid
                        record[f"FACING_STREET_{i}_DIST_FT"] = distance
                        break
            elif shared_boundary == 1:
                # Other side
                for i in range(1, max_sides + 1):
                    if record[f"OTHER_SIDE_{i}_PB_FID"] == -1:
                        record[f"OTHER_SIDE_{i}_PB_FID"] = near_fid
                        record[f"OTHER_SIDE_{i}_DIST_FT"] = distance
                        break
    
    # Create output table
    # TODO - pass full path to function to avoid use of getenv in function
    gdb_path = os.getenv("GEODATABASE")
    arcpy.management.CreateTable(gdb_path, output_table_name)
    output_table = os.path.join(gdb_path, output_table_name)
    for field in output_fields:
        arcpy.management.AddField(output_table, field, "LONG" if "PB_FID" in field else "FLOAT")
    
    # Insert transformed data using InsertCursor
    with arcpy.da.InsertCursor(output_table, output_fields) as cursor:
        for record in transformed_data.values():
            cursor.insertRow([record[field] for field in output_fields])
    
    return output_table


def join_transformed_near_table_to_building_fc(near_table, building_fc, trimmed_table_name, output_fc_name):
    """
    Join the transformed near table to the original building feature class.
    :param near_table: Path to the transformed near table.
    :param building_fc: Path to the building feature class.
    :param trimmed_table_name: Name of the near table prior to joins in trim_near_table() to be used as prefix in field name e.g. 'trimmed_near_table_with_parcel_info'.
    :param output_fc_name: Path to the output feature class.
    :return: Path to the output feature class.
    """
    near_table_view = "near_table_view"
    arcpy.management.MakeTableView(near_table, near_table_view)
    building_layer = "building_layer"
    arcpy.management.MakeFeatureLayer(building_fc, building_layer)
    near_table_in_fid_field = f"{trimmed_table_name}_IN_FID"
    arcpy.management.AddJoin(
        in_layer_or_view=building_layer,
        in_field="OBJECTID",
        join_table=near_table_view,
        join_field=near_table_in_fid_field,
        join_type="KEEP_ALL",
        index_join_fields="NO_INDEX_JOIN_FIELDS",
        rebuild_index="NO_REBUILD_INDEX",
        join_operation=""
    )
    output_fc = os.path.join(os.getenv("FEATURE_DATASET"), output_fc_name)
    drop_gdb_item_if_exists(output_fc)
    arcpy.management.CopyFeatures(building_layer, output_fc_name)
    logger.info(f"Check full output feature class at: {output_fc}")
    return output_fc


def rename_fields(full_results_fc, trimmed_table_name, output_fc_name):  
    """
    Rename fields in the full output feature class - original field names are in aliases after all joins, and aliases contain trimmed table name.
    :param full_results_fc: Path to the full output feature class.
    :param trimmed_table_name: Name of the near table prior to joins in trim_near_table() to be used as prefix in field name e.g. 'trimmed_near_table_with_parcel_info'.
    :param output_fc_name: Name of the output feature class with renamed fields.
    :return: Path to the output feature class.
    """
    fields = [f for f in arcpy.ListFields(full_results_fc) if f.type not in ["Geometry", "OID"]]
    results_layer = "results_layer"
    arcpy.management.MakeFeatureLayer(full_results_fc, results_layer)
    for f in fields:
        if trimmed_table_name in f.aliasName:
            new_field_name = f.aliasName.replace(f"{trimmed_table_name}_", "")
            arcpy.management.AlterField(results_layer, f.name, new_field_name, new_field_name)
        elif f.aliasName != "OBJECTID" and f.name != "OBJECTID" and f.name != "SHAPE@":
            arcpy.management.AlterField(results_layer, f.name, f.aliasName, f.aliasName)
        elif f.aliasName == "OBJECTID":
            arcpy.management.DeleteField(results_layer, f.name)
    arcpy.management.CopyFeatures(results_layer, output_fc_name)
    output_fc = os.path.join(os.getenv("FEATURE_DATASET"), output_fc_name)
    logger.info(f"Check renamed fields in output feature class at: {output_fc}")
    return output_fc
        

def filter_results(results_fc, setback_count_max, filtered_fc_name):
    """
    Filter the results feature class to include only those buildings with:
     - a max number of setback distances and 
     - no setback distances of zero (meaning the building footprint extends beyond the parcel boundary)
    :param results_fc: Path to the results feature class.
    :param setback_count_max: Maximum number of setback distances to keep a building (those with too many distances may introduce errors)
    :param filtered_fc_name: Name of the filtered feature class.
    :return filtered_fc: Path to the filtered feature class.
    """
    drop_gdb_item_if_exists(filtered_fc_name)
    arcpy.management.CopyFeatures(results_fc, filtered_fc_name)
    fields = arcpy.ListFields(results_fc)
    all_field_names = [f.name for f in fields]
    logger.debug(f"All field names from results fc: {all_field_names}")
    # sort field names to get FACING_STREET fields checked before OTHER_SIDE fields
    field_names = sorted([f.name for f in fields if "DIST" in f.name])
    with arcpy.da.UpdateCursor(filtered_fc_name, field_names) as cursor:
        for row in cursor:
            setback_values = []
            for i in range(0, len(field_names)):
                if row[i] and row[i] > -1:
                    setback_values.append(row[i])
            if len(setback_values) > setback_count_max or 0 in setback_values:
                cursor.deleteRow()
    filtered_fc = os.path.join(os.getenv("FEATURE_DATASET"), filtered_fc_name)
    logger.info(f"Check filtered results feature class at: {filtered_fc}")
    return filtered_fc


def get_average(results_fc, setback_type):
    """
    Create a table holding average setback distances for building sides facing streets (non) and for those not facing streets (shared boundaries).
    :param results_fc - string: Path to the filtered results feature class.
    :param setback_type - string: Type of setback to calculate averages - either "FACING_STREET" or "OTHER_SIDE".
    :return: dict containing the sum, count, and average of the setback distances.
    """
    fields = arcpy.ListFields(results_fc)
    setback_sum = 0
    setback_count = 0
    field_names = [f.name for f in fields if setback_type in f.name and "DIST" in f.name]
    with arcpy.da.SearchCursor(results_fc, field_names) as cursor:
        for row in cursor:
            for i in range(0, len(field_names)):
                if row[i] is not None and row[i] > -1:
                    setback_sum += row[i]
                    setback_count += 1
    setback_average = setback_sum / setback_count
    results_dict = {"sum": setback_sum, "count": setback_count, "average": setback_average}
    print(f"sum, count, and average for {setback_type}: {results_dict}")
    return results_dict


def create_average_table(filtered_fc, output_table_name):
    """
    Create a table holding average setback distances for building sides facing streets (non) and for those not facing streets (shared boundaries).
    :param output_table_name - string: Name of the output table.
    :return: Path to the output table.
    """
    drop_gdb_item_if_exists(output_table_name)
    arcpy.management.CreateTable(os.getenv("GEODATABASE"), output_table_name)
    output_table = os.path.join(os.getenv("GEODATABASE"), output_table_name)
    arcpy.management.AddField(output_table, "setback_type", "TEXT")
    arcpy.management.AddField(output_table, "sum", "DOUBLE")
    arcpy.management.AddField(output_table, "count", "LONG")
    arcpy.management.AddField(output_table, "average", "DOUBLE")
    facing_street_averages = get_average(filtered_fc, "FACING_STREET")
    other_side_averages = get_average(filtered_fc, "OTHER_SIDE")
    output_table_view = os.path.join(os.getenv("GEODATABASE"), "output_table_view")
    arcpy.management.MakeTableView(output_table, output_table_view)
    with arcpy.da.InsertCursor(output_table_view, ["setback_type", "sum", "count", "average"]) as cursor:
        cursor.insertRow(["facing street"] + list(facing_street_averages.values()))
        cursor.insertRow(["other side"] + list(other_side_averages.values()))
    print(f"Check average table at: {output_table}")
    return output_table


def run(building_fc, parcel_line_fc, building_parcel_join_fc, parcel_id_table, output_near_table_suffix, max_side_fields=4):
    """
    Run the process to measure distances between buildings and parcels.
    :param building_fc - string: Path to the building (polygon) feature class.
    :param parcel_line_fc - string: Path to the parcel line feature class.
    :param building_parcel_join_fc: Path to the feature class (or name if in working feature dataset) that links each building polygon ID to the ID of the parcel polygon it is contained by.
    :param parcel_id_table - string: Path to the table that links each parcel polygon OID to the parcel line OIDs that 
        share a boundary with the given polygon (output of get_parcel_id_table() in prep_data.py).
    :param output_near_table_suffix - string: Suffix to append to the output near table name.
    :param max_side_fields - int: Maximum number of fields to add to the near table for holding info on parcel boundary sides.
    """
    start_time = time.time()
    logger.info(f"Starting setback distance calculation with fields holding info on adjacent streets {time.ctime(start_time)}")
    # set environment to feature dataset
    set_environment()
    
    # TODO - fix hardcoded names of feature classes and intermediate tables/fc's
    near_table = get_near_table(building_fc, parcel_line_fc, output_near_table_suffix, max_side_fields=max_side_fields)
    near_table_with_parcel_info = get_near_table_with_parcel_info(near_table, parcel_line_fc, f"near_table_with_parcel_info_{output_near_table_suffix}")
    trimmed_table_name = "trimmed_near_table_with_parcel_info"
    trimmed_near_table = trim_near_table(near_table_with_parcel_info, building_parcel_join_fc, parcel_id_table)
    transformed_table_name = f"transformed_near_table_{output_near_table_suffix}"
    transformed_near_table = transform_detailed_near_table(trimmed_near_table, trimmed_table_name, transformed_table_name)
    full_output_fc_name = f"buildings_with_setback_values_{output_near_table_suffix}"
    full_output_fc = join_transformed_near_table_to_building_fc(transformed_near_table, building_fc, trimmed_table_name, full_output_fc_name)
    clean_fc_name = f"clean_{full_output_fc_name}"
    clean_output_fc = rename_fields(full_output_fc, trimmed_table_name, clean_fc_name)
    filtered_fc_name = f"filtered_results_{output_near_table_suffix}"
    filtered_fc = filter_results(clean_output_fc, 4, filtered_fc_name)
    create_average_table(filtered_fc, f"averages_{output_near_table_suffix}")
    elapsed_minutes = (time.time() - start_time) / 60
    logger.info(f"Setback distance calculation with street info fields complete in {round(elapsed_minutes, 2)} minutes.")


# Run the script
if __name__ == "__main__":
    set_environment()
    building_fc = "extracted_footprints_nearmap_20240107_in_aoi_and_zones_r_th_otmu_li_ao"
    parcel_line_fc = "parcel_lines_from_polygons_20250218"
    gdb_path = os.getenv("GEODATABASE")
    # TODO - better to prevent user from naming the parcel_id_table??
    parcel_id_table_name = "parcel_id_table_20250218"
    parcel_id_table = os.path.join(gdb_path, parcel_id_table_name)
    output_near_table_suffix = "nm_20240107_20250218"
    #building_parcel_join_fc = "buildings_with_parcel_ids"
    building_parcel_join_fc = "building_parcel_join_20250218"
    run(building_fc, parcel_line_fc, building_parcel_join_fc, parcel_id_table, output_near_table_suffix, max_side_fields=4)
