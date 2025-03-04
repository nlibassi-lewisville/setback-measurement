import os
import math
import arcpy
import time
import pandas as pd
import numpy as np
from shared import set_environment


def calculate_angle(geometry):
    # Same as before
    start = geometry.firstPoint
    end = geometry.lastPoint
    dx = end.X - start.X
    dy = end.Y - start.Y
    angle = math.degrees(math.atan2(dy, dx)) % 360
    return angle if angle <= 180 else angle - 180


def is_parallel(angle1, angle2, tolerance=10):
    # Same as before
    diff = abs(angle1 - angle2)
    return diff <= tolerance


def transform_near_table_with_street_info(gdb_path, near_table_name, parcel_street_join, street_fc, parcel_line_fc):
    print("Transforming near table to include info on adjacent streets and other sides...")

    # Load spatial join results
    join_array = arcpy.da.TableToNumPyArray(parcel_street_join, ["TARGET_FID", "StFULLName", "is_parallel_to_street"])
    join_df = pd.DataFrame(join_array)
    join_df = join_df.rename(columns={"TARGET_FID": "PB_FID", "StFULLName": "STREET_NAME"})

    # Load the near table
    near_table_path = os.path.join(gdb_path, near_table_name)
    near_array = arcpy.da.TableToNumPyArray(near_table_path, "*")
    near_df = pd.DataFrame(near_array)

    # Merge near table with join results
    merged_df = near_df.merge(join_df, left_on="NEAR_FID", right_on="PB_FID", how="left")
    merged_df["is_facing_street"] = (merged_df["STREET_NAME"].notna()) & (merged_df["is_parallel_to_street"] == "Yes")

    # Populate fields for facing streets and other sides
    output_data = []
    for in_fid, group in merged_df.groupby("IN_FID"):
        row = {"IN_FID": in_fid}
        facing_count, other_count = 1, 1

        for _, record in group.iterrows():
            near_fid = record["NEAR_FID"]
            distance = record["NEAR_DIST"]

            if record["is_facing_street"]:
                if facing_count <= 4:
                    row[f"FACING_STREET_{facing_count}"] = record["STREET_NAME"]
                    row[f"FACING_STREET_{facing_count}_PB_FID"] = near_fid
                    row[f"FACING_STREET_{facing_count}_DIST_FT"] = distance
                    facing_count += 1
            else:
                if other_count <= 4:
                    row[f"OTHER_SIDE_{other_count}_PB_FID"] = near_fid
                    row[f"OTHER_SIDE_{other_count}_DIST_FT"] = distance
                    other_count += 1

        output_data.append(row)

    output_df = pd.DataFrame(output_data)
    output_df.fillna(-1, inplace=True)

    output_array = np.array(
        [tuple(row) for row in output_df.to_records(index=False)],
        dtype=[(col, "f8" if "DIST" in col else "<U50") for col in output_df.columns]
    )

    transformed_table_path = os.path.join(gdb_path, "transformed_near_table_with_street_info")
    if arcpy.Exists(transformed_table_path):
        arcpy.management.Delete(transformed_table_path)

    arcpy.da.NumPyArrayToTable(output_array, transformed_table_path)
    print(f"Transformed near table written to: {transformed_table_path}")
    return transformed_table_path


