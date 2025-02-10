import os
import math
from dotenv import load_dotenv
import arcpy
import pathlib

def set_environment():
    """
    Set up the environment and workspace.
    """
    script_dir = pathlib.Path(__file__).parent.absolute()
    env_path = script_dir / '.env'
    load_dotenv(env_path)
    arcpy.env.workspace = os.getenv("FEATURE_DATASET")
    arcpy.env.overwriteOutput = True
    print(f"Workspace set to {arcpy.env.workspace}")


def drop_field_if_exists(feature_class, field_name):
    """
    Drop a field from a feature class if it exists.
    :param feature_class: The feature class from which to drop the field.
    :param field_name: The name of the field to drop.
    """
    fields = arcpy.ListFields(feature_class)
    for field in fields:
        if field.name == field_name:
            arcpy.DeleteField_management(feature_class, field_name)
            print(f"Field '{field_name}' dropped from {feature_class}.")
            break
    else:
        print(f"Field '{field_name}' does not exist in {feature_class}.")


def calculate_field_if_exists(feature_class, field_name, expression, expression_type="PYTHON3"):
    """
    Calculate a field in a feature class if it exists.
    :param feature_class: The feature class containing the field.
    :param field_name: The name of the field to calculate.
    :param expression: The expression to calculate the field with.
    :param expression_type: The type of the expression (default is "PYTHON3").
    :return: Name of field if it does not exist, otherwise None.
    """
    fields = arcpy.ListFields(feature_class)
    for field in fields:
        if field.name == field_name:
            arcpy.management.CalculateField(feature_class, field_name, expression, expression_type)
            print(f"Field '{field_name}' calculated in {feature_class}.")
            break
    else:
        print(f"Field '{field_name}' does not exist in {feature_class}.")
        return field_name
    
# TODO - ensure this works on tables as well
def drop_feature_class_if_exists(feature_class):
    """
    Drop a feature class if it exists.
    :param feature_class: The feature class to drop.
    """
    if arcpy.Exists(feature_class):
        arcpy.Delete_management(feature_class)
        print(f"Feature class '{feature_class}' dropped.")
    else:
        print(f"Feature class '{feature_class}' does not exist.")


def calculate_angle(geometry):
    """
    Calculate the angle (bearing) between first and last points of a line geometry in degrees, accounting for bidirectional lines.
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