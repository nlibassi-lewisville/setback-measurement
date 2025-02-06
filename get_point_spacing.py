import arcpy
import os
import json
from shared import set_environment


def add_fields(line_fc):
    """Add fields for 'parcel_line_OID' (LONG) and 'point_spacing' (TEXT 3000 chars)"""
    arcpy.AddField_management(line_fc, "parcel_line_OID", "LONG")
    arcpy.AddField_management(line_fc, "point_spacing", "TEXT", field_length=3000)


def populate_oid_field(line_fc):
    """Populates 'parcel_line_OID' with OBJECTID."""
    with arcpy.da.UpdateCursor(line_fc, ["parcel_line_OID", "OBJECTID"]) as cursor:
        for row in cursor:
            row[0] = row[1]
            cursor.updateRow(row)


def convert_lines_to_points(line_fc, output_point_fc):
    """Runs 'Feature Vertices to Points' to generate points at line vertices."""
    arcpy.FeatureVerticesToPoints_management(line_fc, output_point_fc, "ALL")


def remove_duplicate_points(point_fc, unique_point_fc):
    """Deletes points with duplicate geometries."""
    arcpy.DeleteIdentical_management(point_fc, ["Shape"])
    arcpy.CopyFeatures_management(point_fc, unique_point_fc)


def calculate_point_spacing(unique_point_fc, line_fc):
    """Calculates spacing between consecutive points and stores results in the line feature class."""
    
    # Dictionary to store spacing information for each line
    line_spacing = {}

    # Read points, grouped by parcel_line_OID, sorted by sequence
    with arcpy.da.SearchCursor(unique_point_fc, ["parcel_line_OID", "OBJECTID", "SHAPE@"], sql_clause=(None, "ORDER BY parcel_line_OID, OBJECTID")) as cursor:
        current_line_id = None
        previous_point = None
        spacing_dict = {}

        for row in cursor:
            if row[0] != current_line_id:
                # Store previous line's spacing info
                if current_line_id is not None:
                    line_spacing[current_line_id] = json.dumps(spacing_dict)

                # Reset for new line
                current_line_id = row[0]
                previous_point = None
                spacing_dict = {}

            if previous_point is not None:
                # Calculate distance between current and previous point (feet)
                #dist = ((row[2][0] - previous_point[0]) ** 2 + (row[2][1] - previous_point[1]) ** 2) ** 0.5 * 3.28084  # Convert meters to feet
                dist = ((row[2].centroid.X - previous_point[0]) ** 2 + (row[2].centroid.Y - previous_point[1]) ** 2) ** 0.5
                spacing_dict[row[1]] = round(dist, 2)

            #previous_point = row[2]
            previous_point = (row[2].centroid.X, row[2].centroid.Y)
        
        # Store last line's spacing info
        if current_line_id is not None:
            line_spacing[current_line_id] = json.dumps(spacing_dict)

    # Write spacing dictionary to 'point_spacing' in the line feature class
    with arcpy.da.UpdateCursor(line_fc, ["parcel_line_OID", "point_spacing"]) as cursor:
        for row in cursor:
            row[1] = line_spacing.get(row[0], "{}")
            cursor.updateRow(row)


def get_curved_lines(line_fc,  distance_threshold=4, point_count_threshold=5):
    """
    Selects curved lines from the input feature class based on number of consecutive points separated by a distance less than a given threshold.
    :param line_fc: Input feature class containing lines and a poit_spacing field (added in calculate_point_spacing()).
    :param distance_threshold: Maximum distance (in feet) between consecutive points for identification of a curve.
    :param point_count_threshold: Minimum number of consecutive points under the distance_threshold for identification of a curve.
    """
    curved_oids = []
    with arcpy.da.SearchCursor(line_fc, ["OBJECTID", "point_spacing"]) as cursor:
        for row in cursor:
            # TODO need for json.loads() here?
            point_spacing = json.loads(row[1])
            consecutive_points = 0
            for oid, spacing in point_spacing.items():
                if spacing < distance_threshold:
                    consecutive_points += 1
                    if consecutive_points >= point_count_threshold:
                        curved_oids.append(row[0])
                        break
                else:
                    consecutive_points = 0
    #arcpy.selectlayerbyattribute(line_fc, "OBJECTID", "IN", curved_oids)
    #arcpy.management.SelectLayerByAttribute(line_fc, "NEW_SELECTION", f"OBJECTID IN {','.join(map(str, curved_oids))}")
    curved_lines = "curved_lines_layer"
    arcpy.management.MakeFeatureLayer(line_fc, curved_lines, f"OBJECTID IN ({','.join(map(str, curved_oids))})")
    curved_lines_fc = os.path.join(workspace, f"curved_lines_using_{point_count_threshold}_consecutive_pts_with_{distance_threshold}_ft_spacing")
    arcpy.CopyFeatures_management(curved_lines, curved_lines_fc)


def main(line_fc, workspace):
    """Main function that executes all steps."""
    # TODO - check for redundancy in set_environment()
    arcpy.env.workspace = workspace
    arcpy.env.overwriteOutput = True

    # Define intermediate datasets
    point_fc = os.path.join(workspace, "line_vertices_points_20250204")
    unique_point_fc = os.path.join(workspace, "unique_line_vertices_20250204")
    add_fields(line_fc)
    populate_oid_field(line_fc)
    convert_lines_to_points(line_fc, point_fc)
    remove_duplicate_points(point_fc, unique_point_fc)
    calculate_point_spacing(unique_point_fc, line_fc)
    get_curved_lines(line_fc, distance_threshold=5, point_count_threshold=5)
    print("Processing completed successfully.")

# Example usage:
if __name__ == "__main__":
    set_environment()
    input_line_fc = "parcel_lines_from_polygons_TEST"
    workspace = os.getenv("GEODATABASE")
    main(input_line_fc, workspace)
