import os
import math
import arcpy
import time
import pandas as pd
import numpy as np
from shared import set_environment


def calculate_angle(geometry):
    """
    Calculate the angle (bearing) of a line geometry in degrees, accounting for bidirectional lines.
    :param geometry: The geometry object of the line.
    :return: Angle in degrees (0-360).
    """
    start = geometry.firstPoint
    end = geometry.lastPoint
    dx = end.X - start.X
    dy = end.Y - start.Y
    angle = math.degrees(math.atan2(dy, dx))
    # Normalize to 0-360 degrees
    angle = angle % 360
    # Normalize the angle to the range 0-180 (to account for bidirectional lines)
    if angle > 180:
        angle -= 180
    return angle


def is_parallel(angle1, angle2, tolerance=10):
    """
    Check if two angles are roughly parallel within a given tolerance.
    :param angle1: Angle of the first line in degrees.
    :param angle2: Angle of the second line in degrees.
    :param tolerance: Tolerance in degrees for determining parallelism.
    :return: True if angles are roughly parallel, False otherwise.
    """
    diff = abs(angle1 - angle2)
    return diff <= tolerance


def clip_streets_near_parcel(parcel_fc, parcel_id, street_fc, output_street_fc, buffer_ft=40):
    """
    Clip streets near a parcel to avoid measuring distances to distant streets.
    :param parcel_fc: Path to the parcel feature class.
    :param parcel_id: The OBJECTID of the parcel to clip streets near.
    :param street_fc: Path to the street feature class.
    :param output_street_fc: Path to the output street feature class.
    :param buffer_ft: Distance in feet to buffer around the parcel.
    """
    print(f"Attempting to clip streets near parcel {parcel_id}...")
    arcpy.management.Delete("current_parcel")
    # Isolate the current parcel
    parcel_layer = "current_parcel"
    arcpy.management.MakeFeatureLayer(parcel_fc, parcel_layer, f"OBJECTID = {parcel_id}")
    
    # TODO - ask for permission to delete output feature class?
    arcpy.management.Delete(output_street_fc)
    arcpy.management.Delete("parcel_buffer")
    print("output_street_fc and parcel_buffer deleted")
    #arcpy.management.SelectLayerByAttribute(parcel_fc, "NEW_SELECTION", f"OBJECTID = {parcel_id}")

    parcel_buffer = "parcel_buffer"

    # TODO - create buffer in memory or delete when finished
    arcpy.analysis.Buffer(
    in_features=parcel_layer,
    out_feature_class=parcel_buffer,
    buffer_distance_or_field=f"{buffer_ft} Feet",
    line_side="FULL",
    line_end_type="ROUND",
    dissolve_option="NONE",
    dissolve_field=None,
    method="PLANAR"
    )
    print("Buffer created")
    # Buffer the parcel to clip streets
    #buffer_layer = "parcel_buffer"
    #arcpy.analysis.Buffer(parcel_layer, buffer_layer, f"{buffer_ft} Feet")

    # Clip streets near the parcel - returns almost all streets (but because the buffer created was too large - may be able to return to this)
    arcpy.analysis.Clip(street_fc, parcel_buffer, output_street_fc)


    # TODO - find faster solution for this?
    #arcpy.gapro.ClipLayer(
    #    input_layer=street_fc,
    #    clip_layer=parcel_buffer,
    #    out_feature_class=output_street_fc,
    #    )



