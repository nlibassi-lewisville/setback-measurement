import time
import arcpy
from shared import set_environment


def add_surrounding_parcels_to_buildings(building_fc, parcel_fc, output_fc):
    """
    Add the OBJECTID values of surrounding parcel polygons to a new field in the building feature class.
    :param building_fc: Path to the building polygon feature class.
    :param parcel_fc: Path to the parcel polygon feature class.
    :param output_fc: Path to the output building feature class with parcel OBJECTIDs.
    """
    print("Adding surrounding parcel OBJECTIDs to buildings...")
    arcpy.management.AddField(building_fc, "enclosing_parcel_polygon_oid", "TEXT")

    # Spatial join to get parcel OBJECTIDs for each building
    parcel_oid_field = arcpy.Describe(parcel_fc).OIDFieldName
    arcpy.analysis.SpatialJoin(
        target_features=building_fc,
        join_features=parcel_fc,
        out_feature_class=output_fc,
        join_type="KEEP_COMMON",
        match_option="INTERSECT",
        field_mapping=f"enclosing_parcel_polygon_oid '{parcel_oid_field}' true true false 255 Text 0 0 ,First,#,{parcel_fc},{parcel_oid_field},-1,-1",
    )
    print(f"Surrounding parcel OBJECTIDs added to buildings in {output_fc}.")


def create_line_features(parcel_polygon_fc, building_polygon_fc, parcel_line_fc, building_line_fc):
    """
    Convert parcel and building polygons to line features.
    :param parcel_polygon_fc - string: Path to the parcel polygon feature class.
    :param building_polygon_fc - string: Path to the building polygon feature class.
    :param parcel_line_fc - string: Path for the output parcel line feature class.
    :param building_line_fc - string: Path for the output building line feature class.
    """
    print("Converting polygons to lines...")
    arcpy.management.PolygonToLine(parcel_polygon_fc, parcel_line_fc)
    arcpy.management.PolygonToLine(building_polygon_fc, building_line_fc)
    print("Line features created.")


'''
TODO - remove if unused
def preserve_parcel_oids_in_lines(parcel_fc, output_fc):
    """
    Convert parcel polygons to lines while preserving their OBJECTID values.
    :param parcel_fc: Path to the parcel polygon feature class.
    :param output_fc: Path to the output parcel line feature class.
    """
    print("Converting parcels to lines while preserving OBJECTIDs...")
    arcpy.management.PolygonToLine(parcel_fc, output_fc)
    print(f"Parcel polygons converted to lines in {output_fc}.")


def convert_buildings_to_outer_lines(building_fc, output_fc):
    """
    Convert building polygons to lines, preserving only the outermost lines.
    :param building_fc: Path to the building polygon feature class.
    :param output_fc: Path to the output building line feature class.
    """
    print("Converting buildings to outer lines...")
    arcpy.management.PolygonToLine(building_fc, output_fc, "IGNORE_HOLES")
    print(f"Building polygons converted to outer lines in {output_fc}.")
'''

# TODO - remove or move to measure.py
def calculate_distances_to_filtered_parcels(building_lines_fc, parcel_lines_fc, output_table):
    """
    For each building line, calculate distances to the parcel lines whose OID matches the surrounding parcel IDs.
    :param building_lines_fc: Path to the building line feature class.
    :param parcel_lines_fc: Path to the parcel line feature class.
    :param output_table: Path to the output table with calculated distances.
    """
    print("Calculating distances to filtered parcel lines...")
    building_oid_field = arcpy.Describe(building_lines_fc).OIDFieldName
    arcpy.management.AddField(building_lines_fc, "enclosing_parcel_polygon_oid", "TEXT")  # Field to store parcel IDs

    # Iterate through each building
    with arcpy.da.UpdateCursor(building_lines_fc, ["SHAPE@", "enclosing_parcel_polygon_oid", building_oid_field]) as building_cursor:
        for building_row in building_cursor:
            building_geom = building_row[0]
            enclosing_parcel_polygon_oid = building_row[1].split(",")  # Get surrounding parcel OIDs
            building_oid = building_row[2]

            # Select parcel lines by matching OIDs
            where_clause = f"OBJECTID IN ({','.join(enclosing_parcel_polygon_oid)})"
            arcpy.management.MakeFeatureLayer(parcel_lines_fc, "filtered_parcel_lines", where_clause)

            # Calculate distances
            near_table = f"in_memory/near_table_{building_oid}"
            arcpy.analysis.GenerateNearTable(
                in_features=building_lines_fc,
                near_features="filtered_parcel_lines",
                out_table=near_table,
                method="PLANAR",
                closest="ALL",
            )

            # Append results to the output table
            arcpy.management.Append(near_table, output_table, "NO_TEST")

    print(f"Distance calculations completed. Results saved to {output_table}.")


# Main Execution
def run(building_source_date):
    """
    Run the process to convert polygons to lines
    :param building_source_date - string: date of imagery used to extract building footprints in format YYYYMMDD e.g. "20240107"
    """
    start_time = time.time()
    print(f"Starting setback distance calculation with fields holding info on adjacent streets {time.ctime(start_time)}")
    set_environment()

    # Input feature classes
    building_fc = f"extracted_footprints_nearmap_{building_source_date}_in_aoi_and_zones_r_th_otmu_li_ao"
    parcel_fc = "parcels_in_zones_r_th_otmu_li_ao"

    # Intermediate outputs
    buildings_with_parcels_fc = f"buildings_{building_source_date}_with_parcel_ids"
    parcel_lines_fc = "parcel_lines"
    building_lines_fc = f"building_lines_{building_source_date}"
    #output_table = "output_distances_table"

    # Add surrounding parcels to buildings
    add_surrounding_parcels_to_buildings(building_fc, parcel_fc, buildings_with_parcels_fc)

    create_line_features(parcel_fc, buildings_with_parcels_fc, parcel_lines_fc, building_lines_fc)

    # Calculate distances to filtered parcels
    #calculate_distances_to_filtered_parcels(building_lines_fc, parcel_lines_fc, output_table)


# Run the script
if __name__ == "__main__":
    run("20240107")