def process_parcel(parcel_id, all_parcel_polygons_fc, building_fc, initial_near_table, output_near_table, output_lines_fc, max_side_fields=4):
    print(f"Processing parcel {parcel_id}...")

    # Isolate the current parcel
    arcpy.management.MakeFeatureLayer(all_parcel_polygons_fc, "parcel_polygon_layer", f"OBJECTID = {parcel_id}")
    parcel_line_fc = f"parcel_line_{parcel_id}"
    arcpy.management.PolygonToLine("parcel_polygon_layer", parcel_line_fc)

    # Add field for polygon ID
    arcpy.management.AddField(parcel_line_fc, "PARCEL_POLYGON_OID", "LONG")
    arcpy.management.CalculateField(parcel_line_fc, "PARCEL_POLYGON_OID", f"{parcel_id}")

    # Split parcel lines
    parcel_points_fc = f"parcel_points_{parcel_id}"
    arcpy.management.FeatureVerticesToPoints(parcel_line_fc, parcel_points_fc, "ALL")
    split_parcel_lines_fc = os.path.join(os.getenv("FEATURE_DATASET"), f"split_parcel_lines_{parcel_id}")
    arcpy.management.SplitLineAtPoint(parcel_line_fc, parcel_points_fc, split_parcel_lines_fc, search_radius="500 Feet")

    # Select buildings within the parcel
    arcpy.management.MakeFeatureLayer(building_fc, "building_layer")
    arcpy.management.SelectLayerByLocation("building_layer", "WITHIN", "parcel_polygon_layer")

    # Generate near table
    arcpy.analysis.GenerateNearTable("building_layer", split_parcel_lines_fc, initial_near_table, method="PLANAR", closest="ALL", search_radius="150 Feet")

    # Add additional fields
    for i in range(1, max_side_fields + 1):
        arcpy.management.AddField(initial_near_table, f"FACING_STREET_{i}", "TEXT")
        arcpy.management.AddField(initial_near_table, f"FACING_STREET_{i}_DIST_FT", "FLOAT")
        arcpy.management.AddField(initial_near_table, f"OTHER_SIDE_{i}_PB_FID", "LONG")
        arcpy.management.AddField(initial_near_table, f"OTHER_SIDE_{i}_DIST_FT", "FLOAT")

    arcpy.management.AddField(initial_near_table, "PARCEL_COMBO_FID", "TEXT")
    arcpy.management.CalculateField(initial_near_table, "PARCEL_COMBO_FID", f"'{parcel_id}-' + str(!NEAR_FID!)", "PYTHON3")


# Run function to tie everything together
def run(building_source_date, parcel_id, all_parcel_lines_fc):
    set_environment()
    gdb = os.getenv("GEODATABASE")
    feature_dataset = os.getenv("FEATURE_DATASET")

    parcel_fc = "parcels_in_zones_r_th_otmu_li_ao"
    building_fc = f"extracted_footprints_nearmap_{building_source_date}_in_aoi_and_zones_r_th_otmu_li_ao"

    initial_near_table = os.path.join(gdb, f"initial_near_table_{parcel_id}")
    process_parcel(parcel_id, parcel_fc, building_fc, initial_near_table, None, None, max_side_fields=4)


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

# using a single previous point and current point
with arcpy.da.SearchCursor("points_from_parcel_lines_from_polygons", ["OBJECTID", "SHAPE@"]) as cursor:
    previous_geom = None
    for row in cursor:
        if row[0] == 1:
            previous_geom = row[1]
        elif row[0] < 7:
            if previous_geom:
                oid = row[0]
                angle = calculate_angle_from_points(previous_geom, row[1])
                print(f"Angle between point with OID {oid-1} and that with {oid}: {angle}")
                previous_geom = row[1]

# using two previous points and current point
with arcpy.da.SearchCursor("points_from_parcel_lines_from_polygons", ["OBJECTID", "SHAPE@"]) as cursor:
    previous_geom_1 = None
    previous_geom_2 = None
    for row in cursor:
        if row[0] == 1:
            previous_geom_1 = row[1]
        elif row[0] == 2:
            previous_geom_2 = row[1]
        elif row[0] < 7:
            oid = row[0]
            angle_1 = calculate_angle_from_points(previous_geom_1, previous_geom_2)
            angle_2 = calculate_angle_from_points(previous_geom_2, row[1])
            angle = angle_2 - angle_1
            print(f"OID's: {oid-2}, {oid-1}, {oid}. Angle: {angle}")
            previous_geom_1 = previous_geom_2
            previous_geom_2 = row[1]    



