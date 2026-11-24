import clr
import math
from collections import defaultdict, Counter

clr.AddReference("RevitAPI")
import Autodesk.Revit.DB as DB

clr.AddReference("RevitServices")
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

doc = DocumentManager.Instance.CurrentDBDocument

# ============================================================
# UNIVERSAL SETTINGS
# ============================================================
DOME_CODE = "D01"
PARENT_ID = "DOME_01"
WRITE_TO_REVIT = True
MAX_MATCH_DISTANCE_FT = 0.30
MAX_METHOD_U_POSITIONS = 25   # user/model convention for each sector

# ============================================================
# HELPERS
# ============================================================
def unwrap(x):
    try:
        return UnwrapElement(x)
    except:
        return x

def flatten(items):
    if items is None:
        return []
    if isinstance(items, (list, tuple)):
        out=[]
        for x in items:
            out.extend(flatten(x))
        return out
    return [items]

def eid(e):
    if e is None:
        return None
    try:
        return e.Id.Value
    except:
        try:
            return e.Id.IntegerValue
        except:
            return None

def point_of(e):
    if e is None:
        return None
    try:
        loc=e.Location
        if isinstance(loc, DB.LocationPoint):
            return loc.Point
    except:
        pass
    try:
        return e.GetTransform().Origin
    except:
        pass
    try:
        bb=e.get_BoundingBox(None)
        if bb:
            return DB.XYZ((bb.Min.X+bb.Max.X)/2.0,
                          (bb.Min.Y+bb.Max.Y)/2.0,
                          (bb.Min.Z+bb.Max.Z)/2.0)
    except:
        pass
    return None

def dist2(p,q):
    dx=p.X-q.X; dy=p.Y-q.Y; dz=p.Z-q.Z
    return dx*dx+dy*dy+dz*dz

def corr(xs,ys):
    n=min(len(xs),len(ys))
    if n<3: return 0.0
    xs=xs[:n]; ys=ys[:n]
    mx=sum(xs)/float(n); my=sum(ys)/float(n)
    dx=[x-mx for x in xs]; dy=[y-my for y in ys]
    denx=math.sqrt(sum(x*x for x in dx)); deny=math.sqrt(sum(y*y for y in dy))
    if denx<1e-12 or deny<1e-12: return 0.0
    return sum(dx[i]*dy[i] for i in range(n))/(denx*deny)

def circular_mean(angles):
    if not angles: return 0.0
    return math.atan2(sum(math.sin(a) for a in angles),sum(math.cos(a) for a in angles))

def near_angle(a,c):
    return math.atan2(math.sin(a-c),math.cos(a-c))

def norm_name(s):
    try:
        return ''.join(ch.lower() for ch in str(s) if ch.isalnum())
    except:
        return ''

def element_identity_text(e):
    parts=[]
    if e is None:
        return ""
    try:
        parts.append(str(e.Name))
    except:
        pass
    try:
        sym=e.Symbol
        if sym is not None:
            try: parts.append(str(sym.Name))
            except: pass
            try:
                fam=sym.Family
                if fam is not None: parts.append(str(fam.Name))
            except:
                pass
    except:
        pass
    try:
        tid=e.GetTypeId()
        if tid is not None and tid != DB.ElementId.InvalidElementId:
            et=doc.GetElement(tid)
            if et is not None:
                try: parts.append(str(et.Name))
                except: pass
                try: parts.append(str(et.FamilyName))
                except: pass
    except:
        pass
    return " | ".join(parts)

def is_blue_tile(e):
    return "curvedrooftileblue" in norm_name(element_identity_text(e))

def is_white_tile(e):
    return "curvedrooftilewhite" in norm_name(element_identity_text(e))

def find_param(e, wanted):
    try:
        p=e.LookupParameter(wanted)
        if p is not None:
            return p
    except:
        pass
    nw=norm_name(wanted)
    try:
        for p in e.Parameters:
            try:
                if norm_name(p.Definition.Name)==nw:
                    return p
            except:
                pass
    except:
        pass
    return None

def has_hdt_params(e):
    return all(find_param(e,n) is not None for n in ["HDT_Element_ID","HDT_Parent_ID","HDT_Zone"])

def normalize_sector_code(x):
    s=str(x).strip().upper() if x is not None else ""
    if s.startswith("S") and len(s)==3 and s[1:].isdigit():
        n=int(s[1:])
        if 1 <= n <= 7:
            return "S{:02d}".format(n)
    return None

