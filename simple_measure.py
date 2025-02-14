import os
import arcpy
import time
import pandas as pd
import numpy as np
from shared import set_environment, drop_feature_class_if_exists
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
    # for closest_count: 20 was not enough when using 150 feet search radius - realized 2/13 that 30 is not enough (though 300 feet search radius might be)
    search_radius = "800 Feet"
    closest_count = 50
    logger.info(f"Generating near table using nearest {closest_count} parcel lines within {search_radius} of each building feature...")
    near_table = os.path.join(os.getenv("GEODATABASE"), f"near_table_{output_near_table_suffix}")
    drop_feature_class_if_exists(near_table)
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
    #while i < max_side_fields:
        # Add facing street and other side fields
        #i += 1
        arcpy.management.AddField(near_table, f"FACING_STREET_{i}_PB_FID", "LONG")
        arcpy.management.AddField(near_table, f"FACING_STREET_{i}_DIST_FT", "FLOAT")
        arcpy.management.AddField(near_table, f"OTHER_SIDE_{i}_PB_FID", "LONG")
        arcpy.management.AddField(near_table, f"OTHER_SIDE_{i}_DIST_FT", "FLOAT")

        arcpy.management.CalculateField(near_table, f"FACING_STREET_{i}_PB_FID", -1, "PYTHON3")
        arcpy.management.CalculateField(near_table, f"FACING_STREET_{i}_DIST_FT", -1, "PYTHON3")
        arcpy.management.CalculateField(near_table, f"OTHER_SIDE_{i}_PB_FID", -1, "PYTHON3")
        arcpy.management.CalculateField(near_table, f"OTHER_SIDE_{i}_DIST_FT", -1, "PYTHON3")

    # TODO - remove if not needed
    # create a new field to hold the parcel polygon ID followed by building polygon ID in format '1583-1', '1583-7', etc.
    #arcpy.management.AddField(near_table, parcel_building_id_field, "TEXT")
    #arcpy.management.CalculateField(near_table, parcel_building_id_field, -1, "PYTHON3")

    return near_table


# TODO - remove if not needed
def get_parcel_building_dict(spatial_join_output):
    """
    Create a dictionary mapping parcel polygon IDs to building polygon IDs.
    :param spatial_join_output: Path to the spatial join output feature class.
    :return: Dictionary with 
        keys: parcel polygon IDs as keys
        values: a list of IDs of buildings contained by parcels.
    """
    parcel_building_dict = {}
    with arcpy.da.SearchCursor(spatial_join_output, ["TARGET_FID", "JOIN_FID"]) as cursor:
        for row in cursor:
            parcel_id = row[0]
            building_id = row[1]
            if parcel_id not in parcel_building_dict:
                parcel_building_dict[parcel_id] = []
            parcel_building_dict[parcel_id].append(building_id)
    return parcel_building_dict



