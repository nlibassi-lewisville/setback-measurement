import arcpy
import math
from shared import set_environment


# TODO - determine if input should be lines split at vertices or lines with vertices
# had originally named this file "combine_segments.py" but it might be easier to create points at which lines should be split
# abandoned this part of the process 2/10 as Planning only needs to know whether or not the setback distances face a street

# Function to calculate angle between two points
def calculate_angle(p1, p2):
    """Calculate the angle of a line segment from p1 to p2 in degrees."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    return math.degrees(math.atan2(dy, dx))


# Function to merge consecutive segments
def merge_segments(segments):
    """
    Merge consecutive segments into a single polyline.
    :param segments: List of segments, where each segment is a list of points (points or lines???).
    """
    merged_polyline = arcpy.Polyline(arcpy.Array([pt for seg in segments for pt in seg]))
    return merged_polyline


def remove_unnecessary_segments(input_fc, output_fc):
    """
    Remove unnecessary line segments in an entire feature class based on angle threshold.
    :param input_fc: Path to the input feature class containing line segments.
    :param output_fc: Path to the output feature class for merged segments.
    """
    # Ensure the output feature class exists
    if arcpy.Exists(output_fc):
        arcpy.Delete_management(output_fc)

    # Create the output feature class with the same spatial reference
    spatial_ref = arcpy.Describe(input_fc).spatialReference
    arcpy.CreateFeatureclass_management(out_path=arcpy.Describe(input_fc).path, 
                                        out_name=output_fc.split("\\")[-1], 
                                        geometry_type="POLYLINE", 
                                        spatial_reference=spatial_ref)

    # Add necessary fields (copy from input if needed)
    arcpy.AddField_management(output_fc, "OriginalID", "LONG")  # Assuming an ID field

    # Read input line segments
    fields = ["OID@", "SHAPE@"]
    # segment_groups has keys of original IDs (OID of each input line feature) and values that are lists of points that comprise each segment
    segment_groups = {}
    # segment_groups has keys of original IDs (OID of each input line feature) and values that are lists of angles between each pair of points in each segment
    angle_groups = {}

    angle_group_diffs = {}

    angle_group_diffs_2 = {}

    # populate segment_groups and angle_groups for each feature in the input feature class
    with arcpy.da.SearchCursor(input_fc, fields) as cursor:
        for row in cursor:
            oid, shape = row
            points = [shape.getPart(0).getObject(i) for i in range(shape.pointCount)]
            if oid not in segment_groups:
                segment_groups[oid] = []
            segment_groups[oid].append(points)

            points = [(p.X, p.Y) for p in points]

            angles = []
            for i in range(len(points) - 1):
                angle = calculate_angle(points[i], points[i + 1])
                angles.append(angle)
            angle_groups[oid] = angles

            # add absolute values of differences between angles to angle_group_diffs (TODO - stop using abs values??)
            angle_group_diffs[oid] = [abs(angle_groups[oid][i] - angle_groups[oid][i + 1]) for i in range(len(angle_groups[oid]) - 1)]

            angle_group_diffs_2[oid] = [abs(angle_group_diffs[oid][i] - angle_group_diffs[oid][i + 2]) for i in range(len(angle_group_diffs[oid]) - 2)]

    print(f"first two segment groups: {list(segment_groups.items())[:2]}\n")
    print(f"first 15 angle groups: {list(angle_groups.items())[:15]}\n")
    print(f"first 15 angle group differences: {list(angle_group_diffs.items())[:15]}\n")
    print(f"first 15 angle group differences of differences: {list(angle_group_diffs_2.items())[:15]}\n")

    diff_threshold = 0.5

    # testing with diff_list
    diff_list = []

    previous_diff = None
    # testing with list of differences in angle_group_diffs_2 for OID 11
    for diff in angle_group_diffs_2[11]:
        if diff < diff_threshold and (previous_diff is None or previous_diff < diff_threshold):
            diff_list.append(diff)

    print(f"diff_list for angle_group_diffs_2[11]: {diff_list}\n")

    # Process each group of segments
    #angle_threshold = 10  # Degrees; adjust as needed

    #with arcpy.da.InsertCursor(output_fc, ["SHAPE@", "OriginalID"]) as insert_cursor:
    #    for original_id, segments in segment_groups.items():
    #        #merged_segments = []
    #        current_merge = [segments[0]]  # Start with the first segment
    #        for i in range(1, len(segments)):
    #            prev_segment = segments[i - 1]
    #            current_segment = segments[i]
    #            # Calculate angles of previous and current segment
    #            prev_angle = calculate_angle(prev_segment[0], prev_segment[-1])
    #            curr_angle = calculate_angle(current_segment[0], current_segment[-1])
    #            # Check if angle difference is within threshold
    #            if abs(prev_angle - curr_angle) <= angle_threshold:
    #                # Merge by adding current segment to ongoing merge
    #                current_merge.append(current_segment)
    #            else:
    #                # Insert the merged segment and start a new merge
    #                insert_cursor.insertRow([merge_segments(current_merge), original_id])
    #                current_merge = [current_segment]
    #        # Insert the last merged segment
    #        if current_merge:
    #            insert_cursor.insertRow([merge_segments(current_merge), original_id])

    print("Processing complete. Merged feature class created at:", output_fc)


def main():
    set_environment()
    input_fc = "parcel_block_boundary_lines_one_diff_over_0_5"
    output_fc = "merged_segments_output"
    if arcpy.Exists(output_fc):
        arcpy.Delete_management(output_fc)
    remove_unnecessary_segments(input_fc, output_fc)


if __name__ == "__main__":
    main()