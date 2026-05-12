"""
web_server.py – Versi Stabil Tanpa API Eksternal.
Menggunakan algorithm.py dan campus_data.py lokal untuk menjamin kecepatan dan fitur.
"""
import json
import os
import sys

from flask import Flask, jsonify, render_template, request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from algorithm import build_engine
from campus_data import CAMPUS_EDGES, CAMPUS_NODES, SCENARIO_CONFIG, Scenario

app = Flask(__name__, template_folder="templates")
CUSTOM_GRAPH_FILE = os.path.join(BASE_DIR, "data", "custom_graph.json")
CONDITIONS_FILE = os.path.join(BASE_DIR, "data", "conditions.json")

def _load_custom_graph():
    try:
        if os.path.exists(CUSTOM_GRAPH_FILE):
            with open(CUSTOM_GRAPH_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                data.setdefault("nodes", [])
                data.setdefault("edges", [])
                data.setdefault("deleted_edges", [])
                return data
    except: pass
    return {"nodes": [], "edges": [], "deleted_edges": []}

def _save_custom_graph(data):
    os.makedirs(os.path.dirname(CUSTOM_GRAPH_FILE), exist_ok=True)
    with open(CUSTOM_GRAPH_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def _build_combined_engine():
    custom = _load_custom_graph()
    
    # We will temporarily modify CAMPUS_NODES and CAMPUS_EDGES just for the engine build,
    # or build engine with custom data. Since algorithm.py expects dicts in engine...
    # actually build_engine() creates the engine from campus_data.
    # It's better to manually inject into the engine after building.
    engine = build_engine()
    
    for n in custom.get("nodes", []):
        engine.nodes[n["id"]] = n
    
    deleted_edges = set(custom.get("deleted_edges", []))
    engine._edges = [e for e in engine.edges if e["id"] not in deleted_edges]
    
    for e in custom.get("edges", []):
        if e["id"] not in deleted_edges:
            engine._edges.append(e)
        
    return engine

# Build engine saat startup
engine = _build_combined_engine()

def _load_conditions():
    try:
        if os.path.exists(CONDITIONS_FILE):
            with open(CONDITIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except: pass
    return {"edge_conditions": {}, "edge_directions": {}}

def _save_conditions(data):
    os.makedirs(os.path.dirname(CONDITIONS_FILE), exist_ok=True)
    with open(CONDITIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/graph")
def api_graph():
    nodes = [{"id": n.id, "name": n.name, "type": n.node_type.value, "lat": n.lat, "lon": n.lon} for n in CAMPUS_NODES]
    edges = [{"id": e.id, "from": e.from_node, "to": e.to_node, "distance": e.distance, "surface": e.surface.name, "geometry": e.geometry} for e in CAMPUS_EDGES]
    
    custom = _load_custom_graph()
    deleted_edges = set(custom.get("deleted_edges", []))
    
    edges = [e for e in edges if e["id"] not in deleted_edges]
    
    nodes.extend(custom.get("nodes", []))
    custom_edges = [e for e in custom.get("edges", []) if e["id"] not in deleted_edges]
    edges.extend(custom_edges)
    
    scenarios = [{"id": sc.value, "description": cfg.get("description", ""), "color": cfg.get("color", "#14b8a6")} for sc, cfg in SCENARIO_CONFIG.items()]
    return jsonify({"nodes": nodes, "edges": edges, "scenarios": scenarios})

@app.route("/api/route", methods=["POST"])
def api_route():
    body = request.get_json(force=True)
    start_id = body.get("start")
    end_id = body.get("end")
    scenario_name = body.get("scenario", "Normal")
    time_fac = float(body.get("time_factor", 1.0))

    # Update conditions di engine sebelum hitung
    conds = _load_conditions()
    engine.set_conditions(conds)

    # Cari scenario enum
    sc_enum = Scenario.NORMAL
    for s in Scenario:
        if s.value == scenario_name:
            sc_enum = s
            break

    result = engine.find_path(start_id, end_id, sc_enum, time_fac)
    
    # Tambahkan geometry untuk visualisasi
    if "path" in result:
        edge_map = {e.id: e for e in CAMPUS_EDGES}
        custom = _load_custom_graph()
        for e in custom.get("edges", []):
            # simulate CampusEdge structure for geometry
            edge_map[e["id"]] = type('obj', (object,), {'geometry': e.get("geometry", [])})
            
        result["edges_geometry"] = [{"id": eid, "geometry": edge_map[eid].geometry} for eid in result.get("edges_used", []) if eid in edge_map]

    return jsonify(result)

@app.route("/api/conditions", methods=["GET", "POST"])
def api_conditions():
    if request.method == "POST":
        body = request.get_json(force=True)
        # Handle individual edge update or full reset
        if "edge_id" in body:
            conds = _load_conditions()
            eid = body["edge_id"]
            status = body.get("status", "NORMAL").upper()
            if status == "NORMAL":
                conds["edge_conditions"].pop(eid, None)
            else:
                conds["edge_conditions"][eid] = {"status": status, "severity": body.get("severity", 1.0)}
            _save_conditions(conds)
            return jsonify({"ok": True, "conditions": conds})
        else:
            _save_conditions(body)
            return jsonify({"ok": True})
    return jsonify(_load_conditions())

@app.route("/api/conditions/reset", methods=["POST"])
def api_reset():
    data = {"edge_conditions": {}, "edge_directions": {}}
    _save_conditions(data)
    return jsonify({"ok": True})

@app.route("/api/nodes", methods=["POST"])
def api_nodes():
    body = request.get_json(force=True)
    custom = _load_custom_graph()
    
    new_node = {
        "id": f"C{len(custom.get('nodes', [])) + 1}",
        "name": body.get("name", "Gedung Kustom"),
        "type": body.get("type", "Gedung"),
        "lat": float(body.get("lat")),
        "lon": float(body.get("lon"))
    }
    custom.setdefault("nodes", []).append(new_node)
    _save_custom_graph(custom)
    
    global engine
    engine = _build_combined_engine()
    return jsonify({"ok": True, "node": new_node})

@app.route("/api/edges", methods=["POST"])
def api_edges():
    import math
    import json
    import urllib.request
    
    body = request.get_json(force=True)
    custom = _load_custom_graph()
    
    # get coordinates from engine to calculate distance
    global engine
    try:
        n1 = engine.nodes[body["from"]]
        n2 = engine.nodes[body["to"]]
        
        start = (n1["lat"], n1["lon"])
        end = (n2["lat"], n2["lon"])
        
        # OSRM geometry logic
        url = f"https://router.project-osrm.org/route/v1/foot/{start[1]},{start[0]};{end[1]},{end[0]}?overview=full&geometries=geojson"
        geom = [[start[0], start[1]], [end[0], end[1]]]
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'UNIB-Navigator-Bot'})
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                if data['code'] == 'Ok':
                    coords = data['routes'][0]['geometry']['coordinates']
                    # Ensure the line connects precisely from the building to the OSRM snapped start point, 
                    # and from the OSRM snapped end point to the destination building.
                    geom = [[start[0], start[1]]] + [[round(c[1], 5), round(c[0], 5)] for c in coords] + [[end[0], end[1]]]
        except Exception as e:
            print(f"Error fetching OSRM: {e}")
            
        # Calculate path distance
        from algorithm import haversine
        distance = 0.0
        for i in range(len(geom)-1):
            distance += haversine(geom[i][0], geom[i][1], geom[i+1][0], geom[i+1][1])
        distance = round(distance, 1)
        
    except KeyError:
        return jsonify({"error": "Node not found"}), 400

    new_edge = {
        "id": f"CE{len(custom.get('edges', [])) + 1}",
        "from": body["from"],
        "to": body["to"],
        "distance": distance,
        "surface": "ASPHALT",
        "bidirectional": True,
        "geometry": geom
    }
    
    custom.setdefault("edges", []).append(new_edge)
    _save_custom_graph(custom)
    
    engine = _build_combined_engine()
    return jsonify({"ok": True, "edge": new_edge})

@app.route("/api/edges/<edge_id>", methods=["DELETE"])
def api_delete_edge(edge_id):
    custom = _load_custom_graph()
    custom.setdefault("deleted_edges", []).append(edge_id)
    _save_custom_graph(custom)
    
    global engine
    engine = _build_combined_engine()
    return jsonify({"ok": True})

if __name__ == "__main__":
    print("SERVER READY: Menggunakan Algoritma A* Lokal (UNIB)")
    app.run(debug=True, port=5000)