def populate_parallel_field(parcel_street_join_fc, parcel_line_fc, street_name_field, parallel_field, street_fc):
    """
    Populate a field in the parcel-street join table with info on whether or not each segment is parallel to the street.
    :param parcel_street_join_fc: Path to the feature class resulting from the spatial join between parcel boundary segments and streets.
    :param parcel_line_fc: Path to the parcel line feature class.
    :param street_name_field: Name of the field in the parcel_street_join_fc that contains the street name associated with each parcel boundary segment feature.
    :param parallel_field: Name of the field to populate with parallelism info.
    :param street_fc: Path to the street feature class.
    """
    print("Attempting to populate parallel field...")

    #parcel_line_fc = "parcel_lines"

    # TODO - move spatial join and addition of "is_parallel_to_street" to separate function!!

    #Pre-compute spatial relationships between parcel lines and streets
    #parcel_street_join = os.path.join(gdb_path, "parcel_street_join")
    if arcpy.Exists(parcel_street_join_fc):
        arcpy.management.Delete(parcel_street_join_fc)

    print("Performing spatial join between parcel lines and streets...")

    #TODO: # Use a search radius that is appropriate for the data
    # value of join_type may not matter when join_operation is JOIN_ONE_TO_MANY
    # field mapping came from Pro to preserve shared_boundary and parcel_polygon_OID fields - may need to adjust
    arcpy.analysis.SpatialJoin(parcel_line_fc, street_fc, parcel_street_join_fc, join_operation="JOIN_ONE_TO_MANY", join_type="KEEP_COMMON", 
        match_option="WITHIN_A_DISTANCE", search_radius="50 Feet", field_mapping='FID_parcels_in_zones_r_th_otmu_li_ao "FID_parcels_in_zones_r_th_otmu_li_ao" true true false 4 Long 0 0,First,#,parcel_lines_from_polygons_TEST,FID_parcels_in_zones_r_th_otmu_li_ao,-1,-1;PROP_TYPE "Property Type" true true false 5 Text 0 0,First,#,parcel_lines_from_polygons_TEST,PROP_TYPE,0,4;prop_id "Property ID" true true false 4 Long 0 0,First,#,parcel_lines_from_polygons_TEST,prop_id,-1,-1;RNUMBER "RNUMBER" true true false 20 Text 0 0,First,#,parcel_lines_from_polygons_TEST,RNUMBER,0,19;ABST_SUBD_NUM "Abstract Subdivision Number" true true false 254 Text 0 0,First,#,parcel_lines_from_polygons_TEST,ABST_SUBD_NUM,0,253;ABST_SUBD_NAME "Abstract Subdivision Name" true true false 254 Text 0 0,First,#,parcel_lines_from_polygons_TEST,ABST_SUBD_NAME,0,253;OWNER "OWNER" true true false 70 Text 0 0,First,#,parcel_lines_from_polygons_TEST,OWNER,0,69;ADDR1 "ADDR1" true true false 60 Text 0 0,First,#,parcel_lines_from_polygons_TEST,ADDR1,0,59;ADDR2 "ADDR2" true true false 60 Text 0 0,First,#,parcel_lines_from_polygons_TEST,ADDR2,0,59;ADDR3 "ADDR3" true true false 60 Text 0 0,First,#,parcel_lines_from_polygons_TEST,ADDR3,0,59;CITY "CITY" true true false 50 Text 0 0,First,#,parcel_lines_from_polygons_TEST,CITY,0,49;STATE "STATE" true true false 50 Text 0 0,First,#,parcel_lines_from_polygons_TEST,STATE,0,49;ZIP "ZIP" true true false 20 Text 0 0,First,#,parcel_lines_from_polygons_TEST,ZIP,0,19;SITUS "Address" true true false 150 Text 0 0,First,#,parcel_lines_from_polygons_TEST,SITUS,0,149;SITUS_NUM "Address Number" true true false 50 Text 0 0,First,#,parcel_lines_from_polygons_TEST,SITUS_NUM,0,49;SITUS_STREET "Street" true true false 140 Text 0 0,First,#,parcel_lines_from_polygons_TEST,SITUS_STREET,0,139;SITUS_PREDIR "Street Predirection" true true false 20 Text 0 0,First,#,parcel_lines_from_polygons_TEST,SITUS_PREDIR,0,19;SITUS_STREETNAME "SITUS_STREETNAME" true true false 60 Text 0 0,First,#,parcel_lines_from_polygons_TEST,SITUS_STREETNAME,0,59;SITUS_STREETTYPE "SITUS_STREETTYPE" true true false 40 Text 0 0,First,#,parcel_lines_from_polygons_TEST,SITUS_STREETTYPE,0,39;LEGAL_DESC "Legal Description" true true false 254 Text 0 0,First,#,parcel_lines_from_polygons_TEST,LEGAL_DESC,0,253;BLOCK "Block" true true false 50 Text 0 0,First,#,parcel_lines_from_polygons_TEST,BLOCK,0,49;LOT "Lot" true true false 50 Text 0 0,First,#,parcel_lines_from_polygons_TEST,LOT,0,49;LANDSQFT "LANDSQFT" true true false 8 Double 0 0,First,#,parcel_lines_from_polygons_TEST,LANDSQFT,-1,-1;ACREAGE "Acreage" true true false 8 Double 0 0,First,#,parcel_lines_from_polygons_TEST,ACREAGE,-1,-1;LIVINGAREA "LIVINGAREA" true true false 8 Double 0 0,First,#,parcel_lines_from_polygons_TEST,LIVINGAREA,-1,-1;yr_blt "YR_BLT" true true false 2 Short 0 0,First,#,parcel_lines_from_polygons_TEST,yr_blt,-1,-1;EXEMPTION "Exemption" true true false 100 Text 0 0,First,#,parcel_lines_from_polygons_TEST,EXEMPTION,0,99;TAXUNIT "Tax Unit" true true false 72 Text 0 0,First,#,parcel_lines_from_polygons_TEST,TAXUNIT,0,71;SPTB_CODE "SPTB Code" true true false 10 Text 0 0,First,#,parcel_lines_from_polygons_TEST,SPTB_CODE,0,9;LAND_TYPE "Land Type" true true false 10 Text 0 0,First,#,parcel_lines_from_polygons_TEST,LAND_TYPE,0,9;DCADHyperlink "DCADHyperlink" true true false 250 Text 0 0,First,#,parcel_lines_from_polygons_TEST,DCADHyperlink,0,249;LAST_IMPORT_DATE "Last Import Date" true true false 8 Date 0 1,First,#,parcel_lines_from_polygons_TEST,LAST_IMPORT_DATE,-1,-1;Plats "Plats" true true false 500 Text 0 0,First,#,parcel_lines_from_polygons_TEST,Plats,0,499;cert_mkt_v "market value" true true false 8 Double 0 0,First,#,parcel_lines_from_polygons_TEST,cert_mkt_v,-1,-1;cad_zoning "cad_zoning" true true false 255 Text 0 0,First,#,parcel_lines_from_polygons_TEST,cad_zoning,0,254;parcel_polygon_OID "parcel_polygon_OID" true true false 4 Long 0 0,First,#,parcel_lines_from_polygons_TEST,parcel_polygon_OID,-1,-1;Shape_Length "Shape_Length" false true true 8 Double 0 0,First,#,parcel_lines_from_polygons_TEST,Shape_Length,-1,-1;shared_boundary "shared_boundary" true true false 2 Short 0 0,First,#,parcel_lines_from_polygons_TEST,shared_boundary,-1,-1;StFULLName "Street_Name_Full" true true false 50 Text 0 0,First,#,clipped_streets_near_parcel_62,StFULLName,0,49;MILES "Miles" true true false 8 Double 0 0,First,#,clipped_streets_near_parcel_62,MILES,-1,-1;LaneMiles "Lane_Miles" true true false 8 Double 0 0,First,#,clipped_streets_near_parcel_62,LaneMiles,-1,-1;Shoulder "Shoulder" true true false 20 Text 0 0,First,#,clipped_streets_near_parcel_62,Shoulder,0,19;FacilityID "FacilityID" true true false 30 Text 0 0,First,#,clipped_streets_near_parcel_62,FacilityID,0,29;L_ADD_FROM "L_ADD_FROM" true true false 8 Double 0 0,First,#,clipped_streets_near_parcel_62,L_ADD_FROM,-1,-1;L_ADD_TO "L_ADD_TO" true true false 8 Double 0 0,First,#,clipped_streets_near_parcel_62,L_ADD_TO,-1,-1;R_ADD_FROM "R_ADD_FROM" true true false 8 Double 0 0,First,#,clipped_streets_near_parcel_62,R_ADD_FROM,-1,-1;R_ADD_TO "R_ADD_TO" true true false 8 Double 0 0,First,#,clipped_streets_near_parcel_62,R_ADD_TO,-1,-1;PRETYPE "PRETYPE" true true false 20 Text 0 0,First,#,clipped_streets_near_parcel_62,PRETYPE,0,19;STDIR "STDIR" true true false 2 Text 0 0,First,#,clipped_streets_near_parcel_62,STDIR,0,1;STNAME "STNAME" true true false 50 Text 0 0,First,#,clipped_streets_near_parcel_62,STNAME,0,49;STTYPE "STTYPE" true true false 20 Text 0 0,First,#,clipped_streets_near_parcel_62,STTYPE,0,19;STSUF "STSUF" true true false 2 Text 0 0,First,#,clipped_streets_near_parcel_62,STSUF,0,1;TRANS_CLAS "Transportation_Class" true true false 10 Text 0 0,First,#,clipped_streets_near_parcel_62,TRANS_CLAS,0,9;SPEEDLIMIT "Speed_Limit" true true false 8 Double 0 0,First,#,clipped_streets_near_parcel_62,SPEEDLIMIT,-1,-1;MINUTES "MINUTES" true true false 8 Double 0 0,First,#,clipped_streets_near_parcel_62,MINUTES,-1,-1;ID "ID" true true false 8 Double 0 0,First,#,clipped_streets_near_parcel_62,ID,-1,-1;OneWay "OneWay" true true false 2 Text 0 0,First,#,clipped_streets_near_parcel_62,OneWay,0,1;Add_Start "Add_Start" true true false 8 Double 0 0,First,#,clipped_streets_near_parcel_62,Add_Start,-1,-1;Add_End "Add_End" true true false 8 Double 0 0,First,#,clipped_streets_near_parcel_62,Add_End,-1,-1;Addr_Range "Addr_Range" true true false 50 Text 0 0,First,#,clipped_streets_near_parcel_62,Addr_Range,0,49;BlockRng "BlockRng" true true false 50 Text 0 0,First,#,clipped_streets_near_parcel_62,BlockRng,0,49;Owner_1 "Owner" true true false 50 Text 0 0,First,#,clipped_streets_near_parcel_62,Owner,0,49;Owner_DESC "Owner_DESC" true true false 254 Text 0 0,First,#,clipped_streets_near_parcel_62,Owner_DESC,0,253;LegacyID "LegacyID" true true false 30 Text 0 0,First,#,clipped_streets_near_parcel_62,LegacyID,0,29;SHAPE_STLe "SHAPE_STLe" true true false 8 Double 0 0,First,#,clipped_streets_near_parcel_62,SHAPE_STLe,-1,-1;Deactive_Date "Deactive_Date" true true false 8 Date 0 1,First,#,clipped_streets_near_parcel_62,Deactive_Date,-1,-1;created_user "created_user" true true false 255 Text 0 0,First,#,clipped_streets_near_parcel_62,created_user,0,254;created_date "created_date" true true false 8 Date 0 1,First,#,clipped_streets_near_parcel_62,created_date,-1,-1;last_edited_user "last_edited_user" true true false 255 Text 0 0,First,#,clipped_streets_near_parcel_62,last_edited_user,0,254;last_edited_date "last_edited_date" true true false 8 Date 0 1,First,#,clipped_streets_near_parcel_62,last_edited_date,-1,-1;Block_1 "Block" true true false 2 Short 0 0,First,#,clipped_streets_near_parcel_62,Block,-1,-1;PavType "Pavement_Type" true true false 25 Text 0 0,First,#,clipped_streets_near_parcel_62,PavType,0,24;F_ELEV "F_ELEV" true true false 2 Short 0 0,First,#,clipped_streets_near_parcel_62,F_ELEV,-1,-1;T_ELEV "T_ELEV" true true false 2 Short 0 0,First,#,clipped_streets_near_parcel_62,T_ELEV,-1,-1;MuniLeft "MuniLeft" true true false 50 Text 0 0,First,#,clipped_streets_near_parcel_62,MuniLeft,0,49;MuniRight "MuniRight" true true false 50 Text 0 0,First,#,clipped_streets_near_parcel_62,MuniRight,0,49;ZIPLeft "ZIPLeft" true true false 10 Text 0 0,First,#,clipped_streets_near_parcel_62,ZIPLeft,0,9;ZIPRight "ZIPRight" true true false 10 Text 0 0,First,#,clipped_streets_near_parcel_62,ZIPRight,0,9;ESNLeft "ESNLeft" true true false 4 Long 0 0,First,#,clipped_streets_near_parcel_62,ESNLeft,-1,-1;ESNRight "ESNRight" true true false 4 Long 0 0,First,#,clipped_streets_near_parcel_62,ESNRight,-1,-1;COUNTYLeft "COUNTYLeft" true true false 50 Text 0 0,First,#,clipped_streets_near_parcel_62,COUNTYLeft,0,49;COUNTYRight "COUNTYRight" true true false 50 Text 0 0,First,#,clipped_streets_near_parcel_62,COUNTYRight,0,49;STATELeft "STATELeft" true true false 2 Text 0 0,First,#,clipped_streets_near_parcel_62,STATELeft,0,1;STATERight "STATERight" true true false 2 Text 0 0,First,#,clipped_streets_near_parcel_62,STATERight,0,1;COUNTRYLeft "COUNTRYLeft" true true false 2 Text 0 0,First,#,clipped_streets_near_parcel_62,COUNTRYLeft,0,1;COUNTRYRight "COUNTRYRight" true true false 2 Text 0 0,First,#,clipped_streets_near_parcel_62,COUNTRYRight,0,1;gc_exception "gc_exception" true true false 10 Text 0 0,First,#,clipped_streets_near_parcel_62,gc_exception,0,9;from_street "from_street" true true false 50 Text 0 0,First,#,clipped_streets_near_parcel_62,from_street,0,49;to_street "to_street" true true false 50 Text 0 0,First,#,clipped_streets_near_parcel_62,to_street,0,49;Shape_Length_1 "Shape_Length" false true true 8 Double 0 0,First,#,clipped_streets_near_parcel_62,Shape_Length,-1,-1')
    
    # TODO - may be able to remove fields list and if statement after testing
    join_fields = arcpy.ListFields(parcel_street_join_fc)
    if not any(field.name == "is_parallel_to_street" for field in join_fields):
        arcpy.management.AddField(parcel_street_join_fc, "is_parallel_to_street", "SHORT")

    # TODO - remove TARGET_FID if not needed - only included for testing/logging
    with arcpy.da.UpdateCursor(parcel_street_join_fc, ["SHAPE@", street_name_field, parallel_field, "TARGET_FID"]) as cursor:
        for row in cursor:
            parcel_geom = row[0]
            street_name = row[1]
            parcel_segment_id = row[3]
            
            # Get the angle of the parcel segment
            parcel_angle = calculate_angle(parcel_geom)
            
            # Use a cursor to find the associated street geometry
            street_angle = None
            with arcpy.da.SearchCursor(street_fc, ["SHAPE@", "StFULLName"]) as street_cursor:
                for street_row in street_cursor:
                    if street_row[1] == street_name:
                        street_angle = calculate_angle(street_row[0])
                        break
            
            # Check if the angles are parallel
            if street_angle is not None:
                row[2] = 1 if is_parallel(parcel_angle, street_angle, tolerance=10) else 0
            else:
                # If no street found, set to -1
                row[2] = -1
            
            cursor.updateRow(row)

    # from Copilot - remove if not needed
    # Load the join table into a pandas DataFrame
    #join_array = arcpy.da.TableToNumPyArray(parcel_street_join_fc, ["TARGET_FID", "StFULLName", "Angle"])
    #join_df = pd.DataFrame(join_array)
    #join_df = join_df.rename(columns={"TARGET_FID": "PB_FID", "StFULLName": "STREET_NAME", "Angle": "STREET_ANGLE"})
    ## Load the street feature class into a pandas DataFrame
    #street_array = arcpy.da.FeatureClassToNumPyArray(street_fc, ["OBJECTID", "Angle"])
    #street_df = pd.DataFrame(street_array)
    #street_df = street_df.rename(columns={"OBJECTID": "STREET_FID", "Angle": "STREET_ANGLE"})
    ## Merge the join table with the street table to get street angles
    #merged_df = join_df.merge(street_df, left_on="PB_FID", right_on="STREET_FID", how="left")
    ## Populate the parallel field based on angle comparison
    #merged_df[parallel_field] = merged_df.apply(
    #    lambda row: is_parallel(row["STREET_ANGLE"], row["STREET_ANGLE"]), axis=1
    #)
    ## Convert output to a NumPy structured array and write to the table
    #output_array = np.array([tuple(row) for row in merged_df.to_records(index=False)])
    #arcpy.da.NumPyArrayToTable(output_array, parcel_street_join_fc)


