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
 

To remove excess splits in parcel lines 1/29/25:
- [x] add polygon oid to attribute table of parcel polygons
- [x] convert parcel polgyons to lines
- [x] add line oid to attribute table
- [x] convert lines to points
- [x] for each group of points with the same line oid (if there are more than 2 points in line segment), append all angles between adjacent points to a list (ensure that order of points is preserved)
    - [x] check on threshold - check some from list below in fc points_for_splitting_angle_threshold_15
    - [ ] for each group of three points representing a line:
        -[x] if list of angles contains any values over a threshold (~10-15), insert a point that will be used for splitting
        -[ ] if list of angles contains only smaller angles:
            - [ ] if angle between first and last points of line suggests a corner, split line at midpoint only
            - [ ] if angle between first and last points of line suggests a U-shaped line, split line into thirds (knowing that there will be exceptions where one side is longer than another e.g. parcel 1455)
- [x] for each pair of points with the same line oid (lines with exactly two vertices - start and end only), add both points directly to fc holding points for splitting lines OR include the start and end points of all lines?

check separately if not fixed by adding all points that make up two-point lines: 
line oid 13 (points 29-32)


Example where no points (for splitting line) should be added (line is mostly straight with a slight curve):
with arcpy.da.SearchCursor("points_from_parcel_lines_from_polygons_TEST", ["OBJECTID", "SHAPE@"]) as cursor:
    previous_geom_1 = None
    previous_geom_2 = None
    for row in cursor:
        print(f"OID: {row[0]}")
        if row[0] < 11:
            continue
        elif row[0] == 11:
            previous_geom_1 = row[1]
        elif row[0] == 12:
            previous_geom_2 = row[1]
        elif row[0] < 18:
            oid = row[0]
            angle_1 = calculate_angle_from_points(previous_geom_1, previous_geom_2)
            angle_2 = calculate_angle_from_points(previous_geom_2, row[1])
            angle = angle_2 - angle_1
            print(f"OID's: {oid-2}, {oid-1}, {oid}. Angle: {angle}")
            previous_geom_1 = previous_geom_2
            previous_geom_2 = row[1]
        elif row[0] == 18:
            break
OID: 11
OID: 12
OID: 13
OID's: 11, 12, 13. Angle: 0.4418921217899765
OID: 14
OID's: 12, 13, 14. Angle: -6.944883682717659
OID: 15
OID's: 13, 14, 15. Angle: -6.95783147150803
OID: 16
OID's: 14, 15, 16. Angle: -6.947908190945725
OID: 17
OID's: 15, 16, 17. Angle: -6.948837549794746

Example where three points (for splitting line) should be added (not at point with OID 2 but at points with OIDs 3, 4, 5):
with arcpy.da.SearchCursor("points_from_parcel_lines_from_polygons_TEST", ["OBJECTID", "SHAPE@"]) as cursor:
    previous_geom_1 = None
    previous_geom_2 = None
    for row in cursor:
        if row[0] == 1:
            previous_geom_1 = row[1]
        elif row[0] == 2:
            previous_geom_2 = row[1]
        elif row[0] < 7:
            oid = row[0]
            angle_1 = calculate_angle_from_points(previous_geom_1, previous_geom_2)
            angle_2 = calculate_angle_from_points(previous_geom_2, row[1])
            angle = angle_2 - angle_1
            print(f"OID's: {oid-2}, {oid-1}, {oid}. Angle: {angle}")
            previous_geom_1 = previous_geom_2
            previous_geom_2 = row[1]
OID's: 1, 2, 3. Angle: 0.005249458632675896
OID's: 2, 3, 4. Angle: -131.16694330596823
OID's: 3, 4, 5. Angle: 109.27683515899992
OID's: 4, 5, 6. Angle: -88.77338093846737