# creating a feature class from coordinate pairs (in Python window in Pro)

spatial_reference = arcpy.Describe("parcel_lines_from_polygons").spatialReference
point_list = []
with arcpy.da.SearchCursor("parcel_lines_from_polygons", ["SHAPE@"]) as cursor:
    for row in cursor:
        coords = []
        coords.append(row[0].positionAlongLine(0.5,True).firstPoint.X)
        coords.append(row[0].positionAlongLine(0.5,True).firstPoint.Y)
        point_list.append(coords)
point_list
[[2430329.0269888253, 7065293.877205671], [2430446.8901319727, 7065241.751775163], [2430515.0806996343, 7065314.388608029]]
points = [arcpy.PointGeometry(arcpy.Point(*c), spatial_reference) for c in point_list]
arcpy.management.CopyFeatures(points, "test2_points_from_coords")


# true centroid test
with arcpy.da.SearchCursor("parcel_lines_from_polygons", ["OBJECTID", "SHAPE@"]) as cursor:
    for row in cursor:
        print(f"OID: {row[0]}, X of centroid: {row[1].centroid.X}, X of true centroid: {row[1].trueCentroid.X}")
#OID: 331, X of centroid: 2429063.533212676, X of true centroid: 2429064.295714088 (U-shaped (upside down) with rounded corners)
#OID: 1955, X of centroid: 2430329.195365561, X of true centroid: 2430353.3099913066 (corner lot with one curve)
#OID: 1959, X of centroid: 2430560.5866131866, X of true centroid: 2430574.7136286166 (corner lot with one curve)
#OID: 2024, X of centroid: 2430424.334699686, X of true centroid: 2430424.4031898836 (U-shaped (right side up) with 90-degree corners) - same x coord for centroid types but y coord should be different
#OID: 2025, X of centroid: 2430625.936357139, X of true centroid: 2430625.931949639 (nearly straight line with more than 2 points)
#OID: 5325, X of centroid: 2430422.4844325962, X of true centroid: 2430422.4844340817 (straight line generally north-south)
#OID: 5327, X of centroid: 2430448.7651312305, X of true centroid: 2430448.765131 (straight line generally east-west)
#OID: 5329, X of centroid: 2430505.888046725, X of true centroid: 2430505.888046249 (straight line generally east-west)
#OID: 5598, X of centroid: 2430261.17807485, X of true centroid: 2430222.13639151 (U-shaped (opening to the left) with corners somewhat rounded) 
#OID: 5797, X of centroid: 2429745.6830369025, X of true centroid: 2429741.278611942 (Upside down backwards L with 90 degree corner)

# why would hasCurves always return False for these lines?
with arcpy.da.SearchCursor("parcel_lines_from_polygons", ["OBJECTID", "SHAPE@"]) as cursor:
    for row in cursor:
        print(f"OID: {row[0]}, has curves: {row[1].hasCurves}")
#OID: 331, has curves: False
#OID: 1955, has curves: False
#OID: 1959, has curves: False
#OID: 2024, has curves: False
#OID: 2025, has curves: False
#OID: 5325, has curves: False
#OID: 5327, has curves: False
#OID: 5329, has curves: False
#OID: 5598, has curves: False
#OID: 5797, has curves: False
#OID: 5977, has curves: False       


# example using json but also returns 'No curves' for all input geometries though some have curves
geometries = arcpy.CopyFeatures_management("inputFeatures", arcpy.Geometry())
import json
for g in geometries:
    j = json.loads(g.JSON)
    if 'curve' in j:print("You have true curves!")
    else: print("No curves here")

#No curves here
#No curves here
#You have true curves!
#You have true curves!
#No curves here
#You have true curves!
#No curves here
#No curves here
#You have true curves!
#You have true curves!
#You have true curves!
#You have true curves!
#You have true curves!


