import json, re

def surface_enum(val):
    v = val.upper()
    if "CON" in v: return "SurfaceType.CONCRETE"
    if "DIRT" in v: return "SurfaceType.DIRT"
    if "STA" in v: return "SurfaceType.STAIRS"
    if "RAMP" in v: return "SurfaceType.RAMP"
    return "SurfaceType.ASPHALT"

def type_enum(val):
    if "Gerbang" in val: return "NodeType.ENTRY"
    if "Gedung" in val or "Dekanat" in val or "Fakultas" in val or "Lab" in val: return "NodeType.BUILDING"
    if "Fasilitas" in val or "Masjid" in val or "Perpustakaan" in val or "ATM" in val or "BNI" in val: return "NodeType.FACILITY"
    if "Parkir" in val: return "NodeType.PARKING"
    return "NodeType.OPEN"

with open("data/custom_graph.json", "r") as f:
    custom = json.load(f)

with open("campus_data.py", "r", encoding="utf-8") as f:
    content = f.read()

# --- 1. Update base node coordinates if overridden in custom_graph ---
base_node_overrides = {n["id"]: n for n in custom.get("nodes", []) if not n["id"].startswith("C")}
for nid, n in base_node_overrides.items():
    lat, lon = round(n["lat"], 5), round(n["lon"], 5)
    # Match CampusNode("ID", ..., lat, lon) and update coordinates
    pattern = rf'(CampusNode\("{re.escape(nid)}"[^,]+,\s*[^,]+,\s*NodeType\.\w+,\s*)-?\d+\.\d+,\s*-?\d+\.\d+'
    replacement = rf'\g<1>{lat}, {lon}'
    new_content = re.sub(pattern, replacement, content)
    if new_content != content:
        print(f"  Updated location: {nid} -> ({lat}, {lon})")
        content = new_content
    else:
        print(f"  WARN: could not find pattern for node {nid}")

# --- 2. Update edges that reference overridden base nodes (fix geometry endpoints) ---
# These edges are stored in custom as updated versions - we need to update campus_data.py edges too
base_edge_overrides = {e["id"]: e for e in custom.get("edges", []) if not e["id"].startswith("C")}
for eid, e in base_edge_overrides.items():
    # These override base edges - update geometry start/end in campus_data.py
    geom = e["geometry"]
    # Replace the edge definition in campus_data.py with updated geometry
    if len(geom) > 2:
        via_list = ", ".join(f"({round(p[0],5)}, {round(p[1],5)})" for p in geom[1:-1])
        via_str = f", via=[{via_list}]"
    else:
        via_str = ""
    sur = surface_enum(e["surface"])
    bidi = str(e["bidirectional"])
    new_edge_line = f'    edge("{eid}", "{e["from"]}", "{e["to"]}", surface={sur}, bidirectional={bidi}{via_str}),'
    # Find and replace existing edge line
    pattern = rf'    edge\("{re.escape(eid)}".*?\),'
    new_content = re.sub(pattern, new_edge_line, content, flags=re.DOTALL)
    if new_content != content:
        print(f"  Updated edge: {eid}")
        content = new_content
    else:
        print(f"  WARN: could not find edge {eid} to update")

# --- 3. Append new custom nodes (C-prefix) to CAMPUS_NODES ---
existing_node_ids = set(re.findall(r'CampusNode\("(\w+)"', content))
new_nodes_str = ""
for n in custom.get("nodes", []):
    if n["id"].startswith("C") and n["id"] not in existing_node_ids:
        nt = type_enum(n.get("type", ""))
        lat, lon = round(n["lat"], 5), round(n["lon"], 5)
        new_nodes_str += f'    CampusNode("{n["id"]}", "{n["name"]}", {nt}, {lat}, {lon}),\n'
        print(f"  Adding node: {n['id']} - {n['name']}")

if new_nodes_str:
    content = content.replace("]\n\nNODE_BY_ID", new_nodes_str + "]\n\nNODE_BY_ID")

# --- 4. Append new custom edges (CE-prefix) to CAMPUS_EDGES ---
existing_edge_ids = set(re.findall(r'edge\("(\w+)"', content))
new_edges_str = ""
remaining_edges = []
for e in custom.get("edges", []):
    if e["id"].startswith("CE") and e["id"] not in existing_edge_ids:
        geom = e["geometry"]
        via_str = ""
        if len(geom) > 2:
            via_list = ", ".join(f"({round(p[0],5)}, {round(p[1],5)})" for p in geom[1:-1])
            via_str = f", via=[{via_list}]"
        sur = surface_enum(e["surface"])
        bidi = str(e["bidirectional"])
        new_edges_str += f'    edge("{e["id"]}", "{e["from"]}", "{e["to"]}", surface={sur}, bidirectional={bidi}{via_str}),\n'
        print(f"  Adding edge: {e['id']} ({e['from']} -> {e['to']})")
    else:
        remaining_edges.append(e)

if new_edges_str:
    content = content.replace("]\n\nSCENARIO_CONFIG", new_edges_str + "]\n\nSCENARIO_CONFIG")

with open("campus_data.py", "w", encoding="utf-8") as f:
    f.write(content)

# --- 5. Clean custom_graph (remove migrated data, keep only non-CE/C) ---
custom["nodes"] = [n for n in custom.get("nodes", []) if not n["id"].startswith("C") and n["id"] not in base_node_overrides]
custom["edges"] = remaining_edges
custom["deleted_edges"] = []
with open("data/custom_graph.json", "w") as f:
    json.dump(custom, f, indent=2)

print("\nDONE. Verifying...")
import campus_data as cd_check
print(f"campus_data: {len(cd_check.CAMPUS_NODES)} nodes, {len(cd_check.CAMPUS_EDGES)} edges")
