import os
import arcpy
from dotenv import load_dotenv

def set_environment():
    load_dotenv('.env')
    arcpy.env.workspace = os.getenv("WORKSPACE")
    arcpy.env.overwriteOutput = True
    print("Environment set.")


def get_line_layers(parcel_poly_fc, building_poly_fc, street_poly_fc):
    '''
    Return line layers for parcels and buildings from polygon inputs
    :param parcel_poly_fc - string: name of input parcel polygon feature class
    :param building_poly_fc - string: name of input building polygon feature class
    :param streets_layer - string: name of input streets polygon feature class
    :return: Tuple of line layers (parcel_line_fc, building_line_fc)
    '''
    # Create line layers from polygon inputs
    parcel_line_fc = "parcel_line_fc"
    building_line_fc = "building_line_fc"
    # Select parcels that intersect with streets
    arcpy.management.SelectLayerByLocation(parcel_poly_fc, "INTERSECT", street_poly_fc)
    # TODO: ensure that selected parcels are used here
    arcpy.management.PolygonToLine(parcel_poly_fc, parcel_line_fc)
    arcpy.management.PolygonToLine(building_poly_fc, building_line_fc)
    return parcel_line_fc, building_line_fc


def calculate_setbacks(parcel_line_fc, building_line_fc):
    '''
    Calculate setbacks between edges of buildings and parcel boundaries
    :param parcel_line_fc - string: name of parcel line feature class
    :param building_line_fc - string: name of building line feature class
    '''
    near_table = "near_table"
    # Calculate nearest distance between building front and parcel front
    arcpy.analysis.GenerateNearTable(building_line_fc, parcel_line_fc, near_table, 
                                    method="PLANAR", closest="ALL", distance_unit="Feet")

    # Optional: Add results to the parcels or buildings layer
    arcpy.management.JoinField(building_line_fc, "OBJECTID", near_table, "IN_FID", 
                            ["NEAR_DIST"])
    print("Setback distance calculation complete.")


def run(parcel_poly_fc, building_poly_fc, street_poly_fc):
    set_environment()
    parcel_line_fc, building_line_fc = get_line_layers(parcel_poly_fc, building_poly_fc, street_poly_fc)
    calculate_setbacks(parcel_line_fc, building_line_fc)


set_environment()