# ============================================================
# INPUTS
# IN[0] = all project roof Curtain Panels from existing graph
# IN[1] = selected real DividedSurface (Select Model Element)
# IN[2] = Select Divided Surface Families output for SAME surface
# IN[3] = sector code string, e.g. S01 ... S07
# ============================================================
project_tiles=[unwrap(x) for x in flatten(IN[0])]
project_tiles=[x for x in project_tiles if x is not None and is_blue_tile(x)]
selected_ds=unwrap(IN[1]) if len(IN)>1 else None
selected_native=[unwrap(x) for x in flatten(IN[2])] if len(IN)>2 else []
selected_native_all=[x for x in selected_native if x is not None]
selected_native=[x for x in selected_native_all if is_blue_tile(x)]
sector_code=normalize_sector_code(IN[3] if len(IN)>3 else None)
errors=[]

# Project roof tile points also provide a stable dome XY center.
project_ready=[]
all_project_pts=[]
for e in project_tiles:
    p=point_of(e)
    if p is not None:
        all_project_pts.append(p)
    if has_hdt_params(e) and p is not None:
        project_ready.append({"element":e,"ElementId":eid(e),"point":p})

if all_project_pts:
    dome_cx=sum(p.X for p in all_project_pts)/float(len(all_project_pts))
    dome_cy=sum(p.Y for p in all_project_pts)/float(len(all_project_pts))
else:
    dome_cx=dome_cy=0.0

stop_reasons=[]
if sector_code is None:
    stop_reasons.append("invalid sector code; use S01 ... S07")
if selected_ds is None or not isinstance(selected_ds,DB.DividedSurface):
    stop_reasons.append("IN[1] is not Autodesk.Revit.DB.DividedSurface")
if len(selected_native)==0:
    stop_reasons.append("Select Divided Surface Families returned no tile instances")

if stop_reasons:
    OUT=[
        ["MODE","V18.1 BLUE-ONLY UNIVERSAL SECTOR WRITER"],
        ["STATUS","STOPPED"],
        ["Reasons",stop_reasons],
        ["Sector code",sector_code],
        ["Selected DividedSurface ElementId",eid(selected_ds)],
        ["Selected Divided Surface Families count",len(selected_native)],
    ]
