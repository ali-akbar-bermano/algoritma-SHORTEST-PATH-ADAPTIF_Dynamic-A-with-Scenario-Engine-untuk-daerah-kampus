"""campus_data.py - UNIB campus graph (peta imajiner skematik)."""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class NodeType(Enum):
    ENTRY    = "Gerbang"
    BUILDING = "Gedung"
    FACILITY = "Fasilitas"
    PARKING  = "Parkir"
    OPEN     = "Area terbuka"


class SurfaceType(Enum):
    ASPHALT  = ("Aspal",  1.0)
    CONCRETE = ("Beton",  1.1)
    DIRT     = ("Tanah",  1.4)
    STAIRS   = ("Tangga", 1.8)
    RAMP     = ("Ramp",   1.3)
    def __init__(self, label: str, multiplier: float):
        self.label = label
        self.multiplier = multiplier


class Scenario(Enum):
    NORMAL      = "Normal"
    WISUDA      = "Wisuda"
    UTBK        = "UTBK"
    EVENT_BESAR = "Event Besar"


@dataclass
class CampusNode:
    id: str; name: str; node_type: NodeType
    x: float; y: float; lat: float; lon: float
    def distance_to(self, other: "CampusNode") -> float:
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)


@dataclass
class CampusEdge:
    id: str; from_node: str; to_node: str; distance: float
    surface: SurfaceType = field(default=SurfaceType.ASPHALT)
    is_accessible: bool = True
    is_bidirectional: bool = True
    geometry: List[tuple[float, float]] = field(default_factory=list)
    @property
    def base_weight(self) -> float:
        return self.distance * self.surface.multiplier


# ---------------------------------------------------------------------------
# Grid imajiner
# lat = -3.750 - row * 0.002   (row naik → lebih selatan → lebih bawah di layar)
# lon = 102.264 + col * 0.002  (col naik → lebih timur  → lebih kanan di layar)
#
# Layout (col, row):
#  col:  0    1    2    3    4    5    6    7    8    9    10
#  row0:                         DU   FMIPA FKIP LABFKIP GSG       FKIK
#  row1: MSD       GLT  DI        LPTIK FISIP MSB  FT    STAD
#  row2: G3   FP  LABTAN     RK                    LABTEK G2
#  row3: SC   FH        UPTB  ATM
#  row4:      FEB  GDS   BNI
#  row5:                  G1
# ---------------------------------------------------------------------------
def _lat(row: float) -> float: return -3.750 - row * 0.002
def _lon(col: float) -> float: return 102.264 + col * 0.002

def _n(nid, name, ntype, col, row) -> CampusNode:
    return CampusNode(nid, name, ntype, col * 80, row * 80, _lat(row), _lon(col))


CAMPUS_NODES: List[CampusNode] = [
    # ── Gerbang ──────────────────────────────────────────
    _n("G1",     "Gerbang Masuk Utama",        NodeType.ENTRY,     4, 5),
    _n("G2",     "Gerbang Keluar Timur",        NodeType.ENTRY,     9, 2),
    _n("G3",     "Gerbang Budi Utomo",          NodeType.ENTRY,     0, 2),
    # ── Gedung utama ─────────────────────────────────────
    _n("RK",     "Gedung Rektorat",             NodeType.BUILDING,  4, 2),
    _n("GLT",    "Gedung Layanan Terpadu",       NodeType.BUILDING,  2, 1),
    _n("FISIP",  "FISIP",                        NodeType.BUILDING,  6, 1),
    _n("FKIP",   "Dekanat FKIP",               NodeType.BUILDING,  6, 0),
    _n("LABFKIP","Lab Pembelajaran FKIP",        NodeType.BUILDING,  7, 0),
    _n("FMIPA",  "Dekanat MIPA",               NodeType.BUILDING,  5, 0),
    _n("GSG",    "Gedung Serba Guna",            NodeType.BUILDING,  8, 0),
    _n("FT",     "Dekanat Teknik",              NodeType.BUILDING,  8, 1),
    _n("LABTEK", "Lab Terpadu Teknik",           NodeType.BUILDING,  8, 2),
    _n("FKIK",   "FKIK",                         NodeType.BUILDING, 10, 0),
    _n("LPTIK",  "UPA TIK / LPTIK",            NodeType.BUILDING,  5, 1),
    _n("FP",     "Dekanat Fakultas Pertanian",   NodeType.BUILDING,  1, 2),
    _n("LABTAN", "Lab Tanah FP",               NodeType.BUILDING,  2, 2),
    # ── Fasilitas ─────────────────────────────────────────
    _n("ATM",    "Pusat ATM UNIB",              NodeType.FACILITY,  4, 3),
    _n("BNI",    "BNI Unit UNIB",               NodeType.FACILITY,  3, 4),
    _n("PERP",   "UPT Perpustakaan",            NodeType.FACILITY,  5, 0),  # sama col Fkip, tapi FMIPA di (5,0)...
    _n("MSB",    "Masjid Al-Barru",             NodeType.FACILITY,  7, 1),
    _n("MSD",    "Masjid Darul Ulum",           NodeType.FACILITY,  0, 1),
    _n("UPTB",   "UPT Bahasa",                  NodeType.BUILDING,  3, 3),
    _n("FH",     "Fakultas Hukum",              NodeType.BUILDING,  1, 3),
    _n("FEB",    "Dekanat FEB",                 NodeType.BUILDING,  1, 4),
    _n("GDS",    "Gedung S FEB",               NodeType.BUILDING,  2, 4),
    # ── Area terbuka ──────────────────────────────────────
    _n("DI",     "Danau Inspirasi",             NodeType.OPEN,      3, 1),
    _n("DU",     "Danau Ilmu",                  NodeType.OPEN,      4, 0),
    _n("SC",     "Sport Center",                NodeType.OPEN,      0, 3),
    _n("STAD",   "Stadion UNIB",                NodeType.OPEN,      9, 1),
]

