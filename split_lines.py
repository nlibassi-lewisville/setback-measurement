import os
import math
import time
import arcpy
from shared import set_environment


def line_to_points(input_fc, output_fc):
    """Convert input lines to points."""
    print("Entered lines_to_points()...")
    arcpy.management.FeatureVerticesToPoints(input_fc, output_fc, "ALL")


def categorize_lines_based_on_x_points(input_fc, x=2):
    """
    Get lists of line OBJECTIDs with more than and less than x vertices.
    :param input_fc - string: Input line feature class
    :param x - int: Threshold number of vertices used to categorize lines
    :return - tuple of two lists of int values: List of line OBJECTIDs with more than x vertices, List of line OBJECTIDs with less than x vertices
    """
    print("Entered get_lines_with_x_points()...")
    line_oids_with_more_points = []
    line_oids_with_less_points = []
    with arcpy.da.SearchCursor(input_fc, ["OBJECTID", "SHAPE@"]) as cursor:
        for row in cursor:
            if len(row[1].getPart(0)) > x:
                line_oids_with_more_points.append(row[0])
            else:
                line_oids_with_less_points.append(row[0])
    return (line_oids_with_more_points, line_oids_with_less_points)


def calculate_angle_from_points(start, end):
    """
    Calculate the angle (bearing) between first and last points of a line geometry in degrees, accounting for bidirectional lines.
    :param start: The geometry object of the starting point.
    :param end: The geometry object of the ending point.
    :return: Angle in degrees (0-360).
    """
    start_geom = start.getPart()
    end_geom = end.getPart()
    dx = end_geom.X - start_geom.X
    dy = end_geom.Y - start_geom.Y
    angle = math.degrees(math.atan2(dy, dx))
    # Normalize to 0-360 degrees
    angle = angle % 360
    # Normalize the angle to the range 0-180 (to account for bidirectional lines)
    if angle > 180:
        angle -= 180
    return angle


