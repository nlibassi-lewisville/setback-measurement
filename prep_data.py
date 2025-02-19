import os
import arcpy
import time
import pandas as pd
import numpy as np
from shared import set_environment, drop_gdb_item_if_exists
from base_logger import logger


def create_parcel_line_fc(parcel_polygon_fc, parcel_line_fc, parcel_polygon_OID_field):
    """
    Converts a parcel polygon feature class to a line feature class with a field to hold the parcel line id.
    :param parcel_polygon_fc - string: Path to input parcel polygon feature class
    :param parcel_line_fc - string: Path to output line feature class
    :param parcel_polygon_OID_field - string: Name of field to store the OID from the parcel polygon feature class
    return: string: Path to the output line feature class
    """
    # preserve polygon OID
    polygon_fields = arcpy.ListFields(parcel_polygon_fc)
    if not any(field.name == parcel_polygon_OID_field for field in polygon_fields):
        arcpy.management.AddField(parcel_polygon_fc, parcel_polygon_OID_field, "LONG")
    arcpy.management.CalculateField(parcel_polygon_fc, parcel_polygon_OID_field, "!OBJECTID!", "PYTHON3")

    arcpy.management.FeatureToLine(
        in_features=parcel_polygon_fc,
        out_feature_class=parcel_line_fc,
        cluster_tolerance=None,
        attributes="ATTRIBUTES"
        )
    logger.info(f"Total number of features in {parcel_line_fc}: {arcpy.management.GetCount(parcel_line_fc)}")
    
    parcel_line_OID_field = "parcel_line_OID"
    # store the parcel line OID in a separate field
    arcpy.AddField_management(parcel_line_fc, parcel_line_OID_field, "LONG")
    arcpy.CalculateField_management(parcel_line_fc, parcel_line_OID_field, "!OBJECTID!", "PYTHON3")
    logger.info(f"Added and populated {parcel_line_OID_field} field in {parcel_line_fc}.")
    return parcel_line_fc
    
    
def identify_shared_parcel_boundaries(parcel_line_fc, shared_boundary_field):
    """
    Add and populate a new field in the parcel line feature class where values denote shared boundaries between parcels.
    parcel_line_fc: Line feature class converted from polygons
    shared_boundary_field: Name of field to be created for shared boundary flag
    """
    #arcpy.management.FeatureToLine(
    #    in_features=parcel_polygon_fc,
    #    out_feature_class=parcel_line_fc,
    #    cluster_tolerance=None,
    #    attributes="ATTRIBUTES"
    #    )
    #logger.info(f"Total number of features in parcel_line_fc: {arcpy.management.GetCount(parcel_line_fc)}")
    # Add a new field for shared boundary flag
    field_name = shared_boundary_field
    if not arcpy.ListFields(parcel_line_fc, field_name):
        arcpy.management.AddField(parcel_line_fc, field_name, "SHORT")

    self_intersect_fc = "parcel_lines_self_intersect"

    arcpy.analysis.Intersect(
        in_features=[parcel_line_fc, parcel_line_fc],
        out_feature_class=self_intersect_fc,
        join_attributes="ALL",
        cluster_tolerance=None,
        output_type="LINE"
        )
    logger.info(f"Total number of features in self_intersect_fc: {arcpy.management.GetCount(self_intersect_fc)}")
    gdb = os.getenv("GEODATABASE")
    identical_parcel_lines_table = os.path.join(gdb, "identical_parcel_lines")
    logger.info("Finding identical lines...")
    arcpy.management.FindIdentical(
        in_dataset="parcel_lines_self_intersect",
        out_dataset=identical_parcel_lines_table,
        fields="Shape",
        xy_tolerance=None,
        z_tolerance=0,
        output_record_option="ONLY_DUPLICATES"
        )
    
    self_intersect_identical_line_ids = set()
    with arcpy.da.SearchCursor(identical_parcel_lines_table, "IN_FID") as cursor:
        for row in cursor:
            self_intersect_identical_line_ids.add(row[0])

    logger.info(f"Identified {len(self_intersect_identical_line_ids)} identical lines.")
    #logger.info("Identical line IDs:", self_intersect_identical_line_ids)
    logger.info("Populating shared boundary field...")
    # populate the shared boundary field of the self_intersect_fc with 1 if the line is shared, 0 if not
    with arcpy.da.UpdateCursor(self_intersect_fc, ["OBJECTID", shared_boundary_field]) as cursor:
        for row in cursor:
            row[1] = 1 if row[0] in self_intersect_identical_line_ids else 0
            cursor.updateRow(row)

    # original line ids with shared boundaries
    identical_line_ids = set()
    # get original line ids with shared boundaries
    with arcpy.da.SearchCursor(self_intersect_fc, [f"FID_{parcel_line_fc}", shared_boundary_field]) as cursor:
        for row in cursor:
            if row[1] == 1:
                identical_line_ids.add(row[0])

    # populate the shared boundary field of the parcel_line_fc with 1 if the line is shared, 0 if not
    logger.info(f"Identified {len(identical_line_ids)} lines with shared boundaries.")
    with arcpy.da.UpdateCursor(parcel_line_fc, ["OBJECTID", shared_boundary_field]) as cursor:
        for row in cursor:
            row[1] = 1 if row[0] in identical_line_ids else 0
            cursor.updateRow(row)

    arcpy.management.DeleteIdentical(
        in_dataset=parcel_line_fc,
        fields="Shape",
        xy_tolerance=None,
        z_tolerance=0
    )
    logger.info(f"Total number of features in {parcel_line_fc} AFTER removal of those with duplicate geoemtry: {arcpy.management.GetCount(parcel_line_fc)}")

    logger.info("Shared boundary identification complete.")
    

