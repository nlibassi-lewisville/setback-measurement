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
3. Run the script directly by executing it as a standalone Python script (`python path/to/measure.py` or `propy path/to/measure.py` if using 'propy' environment provided with ArcGIS Pro).

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

Where the input (polygon) parcel layer contains features with curved lines (especially at corner lots), the line version of the parcel boundaries does not contain separate line segments - in a future iteration of the script, these could be split at the curve to ensure setbacks are measured on at least four sides.

While the building layer 'OpenStreetMap Buildings for North America' obtained from the ArcGIS Living Atlas was deemed adequate for this project and the results match distances measured in ArcGIS Pro, field checking some of the measurements is recommended. 

Better results should be expected with better input building data - one option would be to extract building features from recent imagery.


### Changes in Process

TODO - clean up this section

Add name of street facing side of structure.

UPDATE 1/7:

Also, shared parcel lines create a problem. May need to iterate over parcels. 

For each parcel:

1. Convert parcel polygon feature to line feature (ensure parcel polygon OID is in table of line fc)
2. Split line feature at vertices (handle issue of curved parcel boundary line segments later - start with a simple rectangular parcel)
3. Measure distances between all lines and all buildings inside parcel polygon (generate ‘near table’)
    - Figure out how to keep original OID of buildings
4. Add facing street fields and other side fields to ‘near tables’
    - Parcel id’s will probably need to be a combination of parcel polygon OID and line segment OID

Then, when finished, aggregate all ‘near tables’ into a single results table

This seems to resolve the problem of shared boundaries, but if near tables will be aggregated, original OIDs have to be tracked very carefully

UPDATE 1/21:

The above worked (mostly) as expected but also required a test to see if the street segment nearest to each parcel segment is parallel to parcel segment...

...that also generally worked, but in some cases, a parcel boundary shared between two parcels was found to be parallel with a street not running alongside the parcel but perpendicular to the street running alongside the parcel...

...so the need to first check for shared parcel boundaries arose.

Revised process:

1. add and populate 'shared_boundary' field to parcel line segments in prep_data.py 
    - input: parcel polygons
    - output: parcel lines with 'shared_boundary' field populated
2. for each parcel:
    - clip streets to get only those streets inside buffer around parcel
    - after joining streets and parcels (parcel_street_join where features represent parcel segments but also have attributes from streets table), add and populate 'is_parallel_to_street'
    - generate near table for all parcel segments and
        - add 'facing street' info for those that have value of 1 in 'is_parallel_to_street' field and value of 0 in 'shared_boundary' field
        - add 'other side' info for those that value of 1 in 'shared_boundary' field (and value of 0 in 'is_parallel_to_street' field??)
    - transform table to get info on all sides into a single row/record
3. aggregate output near tables


Explanation of prep_data.py:

Takes a parcel polygon feature class and creates line feature class that includes a field called 'shared_boundary' with values of 'yes' or 'no' for each feature

Explanation of measure_per_parcel.py after testing 1/24/25 with parcel 62:

Currently takes the following:
- :param building_source_date - string: date of imagery used to extract building footprints in format YYYYMMDD e.g. "20240107"
- :param parcel_id - int: OBJECTID of the parcel to process
- :param all_parcel_lines_fc - string: path to the feature class holding all parcel lines

1. clip_streets_near_parcel() clipped streets near parcel
2. populate_parallel_field() parcel street join - add joined street info to each parcel boundary line segment and populate field is_parallel_to_street
3. process_parcel() 
    intermediate data: parcel_line_62 (single line feature from polygon), parcel_points_62, split_parcel_lines_62 (CANNOT FIND?)
    ACTION ITEM 3: ensure that split_parcel_lines_62 can be found in the feature dataset after running
    results in initial_near_table_62 with fields:
    - in_fid (representing the building polygon)
    - near_fid (representing the line segment of the parcel boundary)
    - near_dist (populated)
    - facing and other side fields (not yet(?) populated)
    - parcel_combo_fid (e.g 62-6 - the parcel polygon fid followed by the parcel line segment fid)
    ACTION ITEM 2: initial_near_table_62 has a lot of excess info on buildings outside the parcel - should be able to get this only for the building(s) inside the parcel
4. transform_near_table_with_street_info() results in transformed_near_table_with_street_info_parcel_62
    - has 'other side' fields but no 'facing street' fields
    ACTION ITEM 1: ensure that data on 'facing fields' is included - if a given parcel segment does not have a shared boundary and is parallel to a street, 
    the 'facing street' fields should be populated


remaining as of 1/27/25:

- [x] remove excess info from initial table on buildings outside the parcel (ACTION ITEM 2 above) - done (first commit of day)
- [x] parcel_street_join needs to keep the 'shared_boundary' field
    - added it by selecting all fields via field mapping but values are incorrect
    - ...though shared_boundary field has correct values in fc output by prep_data.py ('parcel_lines_from_polygons_TEST')
    - ...parcel_street_join now has the correct info for shared_boundary, but merged_df has values of NaN for shared_boundary (and for is_parallel_to_street and others PB_FID, STREET_NAME)
    - 'PB_FIDs' of join_df do not match 'NEAR_FIDs' of near_df!!!
- [x] in process_parcel(), use split parcel boundaries from prep_data.py instead of splitting again in measure_per_parcel.py (done)
- [x] remove repeat facing streets and repeat other streets (done but could be more efficient - tested with parcel 62)
- [x] ensure correct distances and PB_FIDs are appearing in final transformed table (looks good for simplest parcel boundary case i.e. no parcel boundary curved segments)
- [x] test with multiple buildings in a single parcel - tested:
    - parcel 52 with buildings 29 and 970 (results are as-expected)
    - parcel 1295 with buildings 969, 971, 972 (not yet behaving as expected - building 972 extends beyond parcel boundary and was completely left out of results table though one side is completely within parcel; also increased default buffer distance to 40 ft as 30 ft on 1295 did not reach St. Charles St)
- [x] account for rounded parcel segments - split and rejoin when necessary (probably in prep_data.py) (done despite rounded segments being broken into an excessive number of segments)
- [ ] move split_lines logic into prep_data.py?
- [ ] check results on caddy corner parcel boundaries (seems to be fine but will be better after removing excessive splits)
- [ ] remove excessive splits in line segments (have not yet tried latest suggestion from chatgpt as FeatureToPoint() did not finish in over an hour)
- [ ] run with all parcels
- [ ] run with building footprints extracted from newest Nearmap data (late Jan 2025)
- [ ] join transformed table back to building polygon (or line) footprint fc
- [ ] cleanup
 