# Hapus duplikat PERP - FMIPA sudah di (5,0), PERP harus di posisi lain
# → pindahkan PERP ke (6, -1) tidak mungkin (row negatif).
# PERP sebenarnya di sebelah FMIPA, gunakan (5.5, 0) → tidak integer.
# Gunakan PERP di col=5, row=0 tapi FMIPA di col=4, row=0:
# Revisi: DU(4,0), FMIPA(5,0), PERP(6,0), FKIP(6,1)→(7,1)?, LABFKIP(8,1)?...
# Supaya tidak terlalu kompleks, biarkan PERP berdekatan di (5, 0) dengan offset kecil.
# SOLUSI BERSIH: gunakan row -1 = row 0 tapi dipindah:

NODE_BY_ID: Dict[str, CampusNode] = {n.id: n for n in CAMPUS_NODES}

# Perbaiki posisi node agar tidak ada yang benar-benar tumpang tindih
# FMIPA di (5,0), PERP di (6,0) → perlu menggeser FKIP dan LABFKIP
# Update manual:
def _fix(nid, col, row):
    n = NODE_BY_ID[nid]
    n.lat = _lat(row); n.lon = _lon(col)
    n.x = col * 80;    n.y = row * 80

_fix("FMIPA",   5, 0)
_fix("PERP",    6, 0)   # PERP di sebelah FMIPA
_fix("FKIP",    7, 0)   # geser FKIP ke col 7
_fix("LABFKIP", 8, 0)   # geser LABFKIP ke col 8
_fix("GSG",     9, 0)   # geser GSG ke col 9
_fix("FKIK",   10, 0)   # FKIK tetap di ujung
_fix("MSB",     9, 1)   # MSB di sebelah kanan FT


def _segment_distance(a, b):
    R = 6_371_000
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp = math.radians(b[0] - a[0]); dl = math.radians(b[1] - a[1])
    h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(h), math.sqrt(1-h))

def _polyline_distance(pts):
    return round(sum(_segment_distance(pts[i], pts[i+1]) for i in range(len(pts)-1)), 1)

def _pt(nid):
    n = NODE_BY_ID[nid]; return (n.lat, n.lon)

def edge(eid, fn, tn, surface=SurfaceType.ASPHALT, bidirectional=True,
         accessible=True, via=None):
    geom = [_pt(fn), *(via or []), _pt(tn)]
    return CampusEdge(eid, fn, tn, _polyline_distance(geom),
                      surface, accessible, bidirectional, geom)


