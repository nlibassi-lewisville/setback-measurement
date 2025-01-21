import os
import arcpy
import time
from shared import set_environment


def create_parcel_line_fc(parcel_polygon_fc, parcel_line_fc):
    """
    Converts a parcel polygon feature class to a line feature class.
    parcel
    parcel_polygon_fc: Input parcel polygon feature class
    parcel_line_fc: Output line feature class
    """
    # preserve polygon OID
    arcpy.management.AddField(parcel_polygon_fc, "parcel_polygon_OID", "LONG")
    arcpy.management.CalculateField(parcel_line_fc, "parcel_polygon_OID", "OBJECTID", "PYTHON3")

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


if __name__ == "__main__":
    start_time = time.time()
    set_environment()
    parcel_polygon_fc = "parcels_in_zones_r_th_otmu_li_ao"
    parcel_line_fc = "parcel_lines_from_polygons_TEST"

    identify_shared_parcel_boundaries(parcel_polygon_fc, parcel_line_fc, "shared_boundary")

    print("Total time: {:.2f} seconds".format(time.time() - start_time))