def get_near_table_with_parcel_info(near_table, parcel_line_fc):
    """
    Join near table with table from parcel line feature class to get parcel line and polygon IDs as well as shared boundary info.
    :param near_table: Path to the near table.
    :param parcel_line_fc: Path to the parcel line feature class.
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
    output_table = os.path.join(os.getenv("GEODATABASE"), "near_table_with_parcel_info_20250212")
    drop_feature_class_if_exists(output_table)
    arcpy.da.NumPyArrayToTable(output_array, output_table)
    return output_table


def trim_near_table(near_table, building_parcel_join_fc, parcel_id_table):
    """
    Trim the near table to include only the nearest parcel lines.
    :param near_table: Path to the near table (that includes parcel info).
    :param building_parcel_join_fc: Path to the feature class that links each building polygon ID to the ID of the parcel polygon it is contained by.
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
    test_join_table = os.path.join(os.getenv("GEODATABASE"), "test_trimmed_near_table_after_first_join")
    arcpy.management.CopyRows(trimmed_near_table_view, test_join_table)

    fields = arcpy.ListFields(test_join_table)
    logger.debug(f"Fields in trimmed_near_table_view after FIRST join: {[f.name for f in fields]}")

    # why was original field_type TEXT here?
    arcpy.management.CalculateField(
        in_table=trimmed_near_table_view,
        field="intended_parcel_polygon_OID",
        expression="int(!buildings_with_parcel_ids.enclosing_parcel_polygon_oid!)",
        expression_type="PYTHON3",
        code_block="",
        field_type="LONG",
        enforce_domains="NO_ENFORCE_DOMAINS"
    )
    logger.debug("intended_parcel_polygon_OID field UPDATED in trimmed_near_table_view!!!!!")
    logger.debug(f"trimmed_near_table: {trimmed_near_table}")
    trimmed_near_table_name = trimmed_near_table.split("\\")[-1]

    # print first row for debugging
    fields = arcpy.ListFields(trimmed_near_table_view)
    logger.debug(f"Fields in trimmed_near_table_view after first join: {[f.name for f in fields]}")
    logger.debug("first row of trimmed_near_table_view after first join:")
    # for debugging only
    #with arcpy.da.SearchCursor(trimmed_near_table_view, [f.name for f in fields]) as cursor:
    #    for row in cursor:
    #        logger.info(row)
    #        break
    #logger.info("first value in field trimmed_near_table_with_parcel_info.intended_parcel_polygon_OID of trimmed_near_table_view:")
    #with arcpy.da.SearchCursor(trimmed_near_table_view, "trimmed_near_table_with_parcel_info.intended_parcel_polygon_OID") as cursor:
    #    for row in cursor:
    #        logger.info(row)
    #        break
    # could work but these are apparently strings e.g. '1583'
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
    #with arcpy.da.SearchCursor(parcel_id_table_view, [f.name for f in fields]) as cursor:
    #    for row in cursor:
    #        logger.info(row)
    #        break

    trimmed_near_table_2_name = "updated_trimmed_near_table_with_parcel_info"
    trimmed_near_table_2 = os.path.join(os.getenv("GEODATABASE"), trimmed_near_table_2_name)
    arcpy.management.CopyRows(trimmed_near_table_view, trimmed_near_table_2)
    fields = arcpy.ListFields(trimmed_near_table_2)
    logger.debug(f"\nFields in trimmed_near_table_2 after second join: {[f.name for f in fields]}")
    # TODO - get full names of fields modified due to join?
    #iterate through the rows in the near table and remove rows where value in parcel_line_OID column is not in list in parcel_line_OIDs

    # expecting'trimmed_near_table_with_parcel_info_parcel_line_OID' below
    parcel_line_OID_field = f"{trimmed_near_table_name}_parcel_line_OID"
    parcel_id_table_name = parcel_id_table.split("\\")[-1]
    logger.debug(f"parcel_id_table_name: {parcel_id_table_name}")
    # expecting 'parcel_id_table_20250212_parcel_line_OIDs' below
    parcel_line_OIDs_field = f"{parcel_id_table_name}_parcel_line_OIDs" 
    #parcel_line_OIDs_field = f"{parcel_id_table_name}.parcel_line_OIDs" 
    logger.debug(f"field used in update cursor for parcel line OIDs: {parcel_line_OIDs_field}")
    with arcpy.da.UpdateCursor(trimmed_near_table_2, [parcel_line_OID_field, parcel_line_OIDs_field]) as cursor:
        for row in cursor:
            parcel_line_OID = row[0]
            parcel_line_OIDs = row[1]
            if str(parcel_line_OID) not in parcel_line_OIDs:
                cursor.deleteRow()

    logger.info(f"Check state of output trimmed near table at: {trimmed_near_table_2}")
    return trimmed_near_table_2


