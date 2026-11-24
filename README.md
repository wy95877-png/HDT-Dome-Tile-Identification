# HDT Dome and Roof Tile Identification

**Version 2.0.0**  
**Zenodo DOI:** [10.5281/zenodo.24502303](https://doi.org/10.5281/zenodo.24502303)

This repository contains the Dynamo workflows and Python implementations developed for automated component-level identification of tiled elements within an HBIM model of the Hermitage of San Bernat.

The workflows support geometric-semantic structuring of repetitive heritage components for Historic Digital Twin (HDT) development by assigning persistent identifiers and HDT-oriented parameters to individual Revit curtain-panel instances.

## Identification hierarchy

Three complementary identification schemes are implemented.

### 1. Dome sector tiles

Regular dome tiles are identified as:

`D01_Sxx_Uxx_Vxx`

where:

- `D01` = Dome 01
- `Sxx` = sector number (S01-S07)
- `Uxx` = local circumferential position
- `Vxx` = local meridional row

### 2. Dome boundary tiles

Boundary tile strips are identified as:

`D01_Sxx_Uxx_B01`

where `B01` denotes the boundary strip associated with the corresponding dome sector.

### 3. Roof sector tiles

Surrounding roof tiles are identified as:

`R01_Sxx_Uxx_Vxx`

where:

- `R01` = Roof 01
- `Sxx` = sector number (S01-S07)
- `Uxx` and `Vxx` define the local component position within the selected roof sector

## Method

The final workflow uses the native parametric organization of Revit `DividedSurface` elements rather than reconstructing U/V coordinates from bounding-box positions.

For sector-based tile systems, the procedure:

1. selects the relevant Revit `DividedSurface`;
2. retrieves its native `GridNode(U,V)` organization;
3. obtains the associated native tile family instances;
4. determines the orientation of the native U/V axes relative to the model geometry;
5. normalizes the indices to the methodological U/V convention used in the study;
6. matches the native divided-surface tiles to the corresponding project-level curtain-panel instances;
7. generates persistent HDT component identifiers; and
8. writes the resulting information to instance parameters in Revit.

For dome boundary strips, the selected one-dimensional tile sequence is ordered spatially from the dome apex toward the eave and identified using the `Uxx_B01` structure.

## Revit parameters

The workflows assign the following instance-based parameters:

- `HDT_Element_ID`
- `HDT_Parent_ID`
- `HDT_Zone`

Typical values include:

- `HDT_Element_ID = D01_S01_U13_V08`
- `HDT_Element_ID = D01_S01_U13_B01`
- `HDT_Element_ID = R01_S01_U13_V08`
- `HDT_Parent_ID = DOME_01` or `ROOF_01`
- `HDT_Zone = S01` to `S07`

## Repository files

### Dome sector tiles

- `HDT_Dome_Sector_Tile_Identification.dyn`
- `HDT_Dome_Sector_Tile_Identification.py`

Automated identification of regular dome tiles using the native U/V organization of the selected Revit DividedSurface.

### Dome boundary tiles

- `HDT_Dome_Boundary_Tile_Identification.dyn`
- `HDT_Dome_Boundary_Tile_Identification.py`

Automated one-dimensional identification of the dome boundary tile strips using the `D01_Sxx_Uxx_B01` identifier structure.

### Roof sector tiles

- `HDT_Roof_Sector_Tile_Identification.dyn`
- `HDT_Roof_Sector_Tile_Identification.py`

Automated identification of roof-sector tiles using the native parametric organization of the corresponding Revit DividedSurface.

## Typical execution workflow

For each sector:

1. enter the corresponding Revit mass-editing environment;
2. select the target `DividedSurface`;
3. use the Dynamo selection node for the associated divided-surface family instances;
4. set the sector code (`S01`-`S07`);
5. finish mass editing;
6. execute the Dynamo workflow;
7. verify that duplicate candidate identifiers are zero and that the write status is successful; and
8. validate the resulting identifiers through a Revit schedule.

## Software requirements

The workflow was developed for:

- Autodesk Revit 2026
- Dynamo for Revit
- Python Script node within Dynamo
- Autodesk Revit API
- RevitServices libraries

The `.dyn` files are intended to be executed within Dynamo for Revit.

## Research context

This software was developed as part of a geometric-semantic HBIM framework for openBIM-based Historic Digital Twin readiness. The generated identifiers provide persistent component-level references that can support semantic enrichment, inspection records, monitoring information, and subsequent IFC/openBIM workflows.

## Citation

If you use this software, please cite the archived software release:

**Wang, Y. (2026). _HDT Dome and Roof Tile Identification_ (Version 2.0.0). Zenodo. https://doi.org/10.5281/zenodo.24502303**

Citation metadata are also provided in `CITATION.cff`.