def list_fc_paths_in_gdb(gdb_path):
    """
    List all feature classes in a geodatabase.
    :param gdb_path: Path to the geodatabase.
    :return: List of feature class paths.
    """
    arcpy.env.workspace = gdb_path
    fc_list = arcpy.ListFeatureClasses()
    fc_paths = [os.path.join(gdb_path, fc) for fc in fc_list]
    return fc_paths


def process_parcel(parcel_id, all_parcel_polygons_fc, all_parcel_lines_fc, building_fc, initial_near_table, output_near_table, output_lines_fc, max_side_fields=4):
    """
    Process a single parcel: convert to lines, measure distances, and generate a near table.
    :param parcel_id: The OBJECTID of the parcel being processed.
    :param all_parcel_polygons_fc: Path to the polygon feature class holding all parcels.
    :param all_parcel_lines_fc: Path to the line feature class holding all parcel segments (output of prep_data.py).
    :param building_fc: Path to the building polygon feature class.
    TODO remove if not needed  
    :param parcel_line_fc: Path to the temporary parcel line feature class.

    :param output_near_table: Path to the temporary output near table.
    :param output_lines_fc: Path to the combined output parcel line feature class.
    """
    # TODO - clean up naming
    #arcpy.management.Delete("current_parcel2")
    ## Isolate the current parcel
    #parcel_layer = "current_parcel_test"
    
    print(f"all_parcel_polygons_fc: {all_parcel_polygons_fc}")
    arcpy.management.MakeFeatureLayer(all_parcel_polygons_fc, "parcel_polygon_layer", f"OBJECTID = {parcel_id}")
    # TODO ****** REPLACE ENTIRE BLOCK WITH USE OF all_parcel_lines_fc
    #parcel_line_fc = f"parcel_line_{parcel_id}"
    ## Convert parcel polygon to lines
    #arcpy.management.PolygonToLine("parcel_polygon_layer", parcel_line_fc)
    ## Add a field to store the polygon parcel ID
    #arcpy.management.AddField(parcel_line_fc, "PARCEL_POLYGON_OID", "LONG")
    #arcpy.management.CalculateField(parcel_line_fc, "PARCEL_POLYGON_OID", f"{parcel_id}")
    ## TODO - uncomment and fix after processing single parcel
    #parcel_points_fc = f"parcel_points_{parcel_id}"
    #arcpy.management.FeatureVerticesToPoints(parcel_line_fc, parcel_points_fc, "ALL")
    ## should not need to specify feature dataset path but not finding split parcel lines feature class in feature dataset???
    #split_parcel_lines_fc = os.path.join(os.getenv("FEATURE_DATASET"), f"split_parcel_lines_{parcel_id}")
    #fc_list = arcpy.ListFeatureClasses()
    #print(f"feature classes in feature dataset: {fc_list}")
    ## TODO - adjust search radius if necessary
    ## original - before refactoring
    ##arcpy.management.SplitLineAtPoint(parcel_line_fc, parcel_points_fc, split_parcel_lines_fc, search_radius="500 Feet")
    ## split_parcel_lines_62 may be in memory? not seeing it in feature dataset, but why is parcel_points_62 in feature dataset?
    #arcpy.management.SplitLineAtPoint(parcel_line_fc, parcel_points_fc, split_parcel_lines_fc, search_radius="500 Feet")
    #print(f"Split parcel lines feature class created: {split_parcel_lines_fc}")
    # **********

    # TODO - pass name of parcel_polygon_OID field to this function??
    arcpy.management.MakeFeatureLayer(all_parcel_lines_fc, "parcel_line_layer", f"parcel_polygon_OID = {parcel_id}")

    # Select buildings inside the parcel
    #building_layer = "building_layer"
    arcpy.management.MakeFeatureLayer(building_fc, "building_layer")
    print(f"Selecting building(s) inside parcel {parcel_id}...")
    print(f"building_fc: {building_fc}")
    #with arcpy.da.SearchCursor(building_fc, ["OBJECTID"]) as cursor:
    #    for row in cursor:
    #        print(row)
    #print(f"parcel_layer: {parcel_layer}")
    #print(f"number of features in parcel_layer: {arcpy.management.GetCount(parcel_layer)}")
    #with arcpy.da.SearchCursor(parcel_layer, ["OBJECTID"]) as cursor:
    #    for row in cursor:
    #        print(row)
    #arcpy.management.SelectLayerByLocation(building_layer, "WITHIN", parcel_layer)
    #arcpy.management.SelectLayerByLocation("building_layer", "WITHIN", "parcel_layer")
    #arcpy.management.SelectLayerByLocation("building_layer", "WITHIN", "parcel_polygon_layer")
    arcpy.management.SelectLayerByLocation("building_layer", "INTERSECT", "parcel_polygon_layer")

    # ok to have multiple buildings in a parcel 
    #count = arcpy.management.GetCount(building_fc)
    #count_result = int(count.getOutput(0))
    #if count_result != "1":
    #    print(f"WARNING: {count_result} buildings found inside parcel {parcel_id}.")

    # commented out 1/27/25
    #building_polygon_ids = []
    #with arcpy.da.SearchCursor(building_fc, ["OBJECTID"]) as cursor:
    #    for row in cursor:
    #        building_polygon_ids.append(row[0])
    #string_ids = ", ".join(str(id) for id in building_polygon_ids)
    #query = f"OBJECTID in ({string_ids})"
    #building_layer = f"buildings_in_parcel_{parcel_id}"
    #arcpy.management.MakeFeatureLayer(building_fc, building_layer, query)

    # TODO - uncomment and fix after processing single parcel
    # Generate near table
    #near_table = f"in_memory/near_table_{parcel_id}"

    print(f"Generating near table for parcel {parcel_id}...")
    arcpy.analysis.GenerateNearTable(
        #"building_layer", split_parcel_lines_fc, initial_near_table, method="PLANAR", closest="ALL", search_radius="150 Feet"
        "building_layer", "parcel_line_layer", initial_near_table, method="PLANAR", closest="ALL", search_radius="150 Feet"
    )

    #i = 0
    print(f"Adding fields with side info to near table for parcel {parcel_id}...")
    for i in range(1, max_side_fields + 1):
    #while i < max_side_fields:
        # Add facing street and other side fields
        #i += 1
        arcpy.management.AddField(initial_near_table, f"FACING_STREET_{i}", "TEXT")
        arcpy.management.AddField(initial_near_table, f"FACING_STREET_{i}_DIST_FT", "FLOAT")
        arcpy.management.AddField(initial_near_table, f"OTHER_SIDE_{i}_PB_FID", "LONG")
        arcpy.management.AddField(initial_near_table, f"OTHER_SIDE_{i}_DIST_FT", "FLOAT")

    # TODO - add logic for populating these fields here or elsewhere

    # In a new field, hold the parcel polygon ID followed by parcel line ID in format 64-1, 64-2, etc.
    arcpy.management.AddField(initial_near_table, f"PARCEL_COMBO_FID", "TEXT")
    arcpy.management.CalculateField(initial_near_table, "PARCEL_COMBO_FID", f"'{parcel_id}-' + str(!NEAR_FID!)", "PYTHON3")
    #arcpy.management.CalculateField("initial_near_table_64", "PARCEL_COMBO_FID", "'64-' + str(!NEAR_FID!)")

    # In a new field, hold the building polygon ID followed by parcel line ID in format 54-1, 54-2, etc.
    arcpy.management.AddField(initial_near_table, f"BUILDING_COMBO_FID", "TEXT")
    arcpy.management.CalculateField(initial_near_table, "BUILDING_COMBO_FID", "str(!IN_FID!) + '-' + str(!NEAR_FID!)", "PYTHON3")
    
    # TODO - uncomment and fix after processing single parcel
    # Append the near table to the output table
    #print(f"Appending near table to output table for parcel {parcel_id}...")
    #arcpy.management.Append(initial_near_table, output_near_table, "NO_TEST")
    #arcpy.management.Delete(initial_near_table)  # Clean up in-memory table


