import arcpy
import os
from shared import set_environment

def add_oid_field(line_fc, oid_field="parcel_line_OID"):
    """Adds and populates a field with the ObjectID."""
    arcpy.AddField_management(line_fc, oid_field, "LONG")
    with arcpy.da.UpdateCursor(line_fc, [oid_field, "OID@"]) as cursor:
        for row in cursor:
            row[0] = row[1]
            cursor.updateRow(row)

def convert_lines_to_points(line_fc, output_point_fc):
    """Runs 'Feature Vertices to Points' to generate points at line vertices."""
    arcpy.FeatureVerticesToPoints_management(line_fc, output_point_fc, "ALL")

def summarize_points_by_line(point_fc, summary_table, oid_field="parcel_line_OID"):
    """Summarizes the number of points per line based on parcel_line_OID."""
    arcpy.Statistics_analysis(point_fc, summary_table, [[oid_field, "COUNT"]], oid_field)
    arcpy.AddField_management(summary_table, "point_count", "LONG")
    
    with arcpy.da.UpdateCursor(summary_table, ["FREQUENCY", "point_count"]) as cursor:
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)

def join_summary_to_lines(line_fc, summary_table, oid_field="parcel_line_OID"):
    """Joins the summarized point count table back to the original line feature class."""
    arcpy.JoinField_management(line_fc, oid_field, summary_table, oid_field, ["point_count"])

def calculate_vertex_density(line_fc):
    """Adds and populates 'vertex_density' as point_count / Shape_Length."""
    arcpy.AddField_management(line_fc, "vertex_density", "DOUBLE")
    with arcpy.da.UpdateCursor(line_fc, ["point_count", "Shape_Length", "vertex_density"]) as cursor:
        for row in cursor:
            row[2] = row[0] / row[1] if row[1] != 0 else 0
            cursor.updateRow(row)

def main(line_fc, workspace):
    """Main function that executes all steps."""
    arcpy.env.workspace = workspace
    arcpy.env.overwriteOutput = True

    # Define intermediate datasets
    point_fc = os.path.join(workspace, "line_vertices_points")
    gdb = os.getenv("GEODATABASE")
    summary_table = os.path.join(gdb, "line_point_summary")

    # Step 1-3: Add and populate OID field
    add_oid_field(line_fc)

    # Step 4: Convert lines to points
    convert_lines_to_points(line_fc, point_fc)

    # Step 5: Summarize points per line
    summarize_points_by_line(point_fc, summary_table)

    # Step 6: Join summary table back to line FC
    join_summary_to_lines(line_fc, summary_table)

    # Step 7: Calculate vertex density
    calculate_vertex_density(line_fc)

    print("Processing completed successfully.")

# Example usage:
if __name__ == "__main__":
    set_environment()
    input_line_fc = r"parcel_lines_from_polygons"
    feature_dataset = os.getenv("FEATURE_DATASET")
    workspace = feature_dataset
    main(input_line_fc, workspace)