def get_points_for_splitting(input_point_fc, line_oid_lists, angle_threshold):
    """
    Create a feature class of points at which lines will be split.
    :param input_point_fc - string: Input point feature class (created from line feature class) that has a field called 'parcel_line_OID'
    :param line_oid_lists - tuple of two lists of int values: List of line OBJECTIDs with more than x vertices, List of line OBJECTIDs with less than x vertices
    :param angle_threshold - float: Threshold (in degrees) beyond which points will be used for splitting lines

    TODO - remove if unused
    :param output_point_fc - string: Output point feature class holding points at which lines will be split
    """
    print("Entered get_points_for_splitting()...")
    line_oids_with_more_points = line_oid_lists[0]
    # less_points is exactly two points
    line_oids_with_less_points = line_oid_lists[1]
    oids_of_split_points = []
    feature_layer = "input_points_on_two_point_line"
    two_point_line_query = f"parcel_line_OID IN ({', '.join(map(str, line_oids_with_less_points))})"
    arcpy.management.MakeFeatureLayer(input_point_fc, feature_layer, two_point_line_query)
    # append the OBJECTIDs of the two points in each two-point line to the list of split points
    print("Getting object id's of points from two-point lines...")
    with arcpy.da.SearchCursor(feature_layer, ["OBJECTID"]) as cursor:
        for row in cursor:
            oids_of_split_points.append(row[0])
    #print(f"OID's of points from two-point lines: {oids_of_split_points}")
    print("Getting object id's of points from lines with more than two points...")
    #print(f"Line OBJECTIDs with more than two points: {line_oids_with_more_points}")
    for oid in line_oids_with_more_points:
        #arcpy.management.SelectLayerByAttribute(input_point_fc, "NEW_SELECTION", f"parcel_line_OID = {oid}")
        # should be working only with selected point features from here forward but doesn't seem to be the case
        feature_layer = "input_points_on_single_line"
        arcpy.management.MakeFeatureLayer(input_point_fc, feature_layer, f"parcel_line_OID = {oid}")
        #with arcpy.da.SearchCursor(input_point_fc, ["OBJECTID", "SHAPE@"], sql_clause=(None, 'ORDER BY OBJECTID ASC')) as cursor:
        with arcpy.da.SearchCursor(feature_layer, ["OBJECTID", "SHAPE@"], sql_clause=(None, 'ORDER BY OBJECTID ASC')) as cursor:
            rows = list(cursor)
            row_count = len(rows)
            #print(f"Number of points in line with oid {oid}: {row_count}")
            #print(f"rows: {rows}")
            # append the OBJECTIDs of the first and last points of each line to the list of split points
            oids_of_split_points.append(rows[0][0])
            oids_of_split_points.append(rows[row_count - 1][0])
            previous_geom_1 = rows[0][1]
            previous_geom_2 = rows[1][1]
            current_row = 0
        # same cursor has to be recreated here in order to iterate through the rows again
        with arcpy.da.SearchCursor(feature_layer, ["OBJECTID", "SHAPE@"], sql_clause=(None, 'ORDER BY OBJECTID ASC')) as cursor:
            for row in cursor:
                current_row += 1
                # skip first two points in line as we need three to calculate an angle
                if current_row < 3:
                    continue
                else:
                    oid = row[0]
                    angle_1 = calculate_angle_from_points(previous_geom_1, previous_geom_2)
                    angle_2 = calculate_angle_from_points(previous_geom_2, row[1])
                    angle = abs(angle_2 - angle_1)
                    #if oid - 1 in [8810, 8823]:
                    #    print(f"OID's: {oid-2}, {oid-1}, {oid}. Angle: {angle}")
                    #if angle > angle_threshold:
                    if angle > angle_threshold and angle < 180 - angle_threshold:
                        # append OID of 2nd point in the 3-point sequence
                        oids_of_split_points.append(oid - 1)
                        #if angle < angle_threshold + 5:
                        #    print(f"Angle: {angle} between points with OID {oid-2}, {oid-1}, and {oid} is 5 degrees OVER threshold of {angle_threshold}.")
                    #elif angle < angle_threshold and angle > angle_threshold - 5:
                    #    print(f"Angle: {angle} between points with OID {oid-2}, {oid-1}, and {oid} is 5 degrees UNDER threshold of {angle_threshold}.")
                    previous_geom_1 = previous_geom_2
                    previous_geom_2 = row[1]

    # same as below
    #query_string = f"OBJECTID IN ({', '.join(map(str, oids_of_split_points))})"
    query_string = f"OBJECTID IN ({', '.join(str(oid) for oid in oids_of_split_points)})"
    print(f"length of oids_of_split_points: {len(oids_of_split_points)}")
    #arcpy.management.SelectLayerByAttribute(input_point_fc, "NEW_SELECTION", query_string)
    output_feature_layer = "output_points_for_splitting"
    arcpy.management.MakeFeatureLayer(input_point_fc, output_feature_layer, query_string)
    #arcpy.management.SelectLayerByAttribute(input_point_fc, "NEW_SELECTION", query_string)
    output_point_fc = f"points_for_splitting_angle_threshold_{angle_threshold}"
    arcpy.management.CopyFeatures(output_feature_layer, output_point_fc)


    #spatial_reference = arcpy.Describe(input_fc).spatialReference
    #out_path = os.getenv("FEATURE_DATASET")
    #arcpy.CreateFeatureclass_management(
    #    out_path=out_path,
    #    out_name=output_fc_name,
    #    geometry_type="POINT",
    #    spatial_reference=spatial_reference
    #)
    #output_fc = os.path.join(out_path, output_fc_name)
    #with arcpy.da.SearchCursor(input_fc, ["OBJECTID", "SHAPE@"]) as search_cursor, \
    #     arcpy.da.InsertCursor(output_fc, ["SHAPE@"]) as insert_cursor:
    #    for row in search_cursor:
    #        if row[0] in line_oids:
    #            line = row[1]
    #            part = line.getPart(0)
    #            for point in part:
    #                insert_cursor.insertRow([point])


def get_clustered_points(input_fc, line_oids, output_fc_name, cluster_vertex_min, cluster_distance_max):
    """
    Find points where more than x (cluster_vertex_min) vertices are within y (cluster_distance_max) feet of each other,
    and retain only a single representative point for each cluster.
    
    :param input_fc: Input feature class
    :param line_oids: List of line OBJECTIDs to process
    :param output_fc_name: Output feature class name
    :param cluster_vertex_min: Minimum number of vertices to define a cluster
    :param cluster_distance_max: Distance in feet over which a cluster is defined
    """
    print("Entered get_clustered_points()...")
    spatial_reference = arcpy.Describe(input_fc).spatialReference
    out_path = os.getenv("FEATURE_DATASET", arcpy.env.workspace)
    arcpy.CreateFeatureclass_management(
        out_path=out_path,
        out_name=output_fc_name,
        geometry_type="POINT",
        spatial_reference=spatial_reference
    )
    output_fc = os.path.join(out_path, output_fc_name)

    with arcpy.da.SearchCursor(input_fc, ["OBJECTID", "SHAPE@"]) as search_cursor, \
         arcpy.da.InsertCursor(output_fc, ["SHAPE@"]):
        for row in search_cursor:
            if row[0] in line_oids:
                line = row[1]
                part = line.getPart(0)

                visited = set()
                cluster_centers = []

                for i, point in enumerate(part):
                    if i in visited:
                        continue

                    cluster = []
                    for j, other_point in enumerate(part):
                        if i != j and j not in visited:
                            distance = ((point.X - other_point.X)**2 + (point.Y - other_point.Y)**2)**0.5
                            if distance <= cluster_distance_max:
                                cluster.append((j, other_point))

                    if len(cluster) >= cluster_vertex_min:
                        # Calculate cluster center
                        x_coords = [point.X] + [p.X for _, p in cluster]
                        y_coords = [point.Y] + [p.Y for _, p in cluster]
                        cluster_center = arcpy.Point(
                            X=sum(x_coords) / len(x_coords),
                            Y=sum(y_coords) / len(y_coords)
                        )
                        cluster_centers.append(cluster_center)
                        visited.update([j for j, _ in cluster])
                        visited.add(i)

                # Insert a single representative point for each cluster
                for cluster_center in cluster_centers:
                    arcpy.da.InsertCursor(output_fc, ["SHAPE@"]).insertRow([cluster_center])
                    

