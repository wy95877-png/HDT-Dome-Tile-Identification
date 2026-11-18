import clr
import math

clr.AddReference("RevitAPI")
import Autodesk.Revit.DB as DB

clr.AddReference("RevitServices")
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

doc = DocumentManager.Instance.CurrentDBDocument

# ------------------------------------------------
# INPUTS
# ------------------------------------------------

# IN[0]: filtered dome-tile components
# IN[1]: reference tile located in Sector S01

tiles = UnwrapElement(IN[0])
reference_tile = UnwrapElement(IN[1])

if not isinstance(tiles, list):
    tiles = [tiles]

DOME_CODE = "D01"
PARENT_CODE = "DOME_01"

# Set to False if the S01-S07 sequence follows
# the opposite direction
CLOCKWISE = True

# Tolerance used to identify tiles belonging
# to the same V row.
# Revit internal units are feet.
ROW_TOLERANCE = 0.08


def element_center(el):
    bb = el.get_BoundingBox(None)

    if bb is None:
        return None

    return (
        (bb.Min.X + bb.Max.X) / 2.0,
        (bb.Min.Y + bb.Max.Y) / 2.0,
        (bb.Min.Z + bb.Max.Z) / 2.0
    )


# ------------------------------------------------
# 1. Calculate the centre of each tile
# ------------------------------------------------

data = []

for tile in tiles:
    c = element_center(tile)

    if c is not None:
        data.append({
            "element": tile,
            "x": c[0],
            "y": c[1],
            "z": c[2]
        })


# ------------------------------------------------
# 2. Calculate the dome centre in plan
# ------------------------------------------------

cx = sum(d["x"] for d in data) / len(data)
cy = sum(d["y"] for d in data) / len(data)

ref = element_center(reference_tile)

ref_angle = math.atan2(
    ref[1] - cy,
    ref[0] - cx
)

sector_angle = 2.0 * math.pi / 7.0


# ------------------------------------------------
# 3. Classify tiles into sectors S01-S07
# ------------------------------------------------

groups = {}

for i in range(1, 8):
    groups["S{:02d}".format(i)] = []

for d in data:

    angle = math.atan2(
        d["y"] - cy,
        d["x"] - cx
    )

    if CLOCKWISE:
        delta = (ref_angle - angle) % (2.0 * math.pi)
    else:
        delta = (angle - ref_angle) % (2.0 * math.pi)

    sector_index = int(
        math.floor(
            (delta + sector_angle / 2.0) / sector_angle
        )
    ) % 7

    sector = "S{:02d}".format(sector_index + 1)
    d["sector"] = sector

    # Determine the central direction of each sector
    if CLOCKWISE:
        sector_centre_angle = (
            ref_angle - sector_index * sector_angle
        )
    else:
        sector_centre_angle = (
            ref_angle + sector_index * sector_angle
        )

    # Calculate the local lateral coordinate
    # used for U indexing
    tangent_x = -math.sin(sector_centre_angle)
    tangent_y = math.cos(sector_centre_angle)

    d["local_u"] = (
        (d["x"] - cx) * tangent_x +
        (d["y"] - cy) * tangent_y
    )

    groups[sector].append(d)


# ------------------------------------------------
# 4. Determine V rows and U positions
# ------------------------------------------------

results = []
row_counts = {}

TransactionManager.Instance.EnsureInTransaction(doc)

for sector in sorted(groups.keys()):

    sector_tiles = groups[sector]

    # Sort tiles from highest to lowest.
    # The highest row corresponds to V01.
    sector_tiles = sorted(
        sector_tiles,
        key=lambda x: x["z"],
        reverse=True
    )

    rows = []

    for tile in sector_tiles:

        assigned = False

        for row in rows:

            row_z = sum(
                x["z"] for x in row
            ) / float(len(row))

            if abs(tile["z"] - row_z) <= ROW_TOLERANCE:
                row.append(tile)
                assigned = True
                break

        if not assigned:
            rows.append([tile])

    # Ensure that V01 corresponds to the upper row
    rows = sorted(
        rows,
        key=lambda row:
            sum(x["z"] for x in row) / float(len(row)),
        reverse=True
    )

    row_counts[sector] = len(rows)

    for v_index, row in enumerate(rows):

        V = v_index + 1

        # Sort tiles laterally to assign
        # U01, U02, U03, ...
        row = sorted(
            row,
            key=lambda x: x["local_u"]
        )

        for u_index, d in enumerate(row):

            U = u_index + 1
            tile = d["element"]

            # Generate the persistent component identifier
            hdt_id = "{}_{}_U{:02d}_V{:02d}".format(
                DOME_CODE,
                sector,
                U,
                V
            )

            p_id = tile.LookupParameter("HDT_Element_ID")
            p_parent = tile.LookupParameter("HDT_Parent_ID")
            p_zone = tile.LookupParameter("HDT_Zone")

            if p_id and not p_id.IsReadOnly:
                p_id.Set(hdt_id)

            if p_parent and not p_parent.IsReadOnly:
                p_parent.Set(PARENT_CODE)

            if p_zone and not p_zone.IsReadOnly:
                p_zone.Set(sector)

            results.append([
                tile.Id.Value,
                hdt_id
            ])

TransactionManager.Instance.TransactionTaskDone()


# ------------------------------------------------
# OUTPUT
# ------------------------------------------------

OUT = {
    "Total tiles": len(data),
    "V rows detected": row_counts,
    "IDs written": len(results),
    "Generated IDs": results
}
