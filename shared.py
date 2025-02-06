import arcpy
import os
from dotenv import load_dotenv
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