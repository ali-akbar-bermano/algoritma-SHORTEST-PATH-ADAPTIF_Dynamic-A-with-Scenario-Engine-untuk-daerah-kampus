import json
import time
import urllib.request
from typing import List, Tuple

from campus_data import CAMPUS_EDGES, NODE_BY_ID

def get_osrm_geometry(start: Tuple[float, float], end: Tuple[float, float]) -> List[Tuple[float, float]]:
    # OSRM format: lon,lat
    url = f"https://router.project-osrm.org/route/v1/foot/{start[1]},{start[0]};{end[1]},{end[0]}?overview=full&geometries=geojson"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'UNIB-Navigator-Bot'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            if data['code'] == 'Ok':
                # Convert geojson [lon, lat] back to [lat, lon]
                coords = data['routes'][0]['geometry']['coordinates']
                return [(c[1], c[0]) for c in coords]
    except Exception as e:
        print(f"Error fetching OSRM: {e}")
    
    # Fallback to straight line if API fails
    return [start, end]

def main():
    print("Mengekstrak geometri asli dari OSRM...")
    updated_edges = []
    
    for i, edge in enumerate(CAMPUS_EDGES):
        n1 = NODE_BY_ID[edge.from_node]
        n2 = NODE_BY_ID[edge.to_node]
        
        start = (n1.lat, n1.lon)
        end = (n2.lat, n2.lon)
        
        print(f"[{i+1}/{len(CAMPUS_EDGES)}] Fetching {edge.id}: {edge.from_node} -> {edge.to_node}...")
        geom = get_osrm_geometry(start, end)
        
        # Round coordinates slightly to keep file size reasonable
        geom_rounded = [(round(p[0], 5), round(p[1], 5)) for p in geom]
        
        edge_str = f'    edge("{edge.id}", "{edge.from_node}", "{edge.to_node}", via={geom_rounded}),'
        updated_edges.append(edge_str)
        
        time.sleep(0.2) # Polite delay for public API
        
    # Generate new python file content
    with open('campus_edges_dump.txt', 'w') as f:
        f.write("\n".join(updated_edges))
        
    print("Geometri OSRM berhasil diekstrak dan disimpan ke campus_edges_dump.txt")

if __name__ == "__main__":
    main()