Angle: 10.005369630727227 between points with OID 563, 564, and 565 is within 5 degrees of threshold. - on a curve for a corner lot - did not add a point which is desired behavior
Angle: 10.056827624432913 between points with OID 566, 567, and 568 is within 5 degrees of threshold.
Angle: 10.005382165499157 between points with OID 847, 848, and 849 is within 5 degrees of threshold.
Angle: 10.010266343659026 between points with OID 849, 850, and 851 is within 5 degrees of threshold.
Angle: 10.009760217974375 between points with OID 851, 852, and 853 is within 5 degrees of threshold.
Angle: 10.001162018066566 between points with OID 941, 942, and 943 is within 5 degrees of threshold.
Angle: 10.047426802030088 between points with OID 1117, 1118, and 1119 is within 5 degrees of threshold.
Angle: 10.03957425508046 between points with OID 1119, 1120, and 1121 is within 5 degrees of threshold.
Angle: 11.653819290571196 between points with OID 1210, 1211, and 1212 is within 5 degrees of threshold.
Angle: 10.034184432339003 between points with OID 1507, 1508, and 1509 is within 5 degrees of threshold.
Angle: 10.04121210485809 between points with OID 1509, 1510, and 1511 is within 5 degrees of threshold.
Angle: 13.085815708848543 between points with OID 1697, 1698, and 1699 is within 5 degrees of threshold. - may or may not need a point with angles of this size
Angle: 10.03632626583618 between points with OID 1997, 1998, and 1999 is within 5 degrees of threshold.
Angle: 10.022331056561896 between points with OID 2000, 2001, and 2002 is within 5 degrees of threshold.
Angle: 10.008484457612255 between points with OID 2002, 2003, and 2004 is within 5 degrees of threshold.
Angle: 13.052953302759136 between points with OID 2159, 2160, and 2161 is within 5 degrees of threshold.
Angle: 10.262681344216084 between points with OID 2207, 2208, and 2209 is within 5 degrees of threshold.
Angle: 10.333547813487339 between points with OID 2211, 2212, and 2213 is within 5 degrees of threshold.
Angle: 11.882408015635711 between points with OID 2216, 2217, and 2218 is within 5 degrees of threshold.
Angle: 10.008100831741643 between points with OID 2464, 2465, and 2466 is within 5 degrees of threshold.
Angle: 10.006385242265651 between points with OID 2468, 2469, and 2470 is within 5 degrees of threshold.
Angle: 10.005617959740562 between points with OID 2483, 2484, and 2485 is within 5 degrees of threshold.
Angle: 10.049613656006471 between points with OID 2485, 2486, and 2487 is within 5 degrees of threshold.
Angle: 10.007207213813388 between points with OID 2489, 2490, and 2491 is within 5 degrees of threshold.
Angle: 10.008054665364853 between points with OID 2530, 2531, and 2532 is within 5 degrees of threshold.
Angle: 10.04849506123091 between points with OID 2532, 2533, and 2534 is within 5 degrees of threshold.
Angle: 10.016127327939628 between points with OID 2534, 2535, and 2536 is within 5 degrees of threshold.
Angle: 10.016926381081433 between points with OID 2536, 2537, and 2538 is within 5 degrees of threshold.
Angle: 10.000759611794052 between points with OID 3306, 3307, and 3308 is within 5 degrees of threshold.
Angle: 14.826257208190967 between points with OID 3615, 3616, and 3617 is within 5 degrees of threshold.
Angle: 10.003393271508845 between points with OID 3632, 3633, and 3634 is within 5 degrees of threshold.
Angle: 10.000485781301414 between points with OID 3634, 3635, and 3636 is within 5 degrees of threshold.
Angle: 10.026628727914442 between points with OID 3998, 3999, and 4000 is within 5 degrees of threshold.
Angle: 10.020004604852687 between points with OID 4000, 4001, and 4002 is within 5 degrees of threshold.
Angle: 10.01325788225077 between points with OID 4004, 4005, and 4006 is within 5 degrees of threshold.
Angle: 11.945616145506392 between points with OID 4028, 4029, and 4030 is within 5 degrees of threshold.
Angle: 10.613754099784558 between points with OID 4386, 4387, and 4388 is within 5 degrees of threshold.
Angle: 10.00891400750595 between points with OID 4485, 4486, and 4487 is within 5 degrees of threshold.
Angle: 10.008606902000054 between points with OID 4486, 4487, and 4488 is within 5 degrees of threshold.
Angle: 10.036287256900948 between points with OID 4489, 4490, and 4491 is within 5 degrees of threshold.
Angle: 10.015027503023589 between points with OID 4491, 4492, and 4493 is within 5 degrees of threshold.
Angle: 10.020647629534949 between points with OID 4492, 4493, and 4494 is within 5 degrees of threshold.
Angle: 10.013896146540276 between points with OID 5794, 5795, and 5796 is within 5 degrees of threshold.
Angle: 10.00337292071572 between points with OID 5796, 5797, and 5798 is within 5 degrees of threshold.
Angle: 10.014577972566883 between points with OID 5797, 5798, and 5799 is within 5 degrees of threshold.
Angle: 10.007436409030959 between points with OID 5799, 5800, and 5801 is within 5 degrees of threshold.
Angle: 14.069510521288066 between points with OID 5982, 5983, and 5984 is within 5 degrees of threshold.
Angle: 10.454891708453772 between points with OID 6031, 6032, and 6033 is within 5 degrees of threshold.
Angle: 10.726789371257496 between points with OID 6036, 6037, and 6038 is within 5 degrees of threshold.
Angle: 10.297680504891218 between points with OID 6224, 6225, and 6226 is within 5 degrees of threshold.
Angle: 11.714871792838835 between points with OID 6411, 6412, and 6413 is within 5 degrees of threshold.
Angle: 10.00184619339666 between points with OID 6426, 6427, and 6428 is within 5 degrees of threshold.
Angle: 12.113417033834324 between points with OID 6489, 6490, and 6491 is within 5 degrees of threshold.
Angle: 10.082822126492971 between points with OID 6499, 6500, and 6501 is within 5 degrees of threshold.
Angle: 10.934952369024643 between points with OID 7142, 7143, and 7144 is within 5 degrees of threshold.
Angle: 10.000714767640261 between points with OID 7214, 7215, and 7216 is within 5 degrees of threshold.
Angle: 10.021073370208683 between points with OID 7218, 7219, and 7220 is within 5 degrees of threshold.
Angle: 10.153762637225782 between points with OID 7532, 7533, and 7534 is within 5 degrees of threshold.
Angle: 11.368914312461357 between points with OID 8212, 8213, and 8214 is within 5 degrees of threshold.
Angle: 10.494119914809175 between points with OID 8218, 8219, and 8220 is within 5 degrees of threshold.
Angle: 11.304143733790854 between points with OID 8220, 8221, and 8222 is within 5 degrees of threshold.
Angle: 10.473938869678568 between points with OID 8221, 8222, and 8223 is within 5 degrees of threshold.
Angle: 11.910057572810615 between points with OID 8222, 8223, and 8224 is within 5 degrees of threshold.
Angle: 12.560207526437303 between points with OID 8226, 8227, and 8228 is within 5 degrees of threshold.
Angle: 13.983154887688784 between points with OID 8229, 8230, and 8231 is within 5 degrees of threshold.
Angle: 13.52233825174848 between points with OID 8231, 8232, and 8233 is within 5 degrees of threshold.
Angle: 10.747859575466379 between points with OID 8236, 8237, and 8238 is within 5 degrees of threshold.
Angle: 10.653125822925233 between points with OID 8399, 8400, and 8401 is within 5 degrees of threshold.
Angle: 13.783610261900236 between points with OID 8404, 8405, and 8406 is within 5 degrees of threshold.
Angle: 11.235749858254756 between points with OID 8407, 8408, and 8409 is within 5 degrees of threshold.
Angle: 13.216103008009775 between points with OID 8408, 8409, and 8410 is within 5 degrees of threshold.
Angle: 14.071645494911081 between points with OID 8419, 8420, and 8421 is within 5 degrees of threshold.
Angle: 14.071645494911081 between points with OID 8420, 8421, and 8422 is within 5 degrees of threshold.
Angle: 12.479710664752304 between points with OID 8422, 8423, and 8424 is within 5 degrees of threshold.
Angle: 13.17557098197284 between points with OID 8426, 8427, and 8428 is within 5 degrees of threshold.
Angle: 12.512414734316451 between points with OID 8428, 8429, and 8430 is within 5 degrees of threshold.
Angle: 10.005637663986391 between points with OID 8432, 8433, and 8434 is within 5 degrees of threshold.
Angle: 10.003110927160918 between points with OID 8434, 8435, and 8436 is within 5 degrees of threshold.
Angle: 10.006348532570598 between points with OID 8435, 8436, and 8437 is within 5 degrees of threshold.
Angle: 10.025189641254457 between points with OID 8437, 8438, and 8439 is within 5 degrees of threshold.
Angle: 14.016354642547881 between points with OID 8538, 8539, and 8540 is within 5 degrees of threshold.
Angle: 13.464550337135563 between points with OID 8540, 8541, and 8542 is within 5 degrees of threshold.
Angle: 10.506331111007768 between points with OID 8549, 8550, and 8551 is within 5 degrees of threshold.
Angle: 13.269959736291582 between points with OID 8552, 8553, and 8554 is within 5 degrees of threshold.
Angle: 13.253994251673447 between points with OID 8553, 8554, and 8555 is within 5 degrees of threshold.
Angle: 12.615694625504204 between points with OID 8555, 8556, and 8557 is within 5 degrees of threshold.
Angle: 14.287048431815663 between points with OID 8557, 8558, and 8559 is within 5 degrees of threshold.
Angle: 11.514352860766394 between points with OID 8563, 8564, and 8565 is within 5 degrees of threshold.
Angle: 13.742038981894837 between points with OID 8565, 8566, and 8567 is within 5 degrees of threshold.
Angle: 11.34752826909591 between points with OID 8626, 8627, and 8628 is within 5 degrees of threshold.
Angle: 14.194503783030214 between points with OID 8632, 8633, and 8634 is within 5 degrees of threshold. - part of strange circular cutouts - no need for a point here
Angle: 12.476147824391418 between points with OID 8634, 8635, and 8636 is within 5 degrees of threshold.
Angle: 13.788697064401674 between points with OID 8639, 8640, and 8641 is within 5 degrees of threshold.
Angle: 11.877660866153036 between points with OID 8644, 8645, and 8646 is within 5 degrees of threshold.
Angle: 11.280519863864527 between points with OID 8645, 8646, and 8647 is within 5 degrees of threshold.
Angle: 14.016354241030854 between points with OID 8652, 8653, and 8654 is within 5 degrees of threshold.
Angle: 10.234186387291572 between points with OID 8655, 8656, and 8657 is within 5 degrees of threshold.
Angle: 11.2629419094681 between points with OID 8693, 8694, and 8695 is within 5 degrees of threshold.
Angle: 13.196865800414642 between points with OID 8696, 8697, and 8698 is within 5 degrees of threshold.
Angle: 14.02739721036258 between points with OID 8701, 8702, and 8703 is within 5 degrees of threshold.
Angle: 12.51509226942163 between points with OID 8702, 8703, and 8704 is within 5 degrees of threshold.
Angle: 12.911153430234464 between points with OID 8704, 8705, and 8706 is within 5 degrees of threshold.
Angle: 14.02739721036258 between points with OID 8709, 8710, and 8711 is within 5 degrees of threshold.
Angle: 12.122255321514558 between points with OID 8712, 8713, and 8714 is within 5 degrees of threshold.
Angle: 10.110802490427858 between points with OID 8713, 8714, and 8715 is within 5 degrees of threshold.
Angle: 10.008362628448879 between points with OID 8811, 8812, and 8813 is within 5 degrees of threshold.
Angle: 10.002057913560463 between points with OID 8812, 8813, and 8814 is within 5 degrees of threshold.
Angle: 10.000159365534046 between points with OID 8813, 8814, and 8815 is within 5 degrees of threshold.
Angle: 10.061452778455418 between points with OID 8817, 8818, and 8819 is within 5 degrees of threshold.
Angle: 10.014608240122314 between points with OID 8901, 8902, and 8903 is within 5 degrees of threshold.
Angle: 10.021348570959212 between points with OID 8903, 8904, and 8905 is within 5 degrees of threshold.
Angle: 10.02794559752693 between points with OID 8905, 8906, and 8907 is within 5 degrees of threshold.
Angle: 10.00348843518735 between points with OID 8907, 8908, and 8909 is within 5 degrees of threshold.
Angle: 10.003280630637391 between points with OID 9039, 9040, and 9041 is within 5 degrees of threshold.
Angle: 13.465502234886998 between points with OID 9242, 9243, and 9244 is within 5 degrees of threshold.
Angle: 10.014841493104228 between points with OID 9316, 9317, and 9318 is within 5 degrees of threshold.
Angle: 10.0328973048411 between points with OID 9318, 9319, and 9320 is within 5 degrees of threshold.
Angle: 10.023595909922378 between points with OID 9320, 9321, and 9322 is within 5 degrees of threshold.
Angle: 10.06540958959161 between points with OID 9322, 9323, and 9324 is within 5 degrees of threshold.
Angle: 10.014958491464597 between points with OID 9366, 9367, and 9368 is within 5 degrees of threshold.
Angle: 10.021836961490749 between points with OID 9368, 9369, and 9370 is within 5 degrees of threshold.
Angle: 10.005413606055981 between points with OID 9371, 9372, and 9373 is within 5 degrees of threshold.
Angle: 10.027059252723035 between points with OID 9625, 9626, and 9627 is within 5 degrees of threshold.
Angle: 10.007470591677503 between points with OID 9627, 9628, and 9629 is within 5 degrees of threshold.
Angle: 10.011654978329716 between points with OID 9629, 9630, and 9631 is within 5 degrees of threshold.
Angle: 10.019055936689995 between points with OID 9917, 9918, and 9919 is within 5 degrees of threshold.
Angle: 10.014331202991343 between points with OID 9921, 9922, and 9923 is within 5 degrees of threshold.
Angle: 10.026014874486648 between points with OID 10085, 10086, and 10087 is within 5 degrees of threshold.
Angle: 10.008911915908115 between points with OID 10086, 10087, and 10088 is within 5 degrees of threshold.
Angle: 10.004197876629924 between points with OID 10088, 10089, and 10090 is within 5 degrees of threshold.
Angle: 10.003966430784768 between points with OID 10092, 10093, and 10094 is within 5 degrees of threshold.
Angle: 11.98832822467108 between points with OID 10156, 10157, and 10158 is within 5 degrees of threshold.
Angle: 10.043861143431798 between points with OID 10609, 10610, and 10611 is within 5 degrees of threshold.
Angle: 10.026296731381876 between points with OID 10611, 10612, and 10613 is within 5 degrees of threshold.
Angle: 10.072153225645451 between points with OID 10613, 10614, and 10615 is within 5 degrees of threshold.
Angle: 10.016030078108713 between points with OID 10615, 10616, and 10617 is within 5 degrees of threshold.
Angle: 10.123059277537237 between points with OID 10683, 10684, and 10685 is within 5 degrees of threshold.
Angle: 10.003977546875262 between points with OID 10686, 10687, and 10688 is within 5 degrees of threshold.
Angle: 10.000498471077691 between points with OID 10703, 10704, and 10705 is within 5 degrees of threshold.
Angle: 10.004451623662874 between points with OID 10705, 10706, and 10707 is within 5 degrees of threshold.
Angle: 10.041172570944 between points with OID 10883, 10884, and 10885 is within 5 degrees of threshold.
Angle: 10.013578534698404 between points with OID 11128, 11129, and 11130 is within 5 degrees of threshold.
Angle: 10.042513770009961 between points with OID 11130, 11131, and 11132 is within 5 degrees of threshold.
Angle: 10.00036843545584 between points with OID 11308, 11309, and 11310 is within 5 degrees of threshold.
Angle: 10.010883848980484 between points with OID 11745, 11746, and 11747 is within 5 degrees of threshold.
Angle: 10.000085891665606 between points with OID 11747, 11748, and 11749 is within 5 degrees of threshold.
Angle: 10.007366192248142 between points with OID 11918, 11919, and 11920 is within 5 degrees of threshold.
Angle: 10.000242282497574 between points with OID 11920, 11921, and 11922 is within 5 degrees of threshold.
Angle: 10.000303582526458 between points with OID 11982, 11983, and 11984 is within 5 degrees of threshold.
Angle: 10.01735458297054 between points with OID 11998, 11999, and 12000 is within 5 degrees of threshold.
Angle: 10.007103981807916 between points with OID 12037, 12038, and 12039 is within 5 degrees of threshold.
Angle: 10.031272513415672 between points with OID 12039, 12040, and 12041 is within 5 degrees of threshold.
Angle: 10.028131926162246 between points with OID 12041, 12042, and 12043 is within 5 degrees of threshold.
Angle: 10.012263511881628 between points with OID 12199, 12200, and 12201 is within 5 degrees of threshold.
Angle: 10.04850385111493 between points with OID 12201, 12202, and 12203 is within 5 degrees of threshold.
Angle: 10.01795831247712 between points with OID 12203, 12204, and 12205 is within 5 degrees of threshold.
Angle: 10.007718998890436 between points with OID 12204, 12205, and 12206 is within 5 degrees of threshold.
Angle: 10.161257305337557 between points with OID 12401, 12402, and 12403 is within 5 degrees of threshold.
Angle: 10.035675468128687 between points with OID 12534, 12535, and 12536 is within 5 degrees of threshold.
Angle: 10.027797841104984 between points with OID 12536, 12537, and 12538 is within 5 degrees of threshold.
Angle: 10.018186620840865 between points with OID 12538, 12539, and 12540 is within 5 degrees of threshold.
Angle: 10.00917497256907 between points with OID 12540, 12541, and 12542 is within 5 degrees of threshold.
Angle: 10.010446825234368 between points with OID 12863, 12864, and 12865 is within 5 degrees of threshold.
Angle: 10.004423453428274 between points with OID 13224, 13225, and 13226 is within 5 degrees of threshold.
Angle: 10.002085836747739 between points with OID 13226, 13227, and 13228 is within 5 degrees of threshold.
Angle: 10.00263784727484 between points with OID 13229, 13230, and 13231 is within 5 degrees of threshold.
Angle: 10.518635664079312 between points with OID 13804, 13805, and 13806 is within 5 degrees of threshold.
Angle: 10.012838055734562 between points with OID 14239, 14240, and 14241 is within 5 degrees of threshold.
Angle: 10.00289786926929 between points with OID 14245, 14246, and 14247 is within 5 degrees of threshold.
Angle: 14.523053011618515 between points with OID 14380, 14381, and 14382 is within 5 degrees of threshold.
Angle: 10.460517342358088 between points with OID 14514, 14515, and 14516 is within 5 degrees of threshold.
Angle: 10.566126721958653 between points with OID 14518, 14519, and 14520 is within 5 degrees of threshold.
Angle: 10.834484729908354 between points with OID 14684, 14685, and 14686 is within 5 degrees of threshold.
Angle: 10.203970590300173 between points with OID 14721, 14722, and 14723 is within 5 degrees of threshold.
Angle: 10.58733907256169 between points with OID 14722, 14723, and 14724 is within 5 degrees of threshold.
Angle: 11.077230032955697 between points with OID 14723, 14724, and 14725 is within 5 degrees of threshold.
Angle: 10.547177221952438 between points with OID 14838, 14839, and 14840 is within 5 degrees of threshold.
Angle: 10.61733364622988 between points with OID 14854, 14855, and 14856 is within 5 degrees of threshold.
Angle: 10.523584291451883 between points with OID 14856, 14857, and 14858 is within 5 degrees of threshold.