def transform_near_table_with_street_info(gdb_path, near_table_name, parcel_street_join, street_fc, parcel_line_fc):
    """
    Transform near table to include info on adjacent street(s) and other side(s).
    :param gdb_path: Path to the geodatabase.
    :param near_table_name: Name of the near table.
    :param parcel_street_join: Path to feature class resulting from join of parcel line feature class with streets feature class.
    TODO add these if necessary
    :param street_fc: Path to the street feature class.
    :param parcel_line_fc: Path to the parcel line feature class.
    :return: Path to the transformed near table.
    """
    print("Transforming near table to include info on adjacent street(s) and other side(s)...")

    # Load spatial join results into a pandas DataFrame
    join_array = arcpy.da.TableToNumPyArray(parcel_street_join, ["TARGET_FID", "StFULLName", "is_parallel_to_street", "shared_boundary", "parcel_polygon_OID"])
    join_df = pd.DataFrame(join_array)
    join_df = join_df.rename(columns={"TARGET_FID": "PB_FID", "StFULLName": "STREET_NAME"})
    #TODO - get subset of join_df where parcel_polygon_OID = parcel_id - may not be necessary because of merge() below - see creation of merged_df below
    #join_df = join_df[join_df["parcel_polygon_OID"] == f"{parcel_id}"]

    print("join_df:")
    print(join_df)

    # Step 2: Load the near table into a pandas DataFrame
    near_table_path = os.path.join(gdb_path, near_table_name)
    print(f"Near table path: {near_table_path}")
    print(f"near table exists: {arcpy.Exists(near_table_path)}")
    # "*" as second arg should return all fields
    #near_array = arcpy.da.TableToNumPyArray(near_table_path, "*")
    #near_table_fields = [field.name for field in arcpy.ListFields(near_table_path)]

    # TODO - modify field list after creating dataframe or add placeholder? - passing empty fields here resulted in TypeError: int() argument must be a string, a bytes-like object or a real number, not 'NoneType'
    near_table_fields = ['IN_FID', 'NEAR_FID', 'NEAR_DIST', 'NEAR_RANK', 'PARCEL_COMBO_FID', 'BUILDING_COMBO_FID']
    print(f"Near table fields: {near_table_fields}")
    near_array = arcpy.da.TableToNumPyArray(near_table_path, near_table_fields)
    near_df = pd.DataFrame(near_array)
    print("near_df:")
    print(near_df)

    # TODO - fix issue below
    # Merge the near table with the spatial join results to identify adjacent streets
    merged_df = near_df.merge(join_df, left_on="NEAR_FID", right_on="PB_FID", how="left")
    merged_df["is_facing_street"] = (merged_df["STREET_NAME"].notna()) & (merged_df["is_parallel_to_street"] == 1) & (merged_df["shared_boundary"] == 0)
    print("merged_df after adding field 'is_facing_street':")
    print(merged_df)

    # Drop duplicate records based on NEAR_DIST, PARCEL_COMBO_FID, and STREET_NAME
    # may or may not need this step
    merged_df = merged_df.drop_duplicates(subset=["NEAR_DIST", "PARCEL_COMBO_FID", "STREET_NAME"])
    print("merged_df after adding is_facing_street and dropping duplicates:")
    print(merged_df)

    # remove unnecessary rows from merged_df - TODO - do this more efficiently?
    facing_street_df = merged_df[merged_df["is_facing_street"]]
    facing_street_df = facing_street_df.drop_duplicates(subset=["NEAR_DIST", "BUILDING_COMBO_FID"])
    other_side_df = merged_df[~merged_df["is_facing_street"]]
    other_side_df = other_side_df.drop_duplicates(subset=["NEAR_DIST", "BUILDING_COMBO_FID"])
    #get series of PB_FID values from other_side_df
    other_side_pb_fids = other_side_df["PB_FID"].unique()
    #get series of PB_FID values from facing_street_df
    facing_street_pb_fids = facing_street_df["PB_FID"].unique()
    for pb_fid in other_side_pb_fids:
        if pb_fid in facing_street_pb_fids:
            # remove row from other side df - best way to do this?
            other_side_df = other_side_df[other_side_df["PB_FID"] != pb_fid]
    #assign combination of facing_street_df and other_side_df to merged_df
    merged_df = pd.concat([facing_street_df, other_side_df])
    print("merged_df after removing unnecessary rows:")
    print(merged_df)

    # Step 3: Populate fields for adjacent streets and other sides
    output_data = []
    for in_fid, group in merged_df.groupby("IN_FID"):
        row = {"IN_FID": in_fid}
        facing_count, other_count = 1, 1

        for _, record in group.iterrows():
            near_fid = record["NEAR_FID"]
            distance = record["NEAR_DIST"]

            if record["is_facing_street"]:
                if facing_count <= 4:  # Limit to 4 adjacent streets
                    row[f"FACING_STREET_{facing_count}"] = record["STREET_NAME"]
                    row[f"FACING_STREET_{facing_count}_PB_FID"] = near_fid
                    row[f"FACING_STREET_{facing_count}_DIST_FT"] = distance
                    facing_count += 1
            else:
                if other_count <= 4:  # Limit to 4 other sides
                    row[f"OTHER_SIDE_{other_count}_PB_FID"] = near_fid
                    row[f"OTHER_SIDE_{other_count}_DIST_FT"] = distance
                    other_count += 1

        output_data.append(row)

    # Step 4: Convert output to a NumPy structured array and write to a table
    output_df = pd.DataFrame(output_data)
    print(output_df.head())
    output_df.fillna(-1, inplace=True)
    output_fields = [(col, "f8" if "DIST" in col else ("i4" if output_df[col].dtype.kind in 'i' else "<U50")) for col in output_df.columns]
    print(f'Output fields: {output_fields}')
    output_array = np.array([tuple(row) for row in output_df.to_records(index=False)], dtype=output_fields)

    #transformed_table_path = os.path.join(gdb_path, "transformed_near_table_with_facing_optimized")
    # TODO - update or remove parcel id from name
    transformed_table_path = os.path.join(gdb_path, "transformed_near_table_with_street_info_parcel_TEST")
    if arcpy.Exists(transformed_table_path):
        arcpy.management.Delete(transformed_table_path)

    arcpy.da.NumPyArrayToTable(output_array, transformed_table_path)
    print(f"Transformed near table written to: {transformed_table_path}")
    return transformed_table_path


