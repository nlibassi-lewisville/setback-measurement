import os
import arcpy
from dotenv import load_dotenv
import pathlib

file_path = pathlib.Path(__file__).parent.absolute()
env_path = os.path.join(file_path, '.env')
load_dotenv(env_path)
# Set environment and paths
workspace = os.getenv("FEATURE_DATASET")
arcpy.env.workspace = workspace
print(f"Workspace set to {arcpy.env.workspace}")


projected_parcels = "parcels_in_zones_r_th_otmu_li_ao"
projected_buildings = "osm_na_buildings_in_zones_r_th_otmu_li_ao"
projected_streets = "streets_20241030"

# new and output layers
parcel_lines = "parcel_lines"
building_lines = "building_footprints_lines"
gdb_path = os.getenv("GEODATABASE")
near_table = os.path.join(gdb_path, "near_table")

out_items = [parcel_lines, building_lines, near_table]
for item in out_items:
    if arcpy.Exists(item):
        arcpy.management.Delete(item)

arcpy.management.PolygonToLine(projected_parcels, parcel_lines)

# Select parcels nearest to streets
arcpy.management.SelectLayerByLocation(projected_parcels, "INTERSECT", projected_streets)

# Convert building footprints to lines
arcpy.management.PolygonToLine(projected_buildings, building_lines)

# Calculate nearest distance between building front and parcel front
arcpy.analysis.GenerateNearTable(building_lines, parcel_lines, near_table, 
                                 method="PLANAR", closest="ALL", distance_unit="Feet")

# Optional: Add results to the parcels or buildings layer
arcpy.management.JoinField(building_lines, "OBJECTID", near_table, "IN_FID", 
                           ["NEAR_DIST"])

print("Setback distance calculation complete.")
