import os
import arcpy
from shared import set_environment


def line_to_points(input_fc, output_fc):
    """Convert input lines to points."""
    arcpy.management.FeatureVerticesToPoints(input_fc, output_fc, "ALL")


def get_lines_with_x_points(input_fc, x):
    """Get a list of line OBJECTIDs with more than x vertices."""
    line_oids = []
    with arcpy.da.SearchCursor(input_fc, ["OBJECTID", "SHAPE@"]) as cursor:
        for row in cursor:
            if len(row[1].getPart(0)) > x:
                line_oids.append(row[0])
    return line_oids


def get_midpoints_and_corners(input_fc, line_oids, output_fc):
    """Calculate the midpoint and detect corners for lines with more than x vertices."""
    spatial_reference = arcpy.Describe(input_fc).spatialReference
    arcpy.CreateFeatureclass_management(
        out_path=os.getenv("FEATURE_DATASET"),
        out_name="midpoints_and_corners",
        geometry_type="POINT",
        spatial_reference=spatial_reference
    )

    with arcpy.da.SearchCursor(input_fc, ["OBJECTID", "SHAPE@"]) as search_cursor, \
         arcpy.da.InsertCursor(output_fc, ["SHAPE@"]) as insert_cursor:
        for row in search_cursor:
            if row[0] in line_oids:
                line = row[1]
                part = line.getPart(0)

                # Calculate midpoint
                halfway_index = len(part) // 2
                midpoint = part[halfway_index]
                insert_cursor.insertRow([midpoint])

                # Detect corners (90-degree turns)
                for i in range(1, len(part) - 1):
                    prev_point = part[i - 1]
                    current_point = part[i]
                    next_point = part[i + 1]

                    # Calculate angle between segments
                    dx1, dy1 = current_point.X - prev_point.X, current_point.Y - prev_point.Y
                    dx2, dy2 = next_point.X - current_point.X, next_point.Y - current_point.Y

                    angle = abs((dx1 * dx2 + dy1 * dy2) / ((dx1**2 + dy1**2)**0.5 * (dx2**2 + dy2**2)**0.5))

                    # If angle is approximately 90 degrees (tolerance for floating-point precision)
                    if 0.7 < angle < 0.8:  # Cosine of 90 degrees is 0
                        insert_cursor.insertRow([current_point])


# TODO: remove if not needed
def get_midpoints(input_fc, line_oids, output_fc):
    """Calculate the midpoint for lines with more than x vertices."""
    spatial_reference = arcpy.Describe(input_fc).spatialReference
    arcpy.CreateFeatureclass_management(
        out_path=os.getenv("FEATURE_DATASET"),
        out_name="midpoints",
        geometry_type="POINT",
        spatial_reference=spatial_reference
    )

    with arcpy.da.SearchCursor(input_fc, ["OBJECTID", "SHAPE@"]) as search_cursor, \
         arcpy.da.InsertCursor(output_fc, ["SHAPE@"]) as insert_cursor:
        for row in search_cursor:
            if row[0] in line_oids:
                line = row[1]
                halfway_index = len(line.getPart(0)) // 2
                midpoint = line.getPart(0)[halfway_index]
                insert_cursor.insertRow([midpoint])


def split_lines(input_fc, midpoints_fc, output_fc):
    """Split input lines using the midpoints."""
    arcpy.management.SplitLineAtPoint(input_fc, midpoints_fc, output_fc)


def run(min_vertices=2):
    set_environment()

    # Define input and output
    input_fc_name = "parcel_lines_in_zones_r_th_otmu_li_ao"
    feature_dataset = os.getenv("FEATURE_DATASET")
    input_fc = os.path.join(feature_dataset, input_fc_name)
    output_midpoints_fc = os.path.join(feature_dataset, "midpoints_and_corners")
    output_split_lines_fc = os.path.join(feature_dataset, "split_parcel_lines_in_zones_r_th_otmu_li_ao")
    # Temporary outputs
    temp_points_fc = os.path.join(feature_dataset, "temp_points_from_lines")
    #temp_points_fc = arcpy.env.scratchGDB + "\temp_points"

    arcpy.management.Delete(output_split_lines_fc)
    arcpy.management.Delete(output_midpoints_fc)
    arcpy.management.Delete(temp_points_fc)

    # Step 1: Convert lines to points
    line_to_points(input_fc, temp_points_fc)

    # Step 2: Get lines with more than x points
    line_oids = get_lines_with_x_points(input_fc, min_vertices)

    # Step 3: Calculate and save midpoints and corners
    get_midpoints_and_corners(input_fc, line_oids, output_midpoints_fc)

    # Step 4: Split lines at midpoints
    split_lines(input_fc, output_midpoints_fc, output_split_lines_fc)

    # Cleanup
    #arcpy.management.Delete(temp_points_fc)

    print("Processing complete.")


run(2)