else:
    ds=selected_ds
    nu=ds.NumberOfUGridlines
    nv=ds.NumberOfVGridlines

    # --------------------------------------------------------
    # A. TRUE native GridNode -> tile mapping
    # --------------------------------------------------------
    native_by_id={}
    duplicate_grid_instances=[]
    for u in range(nu):
        for v in range(nv):
            node=DB.GridNode(u,v)
            try:
                if not ds.IsSeedNode(node):
                    continue
            except:
                continue
            # rectangular pattern normally has one tile/seed; 4 keeps this robust
            for tile_index in range(4):
                try:
                    fi=ds.GetTileFamilyInstance(node,tile_index)
                except:
                    fi=None
                if fi is None:
                    continue
                k=eid(fi)
                if k is None:
                    continue
                rec={
                    "native_element":fi,
                    "native_ElementId":k,
                    "native_U":int(u),
                    "native_V":int(v),
                    "tile_index":int(tile_index),
                }
                if k in native_by_id:
                    old=native_by_id[k]
                    if old["native_U"]!=u or old["native_V"]!=v:
                        duplicate_grid_instances.append((k,old["native_U"],old["native_V"],u,v))
                else:
                    native_by_id[k]=rec
    native_all=list(native_by_id.values())
    native=[r for r in native_all if is_blue_tile(r["native_element"])]
    excluded_white_native=[r for r in native_all if is_white_tile(r["native_element"])]
    excluded_other_native=[r for r in native_all if (not is_blue_tile(r["native_element"]) and not is_white_tile(r["native_element"]))]

    # Validate that the special selection node and the selected DS are the same surface.
    selected_ids=set(eid(x) for x in selected_native if eid(x) is not None)
    native_ids=set(r["native_ElementId"] for r in native)
    common_ids=selected_ids.intersection(native_ids)
    only_selection=selected_ids-native_ids
    only_grid=native_ids-selected_ids
    selection_match_ratio=(len(common_ids)/float(max(1,len(native_ids))))

    # --------------------------------------------------------
    # B. Native axes -> methodological U/V
    #    Use true dome center from ALL project roof tiles.
    # --------------------------------------------------------
    rows=[]
    angles=[]
    for r in native:
        p=point_of(r["native_element"])
        if p is None:
            continue
        r["native_point"]=p
        a=math.atan2(p.Y-dome_cy,p.X-dome_cx)
        r["Z"]=p.Z
        r["angle"]=a
        angles.append(a)
        rows.append(r)

    sector_mean_angle=circular_mean(angles)
    for r in rows:
        r["local_angle"]=near_angle(r["angle"],sector_mean_angle)

    us=[float(r["native_U"]) for r in rows]
    vs=[float(r["native_V"]) for r in rows]
    zs=[float(r["Z"]) for r in rows]
    angs=[float(r["local_angle"]) for r in rows]
    cuZ=corr(us,zs); cvZ=corr(vs,zs)
    cuA=corr(us,angs); cvA=corr(vs,angs)

    # Meridional axis = native axis with stronger height correlation.
    if abs(cuZ)>=abs(cvZ):
        mer_native="native_U"
        circ_native="native_V"
    else:
        mer_native="native_V"
        circ_native="native_U"

    # V: preserve true native-row membership, then rank apex -> eave by mean Z.
    mer_groups=defaultdict(list)
    circ_groups=defaultdict(list)
    for r in rows:
        mer_groups[r[mer_native]].append(r)
        circ_groups[r[circ_native]].append(r)

    mer_order=sorted(
        mer_groups.keys(),
        key=lambda k:sum(x["Z"] for x in mer_groups[k])/float(len(mer_groups[k])),
        reverse=True
    )
    v_rank={raw:i+1 for i,raw in enumerate(mer_order)}

    # U: global column system for the sector. Do NOT restart U row-by-row.
    # Order each native circumferential grid coordinate by its mean physical polar angle.
    circ_order=sorted(
        circ_groups.keys(),
        key=lambda k:sum(x["local_angle"] for x in circ_groups[k])/float(len(circ_groups[k]))
    )
    u_rank={raw:i+1 for i,raw in enumerate(circ_order)}

    for r in rows:
        r["U"]=u_rank[r[circ_native]]
        r["V"]=v_rank[r[mer_native]]
        r["HDT_Element_ID"]="{}_{}_U{:02d}_V{:02d}".format(DOME_CODE,sector_code,r["U"],r["V"])

    ids=[r["HDT_Element_ID"] for r in rows]
    dup_ids=sorted([k for k,c in Counter(ids).items() if c>1])
    coord_counts=Counter((r["U"],r["V"]) for r in rows)
    dup_coords=sorted([k for k,c in coord_counts.items() if c>1])
    u_positions=len(set(r["U"] for r in rows))
    v_positions=len(set(r["V"] for r in rows))

    # --------------------------------------------------------
    # C. Match native DS tiles to visible project Curtain Panels
    # --------------------------------------------------------
    ready_by_id={x["ElementId"]:x for x in project_ready if x["ElementId"] is not None}
    match_records=[]
    for r in rows:
        target=None; d=None; method=None
        nk=r["native_ElementId"]
        if nk in ready_by_id:
            target=ready_by_id[nk]["element"]
            d=0.0
            method="same ElementId"
        else:
            p=r.get("native_point")
            best=None; bestd2=None
            if p is not None:
                for x in project_ready:
                    dd=dist2(p,x["point"])
                    if bestd2 is None or dd<bestd2:
                        bestd2=dd; best=x
            if best is not None:
                target=best["element"]
                d=math.sqrt(bestd2)
                method="nearest project panel"
        rr=dict(r)
        rr["target_element"]=target
        rr["target_ElementId"]=eid(target)
        rr["match_distance_ft"]=d
        rr["match_method"]=method
        match_records.append(rr)

    matched=[r for r in match_records if r["target_element"] is not None]
    target_ids=[r["target_ElementId"] for r in matched]
    duplicate_targets=sorted([k for k,c in Counter(target_ids).items() if k is not None and c>1])
    distances=[r["match_distance_ft"] for r in matched if r["match_distance_ft"] is not None]
    max_dist=max(distances) if distances else None
    mean_dist=sum(distances)/float(len(distances)) if distances else None
    over_limit=[r for r in matched if r["match_distance_ft"] is not None and r["match_distance_ft"]>MAX_MATCH_DISTANCE_FT]

    # --------------------------------------------------------
    # D. Safety gate + write
    # --------------------------------------------------------
    block=[]
    if len(rows)==0: block.append("no native UV tiles")
    if selection_match_ratio < 0.98: block.append("Select Divided Surface Families does not match selected DividedSurface")
    if duplicate_grid_instances: block.append("native instance mapped to multiple GridNodes")
    if dup_ids: block.append("duplicate candidate IDs")
    if dup_coords: block.append("duplicate U/V coordinates")
    if u_positions > MAX_METHOD_U_POSITIONS: block.append("method U exceeds 25 positions")
    if len(matched)!=len(rows): block.append("not all native tiles matched to project panels")
    if duplicate_targets: block.append("multiple native tiles matched to same project panel")
    if over_limit: block.append("project-panel match distance exceeds safety limit")
    if sector_code is None: block.append("invalid sector code")

    write_failures=[]
    written=0
    if WRITE_TO_REVIT and not block:
        try:
            TransactionManager.Instance.EnsureInTransaction(doc)
            for r in matched:
                e=r["target_element"]
                vals={
                    "HDT_Element_ID":r["HDT_Element_ID"],
                    "HDT_Parent_ID":PARENT_ID,
                    "HDT_Zone":sector_code,
                }
                ok=True
                for name,value in vals.items():
                    p=find_param(e,name)
                    if p is None:
                        write_failures.append({"ElementId":r["target_ElementId"],"parameter":name,"reason":"parameter not found"})
                        ok=False
                        continue
                    try:
                        if p.IsReadOnly:
                            write_failures.append({"ElementId":r["target_ElementId"],"parameter":name,"reason":"read-only"})
                            ok=False
                        else:
                            p.Set(str(value))
                    except Exception as ex:
                        write_failures.append({"ElementId":r["target_ElementId"],"parameter":name,"reason":str(ex)})
                        ok=False
                if ok:
                    written+=1
            TransactionManager.Instance.TransactionTaskDone()
            status="WRITTEN" if not write_failures else "WRITTEN WITH PARAMETER FAILURES"
        except Exception as ex:
            try:
                TransactionManager.Instance.ForceCloseTransaction()
            except:
                pass
            status="WRITE FAILED"
            errors.append("Transaction: "+str(ex))
    else:
        status="BLOCKED: "+"; ".join(block) if block else "PREVIEW ONLY"

    # --------------------------------------------------------
    # OUTPUT
    # --------------------------------------------------------
    ordered=sorted(match_records,key=lambda r:(r["V"],r["U"]))
    OUT=[
        ["MODE","V18.2 NATIVE OCCUPIED-ROW UNIVERSAL SECTOR WRITER"],
        ["Sector code",sector_code],
        ["Selected DividedSurface ElementId",eid(ds)],
        ["Selected Divided Surface Families count",len(selected_ids)],
        ["Native GridNode BLUE tile count",len(native_ids)],
        ["Excluded native WHITE tiles",len(excluded_white_native)],
        ["Excluded native OTHER tiles",len(excluded_other_native)],
        ["Selection/native agreement",{
            "common":len(common_ids),
            "only_selection":len(only_selection),
            "only_grid":len(only_grid),
            "match_ratio":round(selection_match_ratio,5)
        }],
        ["Grid settings",{
            "API_U_gridlines":nu,
            "API_V_gridlines":nv,
            "UI_U_fixed_number":getattr(ds.USpacingRule,"Number",None),
            "UI_V_fixed_number":getattr(ds.VSpacingRule,"Number",None)
        }],
        ["Axis mapping",{
            "Method_U_circumferential_from":circ_native,
            "Method_V_meridional_from":mer_native,
            "native_U_vs_Z":round(cuZ,5),
            "native_V_vs_Z":round(cvZ,5),
            "native_U_vs_angle":round(cuA,5),
            "native_V_vs_angle":round(cvA,5)
        }],
        ["Methodological grid",{
            "U_positions":u_positions,
            "V_positions":v_positions,
            "candidate_ID_total":len(ids),
            "duplicate_candidate_IDs":len(dup_ids),
            "duplicate_UV_coordinates":len(dup_coords),
            "max_U":max([r["U"] for r in rows]) if rows else None,
            "max_V":max([r["V"] for r in rows]) if rows else None
        }],
        ["V indexing note","V positions are based on occupied native GridNode rows; UI Fixed Number describes the spacing/grid rule and may differ from occupied tile rows at partial borders."],
        ["Project panel matching",{
            "project_roof_tiles_input":len(project_tiles),
            "project_panels_with_HDT_params":len(project_ready),
            "matched":len(matched),
            "duplicate_targets":len(duplicate_targets),
            "mean_distance_ft":round(mean_dist,6) if mean_dist is not None else None,
            "max_distance_ft":round(max_dist,6) if max_dist is not None else None,
            "over_limit":len(over_limit),
            "limit_ft":MAX_MATCH_DISTANCE_FT
        }],
        ["WRITE STATUS",status],
        ["Elements fully written",written],
        ["Parameter write failures",write_failures[:30]],
        ["First 40 final mappings",[
            {
                "native_ElementId":r["native_ElementId"],
                "project_ElementId":r["target_ElementId"],
                "native_U":r["native_U"],
                "native_V":r["native_V"],
                "U":r["U"],
                "V":r["V"],
                "HDT_Element_ID":r["HDT_Element_ID"],
                "match_distance_ft":round(r["match_distance_ft"],6) if r["match_distance_ft"] is not None else None
            }
            for r in ordered[:40]
        ]],
        ["BLOCK reasons",block],
        ["Errors",errors[:30]],
    ]