# try this call of GenerateNearTable using closet_count = x
output_near_table = 'path_to_your_output_near_table'
arcpy.analysis.GenerateNearTable(
    in_features="extracted_footprints_nm_20240107_in_aoi_and_zones_r_th_otmu_li_ao",
    near_features="parcel_lines_from_polygons",
    out_table=output_near_table,
    search_radius="150 Feet",
    location="NO_LOCATION",
    angle="NO_ANGLE",
    closest="ALL",
    closest_count=8,
    method="PLANAR",
    distance_unit="Feet"
)



arcpy.analysis.GenerateNearTable(
    in_features="extracted_footprints_nm_20240107_in_aoi_and_zones_r_th_otmu_li_ao",
    near_features="parcel_lines_from_polygons",
    out_table=output_near_table,
    search_radius="150 Feet",
    location="NO_LOCATION",
    angle="NO_ANGLE",
    closest="ALL",
    closest_count=8,
    method="PLANAR",
    distance_unit="Feet"
)


# find point clusters
out_fc = "path_to_output_feature_class"
arcpy.gapro.FindPointClusters(
    input_points="vertices_to_points_from_split_parcel_lines_in_zones_r_th_otmu_li_ao_20250128",
    out_feature_class=out_fc,
    clustering_method="HDBSCAN",
    minimum_points=4,
    search_distance=None,
    use_time="NO_TIME",
    search_duration=None
)


# get_point_spacing.py

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
    with arcpy.da.UpdateCursor(line_fc, ["parcel_line_OID", "OID@"]) as cursor:
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
    with arcpy.da.SearchCursor(unique_point_fc, ["parcel_line_OID", "OID@", "SHAPE@XY"], sql_clause=(None, "ORDER BY parcel_line_OID, OID@")) as cursor:
        current_line_id = None
        previous_point = None
        spacing_dict = {}

        for line_id, point_id, point_geom in cursor:
            if line_id != current_line_id:
                # Store previous line's spacing info
                if current_line_id is not None:
                    line_spacing[current_line_id] = json.dumps(spacing_dict)

                # Reset for new line
                current_line_id = line_id
                previous_point = None
                spacing_dict = {}

            if previous_point is not None:
                # Calculate distance between current and previous point (feet)
                dist = ((point_geom[0] - previous_point[0]) ** 2 + (point_geom[1] - previous_point[1]) ** 2) ** 0.5 * 3.28084  # Convert meters to feet
                spacing_dict[point_id] = round(dist, 2)

            previous_point = point_geom
        
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
    input_line_fc = "parcel_lines_from_polygons"
    workspace = os.getenv("GEODATABASE")
    main(input_line_fc, workspace)

# checking some angles - see related screenshots from 2/7

with arcpy.da.SearchCursor("parcel_block_boundary_lines_one_diff_over_0_5_split_at_vertices", ["OBJECTID", "SHAPE@"]) as cursor:
    for row in cursor:
        print(f"OID: {row[0]}, angle: {calculate_angle(row[1])}")
#OID: 3113, angle: 0.47299953129510186
#OID: 3114, angle: 0.47305639178534875
#OID: 3115, angle: 135.23034491568555
#OID: 3116, angle: 89.92880119565746
with arcpy.da.SearchCursor("parcel_block_boundary_lines_one_diff_over_0_5_split_at_vertices", ["OBJECTID", "SHAPE@"]) as cursor:
    for row in cursor:
        print(f"OID: {row[0]}, angle: {calculate_angle(row[1])}")
#OID: 2576, angle: 90.8883067706756
#OID: 2577, angle: 85.87634537471742
#OID: 2578, angle: 75.90097235931594
#OID: 2579, angle: 65.88636411919363
#OID: 2580, angle: 55.894308791371174
#OID: 2581, angle: 45.87296022041196
#OID: 2582, angle: 35.90399642345096
#OID: 2583, angle: 25.876050825924032
#OID: 2584, angle: 15.892794932917578
#OID: 2585, angle: 5.889306497730227
#OID: 2586, angle: 0.888986422617461
with arcpy.da.SearchCursor("parcel_block_boundary_lines_one_diff_over_0_5_split_at_vertices", ["OBJECTID", "SHAPE@"]) as cursor:
    for row in cursor:
        print(f"OID: {row[0]}, angle: {calculate_angle(row[1])}")