def get_building_parcel_join(building_polygon_fc, parcel_polygon_fc, output_fc):
    """
    Perform a spatial join between building and parcel polygons where building features are completely within a parcel feature
    parcel_polygon_fc: Input parcel polygon feature class
    building_polygon_fc: Input building polygon feature class
    output_fc: Output feature class for the join result
    """
    logger.info("Performing spatial join between building and parcel polygons...")
    arcpy.analysis.SpatialJoin(
        target_features=building_polygon_fc,
        join_features=parcel_polygon_fc,
        out_feature_class=output_fc,
        join_operation="JOIN_ONE_TO_ONE",
        join_type="KEEP_ALL",
        match_option="COMPLETELY_WITHIN"
    )


def get_parcel_id_table(parcel_polygon_fc, parcel_line_fc, output_table):
    """
    Create a table with parcel polygon IDs and the line IDs that make up their boundaries.
    :param parcel_polygon_fc: Path to the parcel polygon feature class.
    :param parcel_line_fc: Path to the parcel line feature class.
    :param output_table: Path to the output table.
    """
    logger.info("Getting table with parcel polygon IDs and the line IDs that make up their boundaries...")
    # must pass layer (not fc) to SelectLayerByLocation to get expected results (not all features) in standalone script
    parcel_line_layer = "parcel_line_layer"
    arcpy.management.MakeFeatureLayer(parcel_line_fc, parcel_line_layer)
    # for parcel_id_dict, keys are parcel polygon IDs, values are lists of line IDs
    parcel_id_dict = {}
    with arcpy.da.SearchCursor(parcel_polygon_fc, ["OBJECTID", "SHAPE@"]) as cursor:
        for row in cursor:
            parcel_id = row[0]
            parcel_geometry = row[1]
            #logger.info(f"length of parcel_geometry: {len(parcel_geometry)}")
            arcpy.management.SelectLayerByLocation(parcel_line_layer, "SHARE_A_LINE_SEGMENT_WITH", parcel_geometry, search_distance="300 Feet")
            selected_count = arcpy.management.GetCount(parcel_line_layer)[0]
            #logger.info(f"Selected {selected_count} lines.")
            with arcpy.da.SearchCursor(parcel_line_layer, ["OBJECTID"]) as line_cursor:
                for line in line_cursor:
                    if parcel_id not in parcel_id_dict:
                        parcel_id_dict[parcel_id] = []
                    parcel_id_dict[parcel_id].append(line[0])

    table_fields = [("parcel_polygon_OID", "i4"), ("parcel_line_OIDs", "U100")]
    table_data = np.array([(k, str(v)) for k, v in parcel_id_dict.items()], dtype=table_fields)
    drop_gdb_item_if_exists(output_table)
    arcpy.da.NumPyArrayToTable(table_data, output_table)
    logger.info(f"Parcel ID table created at {output_table}.")