def run(building_source_date, parcel_id, all_parcel_lines_fc):
    """
    Run the process to measure distances between buildings and parcels.
    :param building_source_date - string: date of imagery used to extract building footprints in format YYYYMMDD e.g. "20240107"
    :param parcel_id - int: OBJECTID of the parcel to process
    :param all_parcel_lines_fc - string: path to the feature class holding all parcel lines
    """
    start_time = time.time()
    print(f"Starting setback distance calculation with fields holding info on adjacent streets {time.ctime(start_time)}")
    # set environment to feature dataset
    set_environment()
    input_streets = "streets_20241030"
    gdb = os.getenv("GEODATABASE")
    feature_dataset = os.getenv("FEATURE_DATASET")
    # Paths to input data
    # TODO - pass these as arguments to run() after testing
    building_fc = f"extracted_footprints_nearmap_{building_source_date}_in_aoi_and_zones_r_th_otmu_li_ao"
    parcel_polygon_fc = "parcels_in_zones_r_th_otmu_li_ao"

    # TODO - modify after test or keep in memory only if possible
    # Temporary outputs
    initial_near_table_name = f"initial_near_table_{parcel_id}"
    initial_near_table = os.path.join(gdb, initial_near_table_name)
    temp_parcel_lines = f"temp_parcel_lines_{parcel_id}"

    # TODO - ensure that temp_parcel_lines is created if needed...

    # Final outputs
    output_near_table = f"test_output_near_table_{building_source_date}_parcel_polygon_{parcel_id}"
    output_combined_lines_fc = "temp_combined_parcel_lines"

    # Initialize outputs
    arcpy.management.CreateTable(gdb, output_near_table)
    arcpy.management.CreateFeatureclass(
        gdb, output_combined_lines_fc, "POLYLINE", spatial_reference=parcel_polygon_fc
    )

    # TODO - remove hardcoded parcel id after testing
    clipped_street_fc = f"clipped_streets_near_parcel_{parcel_id}"
    clip_streets_near_parcel(parcel_polygon_fc, parcel_id, input_streets, clipped_street_fc, buffer_ft=40)
    parcel_street_join_path = os.path.join(gdb, "parcel_street_join")
    # 'all_parcel_lines_fc' comes from create_parcel_line_fc() in prep_data.py
    populate_parallel_field(parcel_street_join_path, all_parcel_lines_fc, "StFULLName", "is_parallel_to_street", street_fc=clipped_street_fc)

    # parcels tried so far: 64, 62
    #process_parcel(62, parcel_polygon_fc, building_fc, temp_parcel_lines, initial_near_table, output_near_table, output_combined_lines_fc, max_side_fields=4)
    process_parcel(parcel_id, parcel_polygon_fc, all_parcel_lines_fc, building_fc, initial_near_table, output_near_table, output_combined_lines_fc, max_side_fields=4)

    #transform_near_table_with_street_info(gdb, initial_near_table_name, input_streets, temp_parcel_lines)
    # TODO pass the correct split parcel lines fc in a cleaner way after testing
    split_parcel_lines_fc = os.path.join(feature_dataset, f"split_parcel_lines_{parcel_id}")
    arcpy.Delete_management(split_parcel_lines_fc)
    transform_near_table_with_street_info(gdb, initial_near_table_name, parcel_street_join_path, input_streets, split_parcel_lines_fc)
    ## Iterate over each parcel
    #with arcpy.da.SearchCursor(parcel_polygon_fc, ["OBJECTID"]) as cursor:
    #    for row in cursor:
    #        parcel_id = row[0]
    #        print(f"Processing parcel {parcel_id}...")
    #        process_parcel(parcel_id, parcel_polygon_fc, building_fc, temp_parcel_lines, output_near_table, output_combined_lines_fc, max_side_fields=4)
    ## Join the near table back to building polygons
    #print("Joining near table to building polygons...")
    #arcpy.management.JoinField(building_fc, "OBJECTID", output_near_table, "IN_FID")
    ## Save final outputs
    #arcpy.management.CopyFeatures(output_combined_lines_fc, "path_to_final_parcel_lines")
    #arcpy.management.CopyRows(output_near_table, "path_to_final_near_table")
    elapsed_minutes = (time.time() - start_time) / 60
    print(f"Setback distance calculation with street info fields complete in {round(elapsed_minutes, 2)} minutes.")


# Run the script
if __name__ == "__main__":
    # TODO - remove lines below after testing parallel field population
    #set_environment()
    #street_fc = "streets_20241030"
    #clipped_street_fc = "clipped_streets_near_parcel_62"
    #clip_streets_near_parcel("parcels_in_zones_r_th_otmu_li_ao", 62, street_fc, clipped_street_fc, buffer_ft=30)
    #gdb = os.getenv("GEODATABASE")
    #parcel_street_join_path = os.path.join(gdb, "parcel_street_join")
    #populate_parallel_field(parcel_street_join_path, "StFULLName", "is_parallel_to_street", street_fc=clipped_street_fc)
    #run("20240107", 62, "parcel_lines_from_polygons_TEST")
    #run("20240107", 52, "parcel_lines_from_polygons_TEST")
    #run("20240107", 1295, "parcel_lines_from_polygons_TEST")

    # rounded corner lot - works well despite rounded segment being broken into an excessive number of segments
    #run("20240107", 219, "split_parcel_lines_in_zones_r_th_otmu_li_ao_20250128")
    # TODO - test after normal corner lot parcel with rounded lines
    run("20240107", 1295, "split_parcel_lines_in_zones_r_th_otmu_li_ao_20250128")