def get_clustered_points_OLD(input_fc, line_oids, output_fc_name, cluster_vertex_min, cluster_distance_max):
    """
    Find points where more than x (cluster_vertex_min) vertices are within y (cluster_distance_max) feet of each other.
    :param input_fc - string: Input feature class
    :param line_oids - list: List of line OBJECTIDs to process
    :param output_fc_name - string: Output feature class name
    :param cluster_vertex_min - int: minimum number of vertices to define a cluster
    :param cluster_distance_max - float: distance in feet over which a cluster is defined
    """
    print("Entered get_clustered_points()...")
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
                for i, point in enumerate(part):
                    nearby_count = 0
                    for j, other_point in enumerate(part):
                        if i != j:
                            distance = ((point.X - other_point.X)**2 + (point.Y - other_point.Y)**2)**0.5
                            if distance <= cluster_distance_max:
                                nearby_count += 1
                    if nearby_count >= cluster_vertex_min:
                        insert_cursor.insertRow([point])


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
    start_time = time.time()
    print(f"Starting process of splitting lines at {time.ctime(start_time)}")
    set_environment()
    # Define input and output feature classes
    # parcel_lines_in_zones_r_th_otmu_li_ao has already been split at corners
    #input_line_fc_name = "parcel_lines_in_zones_r_th_otmu_li_ao"

    # all parcel lines
    input_line_fc_name = "parcel_lines_from_polygons_TEST"
    #subset of parcel lines for testing
    #input_line_fc_name = "subset_parcel_lines_from_polygons_TEST"

    # all points from parcel lines
    input_point_fc_name = "points_from_parcel_lines_from_polygons_TEST"
    #subset of points from parcel lines for testing
    #input_point_fc_name = "subset2_points_from_parcel_lines_from_polygons_TEST"

    feature_dataset = os.getenv("FEATURE_DATASET")
    input_fc = os.path.join(feature_dataset, input_line_fc_name)
    output_midpoints_fc_name = "midpoints_and_corners_20250128"
    output_midpoints_fc = os.path.join(feature_dataset, output_midpoints_fc_name)
    output_split_lines_fc = os.path.join(feature_dataset, "split_parcel_lines_in_zones_r_th_otmu_li_ao_20250128")
    # Temporary outputs
    temp_points_fc = os.path.join(feature_dataset, "temp_points_from_lines_20250128")

    # TODO check for existence first and uncomment if needed
    #arcpy.management.Delete(output_split_lines_fc)
    #arcpy.management.Delete(output_midpoints_fc)
    arcpy.management.Delete(temp_points_fc)

    # Step 1: Convert lines to points
    line_to_points(input_fc, temp_points_fc)

    # Step 2: Get lines with more than x points
    line_oid_lists = categorize_lines_based_on_x_points(input_fc, min_vertices)

    # Step 3: Calculate and save midpoints and corners
    #get_midpoints_and_clusters(input_fc, line_oids, output_midpoints_fc_name, 7, 40)
    #get_clustered_points(input_fc, line_oids, output_midpoints_fc_name, 6, 50)

    get_points_for_splitting(input_point_fc_name, line_oid_lists, 30)

    # Step 4: Split lines at midpoints
    #split_lines(input_fc, output_midpoints_fc, output_split_lines_fc, 250)

    # Cleanup
    #arcpy.management.Delete(temp_points_fc)

    print("Processing complete.")
    print("Total time: {:.2f} seconds".format(time.time() - start_time))


run(2)
