import arcpy
import os
import json
from shared import set_environment


def add_fields(line_fc):
    """Adds 'parcel_line_OID' (LONG) and 'point_spacing' (TEXT 3000 chars) fields."""
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
                # TODO - remove conversion from meters to feet?
                #dist = ((row[2][0] - previous_point[0]) ** 2 + (row[2][1] - previous_point[1]) ** 2) ** 0.5 * 3.28084  # Convert meters to feet
                dist = ((row[2].centroid.X - previous_point[0]) ** 2 + (row[2].centroid.Y - previous_point[1]) ** 2) ** 0.5 * 3.28084  # Convert meters to feet
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

def main(line_fc, workspace):
    """Main function that executes all steps."""
    arcpy.env.workspace = workspace
    arcpy.env.overwriteOutput = True

    # Define intermediate datasets
    point_fc = os.path.join(workspace, "line_vertices_points_20250204")
    unique_point_fc = os.path.join(workspace, "unique_line_vertices_20250204")

    # Step 1-2: Add new fields
    add_fields(line_fc)

    # Step 3: Populate OID field
    populate_oid_field(line_fc)

    # Step 4: Convert lines to points
    convert_lines_to_points(line_fc, point_fc)

    # Step 5: Remove duplicate points
    remove_duplicate_points(point_fc, unique_point_fc)

    # Step 6: Calculate and store point spacing
    calculate_point_spacing(unique_point_fc, line_fc)

    print("Processing completed successfully.")

# Example usage:
if __name__ == "__main__":
    set_environment()
    input_line_fc = "parcel_lines_from_polygons_TEST"
    workspace = os.getenv("GEODATABASE")
    main(input_line_fc, workspace)
