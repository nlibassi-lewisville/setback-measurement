import os
import arcpy
from dotenv import load_dotenv

load_dotenv('.env')
# TODO: use python-dotenv to load environment variables
# Set environment and paths
arcpy.env.workspace = os.getenv("WORKSPACE")
# Set input layers
parcel_layer = "parcels_old_town_design_district"
street_layer = "streets_20241024"
building_layer = "usa_structures_old_town_design_district"

projected_crs = arcpy.SpatialReference(2276)

# TODO: clean up - do not repeatedly project layers
#arcpy.management.Project(parcel_layer, "projected_parcels", projected_crs)
#arcpy.management.Project(building_layer, "projected_buildings", projected_crs)
#arcpy.management.Project(street_layer, "projected_streets", projected_crs)

projected_parcels = "projected_parcels"
projected_buildings = "projected_buildings"
projected_streets = "projected_streets"

# new and output layers
parcel_lines = "parcel_lines"
building_lines = "building_footprints_lines"
near_table = "near_table"

out_items = [parcel_lines, building_lines, near_table]
for item in out_items:
    if arcpy.Exists(item):
        arcpy.management.Delete(item)

arcpy.management.PolygonToLine(projected_parcels, parcel_lines)

# Select parcels nearest to streets
arcpy.management.SelectLayerByLocation(projected_parcels, "INTERSECT", street_layer)

# Convert building footprints to lines
arcpy.management.PolygonToLine(projected_buildings, building_lines)

# Calculate nearest distance between building front and parcel front
arcpy.analysis.GenerateNearTable(building_lines, parcel_lines, near_table, 
                                 method="PLANAR", closest="ALL", distance_unit="Feet")

# Optional: Add results to the parcels or buildings layer
arcpy.management.JoinField(building_lines, "OBJECTID", near_table, "IN_FID", 
                           ["NEAR_DIST"])

print("Setback distance calculation complete.")