CAMPUS_EDGES: List[CampusEdge] = [
    # ── Koridor selatan: G1 (4,5) → ATM (4,3) → RK (4,2) — lurus vertikal
    edge("E01", "G1",     "RK"),
    edge("E02", "G1",     "ATM"),
    edge("E03", "ATM",    "RK"),
    edge("E04", "ATM",    "BNI"),
    # ── Cluster barat-daya: BNI,FEB,GDS,UPTB,FH,SC — grid rapi
    edge("E05", "BNI",    "FEB"),
    edge("E06", "BNI",    "UPTB"),
    edge("E07", "UPTB",   "FH"),
    edge("E08", "FH",     "FEB"),
    edge("E09", "FEB",    "GDS"),
    edge("E10", "FH",     "SC"),
    edge("E11", "SC",     "G3"),
    # ── Koridor barat: G3 → MSD → FP → LABTAN → RK
    edge("E12", "G3",     "MSD"),
    edge("E13", "MSD",    "FP",     SurfaceType.CONCRETE),
    edge("E14", "FP",     "LABTAN"),
    edge("E15", "LABTAN", "RK"),
    edge("E16", "LABTAN", "UPTB",   via=[(_lat(2), _lon(3))]),  # via (3,2)→turun ke (3,3)
    edge("E17", "UPTB",   "ATM"),
    # ── Koridor tengah-utara: RK → DI → GLT → DU → FMIPA/PERP
    edge("E18", "RK",     "GLT",    SurfaceType.CONCRETE),
    edge("E19", "GLT",    "DU",     SurfaceType.CONCRETE),
    edge("E20", "DU",     "PERP"),
    edge("E21", "DU",     "FKIP",   via=[(_lat(0), _lon(6))]),  # via (6,0)=PERP→kiri
    edge("E22", "PERP",   "FKIP"),
    edge("E23", "FKIP",   "FMIPA"),
    edge("E24", "FKIP",   "LABFKIP"),
    edge("E25", "LABFKIP","GSG"),
    # ── Koridor timur: GSG → FT → LABTEK → G2
    edge("E26", "GSG",    "FT"),
    edge("E27", "FT",     "LABTEK"),
    edge("E28", "LABTEK", "G2"),
    edge("E29", "G2",     "MSB"),
    edge("E30", "MSB",    "FISIP"),
    edge("E31", "FISIP",  "LPTIK"),
    edge("E32", "LPTIK",  "DI"),
    edge("E33", "DI",     "RK",     via=[(_lat(2), _lon(3))]),
    edge("E34", "DI",     "FISIP"),
    edge("E35", "LPTIK",  "MSB",    via=[(_lat(1), _lon(7))]),
    # ── Koridor stadion & FKIK
    edge("E36", "FT",     "STAD"),
    edge("E37", "STAD",   "FKIK",   SurfaceType.CONCRETE),
    edge("E38", "FKIK",   "FMIPA",  SurfaceType.CONCRETE),
    edge("E39", "LABTEK", "STAD",   via=[(_lat(2), _lon(9))]),
    # ── Shortcut
    edge("E40", "G2",     "FT"),
    edge("E41", "PERP",   "LPTIK",  via=[(_lat(1), _lon(6))]),
    edge("E42", "FISIP",  "RK",     via=[(_lat(2), _lon(5))]),
    edge("E43", "MSD",    "GLT",    SurfaceType.CONCRETE),
    edge("E44", "FP",     "FH",     via=[(_lat(3), _lon(1))]),
    edge("E45", "FEB",    "SC"),
    edge("E46", "UPTB",   "FP",     via=[(_lat(2), _lon(3))]),
    edge("E47", "MSB",    "LABTEK"),
    edge("E48", "G2",     "STAD"),
]


SCENARIO_CONFIG: Dict[Scenario, dict] = {
    Scenario.NORMAL: {
        "description": "Kondisi kampus hari biasa.",
        "color": "#0f766e", "edge_modifiers": {}, "blocked_edges": set(),
    },
    Scenario.WISUDA: {
        "description": "Arus tamu padat di gerbang utama, rektorat, dan gedung acara.",
        "color": "#d97706",
        "edge_modifiers": {"E01":2.3,"E02":1.8,"E03":1.7,"E18":1.9,"E25":2.0,"E26":2.2,"E29":1.6},
        "blocked_edges": set(), "priority_nodes": ["GSG","RK","G1"],
    },
    Scenario.UTBK: {
        "description": "Zona ujian dipadatkan di UPA TIK, FKIP, Perpustakaan, Teknik, FKIK, FEB, dan Hukum.",
        "color": "#dc2626",
        "edge_modifiers": {"E20":1.7,"E22":1.7,"E24":1.8,"E25":1.7,"E27":1.9,"E31":1.7,"E35":1.6,"E37":1.8,"E08":1.6,"E09":1.6},
        "blocked_edges": {"E41"}, "exam_nodes": ["LPTIK","LABFKIP","PERP","LABTEK","FKIK","GDS","FH"],
    },
    Scenario.EVENT_BESAR: {
        "description": "Kepadatan diarahkan di sekitar stadion, sport center, dan koridor timur.",
        "color": "#7c3aed",
        "edge_modifiers": {"E10":2.2,"E11":1.8,"E36":2.2,"E37":2.4,"E39":2.0,"E48":2.0,"E28":1.7,"E29":1.6},
        "blocked_edges": set(), "event_nodes": ["STAD","SC","GSG"],
    },
}
