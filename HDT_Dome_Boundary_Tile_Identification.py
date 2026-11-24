import clr
import math
from collections import Counter

clr.AddReference("RevitAPI")
import Autodesk.Revit.DB as DB

clr.AddReference("RevitServices")
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

doc = DocumentManager.Instance.CurrentDBDocument

# ============================================================
# WHITE BOUNDARY SETTINGS
# ============================================================
DOME_CODE = "D01"
PARENT_ID = "DOME_01"
BOUNDARY_CODE = "B01"
WRITE_TO_REVIT = True
MAX_MATCH_DISTANCE_FT = 0.30

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

def normalize_sector_code(x):
    s=str(x).strip().upper() if x is not None else ""
    if s.startswith('S'):
        try:
            return 'S{:02d}'.format(int(s[1:]))
        except:
            return s
    try:
        return 'S{:02d}'.format(int(s))
    except:
        return s or 'S01'

def family_type_text(e):
    vals=[]
    try: vals.append(e.Name)
    except: pass
    try:
        sym=e.Symbol
        if sym:
            try: vals.append(sym.Name)
            except: pass
            try: vals.append(sym.Family.Name)
            except: pass
    except: pass
    return ' '.join([str(v) for v in vals if v is not None])

def is_white(e):
    t=family_type_text(e).lower()
    return ('curved roof tile' in t and 'white' in t)

def set_text_param(e,name,value):
    try:
        p=e.LookupParameter(name)
    except:
        p=None
    if p is None:
        return False, 'parameter not found'
    try:
        if p.IsReadOnly:
            return False, 'read only'
    except:
        pass
    try:
        p.Set(str(value))
        return True, None
    except Exception as ex:
        return False, str(ex)

# ============================================================
# INPUTS
# IN[0] = project Curved Roof Tile_White curtain panels
# IN[1] = optional selected white DividedSurface (NOT REQUIRED)
# IN[2] = Select Divided Surface Families output for same strip
# IN[3] = sector code S01 ... S07
# ============================================================
project_tiles=[unwrap(x) for x in flatten(IN[0])]
selected_native_all=[unwrap(x) for x in flatten(IN[2])] if len(IN)>2 else []
sector_code=normalize_sector_code(IN[3] if len(IN)>3 else None)

# Keep only usable WHITE elements with positions.
project_white=[]
for e in project_tiles:
    if e is not None and is_white(e) and point_of(e) is not None:
        project_white.append(e)

native_white=[]
for e in selected_native_all:
    if e is not None and is_white(e) and point_of(e) is not None:
        native_white.append(e)

# Remove duplicate selected native IDs while preserving order.
seen=set(); native_unique=[]
for e in native_white:
    k=eid(e)
    if k not in seen:
        seen.add(k); native_unique.append(e)
native_white=native_unique

stop_reasons=[]
if len(native_white)==0:
    stop_reasons.append('No WHITE families received from Select Divided Surface Families')
if len(project_white)==0:
    stop_reasons.append('No project Curved Roof Tile_White panels available for matching')

# ============================================================
# ONE-DIMENSIONAL BOUNDARY ORDER
# U01 = closest to dome apex (highest Z)
# U increases toward eave (lower Z). Radius is tie-breaker.
# ============================================================
ordered=sorted(native_white, key=lambda e: (-point_of(e).Z,
                                           math.hypot(point_of(e).X, point_of(e).Y),
                                           eid(e) or 0))

# Match each native white tile to nearest project white panel.
project_pts=[(e,point_of(e)) for e in project_white]
used_targets=set(); mappings=[]; match_failures=[]
for idx,ne in enumerate(ordered, start=1):
    p=point_of(ne)
    best=None; bestd2=None
    for pe,pp in project_pts:
        pid=eid(pe)
        if pid in used_targets:
            continue
        d2=dist2(p,pp)
        if bestd2 is None or d2<bestd2:
            best=(pe,pp); bestd2=d2
    if best is None:
        match_failures.append({'native_ElementId':eid(ne),'reason':'no unmatched project panel'})
        continue
    dist=math.sqrt(bestd2)
    pe=best[0]
    if dist>MAX_MATCH_DISTANCE_FT:
        match_failures.append({'native_ElementId':eid(ne),'nearest_project_ElementId':eid(pe),'distance_ft':dist,'reason':'distance exceeds limit'})
        continue
    used_targets.add(eid(pe))
    cid='{}_{}_U{:02d}_{}'.format(DOME_CODE,sector_code,idx,BOUNDARY_CODE)
    mappings.append({
        'U':idx,
        'HDT_Element_ID':cid,
        'native_ElementId':eid(ne),
        'project_ElementId':eid(pe),
        'match_distance_ft':round(dist,6),
        'Z_ft':round(p.Z,6),
        'radius_ft':round(math.hypot(p.X,p.Y),6),
        '_project':pe
    })

candidate_ids=[m['HDT_Element_ID'] for m in mappings]
dup_ids=[k for k,v in Counter(candidate_ids).items() if v>1]
dup_targets=[k for k,v in Counter([m['project_ElementId'] for m in mappings]).items() if v>1]

blocked=[]
if stop_reasons: blocked.extend(stop_reasons)
if match_failures: blocked.append('some selected white tiles could not be safely matched')
if dup_ids: blocked.append('duplicate candidate IDs')
if dup_targets: blocked.append('duplicate project-panel targets')

write_failures=[]; written=0
if WRITE_TO_REVIT and not blocked:
    TransactionManager.Instance.EnsureInTransaction(doc)
    try:
        for m in mappings:
            e=m['_project']
            results=[]
            for pn,pv in [('HDT_Element_ID',m['HDT_Element_ID']),
                          ('HDT_Parent_ID',PARENT_ID),
                          ('HDT_Zone',sector_code)]:
                ok,reason=set_text_param(e,pn,pv)
                results.append(ok)
                if not ok:
                    write_failures.append({'ElementId':eid(e),'parameter':pn,'reason':reason})
            if all(results):
                written+=1
    finally:
        TransactionManager.Instance.TransactionTaskDone()

status='WRITTEN' if WRITE_TO_REVIT and not blocked and not write_failures else ('BLOCKED: '+'; '.join(blocked) if blocked else 'WRITTEN WITH PARAMETER FAILURES')

# Strip private object before output.
out_maps=[]
for m in mappings[:50]:
    out_maps.append({k:v for k,v in m.items() if not k.startswith('_')})

OUT=[
    ['MODE','V19.2 WHITE BOUNDARY - NO DIVIDEDSURFACE OBJECT REQUIRED'],
    ['Sector code',sector_code],
    ['Selected white families',len(selected_native_all)],
    ['Selected usable WHITE tiles',len(native_white)],
    ['Project WHITE panels available',len(project_white)],
    ['Boundary indexing',{
        'U_positions':len(mappings),
        'direction':'U01 = highest Z (dome apex) -> increasing toward eave',
        'boundary_code':BOUNDARY_CODE,
        'candidate_ID_total':len(candidate_ids),
        'duplicate_candidate_IDs':len(dup_ids),
        'duplicate_project_targets':len(dup_targets)
    }],
    ['Matching',{
        'max_distance_ft':max([m['match_distance_ft'] for m in mappings], default=None),
        'mean_distance_ft':round(sum([m['match_distance_ft'] for m in mappings])/len(mappings),6) if mappings else None,
        'match_failures':len(match_failures)
    }],
    ['WRITE STATUS',status],
    ['Elements fully written',written],
    ['Parameter write failures',write_failures],
    ['Match failures',match_failures],
    ['First 50 boundary mappings',out_maps]
]