#OID: 2563, angle: 4.479241543440202
#OID: 2564, angle: 3.1560425858000047
#OID: 2565, angle: 172.67486338760494
#OID: 2566, angle: 163.084598752487
#OID: 2567, angle: 153.45750317591097
#OID: 2568, angle: 143.824766646691
#OID: 2569, angle: 134.1877134050668
#OID: 2570, angle: 124.57257101670666
#OID: 2571, angle: 114.95902480361008
#OID: 2572, angle: 105.3381652497722
#OID: 2573, angle: 95.70613422725103
#OID: 2574, angle: 90.88795255969046
#OID: 2575, angle: 91.3236303840443


#merged_df head:
#IN_FID  parcel_polygon_OID
#1                1396
#1                1583
#1                1439
#1                1439
#1                1396

def get_building_parcel_dict(spatial_join_output):
    """

    """
    building_parcel_dict = {}
    with arcpy.da.SearchCursor(spatial_join_output, ["TARGET_FID", "JOIN_FID"]) as cursor:
        for row in cursor:
            building_id = row[0]
            parcel_id = row[1]
            if building_id not in building_parcel_dict:
                building_parcel_dict[building_id] = parcel_id
    return building_parcel_dict


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


# for debugging in Pro 2/19/25

near_table = "trimmed_near_table_with_parcel_info"
fields = [f.name for f in arcpy.ListFields(near_table)]
fields = [f.name for f in arcpy.ListFields(near_table)]
fields
['OBJECTID', 'OBJECTID_1', 'IN_FID', 'NEAR_FID', 'NEAR_DIST', 'NEAR_RANK', 'FACING_STREET_1_PB_FID', 'FACING_STREET_1_DIST_FT', 'OTHER_SIDE_1_PB_FID', 'OTHER_SIDE_1_DIST_FT', 'FACING_STREET_2_PB_FID', 'FACING_STREET_2_DIST_FT', 'OTHER_SIDE_2_PB_FID', 'OTHER_SIDE_2_DIST_FT', 'FACING_STREET_3_PB_FID', 'FACING_STREET_3_DIST_FT', 'OTHER_SIDE_3_PB_FID', 'OTHER_SIDE_3_DIST_FT', 'FACING_STREET_4_PB_FID', 'FACING_STREET_4_DIST_FT', 'OTHER_SIDE_4_PB_FID', 'OTHER_SIDE_4_DIST_FT', 'parcel_line_OID', 'shared_boundary', 'parcel_polygon_OID', 'intended_parcel_polygon_OID']
near_array = arcpy.da.TableToNumPyArray(near_table, fields)

near_table = "trimmed_near_table_with_parcel_info_intended_parcel_polygon_oid_not_null"
near_array = arcpy.da.TableToNumPyArray(near_table, fields)
import pandas as pd
near_df = pd.DataFrame(near_array)
output_data = []
in_fid_field = f"IN_FID"
near_fid_field = f"NEAR_FID"
near_dist_field = f"NEAR_DIST"
facing_street_field_part_1 = f"FACING_STREET"
other_side_field_part_1 = f"OTHER_SIDE"
shared_boundary_field = f"shared_boundary"
for in_fid, group in near_df.groupby(in_fid_field):
    row = {in_fid_field: in_fid}
    facing_count, other_count = 1, 1
    for _, record in group.iterrows():
        near_fid = record[near_fid_field]
        distance = record[near_dist_field]
        if record[shared_boundary_field]:
            print(record)
            break