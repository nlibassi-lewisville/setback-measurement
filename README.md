# Setback Measurement

## Overview

The following Python scripts are used to determine setback values - distances between sides of buildings and segments of parcel boundaries facing each side of a building

- **`prep_data.py`**: Prepares input data by converting parcel polygons to lines, identifying shared boundaries, and generating spatial joins between parcels and buildings.
- **`simple_measure.py`**: Computes setback distances between buildings and parcel boundaries, formats tables, and generates statistical summaries.

These scripts are designed for use within an **ArcGIS** environment and require **arcpy** and other dependencies.

## Input Data

Both scripts operate on geospatial data stored in an **ArcGIS geodatabase**. The required inputs include:

1. **Parcel Polygon Feature Class** - A polygon feature class representing land parcels.
2. **Building Polygon Feature Class** - A polygon feature class representing building footprints.
3. **Parcel Line Feature Class** - A line feature class representing parcel boundaries (generated in `prep_data.py`).
4. **Parcel ID Table** - A table linking parcel polygons to their boundary lines (generated in `prep_data.py`).

## Key Functionality

### `prep_data.py`
- **Converts** parcel polygons into line features.
- **Identifies** shared parcel boundaries.
- **Joins** buildings to their containing parcels.
- **Creates** a table linking parcel polygons to their boundary lines.

### `simple_measure.py`
- **Generates** a near table linking buildings to parcel lines.
- **Filters and trims** the near table to relevant parcel boundaries.
- **Transforms** setback data for better analysis.
- **Joins** setback distances to building features.
- **Filters** out errors and excessive setbacks.
- **Calculates** average setback distances.

## Process

### 1. Prepare Data (`prep_data.py`)
- Convert parcel polygons to lines.
- Identify shared parcel boundaries.
- Perform spatial joins between buildings and parcels.
- Create a parcel ID table linking parcels to their boundary lines.

### 2. Measure Setbacks (`simple_measure.py`)
- Generate a near table linking buildings to parcel lines.
- Join near table with parcel information.
- Trim near table to exclude irrelevant parcel lines.
- Transform near table to structure setback distances.
- Join setback distances back to buildings.
- Filter and clean results.
- Compute average setback distances.

## Dependencies

These scripts require:
- **ArcGIS Pro or ArcGIS Server** with **arcpy**
- **Python 3.x** (as used in ArcGIS)
- **NumPy**
- **Pandas**
- **A configured ArcGIS geodatabase** with the required feature classes and tables

## Usage

1. Ensure all dependencies are installed and that ArcGIS Pro/ArcMap is available with necessary licenses.
2. Configure the .env file to define FEATURE_DATASET and GEODATABASE paths according to the file '.env.example'.
3. In prep_data.py, modify the values assigned to variables under 'BEFORE RUNNING' 
4. Run prep_data.py before running simple_measure.py. The following outputs of prep_data.py are used as inputs of simple_measure.py:
    1. parcel_line_fc - parcel boundary line feature class created from a parcel boundary polygon feature class
    2. building_parcel_join_fc - a feature class that contains buildings with attributes of the parcel in which each building lies
    3. parcel_id_table - a table with parcel polygon IDs and the line IDs that make up their boundaries
4. For simple_measure.py
    1. in get_near_table(), the values of search_radius and closest_count can be modified as needed
    2. in run(), the value of max_side_fields can be modified as needed
    3. edit the inputs of the run() function that appear in the lines before calling run() in simple_measure.py (see comment 'BEFORE RUNNING')

Both scripts can be run as a standalone Python script from a terminal (`python path/to/script.py` or `propy path/to/script.py` if using the 'propy' environment provided with ArcGIS Pro).

## Output

Using the Jan 2024 Nearmap data, the area of interest has 1494 buildings, but buildings in the following situations were not included when calculating the averages:
- those with any setback value of 0 (meaning the building footprint was not entirely within the parcel feature)
- those buildings that had more than four surrounding parcel boundary segments - in the screenshot below, building 542 is an example of one of those that were not included - on the west side of the building, there are four separate parcel line segments - since the distances to all of those segments were found, those distances would skew the average. (This could be addressed in the future if necessary)
- buildings with a footprint that spanned multiple parcels

![sample results](/img/setback-sample-results.png)

TODO - finish this section

Results feature classes and tables:
- averages table - the sums and averages are in feet and 'count' refers to the number of sides of a building used to get the averages. 'Facing street' means the distance is to a parcel boundary that is not shared between two parcel features, and 'other side' means that the parcel boundary is shared between two parcels (see sample screenshot below).
- 'filtered_results...' feature class from which the averages were calculated (773 buildings in this example)
- 'clean_buildings...' feature class - unfiltered results with setback values for all buildings


![sample averages](/img/setback-sample-average-table.png)