def transform_detailed_near_table(near_table, field_prefix):
    """
    Transform near table to include info on pairs of building sides and parcel segments that share a parcel boundary (non-street-facing) and do not share a boundary (street-facing).
    :param near_table_name - string: Path to the near table that includes parcel info (output of trim_near_table()).
    :param field_prefix - string: Name of near table prior to joins in trim_near_table() e.g. 'trimmed_near_table_with_parcel_info'.
    :return: Path to the transformed near table.
    """
    logger.info("Transforming near table to get one record per building and show all setback values for each building side...")
    
    # Load near table data into a pandas DataFrame
    fields = [f.name for f in arcpy.ListFields(near_table)]
    near_array = arcpy.da.TableToNumPyArray(near_table, fields)
    near_df = pd.DataFrame(near_array)

    output_data = []
    # prepare field names
    in_fid_field = f"{field_prefix}_IN_FID"
    near_fid_field = f"{field_prefix}_NEAR_FID"
    near_dist_field = f"{field_prefix}_NEAR_DIST"
    facing_street_field_part_1 = f"{field_prefix}_FACING_STREET"
    other_side_field_part_1 = f"{field_prefix}_OTHER_SIDE"
    shared_boundary_field = f"{field_prefix}_shared_boundary"

    # transform table
    for in_fid, group in near_df.groupby(in_fid_field):
        row = {in_fid_field: in_fid}
        facing_count, other_count = 1, 1
        for _, record in group.iterrows():
            near_fid = record[near_fid_field]
            distance = record[near_dist_field]
            # TODO - add parameter for max number of fields for facing street and other side?
            if not record[shared_boundary_field]:
                # limit to x number of facing street sides
                if facing_count <= 4:
                    #row[f"FACING_STREET_{facing_count}"] = record["STREET_NAME"]
                    row[f"{facing_street_field_part_1}_{facing_count}_PB_FID"] = near_fid
                    row[f"{facing_street_field_part_1}_{facing_count}_DIST_FT"] = distance
                    facing_count += 1
            else:
                # limit to x number of other sides
                if other_count <= 4:
                    row[f"{other_side_field_part_1}_{other_count}_PB_FID"] = near_fid
                    row[f"{other_side_field_part_1}_{other_count}_DIST_FT"] = distance
                    other_count += 1
        output_data.append(row)

    # Convert output to a NumPy structured array and write to a table
    output_df = pd.DataFrame(output_data)
    logger.debug(output_df.head())
    output_df.fillna(-1, inplace=True)
    output_fields = [(col, "f8" if "DIST" in col else "i4") for col in output_df.columns]
    logger.debug(f'Output fields: {output_fields}')
    output_array = np.array([tuple(row) for row in output_df.to_records(index=False)], dtype=output_fields)
    gdb_path = os.getenv("GEODATABASE")
    transformed_table_path = os.path.join(gdb_path, "transformed_near_table_with_street_info_parcel_TEST_20250212")
    drop_feature_class_if_exists(transformed_table_path)
    arcpy.da.NumPyArrayToTable(output_array, transformed_table_path)
    logger.info(f"Check transformed near table written to: {transformed_table_path}")
    return transformed_table_path


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
    drop_feature_class_if_exists(output_fc)
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
    # original field names are in aliases after all the joins
    #type_dict = {"String": "TEXT", "Integer": "LONG", "Double": "DOUBLE", "DateOnly": "DATEONLY"}
    fields = [f for f in arcpy.ListFields(full_results_fc) if f.type not in ["Geometry", "OID"]]
    results_layer = "results_layer"
    arcpy.management.MakeFeatureLayer(full_results_fc, results_layer)
    for f in fields:
        if trimmed_table_name in f.aliasName:
            new_field_name = f.aliasName.replace(f"{trimmed_table_name}_", "")
            #arcpy.management.AlterField(results_layer, f.name, new_field_name, new_field_name, field_type=type_dict[f.type])
            arcpy.management.AlterField(results_layer, f.name, new_field_name, new_field_name)
        elif f.aliasName != "OBJECTID" and f.name != "OBJECTID" and f.name != "SHAPE@":
            #arcpy.management.AlterField(results_layer, f.name, f.aliasName, f.aliasName, field_type=type_dict[f.type])
            arcpy.management.AlterField(results_layer, f.name, f.aliasName, f.aliasName)
        elif f.aliasName == "OBJECTID":
            arcpy.management.DeleteField(results_layer, f.name)
        #arcpy.management.AlterField(full_results_fc, f.name, new_field_name, new_field_name, field_type=f.type)
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
    drop_feature_class_if_exists(filtered_fc_name)
    #results_fc_copy = os.path.join(os.getenv("FEATURE_DATASET"), "results_fc_copy")
    arcpy.management.CopyFeatures(results_fc, filtered_fc_name)
    fields = arcpy.ListFields(results_fc)
    all_field_names = [f.name for f in fields]
    logger.debug(f"All field names from results fc: {all_field_names}")
    # sort field names to get FACING_STREET fields checked before OTHER_SIDE fields
    field_names = sorted([f.name for f in fields if "DIST" in f.name])
    with arcpy.da.UpdateCursor(filtered_fc_name, [field_names]) as cursor:
        for row in cursor:
            setback_values = []
            for i in range(0, len(field_names)):
                if row[i] > -1:
                    setback_values.append(row[i])
            if len(setback_values) > setback_count_max or 0 in setback_values:
                cursor.deleteRow()
    filtered_fc = os.path.join(os.getenv("FEATURE_DATASET"), filtered_fc_name)
    logger.info(f"Check filtered results feature class at: {filtered_fc}")
    return filtered_fc

