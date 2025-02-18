import os
import math
from dotenv import load_dotenv
import pathlib
import arcpy
from base_logger import logger


def set_environment():
    """
    Set up the environment and workspace.
    """
    script_dir = pathlib.Path(__file__).parent.absolute()
    env_path = script_dir / '.env'
    load_dotenv(env_path)
    arcpy.env.workspace = os.getenv("FEATURE_DATASET")
    arcpy.env.overwriteOutput = True
    logger.info(f"Workspace set to {arcpy.env.workspace}")


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
            logger.info(f"Field '{field_name}' dropped from {feature_class}.")
            break
    else:
        logger.info(f"Field '{field_name}' does not exist in {feature_class}.")


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
            logger.info(f"Field '{field_name}' calculated in {feature_class}.")
            break
    else:
        logger.info(f"Field '{field_name}' does not exist in {feature_class}.")
        return field_name
    

def drop_gdb_item_if_exists(item):
    """
    Drop given feature class or table if it exists.
    :param item: The feature class or table to drop.
    """
    if arcpy.Exists(item):
        arcpy.Delete_management(item)
        logger.info(f"Geodatabase item '{item}' dropped.")
    else:
        logger.info(f"Attempted to drop geodatabase item '{item}', but it does not exist.")


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


# may or may not be necessary
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