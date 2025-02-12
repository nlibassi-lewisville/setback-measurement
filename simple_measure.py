import os
import arcpy
import time
import pandas as pd
import numpy as np
from shared import set_environment, calculate_angle, drop_feature_class_if_exists


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
    drop_feature_class_if_exists(output_street_fc)
    drop_feature_class_if_exists("parcel_buffer")
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
    drop_feature_class_if_exists(parcel_street_join_fc)

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

    # TODO set closest_count param to 8-10
    print(f"Generating near table for parcel {parcel_id}...")
    arcpy.analysis.GenerateNearTable(
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



def get_near_table(building_fc, parcel_line_fc, output_near_table_suffix, max_side_fields=4):
    """
    Generate a near table for the parcel line feature class and the building feature class.
    :param building_fc - string: Path to the building feature class.
    :param parcel_line_fc - string: Path to the parcel line feature class.
    :param output_near_table_suffix - string: Suffix to append to the output near table name.
    :param parcel_building_id_field - string: Name of the field to hold the parcel polygon ID followed by building polygon ID.
    :param max_side_fields - int: Maximum number of fields to add to the near table for holding info on parcel boundary sides.
    :return: Path to the near table.
    """
    # TODO - add param for closest_count - 20 was not enough when using 150 feet search radius - 2/12 12:03p: have not tried 30 with 300 feet search radius
    print("Generating near table...")
    near_table = os.path.join(os.getenv("GEODATABASE"), f"near_table_{output_near_table_suffix}")
    arcpy.analysis.GenerateNearTable(
        in_features=building_fc,
        near_features=parcel_line_fc,
        out_table=near_table,
        search_radius="300 Feet",
        location="NO_LOCATION",
        angle="NO_ANGLE",
        closest="ALL",
        closest_count=30,
        method="PLANAR",
        distance_unit="Feet"
    )

    print(f"Adding fields with side info to near table...")
    for i in range(1, max_side_fields + 1):
    #while i < max_side_fields:
        # Add facing street and other side fields
        #i += 1
        arcpy.management.AddField(near_table, f"FACING_STREET_{i}_PB_FID", "LONG")
        arcpy.management.AddField(near_table, f"FACING_STREET_{i}_DIST_FT", "FLOAT")
        arcpy.management.AddField(near_table, f"OTHER_SIDE_{i}_PB_FID", "LONG")
        arcpy.management.AddField(near_table, f"OTHER_SIDE_{i}_DIST_FT", "FLOAT")

        arcpy.management.CalculateField(near_table, f"FACING_STREET_{i}_PB_FID", -1, "PYTHON3")
        arcpy.management.CalculateField(near_table, f"FACING_STREET_{i}_DIST_FT", -1, "PYTHON3")
        arcpy.management.CalculateField(near_table, f"OTHER_SIDE_{i}_PB_FID", -1, "PYTHON3")
        arcpy.management.CalculateField(near_table, f"OTHER_SIDE_{i}_DIST_FT", -1, "PYTHON3")

    # TODO - remove if not needed
    # create a new field to hold the parcel polygon ID followed by building polygon ID in format '1583-1', '1583-7', etc.
    #arcpy.management.AddField(near_table, parcel_building_id_field, "TEXT")
    #arcpy.management.CalculateField(near_table, parcel_building_id_field, -1, "PYTHON3")

    return near_table


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



def get_near_table_with_parcel_info(near_table, parcel_line_fc):
    """
    Join near table with table from parcel line feature class to get parcel line and polygon IDs as well as shared boundary info.
    :param near_table: Path to the near table.
    :param parcel_line_fc: Path to the parcel line feature class.
    :return: Path to the near table with parcel info.
    """
    parcel_line_df = pd.DataFrame(arcpy.da.TableToNumPyArray(parcel_line_fc, ["parcel_line_OID", "shared_boundary", "parcel_polygon_OID"]))
    near_table_fields = [f.name for f in arcpy.ListFields(near_table)]
    print(f"Near table fields: {near_table_fields}")
    near_array = arcpy.da.TableToNumPyArray(near_table, near_table_fields)
    near_df = pd.DataFrame(near_array)
    print("near_df:")
    print(near_df)
    # TODO - fix issue below
    # Merge the near table with the spatial join results to identify adjacent streets
    #merged_df = near_df.merge(join_df, left_on="NEAR_FID", right_on="PB_FID", how="left")
    merged_df = near_df.merge(parcel_line_df, left_on="NEAR_FID", right_on="parcel_line_OID", how="left")
    print("merged_df head:")
    print(merged_df.head())
    print("merged_df where IN_FID is 1:")
    print(merged_df[merged_df["IN_FID"] == 1])
    print("merged_df where IN_FID is 2:")
    print(merged_df[merged_df["IN_FID"] == 2])
    output_fields = [(col, "f8" if "DIST" in col else ("i4" if merged_df[col].dtype.kind in 'i' else "<U50")) for col in merged_df.columns]
    output_array = np.array([tuple(row) for row in merged_df.to_records(index=False)], dtype=output_fields)
    output_table = os.path.join(os.getenv("GEODATABASE"), "near_table_with_parcel_info_20250212")
    arcpy.da.NumPyArrayToTable(output_array, output_table)
    return output_table


def trim_near_table(near_table, building_parcel_join_fc, parcel_id_table):
    """
    Trim the near table to include only the nearest parcel lines.
    :param near_table: Path to the near table (that includes parcel info).
    :param building_parcel_join_fc: Path to the feature class that links each building polygon ID to the ID of the parcel polygon it is contained by.
    :param parcel_id_table: Path to the table that links each parcel polygon OID to the parcel line OIDs that share a boundary with the given polygon.
    :return: Path to the trimmed near table.
    """
    print("Trimming near table...")
    # Create a copy of the near table
    trimmed_near_table = os.path.join(os.getenv("GEODATABASE"), "trimmed_near_table_with_parcel_info")
    arcpy.management.CopyRows(near_table, trimmed_near_table)
    # new field must be added before creating a table view
    arcpy.management.AddField(trimmed_near_table, "intended_parcel_polygon_OID", "LONG")

    # Create views from tables and necesary layer from feature class
    trimmed_near_table_view = "trimmed_near_table_view"
    arcpy.management.MakeTableView(trimmed_near_table, trimmed_near_table_view)
    parcel_id_table_view = "parcel_id_table_view"
    arcpy.management.MakeTableView(parcel_id_table, parcel_id_table_view)
    building_parcel_join_layer = "building_parcel_join_layer"
    arcpy.management.MakeFeatureLayer(building_parcel_join_fc, building_parcel_join_layer)

    # join to get parcel ids that correspond to buildings
    # building polygon ID is: 
    #   IN_FID of near table and 
    #   TARGET_FID of buildings_with_parcel_ids
    arcpy.management.AddJoin(
        in_layer_or_view=trimmed_near_table_view,
        in_field="IN_FID",
        join_table=building_parcel_join_layer,
        join_field="TARGET_FID",
        join_type="KEEP_ALL",
        index_join_fields="NO_INDEX_JOIN_FIELDS",
        rebuild_index="NO_REBUILD_INDEX",
        join_operation=""
    )
    test_join_table = os.path.join(os.getenv("GEODATABASE"), "test_trimmed_near_table_after_first_join")
    arcpy.management.CopyRows(trimmed_near_table_view, test_join_table)

    fields = arcpy.ListFields(test_join_table)
    print(f"Fields in trimmed_near_table_view after FIRST join: {[f.name for f in fields]}")

    #fields = arcpy.ListFields(trimmed_near_table)
    #print(f"Fields in trimmed_near_table after first join: {[f.name for f in fields]}")
    #print(f"Aliases in trimmed_near_table after first join: {[f.aliasName for f in fields]}")

    # why was original field_type TEXT here?
    # TODO - may need to modify expression and/or modify name of field named "OBJECTID_1" in near table
    arcpy.management.CalculateField(
        in_table=trimmed_near_table_view,
        field="intended_parcel_polygon_OID",
        #expression="!OBJECTID_1!",
        expression="int(!buildings_with_parcel_ids.enclosing_parcel_polygon_oid!)",
        expression_type="PYTHON3",
        code_block="",
        field_type="LONG",
        enforce_domains="NO_ENFORCE_DOMAINS"
    )
    print("intended_parcel_polygon_OID field UPDATED in trimmed_near_table_view!!!!!")

    print(f"trimmed_near_table: {trimmed_near_table}")
    trimmed_near_table_name = trimmed_near_table.split("\\")[-1]
    parcel_polygon_OID_field = f"{trimmed_near_table_name}.intended_parcel_polygon_OID"  

    # print first row for debugging
    fields = arcpy.ListFields(trimmed_near_table_view)
    print(f"Fields in trimmed_near_table_view after first join: {[f.name for f in fields]}")
    print("first row of trimmed_near_table_view after first join:")
    with arcpy.da.SearchCursor(trimmed_near_table_view, [f.name for f in fields]) as cursor:
        for row in cursor:
            print(row)
            break
    print("first value in field trimmed_near_table_with_parcel_info.intended_parcel_polygon_OID of trimmed_near_table_view:")
    with arcpy.da.SearchCursor(trimmed_near_table_view, "trimmed_near_table_with_parcel_info.intended_parcel_polygon_OID") as cursor:
        for row in cursor:
            print(row)
            break
    # could work but these are apparently strings e.g. '1583'
    alternate_in_field = 'buildings_with_parcel_ids.enclosing_parcel_polygon_oid'
    alternate_in_field_2 = 'trimmed_near_table_with_parcel_info.intended_parcel_polygon_OID'
    # format of field names after having been copied to a new table
    #alternate_in_field = "buildings_with_parcel_ids_enclosing_parcel_polygon_oid"
    # TODO clean up dirty field names!!
    arcpy.management.AddJoin(
        in_layer_or_view=trimmed_near_table_view,
        #in_field=parcel_polygon_OID_field,
        in_field=alternate_in_field_2,
        join_table=parcel_id_table_view,
        join_field="parcel_polygon_OID",
        join_type="KEEP_ALL",
        index_join_fields="NO_INDEX_JOIN_FIELDS",
        rebuild_index="NO_REBUILD_INDEX",
        join_operation="JOIN_ONE_TO_MANY"
    )
    fields = arcpy.ListFields(parcel_id_table_view)
    print("first row of parcel_id_table_view:")
    with arcpy.da.SearchCursor(parcel_id_table_view, [f.name for f in fields]) as cursor:
        for row in cursor:
            print(row)
            break

    trimmed_near_table_2_name = "updated_trimmed_near_table_with_parcel_info"
    trimmed_near_table_2 = os.path.join(os.getenv("GEODATABASE"), trimmed_near_table_2_name)
    arcpy.management.CopyRows(trimmed_near_table_view, trimmed_near_table_2)
    fields = arcpy.ListFields(trimmed_near_table_2)
    print(f"\nFields in trimmed_near_table_2 after second join: {[f.name for f in fields]}")
    # TODO - get full names of fields modified due to join?
    #iterate through the rows in the near table and remove rows where value in parcel_line_OID column is not in list in parcel_line_OIDs

    # expecting'trimmed_near_table_with_parcel_info_parcel_line_OID' below
    parcel_line_OID_field = f"{trimmed_near_table_name}_parcel_line_OID"
    parcel_id_table_name = parcel_id_table.split("\\")[-1]
    print(f"parcel_id_table_name: {parcel_id_table_name}")
    # expecting 'parcel_id_table_20250212_parcel_line_OIDs' below
    parcel_line_OIDs_field = f"{parcel_id_table_name}_parcel_line_OIDs" 
    #parcel_line_OIDs_field = f"{parcel_id_table_name}.parcel_line_OIDs" 
    print(f"field used in update cursor for parcel line OIDs: {parcel_line_OIDs_field}")
    with arcpy.da.UpdateCursor(trimmed_near_table_2, [parcel_line_OID_field, parcel_line_OIDs_field]) as cursor:
        for row in cursor:
            parcel_line_OID = row[0]
            parcel_line_OIDs = row[1]
            if str(parcel_line_OID) not in parcel_line_OIDs:
                cursor.deleteRow()

    print(f"check state of output trimmed near table at: {trimmed_near_table_2}")
    return trimmed_near_table_2


def transform_detailed_near_table(near_table, field_prefix):
    """
    Transform near table to include info on pairs of building sides and parcel segments that share a parcel boundary (non-street-facing) and do not share a boundary (street-facing).
    :param near_table_name - string: Path to the near table that includes parcel info (output of trim_near_table()).
    :param field_prefix - string: Name of near table prior to joins in trim_near_table() e.g. 'trimmed_near_table_with_parcel_info'.
    :return: Path to the transformed near table.
    """
    print("Transforming near table to include info on adjacent street(s) and other side(s)...")
    
    # Load near table data into a pandas DataFrame
    fields = [f.name for f in arcpy.ListFields(near_table)]
    near_array = arcpy.da.TableToNumPyArray(near_table, fields)
    near_df = pd.DataFrame(near_array)

    output_data = []
    # prepare field names
    in_fid_field = f"{field_prefix}_IN_FID"
    near_fid_field = f"{field_prefix}_NEAR_FID"
    near_dist_field = f"{field_prefix}_NEAR_DIST"
    facing_street_field_part_1 = f"{field_prefix}_FACING_STREET"
    other_side_field_part_1 = f"{field_prefix}_OTHER_SIDE"
    shared_boundary_field = f"{field_prefix}_shared_boundary"

    # transform table
    for in_fid, group in near_df.groupby(in_fid_field):
        row = {in_fid_field: in_fid}
        facing_count, other_count = 1, 1
        for _, record in group.iterrows():
            near_fid = record[near_fid_field]
            distance = record[near_dist_field]
            # TODO - add parameter for max number of fields for facing street and other side?
            if not record[shared_boundary_field]:
                # limit to x number of facing street sides
                if facing_count <= 4:
                    #row[f"FACING_STREET_{facing_count}"] = record["STREET_NAME"]
                    row[f"{facing_street_field_part_1}_{facing_count}_PB_FID"] = near_fid
                    row[f"{facing_street_field_part_1}_{facing_count}_DIST_FT"] = distance
                    facing_count += 1
            else:
                # limit to x number of other sides
                if other_count <= 4:
                    row[f"{other_side_field_part_1}_{other_count}_PB_FID"] = near_fid
                    row[f"{other_side_field_part_1}_{other_count}_DIST_FT"] = distance
                    other_count += 1
        output_data.append(row)

    # Convert output to a NumPy structured array and write to a table
    output_df = pd.DataFrame(output_data)
    #print(output_df.head())
    output_df.fillna(-1, inplace=True)
    output_fields = [(col, "f8" if "DIST" in col else ("i4" if output_df[col].dtype.kind in 'i' else "<U50")) for col in output_df.columns]
    #print(f'Output fields: {output_fields}')
    output_array = np.array([tuple(row) for row in output_df.to_records(index=False)], dtype=output_fields)
    gdb_path = os.getenv("GEODATABASE")
    transformed_table_path = os.path.join(gdb_path, "transformed_near_table_with_street_info_parcel_TEST_20250212")
    drop_feature_class_if_exists(transformed_table_path)
    arcpy.da.NumPyArrayToTable(output_array, transformed_table_path)
    print(f"Check transformed near table written to: {transformed_table_path}")
    return transformed_table_path


def run(building_fc, parcel_line_fc, output_near_table_suffix, spatial_join_output, max_side_fields=4):
    """
    Run the process to measure distances between buildings and parcels.
    :param building_fc - string: Path to the building feature class.
    :param parcel_line_fc - string: Path to the parcel line feature class.
    :param output_near_table_suffix - string: Suffix to append to the output near table name.
    :param spatial_join_output: Path to the spatial join output feature class.
    :param parcel_street_join - string: Path to feature class resulting from join of parcel line feature class with streets feature class.
    """
    start_time = time.time()
    print(f"Starting setback distance calculation with fields holding info on adjacent streets {time.ctime(start_time)}")
    # set environment to feature dataset
    set_environment()
    
    # TODO - uncomment after testing other functions
    #near_table = get_near_table(building_fc, parcel_line_fc, output_near_table_suffix, max_side_fields=max_side_fields)
    #near_table_with_parcel_info = get_near_table_with_parcel_info(near_table, parcel_line_fc)

    building_parcel_join_fc = "buildings_with_parcel_ids"
    gdb_path = os.getenv("GEODATABASE")
    near_table_with_parcel_info = os.path.join(gdb_path, "near_table_with_parcel_info_20250212")
    parcel_id_table = os.path.join(gdb_path, "parcel_id_table_20250212")
    # TODO - uncomment after testing other functions and remove hardcoded paths
    #trimmed_near_table = trim_near_table(near_table_with_parcel_info, building_parcel_join_fc, parcel_id_table)
    trimmed_near_table = os.path.join(gdb_path, "updated_trimmed_near_table_with_parcel_info")

    transform_detailed_near_table(trimmed_near_table, "trimmed_near_table_with_parcel_info")

    # TODO fix and rename transform_near_table_with_street_info() before calling
    #transform_near_table_with_street_info(near_table, spatial_join_output)
    
    #input_streets = "streets_20241030"
    #gdb = os.getenv("GEODATABASE")
    #feature_dataset = os.getenv("FEATURE_DATASET")
    ## Paths to input data
    ## TODO - pass these as arguments to run() after testing
    #building_fc = f"extracted_footprints_nearmap_{building_source_date}_in_aoi_and_zones_r_th_otmu_li_ao"
    #parcel_polygon_fc = "parcels_in_zones_r_th_otmu_li_ao"
    ## TODO - modify after test or keep in memory only if possible
    ## Temporary outputs
    #initial_near_table_name = f"initial_near_table_{parcel_id}"
    #initial_near_table = os.path.join(gdb, initial_near_table_name)
    ##temp_parcel_lines = f"temp_parcel_lines_{parcel_id}"
    ## TODO - ensure that temp_parcel_lines is created if needed...
    ## Final outputs
    #output_near_table = f"test_output_near_table_{building_source_date}_parcel_polygon_{parcel_id}"
    #output_combined_lines_fc = "temp_combined_parcel_lines"
    ## Initialize outputs
    #arcpy.management.CreateTable(gdb, output_near_table)
    #arcpy.management.CreateFeatureclass(
    #    gdb, output_combined_lines_fc, "POLYLINE", spatial_reference=parcel_polygon_fc
    #)
    ## TODO - remove hardcoded parcel id after testing
    #clipped_street_fc = f"clipped_streets_near_parcel_{parcel_id}"
    #clip_streets_near_parcel(parcel_polygon_fc, parcel_id, input_streets, clipped_street_fc, buffer_ft=40)
    #parcel_street_join_path = os.path.join(gdb, "parcel_street_join")
    ## 'all_parcel_lines_fc' comes from create_parcel_line_fc() in prep_data.py
    #populate_parallel_field(parcel_street_join_path, all_parcel_lines_fc, "StFULLName", "is_parallel_to_street", street_fc=clipped_street_fc)
    ## parcels tried so far: 64, 62
    ##process_parcel(62, parcel_polygon_fc, building_fc, temp_parcel_lines, initial_near_table, output_near_table, output_combined_lines_fc, max_side_fields=4)
    #process_parcel(parcel_id, parcel_polygon_fc, all_parcel_lines_fc, building_fc, initial_near_table, output_near_table, output_combined_lines_fc, max_side_fields=4)
    ##transform_near_table_with_street_info(gdb, initial_near_table_name, input_streets, temp_parcel_lines)
    ## TODO pass the correct split parcel lines fc in a cleaner way after testing
    #split_parcel_lines_fc = os.path.join(feature_dataset, f"split_parcel_lines_{parcel_id}")
    #drop_feature_class_if_exists(split_parcel_lines_fc)
    #transform_near_table_with_street_info(gdb, initial_near_table_name, parcel_street_join_path, input_streets, split_parcel_lines_fc)
    ### Iterate over each parcel
    ##with arcpy.da.SearchCursor(parcel_polygon_fc, ["OBJECTID"]) as cursor:
    ##    for row in cursor:
    ##        parcel_id = row[0]
    ##        print(f"Processing parcel {parcel_id}...")
    ##        process_parcel(parcel_id, parcel_polygon_fc, building_fc, temp_parcel_lines, output_near_table, output_combined_lines_fc, max_side_fields=4)
    ### Join the near table back to building polygons
    ##print("Joining near table to building polygons...")
    ##arcpy.management.JoinField(building_fc, "OBJECTID", output_near_table, "IN_FID")
    ### Save final outputs
    ##arcpy.management.CopyFeatures(output_combined_lines_fc, "path_to_final_parcel_lines")
    ##arcpy.management.CopyRows(output_near_table, "path_to_final_near_table")
    elapsed_minutes = (time.time() - start_time) / 60
    print(f"Setback distance calculation with street info fields complete in {round(elapsed_minutes, 2)} minutes.")


# Run the script
if __name__ == "__main__":
    # TODO - remove lines below after testing parallel field population
    set_environment()
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
    #run("20240107", 1295, "split_parcel_lines_in_zones_r_th_otmu_li_ao_20250128")
    #run("20240107", 1618, "split_parcel_lines_in_zones_r_th_otmu_li_ao_20250128")
    building_fc = "extracted_footprints_nearmap_20240107_in_aoi_and_zones_r_th_otmu_li_ao"
    #parcel_line_fc = "split_parcel_lines_in_zones_r_th_otmu_li_ao_20250128"
    parcel_line_fc = "parcel_lines_from_polygons_TEST"
    output_near_table_suffix = "nm_20240107_20250211"
    spatial_join_output = "spatial_join_buildings_completely_within_parcels"
    run(building_fc, parcel_line_fc, output_near_table_suffix, spatial_join_output, max_side_fields=4)
