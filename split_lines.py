import os
import arcpy
from shared import set_environment


def line_to_points(input_fc, output_fc):
    """Convert input lines to points."""
    print("Entered lines_to_points()...")
    arcpy.management.FeatureVerticesToPoints(input_fc, output_fc, "ALL")


def get_lines_with_x_points(input_fc, x):
    """Get a list of line OBJECTIDs with more than x vertices."""
    print("Entered get_lines_with_x_points()...")
    line_oids = []
    with arcpy.da.SearchCursor(input_fc, ["OBJECTID", "SHAPE@"]) as cursor:
        for row in cursor:
            if len(row[1].getPart(0)) > x:
                line_oids.append(row[0])
    return line_oids


def get_midpoints_and_clusters(input_fc, line_oids, output_fc_name, cluster_vertex_min, cluster_distance_max):
    """
    Find midpoints and points where more than x (cluster_vertex_min) vertices are within y (cluster_distance_max) feet of each other.
    :param input_fc - string: Input feature class
    :param line_oids - list: List of line OBJECTIDs to process
    :param output_fc_name - string: Output feature class name
    :param cluster_vertex_min - int: minimum number of vertices to define a cluster
    :param cluster_distance_max - float: distance in feet over which a cluster is defined
    """
    print("Entered get_midpoints_and_clusters()...")
    spatial_reference = arcpy.Describe(input_fc).spatialReference
    out_path = os.getenv("FEATURE_DATASET")
    arcpy.CreateFeatureclass_management(
        out_path=out_path,
        out_name=output_fc_name,
        geometry_type="POINT",
        spatial_reference=spatial_reference
    )
    output_fc = os.path.join(out_path, output_fc_name)

    with arcpy.da.SearchCursor(input_fc, ["OBJECTID", "SHAPE@"]) as search_cursor, \
         arcpy.da.InsertCursor(output_fc, ["SHAPE@"]) as insert_cursor:
        for row in search_cursor:
            if row[0] in line_oids:
                line = row[1]
                part = line.getPart(0)

                # Calculate midpoint
                if len(part) > cluster_vertex_min:
                    midpoint_index = len(part) // 2
                    midpoint = part[midpoint_index]
                    insert_cursor.insertRow([midpoint])

                # Identify clusters and retain one point per cluster
                visited = set()
                for i, point in enumerate(part):
                    if i in visited:
                        continue

                    cluster_points = []
                    for j, other_point in enumerate(part):
                        if i != j and j not in visited:
                            distance = ((point.X - other_point.X)**2 + (point.Y - other_point.Y)**2)**0.5
                            if distance <= cluster_distance_max:
                                cluster_points.append((j, other_point))

                    if len(cluster_points) >= cluster_vertex_min:
                        insert_cursor.insertRow([point])
                        visited.update([idx for idx, _ in cluster_points])
                        visited.add(i)


def split_lines(input_fc, points_fc, output_fc, search_radius=250):
    """
    Split input lines using the given points.
    :param input_fc - string: Input line feature class
    :param points_fc - string: Feature class of points to split lines
    :param output_fc - string: Output feature class
    :param search_radius - float: Search radius in feet (must be defined to split a line in multiple places)
    """
    print("Entered split_lines()...")
    arcpy.management.SplitLineAtPoint(input_fc, points_fc, output_fc, search_radius=f"{search_radius} Feet")


def run(min_vertices=2):
    set_environment()
    # Define input and output feature classes
    # parcel_lines_in_zones_r_th_otmu_li_ao has already been split at corners
    input_fc_name = "parcel_lines_in_zones_r_th_otmu_li_ao"
    feature_dataset = os.getenv("FEATURE_DATASET")
    input_fc = os.path.join(feature_dataset, input_fc_name)
    output_midpoints_fc_name = "midpoints_and_corners_20250128"
    output_midpoints_fc = os.path.join(feature_dataset, output_midpoints_fc_name)
    output_split_lines_fc = os.path.join(feature_dataset, "split_parcel_lines_in_zones_r_th_otmu_li_ao_20250128")
    # Temporary outputs
    temp_points_fc = os.path.join(feature_dataset, "temp_points_from_lines_20250128")

    # TODO check for existence first and uncomment if needed
    #arcpy.management.Delete(output_split_lines_fc)
    #arcpy.management.Delete(output_midpoints_fc)
    #arcpy.management.Delete(temp_points_fc)

    # Step 1: Convert lines to points
    line_to_points(input_fc, temp_points_fc)

    # Step 2: Get lines with more than x points
    line_oids = get_lines_with_x_points(input_fc, min_vertices)

    # Step 3: Calculate and save midpoints and corners
    get_midpoints_and_clusters(input_fc, line_oids, output_midpoints_fc_name, 7, 40)

    # Step 4: Split lines at midpoints
    split_lines(input_fc, output_midpoints_fc, output_split_lines_fc, 250)

    # Cleanup
    #arcpy.management.Delete(temp_points_fc)

    print("Processing complete.")


run(2)
