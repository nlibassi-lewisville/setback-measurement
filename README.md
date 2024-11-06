# Overview

This script automates the process of calculating setback distances between buildings and parcel boundaries using ArcGIS tools. It sets up an ArcGIS environment, performs spatial and attribute operations, and produces output tables that can be used for further spatial analysis. The main operations include selecting parcels near streets, converting polygon features to lines, calculating distances, and transforming the results table in order to join the results to the building (lines) layer.

# Data Preparation

### Inputs

In a feature dataset with projected coordinate system (WKID: 2276) NAD 1983 StatePlane Texas N Central FIPS 4202 (US Feet), the following feature classes were gathered:

1. buildings (polygon)
2. parcels (polygon)
3. zoning (polygon)
4. streets (line)
5. area of interest (polygon)

### Process

1. An area of interest was identified
2. Desired zoning classes were selected: `ZONING_CLASS IN ('AO', 'OTMU1', 'OTMU2', 'R12', 'R18', 'R5', 'R6', 'R7.5', 'R9', 'TH', 'LI')`
3. Parcels in desired zoning classes were exported to a separate feature class
4. Buildings in desired zoning classes were exported to a separate feature class
5. Self-intersecting building features were identified with a spatial join
6. Non-self-intersecting building features were exported to a new feature class using: `OBJECTID NOT IN (170, 171, 172, 174, 380, 389, 725, 728, 836, 837, 1153, 1158)`

# Key Functionality

set_environment(): Configures the ArcGIS environment and workspace, loading necessary environment variables from a .env file.

clear_existing_outputs(): Deletes specified existing outputs to ensure clean results if they already exist.

create_line_features(): Converts parcel and building polygon feature classes into line feature classes for distance calculation.

select_parcels_near_streets(): Selects parcels that intersect nearby streets for targeted analysis.

calculate_nearest_distances(): Generates a near table to store the calculated distances between building lines and parcel lines.

simplify_near_table(): Filters the near table to retain only rows where NEAR_RANK is below a specified threshold, creating a simplified output.

transform_near_table(): Reshapes the simplified near table into a format compatible for joining with building line data, converting it into a structured array and outputting it as a transformed table.

join_near_distances(): Joins the transformed near table with the building lines feature class to add distance results to each building line feature.

modify_out_table_fields(): Modifies fields in the joined table, removing unnecessary fields and adding custom fields for additional analysis.

run(): The main function that orchestrates all steps, executing the workflow from environment setup to final output creation.

# Dependencies

- ArcPy: Used for spatial and data management tasks.
- pandas and NumPy: Used for data manipulation and transformation when reshaping the near table.
- dotenv: Loads environment variables for database and workspace paths.

# Usage

1. Ensure all dependencies are installed and that ArcGIS Pro/ArcMap is available with necessary licenses.
2. Configure the .env file to define FEATURE_DATASET and GEODATABASE paths.
3. Run the script directly by executing it as a standalone Python script (python path/to/measure.py or propy path/to/measure.py if using 'propy' environment provided with ArcGIS Pro).

# Output

### Output Table Fields

Results are found in the feature class called 'building_lines'

- IN_FID: feature id (OBJECTID) of building (line) feature
- PB_X_FID: feature id (OBJECTID) of parcel boundary line segment - the number in place of X represents the rank of the proximity of the parcel boundary segment to the building e.g. PB_1_FID is the id of the parcel boundary closest to the building. For most buildings, only the closest 3-4 parcel boundary segments will be relevant.
- PB_X_DIST_FT: the distance in feet of the given parcel boundary segment from the building
- HEIGHT_FT: an empty field added to hold the height of the building in feet
- AREA_FT: an empty field added to hold the area of the building in feet
- CONDITION: an empty field added to hold the condition of the building


### Recommendations

When reviewing the results in ArcGIS Pro, turn on the labels for the OBJECTID (or IN_FID) of building_lines and for the OBJECTID of parcel_lines.

While the 'OpenStreetMap Buildings for North America' obtained from the ArcGIS Living Atlas were deemed adequate for this project and the results match distances measured in ArcGIS Pro, field checking some of the measurements is recommended. 

Better results should be expected with better input building data - one option would be to extract building features from recent imagery.
