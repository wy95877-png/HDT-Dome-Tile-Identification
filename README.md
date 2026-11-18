# HDT-Dome-Tile-Identification

This repository contains the Dynamo workflow and Python routine developed for automated component-level identification of individual dome tiles within an HBIM model of the Hermitage of San Bernat.

The workflow supports the geometric-semantic structuring of repetitive heritage components for subsequent Historic Digital Twin (HDT) development.

## Workflow

The implemented procedure:

1. filters the relevant dome-tile components within the Revit model;
2. uses a reference tile located in Sector S01 to establish the sector orientation;
3. classifies individual tiles into seven predefined sectors (S01-S07);
4. derives local U/V indices from the spatial position of each component;
5. generates persistent component identifiers following the structure:

`D01_Sxx_Uxx_Vxx`

6. automatically assigns the generated information to the following instance-based parameters:

- `HDT_Element_ID`
- `HDT_Parent_ID`
- `HDT_Zone`

## Repository files

- `HDT_Dome_Tile_Identification.dyn`  
  Dynamo workflow used for component filtering and execution of the automated identification process.

- `automated_component_identification.py`  
  Python routine used within Dynamo for sector classification, local U/V indexing, persistent identifier generation, and parameter assignment.

## Inputs

The Python routine receives:

- `IN[0]`: filtered dome-tile components;
- `IN[1]`: a reference tile located in Sector S01.

## Output

Each processed dome tile receives a persistent identifier such as:

`D01_S04_U06_V08`

where:

- `D01` = Dome 01
- `S04` = Sector 04
- `U06` = local lateral position
- `V08` = local vertical row

## Research context

This workflow was developed as part of a geometric-semantic HBIM framework for openBIM-based Historic Digital Twin readiness.

The complete dome-tile identification dataset is provided separately as supplementary material associated with the study.