# TODO - edit - content of get_averages is mostly from copilot right now!!
def get_averages(results_fc, output_table_name):
    """
    Create a table holding average setback distances for building sides facing streets (non) and for those not facing streets (shared boundaries).
    :param results_fc: Path to the results feature class.
    :param output_table_name: Name of the output table.
    :return: Path to the output table.
    """
    drop_feature_class_if_exists(output_table_name)
    arcpy.management.CopyRows(results_fc, output_table_name)
    fields = arcpy.ListFields(results_fc)

    field_names = [f.name for f in fields if "DIST" in f.name]
    with arcpy.da.UpdateCursor(output_table_name, ["AVERAGE_DISTANCES"]) as cursor:
        for row in cursor:
            total = 0
            count = 0
            for i in range(1, len(field_names) + 1):
                if row[i] > -1:
                    total += row[i]
                    count += 1
            if count > 0:
                row[0] = total / count
                cursor.updateRow(row)
    return output_table_name


def run(building_fc, parcel_line_fc, output_near_table_suffix, spatial_join_output, max_side_fields=4):
    """
    Run the process to measure distances between buildings and parcels.
    :param building_fc - string: Path to the building feature class.
    :param parcel_line_fc - string: Path to the parcel line feature class.
    :param output_near_table_suffix - string: Suffix to append to the output near table name.
    :param spatial_join_output: Path to the spatial join output feature class.
    :param parcel_street_join - string: Path to feature class resulting from join of parcel line feature class with streets feature class.
    """
    start_time = time.time()
    logger.info(f"Starting setback distance calculation with fields holding info on adjacent streets {time.ctime(start_time)}")
    # set environment to feature dataset
    set_environment()
    
    # TODO - uncomment after testing other functions
    near_table = get_near_table(building_fc, parcel_line_fc, output_near_table_suffix, max_side_fields=max_side_fields)
    near_table_with_parcel_info = get_near_table_with_parcel_info(near_table, parcel_line_fc)
    building_parcel_join_fc = "buildings_with_parcel_ids"
    gdb_path = os.getenv("GEODATABASE")
    near_table_with_parcel_info = os.path.join(gdb_path, "near_table_with_parcel_info_20250212")
    parcel_id_table = os.path.join(gdb_path, "parcel_id_table_20250212")
    trimmed_table_name = "trimmed_near_table_with_parcel_info"
    # TODO - uncomment after testing other functions and remove hardcoded paths
    trimmed_near_table = trim_near_table(near_table_with_parcel_info, building_parcel_join_fc, parcel_id_table)
    trimmed_near_table = os.path.join(gdb_path, "updated_trimmed_near_table_with_parcel_info")
    transformed_near_table = transform_detailed_near_table(trimmed_near_table, "trimmed_near_table_with_parcel_info")
    full_output_fc_name = "buildings_with_setback_values_20250213"
    full_output_fc = join_transformed_near_table_to_building_fc(transformed_near_table, building_fc, trimmed_table_name, full_output_fc_name)
    clean_fc_name = f"clean_{full_output_fc_name}"
    clean_output_fc = rename_fields(full_output_fc, trimmed_table_name, clean_fc_name)
    filtered_fc_name = "filtered_results_20250213"
    filtered_fc = filter_results(clean_output_fc, 4, filtered_fc_name)

    # for testing only:
    #rename_fields(full_output_fc_name, trimmed_table_name)
    #filtered_fc_name = "filtered_results_20250213"
    #filtered_fc = filter_results(clean_fc_name, 4, filtered_fc_name)
    elapsed_minutes = (time.time() - start_time) / 60
    logger.info(f"Setback distance calculation with street info fields complete in {round(elapsed_minutes, 2)} minutes.")


# Run the script
if __name__ == "__main__":
    # TODO - remove lines below after testing parallel field population
    set_environment()
    building_fc = "extracted_footprints_nearmap_20240107_in_aoi_and_zones_r_th_otmu_li_ao"
    #parcel_line_fc = "split_parcel_lines_in_zones_r_th_otmu_li_ao_20250128"
    parcel_line_fc = "parcel_lines_from_polygons_TEST"
    output_near_table_suffix = "nm_20240107_20250211"
    spatial_join_output = "spatial_join_buildings_completely_within_parcels"
    run(building_fc, parcel_line_fc, output_near_table_suffix, spatial_join_output, max_side_fields=4)
