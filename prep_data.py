import os
import arcpy
import time
import pandas as pd
from shared import set_environment


def create_parcel_line_fc(parcel_polygon_fc, parcel_line_fc, parcel_polygon_OID_field):
    """
    Converts a parcel polygon feature class to a line feature class.
    parcel_polygon_fc - string: Input parcel polygon feature class
    parcel_line_fc - string: Output line feature class
    parcel_polygon_OID_field - string: Name of field to store the OID from the parcel polygon feature class
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
    print(f"Total number of features in {parcel_line_fc}: {arcpy.management.GetCount(parcel_line_fc)}")


    # copied from process_parcel() function
    # Convert parcel polygon to lines
    #arcpy.management.PolygonToLine(parcel_layer, parcel_lines_fc)
    # Add a field to store the polygon parcel ID
    
    
def identify_shared_parcel_boundaries(parcel_polygon_fc, parcel_line_fc, shared_boundary_field):
    """
    Identifies shared boundaries between parcels using a line feature class converted from polygons.
    parcel_polygon_fc: Input parcel polygon feature class
    parcel_line_fc: Line feature class converted from polygons
    shared_boundary_field: Name of field to be created for shared boundary flag
    """
    arcpy.management.FeatureToLine(
        in_features=parcel_polygon_fc,
        out_feature_class=parcel_line_fc,
        cluster_tolerance=None,
        attributes="ATTRIBUTES"
        )
    print(f"Total number of features in parcel_line_fc: {arcpy.management.GetCount(parcel_line_fc)}")
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
    print(f"Total number of features in self_intersect_fc: {arcpy.management.GetCount(self_intersect_fc)}")
    gdb = os.getenv("GEODATABASE")
    identical_parcel_lines_table = os.path.join(gdb, "identical_parcel_lines")
    print("Finding identical lines...")
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

    print(f"Identified {len(self_intersect_identical_line_ids)} identical lines.")
    #print("Identical line IDs:", self_intersect_identical_line_ids)
    print("Populating shared boundary field...")
    # populate the shared boundary field of the self_intersect_fc with 1 if the line is shared, 0 if not
    with arcpy.da.UpdateCursor(self_intersect_fc, ["OBJECTID", shared_boundary_field]) as cursor:
        for row in cursor:
            row[1] = 1 if row[0] in self_intersect_identical_line_ids else 0
            cursor.updateRow(row)

    # TODO - ensure that updates to self_intersect_fc are persisted if necessary - final results seem correct but not sure why shared_boundary_field is not being populated in self_intersect_fc

    # original line ids with shared boundaries
    identical_line_ids = set()
    # get original line ids with shared boundaries
    with arcpy.da.SearchCursor(self_intersect_fc, [f"FID_{parcel_line_fc}", shared_boundary_field]) as cursor:
        for row in cursor:
            if row[1] == 1:
                identical_line_ids.add(row[0])

    # populate the shared boundary field of the parcel_line_fc with 1 if the line is shared, 0 if not
    print(f"Identified {len(identical_line_ids)} lines with shared boundaries.")
    with arcpy.da.UpdateCursor(parcel_line_fc, ["OBJECTID", shared_boundary_field]) as cursor:
        for row in cursor:
            row[1] = 1 if row[0] in identical_line_ids else 0
            cursor.updateRow(row)

    print("Shared boundary identification complete.")


# TODO - remove if not used
def get_parcel_building_join(parcel_polygon_fc, building_polygon_fc, output_fc):
    """
    Perform a spatial join between parcel and building polygons.
    parcel_polygon_fc: Input parcel polygon feature class
    building_polygon_fc: Input building polygon feature class
    output_fc: Output feature class for the join result
    """
    arcpy.analysis.SpatialJoin(
    target_features=parcel_polygon_fc,
    join_features=building_polygon_fc,
    out_feature_class=output_fc,
    join_operation="JOIN_ONE_TO_MANY",
    join_type="KEEP_ALL",
    match_option="COMPLETELY_CONTAINS",
    search_radius=None,
    distance_field_name="",
    match_fields=None
    )
    

def get_building_parcel_join(building_polygon_fc, parcel_polygon_fc, output_fc):
    """
    Perform a spatial join between building and parcel polygons.
    parcel_polygon_fc: Input parcel polygon feature class
    building_polygon_fc: Input building polygon feature class
    output_fc: Output feature class for the join result
    """
    arcpy.analysis.SpatialJoin(
        target_features=building_polygon_fc,
        join_features=parcel_polygon_fc,
        out_feature_class=output_fc,
        join_operation="JOIN_ONE_TO_ONE",
        join_type="KEEP_ALL",
        match_option="COMPLETELY_WITHIN"
    )


def get_building_parcel_df(spatial_join_output):
    """
    Create a dataframe holding building polygon IDs in TARGET_FID field and the id of the parcel in which each building is found in parcel_polygon_OID.
    :param spatial_join_output: Path to the spatial join output feature class.
    :return: a pandas dataframe with columns for building polygon IDs and parcel polygon IDs.
    """
    # TARGET_FID
    fields = ["TARGET_FID", "parcel_polygon_OID"]
    #building_parcel_df = pd.DataFrame(arcpy.da.TableToNumPyArray(spatial_join_output, ["JOIN_FID", "TARGET_FID"]))
    building_parcel_df = pd.DataFrame(data=arcpy.da.SearchCursor(spatial_join_output, fields))
    #building_parcel_df.columns = ["building_polygon_OID", "parcel_polygon_OID"]
    building_parcel_df.columns = ["IN_FID", "parcel_polygon_OID"]
    return building_parcel_df


def match_parcel_ids(parcel_polygon_fc, parcel_line_fc):
    """
    Create a table with parcel polygon IDs and the line IDs that make up their boundaries.
    :param parcel_polygon_fc: Path to the parcel polygon feature class.
    :param parcel_line_fc: Path to the parcel line feature class.
    :return: a dictionary with parcel polygon IDs as keys and lists of line IDs as values.
    """
    # for parcel_id_dict, keys are parcel polygon IDs, values are lists of line IDs
    parcel_id_dict = {}
    # TODO - test performance of this vs use of arcpy.management.SelectLayerByLocation
    with arcpy.da.SearchCursor(parcel_polygon_fc, ["OBJECTID", "SHAPE@"]) as cursor:
        for row in cursor:
            parcel_id = row[0]
            parcel_geometry = row[1]
            arcpy.management.SelectLayerByLocation(parcel_line_fc, "INTERSECT", parcel_geometry)
            with arcpy.da.SearchCursor(parcel_line_fc, ["OBJECTID"]) as line_cursor:
                for line in line_cursor:
                    if parcel_id not in parcel_id_dict:
                        parcel_id_dict[parcel_id] = []
                        parcel_id_dict[parcel_id].append(line[0])
            # get the lines that make up the boundary of the parcel
            #with arcpy.da.SearchCursor(parcel_line_fc, ["OBJECTID", "SHAPE@"]) as line_cursor:
            #    for line in line_cursor:
            #        #if parcel_geometry.overlaps(line[1]) or parcel_geometry.crosses(line[1]) or parcel_geometry.touches(line[1]):
            #        if parcel_geometry.overlaps(line[1]) or parcel_geometry.crosses(line[1]):
            #            # add line ID to list of line IDs for this parcel
            #            if parcel_id not in parcel_id_dict:
            #                parcel_id_dict[parcel_id] = []
            #            parcel_id_dict[parcel_id].append(line[0])
    return parcel_id_dict


if __name__ == "__main__":
    start_time = time.time()
    print(f"Preparation of data started at: {time.ctime(start_time)}")
    set_environment()
    parcel_polygon_fc = "parcels_in_zones_r_th_otmu_li_ao"
    parcel_line_fc = "parcel_lines_from_polygons_TEST"
    #create_parcel_line_fc(parcel_polygon_fc, parcel_line_fc, "parcel_polygon_OID")
    #identify_shared_parcel_boundaries(parcel_polygon_fc, parcel_line_fc, "shared_boundary")
    #arcpy.management.DeleteIdentical(
    #    in_dataset=parcel_line_fc,
    #    fields="Shape"
    #    )
    ## was created in ArcGIS Pro - not yet run here
    #building_polygon_fc = "extracted_footprints_nearmap_20240107_in_aoi_and_zones_r_th_otmu_li_ao"
    #building_parcel_join_fc = "building_parcel_join"
    #get_building_parcel_join(parcel_polygon_fc, building_polygon_fc, building_parcel_join_fc)
    test_dict = match_parcel_ids(parcel_polygon_fc, parcel_line_fc)
    print(test_dict)

    print("Total time: {:.2f} seconds".format(time.time() - start_time))