def run(parcel_polygon_fc, parcel_line_fc, parcel_polygon_OID_field, shared_boundary_field, building_polygon_fc, building_parcel_join_fc, parcel_id_table_name):
    """
    Run all functions to prepare data
    :param parcel_polygon_fc: Path to the parcel polygon feature class.
    :param parcel_line_fc: Path to the parcel line feature class.
    :param parcel_polygon_OID_field: Name of field to store the OID from the parcel polygon feature class.
    :param shared_boundary_field: Name of field to be created for shared boundary flag.
    :param building_polygon_fc: Path to the building polygon feature class.
    :param building_parcel_join_fc: Output feature class for the join result.
    :param parcel_id_table_name: Name of the (new) output table with parcel polygon IDs and the line IDs that make up their boundaries.
    """
    create_parcel_line_fc(parcel_polygon_fc, parcel_line_fc, parcel_polygon_OID_field)
    identify_shared_parcel_boundaries(parcel_line_fc, shared_boundary_field)
    get_building_parcel_join(building_polygon_fc, parcel_polygon_fc, building_parcel_join_fc)
    
    # TODO remove commented lines if order above ok
    #identify_shared_parcel_boundaries(parcel_polygon_fc, parcel_line_fc, shared_boundary_field)
    #get_building_parcel_join(building_polygon_fc, parcel_polygon_fc, building_parcel_join_fc)
    
    parcel_id_table = os.path.join(os.getenv("GEODATABASE"), parcel_id_table_name)
    get_parcel_id_table(parcel_polygon_fc, parcel_line_fc, parcel_id_table)
    logger.info("Data preparation complete.")


if __name__ == "__main__":
    start_time = time.time()
    logger.info(f"Preparation of data started at: {time.ctime(start_time)}")
    set_environment()
    parcel_polygon_fc = "parcels_in_zones_r_th_otmu_li_ao"
    # parcel_line_fc is desired name of output line feature class created from polygon feature class
    parcel_line_fc = "parcel_lines_from_polygons_20250218"
    #create_parcel_line_fc(parcel_polygon_fc, parcel_line_fc, "parcel_polygon_OID")
    building_polygon_fc = "extracted_footprints_nearmap_20240107_in_aoi_and_zones_r_th_otmu_li_ao"
    # for testing building_parcel_join use existing "buildings_with_parcel_ids"?
    building_parcel_join_fc = "building_parcel_join_20250218"
    #get_building_parcel_join(parcel_polygon_fc, building_polygon_fc, building_parcel_join_fc)
    #parcel_id_table = os.path.join(os.getenv("GEODATABASE"), "parcel_id_table_20250218")
    #get_parcel_id_table(parcel_polygon_fc, parcel_line_fc, parcel_id_table)
    parcel_polygon_OID_field = "parcel_polygon_OID"
    shared_boundary_field = "shared_boundary"
    parcel_id_table_name = "parcel_id_table_20250218"

    run(parcel_polygon_fc, parcel_line_fc, parcel_polygon_OID_field, shared_boundary_field, building_polygon_fc, building_parcel_join_fc, parcel_id_table_name)
    logger.info("Total time: {:.2f} seconds".format(time.time() - start_time))