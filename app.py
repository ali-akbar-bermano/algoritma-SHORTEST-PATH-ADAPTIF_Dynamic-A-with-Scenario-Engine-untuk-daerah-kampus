"""
app.py - UI navigasi kampus UNIB.

Run:
    python app.py
"""

from __future__ import annotations

import json
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

import customtkinter as ctk

from algorithm import build_engine
from campus_data import CAMPUS_EDGES, CAMPUS_NODES, NodeType, Scenario, SCENARIO_CONFIG


APP_DIR = Path(__file__).resolve().parent
CONDITION_FILE = APP_DIR / "data" / "conditions.json"

# ── Warna utama ──────────────────────────────────────────────────────────────
BG          = "#0d1f1c"   # latar utama (dark teal)
SIDEBAR     = "#122b27"   # sidebar panel
SIDEBAR2    = "#1a3a35"   # sidebar tab/card
CARD        = "#1e4a44"   # card di sidebar
CARD_LIGHT  = "#ffffff"   # card di map area
CARD_SOFT   = "#e8f3f0"
TEXT        = "#e8f5f2"   # teks utama (terang di atas dark)
TEXT_DARK   = "#10201d"   # teks gelap (di atas area terang)
MUTED       = "#7fb8b0"   # teks sekunder
BORDER      = "#2a5a54"
PRIMARY     = "#14b8a6"   # teal cerah
PRIMARY_DARK= "#0f9488"
BLUE        = "#60a5fa"
AMBER       = "#fbbf24"
YELLOW      = "#facc15"
RED         = "#f87171"
RED_DARK    = "#dc2626"
PURPLE      = "#a78bfa"
GREEN       = "#4ade80"
ROAD        = "#94a3b8"   # warna default jalan
MAP_BG      = "#f0f7f5"   # latar peta (tetap terang)

STATUS_LABELS = {
    "NORMAL":  "Normal",
    "BUSY":    "Sibuk",
    "POTHOLE": "Berlubang",
    "CLOSED":  "Ditutup",
}
STATUS_BY_LABEL = {label: key for key, label in STATUS_LABELS.items()}
STATUS_COLORS = {
    "NORMAL":  "#64748b",
    "BUSY":    "#f59e0b",
    "POTHOLE": "#eab308",
    "CLOSED":  "#ef4444",
}
STATUS_EMOJI = {
    "NORMAL":  "✅",
    "BUSY":    "🚦",
    "POTHOLE": "⚠️",
    "CLOSED":  "🚫",
}
STATUS_DEFAULT_SEVERITY = {
    "NORMAL":  1.0,
    "BUSY":    2.0,
    "POTHOLE": 1.6,
    "CLOSED":  3.0,
}
NODE_RADIUS = {
    NodeType.ENTRY:    10,
    NodeType.BUILDING:  7,
    NodeType.FACILITY:  7,
    NodeType.PARKING:   6,
    NodeType.OPEN:      6,
}
NODE_COLORS = {
    NodeType.ENTRY:    "#fb923c",
    NodeType.BUILDING: "#60a5fa",
    NodeType.FACILITY: "#34d399",
    NodeType.PARKING:  "#94a3b8",
    NodeType.OPEN:     "#4ade80",
}


class App(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        super().__init__()
        # BUGFIX [KRITIS]: Sembunyikan window sampai sepenuhnya diposisikan.
        # Pola benar: withdraw() → build → deiconify(), bukan langsung tampil
        # lalu loncat saat _center_window() dipanggil.
        self.withdraw()

        self.title("Navigasi Kampus UNIB - Dynamic A*")
        self.minsize(1180, 720)
        self.configure(fg_color=BG)

        self.engine = build_engine()
        self.nodes = CAMPUS_NODES
        self.edges = CAMPUS_EDGES
        self.node_by_id = {node.id: node for node in self.nodes}
        self.edge_by_id = {edge.id: edge for edge in self.edges}

        self.conditions = self._load_conditions()
        self.engine.set_conditions(self.conditions)

        self.node_labels = [self._node_label(node) for node in self.nodes]
        self.start_v = ctk.StringVar(value=self._node_label(self.node_by_id["G1"]))
        self.goal_v = ctk.StringVar(value=self._node_label(self.node_by_id["GSG"]))
        self.event_v = ctk.StringVar(value=self._node_label(self.node_by_id["GSG"]))
        self.scenario_v = ctk.StringVar(value=Scenario.NORMAL.value)
        self.event_scenario_v = ctk.StringVar(value=Scenario.EVENT_BESAR.value)
        self.time_factor_v = ctk.DoubleVar(value=1.0)

        self.edge_v = ctk.StringVar(value=self._edge_label(self.edges[0]))
        self.status_v = ctk.StringVar(value=STATUS_LABELS["NORMAL"])
        self.severity_v = ctk.DoubleVar(value=1.0)
        self.direction_v = ctk.StringVar(value="Dua arah")

        self.pick_target = "start"
        self.selected_edge_id = self.edges[0].id
        self.current_result: dict | None = None
        self.edge_paths = []
        self.route_paths = []
        self.markers = []
        self.direction_choices: list[str] = []
        self.syncing_table = False
        self.geo_bounds = self._compute_geo_bounds()
        self._map_refresh_job: str | None = None
        # State untuk fitur edit interaktif di peta
        self.edit_mode: bool = False
        self._popup_win: tk.Toplevel | None = None
        self._hovered_edge_id: str | None = None

        self._build_ui()
        self._style_treeview()
        self._select_edge(self.selected_edge_id, focus_map=False, refresh_map=False)

        # Posisikan window di tengah layar setelah UI selesai dibangun
        self._center_window(1450, 850)

        # Proses pending geometry/layout events tanpa menjalankan full event loop
        self.update_idletasks()

        # Tampilkan window setelah posisi sudah benar (tidak ada efek "lompat")
        self.deiconify()
        self.update_idletasks()

        # Gambar peta setelah window benar-benar terlihat
        self.after(150, self._draw_map)
        # Paksa window muncul di depan setelah render pertama selesai
        self.after(200, self._bring_to_front)

    def _center_window(self, w: int, h: int):
        """Posisikan window di tengah layar secara eksplisit."""
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        # Pastikan window tidak lebih besar dari layar
        w = min(w, screen_w - 20)
        h = min(h, screen_h - 60)
        x = max(0, (screen_w - w) // 2)
        y = max(0, (screen_h - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _bring_to_front(self):
        """Paksa window muncul di depan layar saat pertama kali dibuka.

        Trik standar Windows: set -topmost True sebentar untuk melompati
        Windows Focus Stealing Prevention, lalu unset setelah 500ms agar
        user tetap bisa menaikkan window lain di atasnya.
        """
        self.state("normal")        # pastikan tidak ter-minimize
        self.attributes("-topmost", True)   # paksa ke depan
        self.lift()
        self.focus_force()
        # Lepas topmost setelah window sudah terlihat
        self.after(500, lambda: self.attributes("-topmost", False))

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header bar ── dark teal
        header = ctk.CTkFrame(self, fg_color=SIDEBAR, corner_radius=0, height=72)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        header.grid_propagate(False)
        ctk.CTkLabel(
            header,
            text="🗺️  Navigasi Kampus UNIB",
            text_color=PRIMARY,
            font=ctk.CTkFont("Segoe UI", 22, "bold"),
        ).grid(row=0, column=0, padx=22, pady=(14, 0), sticky="w")
        ctk.CTkLabel(
            header,
            text="Sistem Rute Dinamis A*  •  Klik jalan di peta untuk mengatur kondisi",
            text_color=MUTED,
            font=("Segoe UI", 12),
        ).grid(row=1, column=0, padx=22, pady=(0, 12), sticky="w")
        # Badge jam
        self.clock_label = ctk.CTkLabel(
            header,
            text="",
            text_color=MUTED,
            font=("Segoe UI", 11),
        )
        self.clock_label.grid(row=0, column=2, padx=18, pady=14, sticky="e")
        self._tick_clock()

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, padx=14, pady=14, sticky="nsew")
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._build_control_tabs(body)
        self._build_map(body)

    def _build_control_tabs(self, parent):
        panel = ctk.CTkFrame(parent, fg_color=SIDEBAR, corner_radius=18, width=440)
        panel.grid(row=0, column=0, sticky="nsw", padx=(0, 12))
        panel.grid_propagate(False)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(0, weight=1)

        self.tabs = ctk.CTkTabview(
            panel,
            fg_color=SIDEBAR2,
            segmented_button_fg_color=SIDEBAR,
            segmented_button_selected_color=PRIMARY,
            segmented_button_selected_hover_color=PRIMARY_DARK,
            segmented_button_unselected_color=SIDEBAR,
            segmented_button_unselected_hover_color=SIDEBAR2,
            corner_radius=16,
        )
        try:
            self.tabs.configure(text_color=TEXT)
        except Exception:
            pass
        self.tabs.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.route_tab = self.tabs.add("🗺 Rute")
        self.road_tab  = self.tabs.add("🛣 Jalan")
        self.event_tab = self.tabs.add("🎉 Acara")
        for tab in (self.route_tab, self.road_tab, self.event_tab):
            tab.grid_columnconfigure(0, weight=1)

        self._build_route_tab()
        self._build_road_tab()
        self._build_event_tab()

    def _build_route_tab(self):
        self._title(self.route_tab, "Cari Rute Tercepat", 0)
        self._label(self.route_tab, "Titik awal", 1)
        ctk.CTkOptionMenu(self.route_tab, variable=self.start_v, values=self.node_labels).grid(
            row=2, column=0, sticky="ew", padx=12, pady=(0, 10)
        )
        self._label(self.route_tab, "Tujuan", 3)
        ctk.CTkOptionMenu(self.route_tab, variable=self.goal_v, values=self.node_labels).grid(
            row=4, column=0, sticky="ew", padx=12, pady=(0, 12)
        )

        pick_frame = ctk.CTkFrame(self.route_tab, fg_color="transparent")
        pick_frame.grid(row=5, column=0, sticky="ew", padx=12, pady=(0, 14))
        pick_frame.grid_columnconfigure((0, 1), weight=1)
        self.pick_start_btn = ctk.CTkButton(
            pick_frame,
            text="Marker = Awal",
            fg_color=PRIMARY,
            hover_color=PRIMARY_DARK,
            command=lambda: self._set_pick_target("start"),
        )
        self.pick_start_btn.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.pick_goal_btn = ctk.CTkButton(
            pick_frame,
            text="📍 Marker = Tujuan",
            fg_color=SIDEBAR2,
            hover_color=CARD,
            text_color=TEXT,
            command=lambda: self._set_pick_target("goal"),
        )
        self.pick_goal_btn.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        self._label(self.route_tab, "Skenario", 6)
        ctk.CTkOptionMenu(
            self.route_tab,
            variable=self.scenario_v,
            values=[scenario.value for scenario in Scenario],
        ).grid(row=7, column=0, sticky="ew", padx=12, pady=(0, 12))

        self._label(self.route_tab, "Faktor jam sibuk", 8)
        factor = ctk.CTkFrame(self.route_tab, fg_color="transparent")
        factor.grid(row=9, column=0, sticky="ew", padx=12, pady=(0, 14))
        factor.grid_columnconfigure(0, weight=1)
        ctk.CTkSlider(
            factor,
            from_=0.5,
            to=3.0,
            number_of_steps=25,
            variable=self.time_factor_v,
            progress_color=PRIMARY,
            button_color=PRIMARY,
            command=lambda value: self.factor_label.configure(text=f"{float(value):.1f}x"),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.factor_label = ctk.CTkLabel(factor, text="1.0x", width=46, text_color=TEXT)
        self.factor_label.grid(row=0, column=1)

        ctk.CTkButton(
            self.route_tab,
            text="🔍 Cari Jalur",
            height=44,
            fg_color=PRIMARY,
            hover_color=PRIMARY_DARK,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            command=self._find_route,
        ).grid(row=10, column=0, sticky="ew", padx=12, pady=(0, 6))
        ctk.CTkButton(
            self.route_tab,
            text="📊 Bandingkan Semua Skenario",
            height=36,
            fg_color=BLUE,
            hover_color="#3b82f6",
            command=self._compare_scenarios,
        ).grid(row=11, column=0, sticky="ew", padx=12, pady=(0, 6))
        ctk.CTkButton(
            self.route_tab,
            text="❌ Hapus Rute dari Peta",
            height=34,
            fg_color=SIDEBAR2,
            hover_color=CARD,
            text_color=MUTED,
            command=self._clear_route,
        ).grid(row=12, column=0, sticky="ew", padx=12, pady=(0, 12))

        metrics = ctk.CTkFrame(self.route_tab, fg_color=CARD, corner_radius=12)
        metrics.grid(row=13, column=0, sticky="ew", padx=12, pady=(0, 10))
        metrics.grid_columnconfigure((0, 1), weight=1)
        self.metric_labels = {}
        METRIC_COLORS = {"dist": BLUE, "cost": AMBER, "eta": GREEN, "iter": PURPLE}
        for row, (key, label) in enumerate(
            [("dist", "Jarak"), ("cost", "Bobot"), ("eta", "ETA"), ("iter", "Iterasi")]
        ):
            ctk.CTkLabel(metrics, text=label, text_color=MUTED, font=("Segoe UI", 10)).grid(
                row=row // 2 * 2,
                column=row % 2,
                padx=12, pady=(8, 0), sticky="w",
            )
            value = ctk.CTkLabel(
                metrics, text="-",
                text_color=METRIC_COLORS.get(key, TEXT),
                font=ctk.CTkFont("Segoe UI", 17, "bold"),
            )
            value.grid(row=row // 2 * 2 + 1, column=row % 2, padx=12, pady=(0, 8), sticky="w")
            self.metric_labels[key] = value

        self.route_output = ctk.CTkTextbox(
            self.route_tab,
            height=190,
            fg_color="#0f172a",
            text_color="#d1fae5",
            font=("Consolas", 11),
            corner_radius=12,
        )
        self.route_output.grid(row=14, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.route_tab.grid_rowconfigure(14, weight=1)
        self._set_output(self.route_output, "Belum ada rute.")

    def _build_road_tab(self):
        # Hint edit interaktif di peta
        hint = ctk.CTkFrame(self.road_tab, fg_color="#0d2b27", corner_radius=10)
        hint.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))
        ctk.CTkLabel(
            hint,
            text="✏️  Aktifkan Mode Edit di toolbar peta,\n     lalu klik langsung jalan yang ingin diubah!",
            text_color=PRIMARY,
            font=("Segoe UI", 10),
            justify="left",
        ).pack(padx=10, pady=6, anchor="w")

        self._title(self.road_tab, "Atur Kondisi Jalan", 1)
        self._label(self.road_tab, "Pilih jalan", 2)
        self.edge_menu = ctk.CTkOptionMenu(
            self.road_tab,
            variable=self.edge_v,
            values=[self._edge_label(edge) for edge in self.edges],
            command=lambda label: self._select_edge(self._edge_id_from_label(label)),
        )
        self.edge_menu.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 8))

        self.edge_info = ctk.CTkLabel(
            self.road_tab,
            text="",
            text_color=MUTED,
            justify="left",
            wraplength=370,
            font=("Segoe UI", 11),
        )
        self.edge_info.grid(row=4, column=0, sticky="w", padx=12, pady=(0, 8))

        self._label(self.road_tab, "Status jalan", 5)
        ctk.CTkOptionMenu(
            self.road_tab,
            variable=self.status_v,
            values=list(STATUS_LABELS.values()),
            command=self._on_status_change,
        ).grid(row=6, column=0, sticky="ew", padx=12, pady=(0, 8))

        self._label(self.road_tab, "Pengaruh ke bobot", 7)
        severity = ctk.CTkFrame(self.road_tab, fg_color="transparent")
        severity.grid(row=8, column=0, sticky="ew", padx=12, pady=(0, 10))
        severity.grid_columnconfigure(0, weight=1)
        ctk.CTkSlider(
            severity,
            from_=1.0,
            to=3.0,
            number_of_steps=20,
            variable=self.severity_v,
            progress_color=AMBER,
            button_color=AMBER,
            command=lambda value: self.severity_label.configure(text=f"{float(value):.1f}x"),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.severity_label = ctk.CTkLabel(severity, text="1.0x", width=46, text_color=MUTED)
        self.severity_label.grid(row=0, column=1)

        self._label(self.road_tab, "Arah lalu lintas", 9)
        self.direction_menu = ctk.CTkOptionMenu(
            self.road_tab,
            variable=self.direction_v,
            values=["Dua arah"],
        )
        self.direction_menu.grid(row=10, column=0, sticky="ew", padx=12, pady=(0, 10))

        actions = ctk.CTkFrame(self.road_tab, fg_color="transparent")
        actions.grid(row=11, column=0, sticky="ew", padx=12, pady=(0, 8))
        actions.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(
            actions,
            text="💾 Simpan Jalan",
            fg_color=PRIMARY,
            hover_color=PRIMARY_DARK,
            command=self._save_selected_edge,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ctk.CTkButton(
            actions,
            text="↩ Normal Lagi",
            fg_color=SIDEBAR2,
            hover_color=CARD,
            text_color=MUTED,
            command=self._reset_selected_edge,
        ).grid(row=0, column=1, sticky="ew", padx=(5, 0))

        ctk.CTkButton(
            self.road_tab,
            text="⚠️ Reset Semua Kondisi Jalan",
            fg_color="#4c1515",
            hover_color="#7f1d1d",
            text_color=RED,
            command=self._reset_all_conditions,
        ).grid(row=12, column=0, sticky="ew", padx=12, pady=(0, 10))

        table_frame = tk.Frame(self.road_tab, bg="#0d2b27")
        table_frame.grid(row=13, column=0, sticky="nsew", padx=12, pady=(0, 12))
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)
        self.road_table = ttk.Treeview(
            table_frame,
            columns=("edge", "status", "direction"),
            show="headings",
            selectmode="browse",
            height=10,
        )
        self.road_table.heading("edge", text="Jalan")
        self.road_table.heading("status", text="Status")
        self.road_table.heading("direction", text="Arah")
        self.road_table.column("edge", width=200, anchor="w")
        self.road_table.column("status", width=80, anchor="center")
        self.road_table.column("direction", width=85, anchor="center")
        self.road_table.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.road_table.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.road_table.configure(yscrollcommand=scrollbar.set)
        self.road_table.bind("<<TreeviewSelect>>", self._on_table_select)
        self.road_tab.grid_rowconfigure(13, weight=1)
        self._refresh_road_table()

    def _build_event_tab(self):
        self._title(self.event_tab, "Mode Acara", 0)
        self._label(self.event_tab, "Lokasi acara", 1)
        ctk.CTkOptionMenu(self.event_tab, variable=self.event_v, values=self.node_labels).grid(
            row=2, column=0, sticky="ew", padx=12, pady=(0, 10)
        )
        self._label(self.event_tab, "Skenario acara", 3)
        ctk.CTkOptionMenu(
            self.event_tab,
            variable=self.event_scenario_v,
            values=[scenario.value for scenario in Scenario],
        ).grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 14))
        ctk.CTkButton(
            self.event_tab,
            text="Hitung Jalur dari Semua Gerbang",
            height=42,
            fg_color=PURPLE,
            hover_color="#6d28d9",
            command=self._event_routes,
        ).grid(row=5, column=0, sticky="ew", padx=12, pady=(0, 12))

        self.event_output = ctk.CTkTextbox(
            self.event_tab,
            height=360,
            fg_color="#0f172a",
            text_color="#d1fae5",
            font=("Consolas", 11),
            corner_radius=12,
        )
        self.event_output.grid(row=6, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.event_tab.grid_rowconfigure(6, weight=1)
        self._set_output(self.event_output, "Belum ada perhitungan acara.")

    def _build_map(self, parent):
        panel = ctk.CTkFrame(parent, fg_color=CARD_LIGHT, corner_radius=18)
        panel.grid(row=0, column=1, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        # Toolbar atas peta
        bar = ctk.CTkFrame(panel, fg_color="#f8fffe", corner_radius=0, height=54)
        bar.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        bar.grid_columnconfigure(0, weight=1)
        bar.grid_propagate(False)

        ctk.CTkLabel(
            bar,
            text="Peta Jalan Kampus Utama UNIB",
            text_color=TEXT_DARK,
            font=ctk.CTkFont("Segoe UI", 16, "bold"),
        ).grid(row=0, column=0, padx=18, pady=8, sticky="w")

        self.map_status = ctk.CTkLabel(
            bar,
            text="Klik jalan untuk lihat info  •  Aktifkan mode edit untuk ubah kondisi",
            text_color="#64748b",
            font=("Segoe UI", 11),
        )
        self.map_status.grid(row=0, column=1, padx=8, pady=8, sticky="w")

        # Tombol kanan toolbar
        btn_frame = ctk.CTkFrame(bar, fg_color="transparent")
        btn_frame.grid(row=0, column=2, padx=12, pady=8, sticky="e")

        ctk.CTkButton(
            btn_frame,
            text="📍 Fit Peta",
            width=110,
            height=32,
            fg_color="#e2e8f0",
            hover_color="#cbd5e1",
            text_color=TEXT_DARK,
            corner_radius=8,
            command=self._fit_campus,
        ).grid(row=0, column=0, padx=(0, 6))

        self.edit_btn = ctk.CTkButton(
            btn_frame,
            text="✏️ Mode Edit Jalan",
            width=150,
            height=32,
            fg_color="#334155",
            hover_color="#1e293b",
            text_color="#ffffff",
            corner_radius=8,
            command=self._toggle_edit_mode,
        )
        self.edit_btn.grid(row=0, column=1)

        # Canvas peta
        map_frame = ctk.CTkFrame(panel, fg_color="#dce8e4", corner_radius=0)
        map_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        map_frame.grid_columnconfigure(0, weight=1)
        map_frame.grid_rowconfigure(0, weight=1)
        self.map_canvas = tk.Canvas(
            map_frame,
            bg=MAP_BG,
            highlightthickness=0,
            borderwidth=0,
            cursor="hand2",
        )
        self.map_canvas.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.map_canvas.bind("<Configure>", self._on_map_configure)

    def _title(self, parent, text: str, row: int):
        ctk.CTkLabel(
            parent,
            text=text,
            text_color=PRIMARY,
            font=ctk.CTkFont("Segoe UI", 15, "bold"),
        ).grid(row=row, column=0, sticky="w", padx=12, pady=(14, 6))

    def _label(self, parent, text: str, row: int):
        ctk.CTkLabel(
            parent,
            text=text,
            text_color=MUTED,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
        ).grid(row=row, column=0, sticky="w", padx=12, pady=(4, 3))

    def _style_treeview(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background="#1a3330",
            foreground="#d1fae5",
            fieldbackground="#1a3330",
            rowheight=30,
            borderwidth=0,
            font=("Segoe UI", 9),
        )
        style.configure(
            "Treeview.Heading",
            background="#0d2b27",
            foreground="#5eead4",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
        )
        style.map("Treeview",
            background=[("selected", "#14b8a6")],
            foreground=[("selected", "#ffffff")],
        )

    # ------------------------------------------------------------------
    # Conditions
    # ------------------------------------------------------------------
    def _load_conditions(self) -> dict:
        default = {"edge_conditions": {}, "edge_directions": {}, "last_modified": ""}
        if not CONDITION_FILE.exists():
            return default
        try:
            data = json.loads(CONDITION_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return default
        return {
            "edge_conditions": data.get("edge_conditions", {}),
            "edge_directions": data.get("edge_directions", {}),
            "last_modified": data.get("last_modified", ""),
        }

    def _save_conditions(self):
        CONDITION_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.conditions["last_modified"] = datetime.now().isoformat(timespec="seconds")
        CONDITION_FILE.write_text(
            json.dumps(self.conditions, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self.engine.set_conditions(self.conditions)

    def _edge_status(self, edge_id: str) -> str:
        item = self.conditions.get("edge_conditions", {}).get(edge_id, {})
        return (item.get("status") or item.get("type") or "NORMAL").upper()

    def _edge_severity(self, edge_id: str) -> float:
        status = self._edge_status(edge_id)
        item = self.conditions.get("edge_conditions", {}).get(edge_id, {})
        return float(item.get("severity", STATUS_DEFAULT_SEVERITY.get(status, 1.0)))

    def _edge_direction(self, edge) -> str:
        override = self.conditions.get("edge_directions", {}).get(edge.id)
        if override:
            return override
        return "TWO_WAY" if edge.is_bidirectional else "ONE_WAY_FORWARD"

    # ------------------------------------------------------------------
    # Map drawing
    # ------------------------------------------------------------------
    def _on_map_configure(self, _event=None):
        """Debounce handler untuk event <Configure> pada canvas.

        Membatalkan job sebelumnya dan menjadwalkan ulang dengan delay 80ms
        sehingga _refresh_map_layers() hanya dipanggil sekali setelah resize
        selesai, bukan ratusan kali per resize.
        """
        if self._map_refresh_job is not None:
            self.after_cancel(self._map_refresh_job)
        self._map_refresh_job = self.after(80, self._refresh_map_layers)

    def _draw_map(self):
        self._refresh_map_layers()

    def _clear_map(self):
        if hasattr(self, "map_canvas"):
            self.map_canvas.delete("all")
        self.edge_paths.clear()
        self.route_paths.clear()
        self.markers.clear()

    def _draw_background(self):
        width  = max(self.map_canvas.winfo_width(), 800)
        height = max(self.map_canvas.winfo_height(), 560)
        # Background gradient simulasi (dua rectangle)
        self.map_canvas.create_rectangle(0, 0, width, height, fill=MAP_BG, outline="")
        self.map_canvas.create_rectangle(0, height * 0.7, width, height,
            fill="#e8f4ef", outline="")
        # Grid tipis
        for xi in range(0, width, 80):
            self.map_canvas.create_line(xi, 0, xi, height, fill="#dde9e4", width=1)
        for yi in range(0, height, 80):
            self.map_canvas.create_line(0, yi, width, yi, fill="#dde9e4", width=1)
        # Border dalam
        self.map_canvas.create_rectangle(
            10, 10, width - 10, height - 10,
            outline="#b2cfc9", width=1, dash=(4, 6),
        )
        # Indikator utara
        self.map_canvas.create_oval(30, 24, 56, 50, fill="#0d1f1c", outline="")
        self.map_canvas.create_text(43, 37, text="N", fill="#14b8a6",
            font=("Segoe UI", 10, "bold"))
        self.map_canvas.create_line(43, 24, 43, 14, fill="#14b8a6", arrow=tk.LAST, width=2)
        # Watermark
        self.map_canvas.create_text(
            width - 16, height - 14,
            text="UNIB Campus • GPS Polyline",
            anchor="e", fill="#b2cfc9", font=("Segoe UI", 8),
        )

    def _draw_edges(self):
        for edge in self.edges:
            status = self._edge_status(edge.id)
            is_changed = (
                status != "NORMAL"
                or edge.id in self.conditions.get("edge_directions", {})
            )
            is_selected = edge.id == self.selected_edge_id
            is_hovered  = edge.id == self._hovered_edge_id

            # Warna
            if is_hovered and self.edit_mode:
                color = "#fde047"   # kuning terang saat hover + edit mode
            elif is_changed:
                color = STATUS_COLORS.get(status, ROAD)
            else:
                color = "#94a3b8"

            # Ketebalan
            width = 6 if is_selected else (4 if is_hovered and self.edit_mode else 3)
            if status == "CLOSED":
                width = max(width, 5)

            dash = (10, 6) if status == "CLOSED" else None
            points = self._flat_points(edge.geometry)
            if len(points) < 4:
                continue

            # Shadow tipis di bawah jalan
            self.map_canvas.create_line(
                *points, fill="#c8d8d0", width=width + 3,
                capstyle=tk.ROUND, joinstyle=tk.ROUND,
            )
            # Garis utama
            item = self.map_canvas.create_line(
                *points,
                fill=color, width=width,
                dash=dash, capstyle=tk.ROUND, joinstyle=tk.ROUND,
                tags=("edge", edge.id),
            )
            # Overlay tambahan untuk POTHOLE: titik-titik putih
            if status == "POTHOLE":
                mid = len(edge.geometry) // 2
                mx, my = self._xy(*edge.geometry[mid])
                for ox, oy in [(-8,0),(0,0),(8,0)]:
                    self.map_canvas.create_oval(
                        mx+ox-2, my+oy-2, mx+ox+2, my+oy+2,
                        fill="#ffffff", outline="",
                    )
            # Overlay X merah untuk CLOSED
            if status == "CLOSED":
                mid = len(edge.geometry) // 2
                mx, my = self._xy(*edge.geometry[mid])
                r = 10
                self.map_canvas.create_oval(
                    mx-r, my-r, mx+r, my+r, fill="#ef4444", outline="#ffffff", width=2
                )
                self.map_canvas.create_text(
                    mx, my, text="X", fill="#ffffff", font=("Segoe UI", 9, "bold")
                )

            # Bind klik
            self.map_canvas.tag_bind(
                item, "<Button-1>",
                lambda _, eid=edge.id: self._on_edge_click(eid),
            )
            # Bind hover
            self.map_canvas.tag_bind(
                item, "<Enter>",
                lambda _, eid=edge.id: self._on_edge_hover(eid),
            )
            self.map_canvas.tag_bind(
                item, "<Leave>",
                lambda _: self._on_edge_leave(),
            )
            self.edge_paths.append(item)

            # Label edge yang dipilih
            if is_selected:
                mx, my = self._xy(*edge.geometry[len(edge.geometry) // 2])
                self.map_canvas.create_rectangle(
                    mx - 22, my - 13, mx + 22, my + 13,
                    fill="#0d1f1c", outline=PRIMARY, width=2, tags="edge_label",
                )
                self.map_canvas.create_text(
                    mx, my, text=edge.id, fill=PRIMARY,
                    font=("Segoe UI", 9, "bold"), tags="edge_label",
                )

    def _draw_markers(self):
        start_id = self._id_from_label(self.start_v.get())
        goal_id  = self._id_from_label(self.goal_v.get())
        for node in self.nodes:
            x, y = self._xy(node.lat, node.lon)
            base_r = NODE_RADIUS.get(node.node_type, 7)
            is_key = node.id in (start_id, goal_id)
            radius = base_r + (3 if is_key else 0)

            outline_color = (
                "#22d3ee" if node.id == start_id
                else "#f87171" if node.id == goal_id
                else "#ffffff"
            )
            fill_color = NODE_COLORS.get(node.node_type, BLUE)

            # Shadow
            self.map_canvas.create_oval(
                x - radius + 2, y - radius + 2,
                x + radius + 2, y + radius + 2,
                fill="#b0cdc6", outline="",
            )
            # Lingkaran node
            item = self.map_canvas.create_oval(
                x - radius, y - radius, x + radius, y + radius,
                fill=fill_color, outline=outline_color,
                width=3 if is_key else 2,
                tags=("node", node.id),
            )
            # Label
            bg_lbl = self.map_canvas.create_rectangle(
                x - 14, y - radius - 18, x + 14, y - radius - 5,
                fill="#0d1f1c", outline="", tags=("node", node.id),
            )
            label = self.map_canvas.create_text(
                x, y - radius - 12,
                text=node.id, fill="#e2fff9",
                font=("Segoe UI", 7, "bold"),
                tags=("node", node.id),
            )
            for itm in (item, bg_lbl, label):
                self.map_canvas.tag_bind(
                    itm, "<Button-1>",
                    lambda _, nid=node.id: self._on_node_click(nid),
                )
            self.markers.extend([item, bg_lbl, label])

    def _draw_route(self, result: dict):
        geometry = self._route_geometry(result)
        if len(geometry) < 2:
            return
        scenario = next((s for s in Scenario if s.value == result.get("scenario")), Scenario.NORMAL)
        points = self._flat_points(geometry)
        shadow = self.map_canvas.create_line(
            *points,
            fill="#ffffff",
            width=12,
            capstyle=tk.ROUND,
            joinstyle=tk.ROUND,
        )
        route = self.map_canvas.create_line(
            *points,
            fill=SCENARIO_CONFIG[scenario]["color"],
            width=7,
            capstyle=tk.ROUND,
            joinstyle=tk.ROUND,
            arrow=tk.LAST,
            arrowshape=(14, 18, 7),
        )
        self.route_paths.extend([shadow, route])

    def _refresh_map_layers(self):
        if not hasattr(self, "map_canvas"):
            return
        self._clear_map()
        self._draw_background()
        self._draw_edges()
        if self.current_result and "error" not in self.current_result:
            self._draw_route(self.current_result)
        self._draw_markers()

    def _fit_campus(self):
        self._refresh_map_layers()

    def _fit_result(self, result: dict):
        self._refresh_map_layers()

    # ------------------------------------------------------------------
    # Edit mode & interactive road editing
    # ------------------------------------------------------------------
    def _tick_clock(self):
        """Update jam di header setiap menit."""
        if hasattr(self, "clock_label"):
            self.clock_label.configure(
                text=datetime.now().strftime("%H:%M  %a, %d %b %Y")
            )
        self.after(30_000, self._tick_clock)

    def _toggle_edit_mode(self):
        """Aktif/nonaktifkan mode edit interaktif di peta."""
        self.edit_mode = not self.edit_mode
        self._hide_edge_popup()
        if self.edit_mode:
            self.edit_btn.configure(
                text="✏️ Mode Edit: ON",
                fg_color=PRIMARY,
                hover_color=PRIMARY_DARK,
            )
            self.map_status.configure(
                text="🖱️  Mode Edit aktif — hover jalan lalu klik untuk ubah kondisi"
            )
            self.map_canvas.configure(cursor="crosshair")
        else:
            self.edit_btn.configure(
                text="✏️ Mode Edit Jalan",
                fg_color="#334155",
                hover_color="#1e293b",
            )
            self.map_status.configure(
                text="Klik jalan untuk lihat info  •  Aktifkan mode edit untuk ubah kondisi"
            )
            self.map_canvas.configure(cursor="hand2")
            self._hovered_edge_id = None
        self._refresh_map_layers()

    def _on_edge_click(self, edge_id: str):
        """Handler klik pada jalan di peta."""
        if self.edit_mode:
            self._select_edge(edge_id, refresh_map=True)
            self._show_edge_popup(edge_id)
            # Alihkan ke tab Jalan
            try:
                self.tabs.set("🛣 Jalan")
            except Exception:
                pass
        else:
            self._select_edge(edge_id, switch_tab=True)

    def _on_edge_hover(self, edge_id: str):
        """Highlight jalan saat hover (hanya di edit mode)."""
        if self.edit_mode and self._hovered_edge_id != edge_id:
            self._hovered_edge_id = edge_id
            self._refresh_map_layers()

    def _on_edge_leave(self):
        """Hapus highlight saat mouse meninggalkan jalan."""
        if self.edit_mode and self._hovered_edge_id is not None:
            self._hovered_edge_id = None
            self._refresh_map_layers()

    def _show_edge_popup(self, edge_id: str):
        """Tampilkan popup kondisi di dekat jalan yang diklik."""
        self._hide_edge_popup()
        edge = self.edge_by_id.get(edge_id)
        if edge is None:
            return

        # Posisi popup: di tengah jalan yang dipilih
        mid_pt = edge.geometry[len(edge.geometry) // 2]
        cx, cy = self._xy(*mid_pt)
        # Konversi koordinat canvas ke koordinat layar
        canvas_x = self.map_canvas.winfo_rootx() + cx
        canvas_y = self.map_canvas.winfo_rooty() + cy - 110  # di atas jalan

        popup = tk.Toplevel(self)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg="#0d1f1c")
        popup.geometry(f"280x155+{canvas_x - 140}+{canvas_y}")
        self._popup_win = popup

        # Header popup
        hdr = tk.Frame(popup, bg="#14b8a6", pady=4)
        hdr.pack(fill="x")
        tk.Label(
            hdr, text=f"✏️  {edge_id}  ({edge.from_node} → {edge.to_node})",
            bg="#14b8a6", fg="#ffffff",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=8)
        tk.Button(
            hdr, text="✕", bg="#0f9488", fg="#ffffff",
            font=("Segoe UI", 9, "bold"), relief="flat", bd=0,
            command=self._hide_edge_popup, cursor="hand2",
        ).pack(side="right", padx=4)

        # Info jarak
        info = tk.Frame(popup, bg="#0d2b27", pady=3)
        info.pack(fill="x")
        cur_status = self._edge_status(edge_id)
        tk.Label(
            info,
            text=f"{STATUS_EMOJI.get(cur_status,'✅')} Status: {STATUS_LABELS.get(cur_status,'Normal')}  |  {edge.distance:.0f} m  |  {edge.surface.label}",
            bg="#0d2b27", fg="#7fb8b0",
            font=("Segoe UI", 8),
        ).pack(padx=8, anchor="w")

        # Tombol kondisi
        btn_frame = tk.Frame(popup, bg="#0d1f1c", pady=6)
        btn_frame.pack(fill="x", padx=8)
        btn_cfg = [
            ("✅ Normal",    "NORMAL",  "#166534", "#22c55e"),
            ("🚦 Sibuk",    "BUSY",    "#92400e", "#fbbf24"),
            ("⚠️ Berlubang", "POTHOLE", "#78350f", "#f59e0b"),
            ("🚫 Ditutup",  "CLOSED",  "#7f1d1d", "#ef4444"),
        ]
        for i, (label, status, bg, fg) in enumerate(btn_cfg):
            is_active = cur_status == status
            btn = tk.Button(
                btn_frame,
                text=label,
                bg=bg if not is_active else fg,
                fg="#ffffff",
                activebackground=fg,
                activeforeground="#ffffff",
                font=("Segoe UI", 8, "bold" if is_active else "normal"),
                relief="flat", bd=0,
                padx=4, pady=3,
                cursor="hand2",
                command=lambda s=status, eid=edge_id: self._apply_quick_condition(eid, s),
            )
            btn.grid(row=0, column=i, padx=2, sticky="ew")
            btn_frame.grid_columnconfigure(i, weight=1)

        # Klik di luar popup menutupnya
        popup.bind("<FocusOut>", lambda _: self._hide_edge_popup())

    def _hide_edge_popup(self):
        """Tutup popup kondisi jalan."""
        if self._popup_win is not None:
            try:
                self._popup_win.destroy()
            except Exception:
                pass
            self._popup_win = None

    def _apply_quick_condition(self, edge_id: str, status: str):
        """Terapkan kondisi langsung dari popup di peta."""
        self._hide_edge_popup()
        edge_conditions = self.conditions.setdefault("edge_conditions", {})
        if status == "NORMAL":
            edge_conditions.pop(edge_id, None)
        else:
            severity = STATUS_DEFAULT_SEVERITY.get(status, 1.0)
            edge_conditions[edge_id] = {
                "status": status,
                "type":   status,
                "severity": severity,
            }
        self._save_conditions()
        self._refresh_road_table()
        self._select_edge(edge_id, refresh_map=True)
        edge = self.edge_by_id[edge_id]
        self.map_status.configure(
            text=f"✅  {edge_id} diubah: {STATUS_EMOJI.get(status,'')} {STATUS_LABELS.get(status,'Normal')}"
        )

    def _route_geometry(self, result: dict) -> list[tuple[float, float]]:
        path = result.get("path", [])
        edge_ids = result.get("edges_used", [])
        geometry: list[tuple[float, float]] = []
        for i, edge_id in enumerate(edge_ids):
            edge = self.edge_by_id[edge_id]
            segment = list(edge.geometry)
            if i < len(path) - 1 and path[i] == edge.to_node and path[i + 1] == edge.from_node:
                segment.reverse()
            if geometry and segment and geometry[-1] == segment[0]:
                geometry.extend(segment[1:])
            else:
                geometry.extend(segment)
        return geometry

    def _compute_geo_bounds(self) -> tuple[float, float, float, float]:
        points = []
        for edge in self.edges:
            points.extend(edge.geometry)
        points.extend((node.lat, node.lon) for node in self.nodes)
        min_lat = min(point[0] for point in points)
        max_lat = max(point[0] for point in points)
        min_lon = min(point[1] for point in points)
        max_lon = max(point[1] for point in points)
        return min_lat, max_lat, min_lon, max_lon

    def _xy(self, lat: float, lon: float) -> tuple[int, int]:
        min_lat, max_lat, min_lon, max_lon = self.geo_bounds
        width = max(self.map_canvas.winfo_width(), 800)
        height = max(self.map_canvas.winfo_height(), 560)
        pad_x = 54
        pad_y = 54
        x = pad_x + (lon - min_lon) / (max_lon - min_lon) * (width - 2 * pad_x)
        y = pad_y + (max_lat - lat) / (max_lat - min_lat) * (height - 2 * pad_y)
        return int(round(x)), int(round(y))

    def _flat_points(self, geometry: list[tuple[float, float]]) -> list[int]:
        points: list[int] = []
        for lat, lon in geometry:
            x, y = self._xy(lat, lon)
            points.extend([x, y])
        return points

    # ------------------------------------------------------------------
    # Route actions
    # ------------------------------------------------------------------
    def _find_route(self):
        start_id = self._id_from_label(self.start_v.get())
        goal_id = self._id_from_label(self.goal_v.get())
        scenario = self._scenario_from_value(self.scenario_v.get())
        result = self.engine.find_path(start_id, goal_id, scenario, self.time_factor_v.get())
        self.current_result = result
        if "error" in result:
            self._clear_metrics()
            self._set_output(self.route_output, result.get("detail", "Tidak ada jalur."))
            messagebox.showwarning("Rute tidak ditemukan", result.get("detail", "Tidak ada jalur."))
        else:
            self._update_metrics(result)
            self._set_output(self.route_output, self._route_summary(result))
        self._refresh_map_layers()
        if "error" not in result:
            self._fit_result(result)

    def _compare_scenarios(self):
        start_id = self._id_from_label(self.start_v.get())
        goal_id = self._id_from_label(self.goal_v.get())
        results = self.engine.compare_all_scenarios(start_id, goal_id, self.time_factor_v.get())

        win = ctk.CTkToplevel(self)
        win.title("Perbandingan Skenario")
        win.geometry("820x420")
        win.configure(fg_color=BG)
        ctk.CTkLabel(
            win,
            text=f"Perbandingan: {start_id} -> {goal_id}",
            text_color=TEXT,
            font=ctk.CTkFont("Segoe UI", 18, "bold"),
        ).pack(anchor="w", padx=18, pady=(18, 10))
        frame = tk.Frame(win, bg=BG)
        frame.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        columns = ("scenario", "path", "dist", "cost", "eta", "iter")
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        headings = {
            "scenario": "Skenario",
            "path": "Jalur",
            "dist": "Jarak",
            "cost": "Bobot",
            "eta": "ETA",
            "iter": "Iterasi",
        }
        for column in columns:
            tree.heading(column, text=headings[column])
            tree.column(column, width=120 if column != "path" else 280, anchor="center")
        for scenario_name, result in results.items():
            if "error" in result:
                values = (scenario_name, "NO PATH", "-", "-", "-", result.get("iterations", "-"))
            else:
                values = (
                    scenario_name,
                    " -> ".join(result["path"]),
                    f"{result['total_dist_m']:.0f} m",
                    f"{result['total_cost']:.0f}",
                    f"{result['eta_minutes']:.1f} mnt",
                    result["iterations"],
                )
            tree.insert("", "end", values=values)
        tree.pack(fill="both", expand=True)

    def _event_routes(self):
        target_id = self._id_from_label(self.event_v.get())
        gate_ids = [node.id for node in self.nodes if node.node_type == NodeType.ENTRY]
        scenario = self._scenario_from_value(self.event_scenario_v.get())
        results = self.engine.event_routing(gate_ids, target_id, scenario, self.time_factor_v.get())
        best = next((result for result in results if "error" not in result), None)

        lines = [f"Tujuan acara: {target_id} - {self.node_by_id[target_id].name}", ""]
        for result in results:
            if "error" in result:
                lines.append(f"{result['gate']}: tidak ada jalur")
            else:
                lines.append(
                    f"{result['gate']} ({result['gate_name']}): "
                    f"{result['total_dist_m']:.0f} m | bobot {result['total_cost']:.0f} | "
                    f"{result['eta_minutes']:.1f} mnt"
                )
                lines.append(f"  {' -> '.join(result['path'])}")

        self._set_output(self.event_output, "\n".join(lines))
        if best:
            self.current_result = best
            self.start_v.set(self._node_label(self.node_by_id[best["gate"]]))
            self.goal_v.set(self._node_label(self.node_by_id[target_id]))
            self.scenario_v.set(scenario.value)
            self._update_metrics(best)
            self._refresh_map_layers()
            self._fit_result(best)

    def _clear_route(self):
        self.current_result = None
        self._clear_metrics()
        self._set_output(self.route_output, "Rute dihapus dari peta. Kondisi jalan tetap tersimpan.")
        self._refresh_map_layers()

    # ------------------------------------------------------------------
    # Road condition actions
    # ------------------------------------------------------------------
    def _select_edge(
        self,
        edge_id: str,
        switch_tab: bool = False,
        focus_map: bool = True,
        refresh_map: bool = True,
    ):
        if edge_id not in self.edge_by_id:
            return
        self.selected_edge_id = edge_id
        edge = self.edge_by_id[edge_id]
        self.edge_v.set(self._edge_label(edge))

        status = self._edge_status(edge.id)
        severity = self._edge_severity(edge.id)
        self.status_v.set(STATUS_LABELS.get(status, "Normal"))
        self.severity_v.set(min(max(severity, 1.0), 3.0))
        self.severity_label.configure(text=f"{self.severity_v.get():.1f}x")

        self.direction_choices = [
            "Dua arah",
            f"Satu arah {edge.from_node} -> {edge.to_node}",
            f"Satu arah {edge.to_node} -> {edge.from_node}",
        ]
        self.direction_menu.configure(values=self.direction_choices)
        direction = self._edge_direction(edge)
        if direction == "ONE_WAY_FORWARD":
            self.direction_v.set(self.direction_choices[1])
        elif direction == "ONE_WAY_REVERSE":
            self.direction_v.set(self.direction_choices[2])
        else:
            self.direction_v.set(self.direction_choices[0])

        self.edge_info.configure(
            text=(
                f"{edge.from_node} - {self.node_by_id[edge.from_node].name}\n"
                f"{edge.to_node} - {self.node_by_id[edge.to_node].name}\n"
                f"Jarak jalan: {edge.distance:.0f} m | Permukaan: {edge.surface.label}"
            )
        )
        self._select_table_row(edge.id)
        if refresh_map:
            self._refresh_map_layers()
        if switch_tab:
            try:
                self.tabs.set("🛣 Jalan")
            except Exception:
                pass

    def _save_selected_edge(self):
        edge = self.edge_by_id[self.selected_edge_id]
        status = STATUS_BY_LABEL.get(self.status_v.get(), "NORMAL")
        edge_conditions = self.conditions.setdefault("edge_conditions", {})
        edge_directions = self.conditions.setdefault("edge_directions", {})

        if status == "NORMAL":
            edge_conditions.pop(edge.id, None)
        else:
            edge_conditions[edge.id] = {
                "status": status,
                "type": status,
                "severity": round(float(self.severity_v.get()), 2),
            }

        direction = self._direction_from_choice(edge)
        default_direction = "TWO_WAY" if edge.is_bidirectional else "ONE_WAY_FORWARD"
        if direction == default_direction:
            edge_directions.pop(edge.id, None)
        else:
            edge_directions[edge.id] = direction

        self._save_conditions()
        self._refresh_road_table()
        self._refresh_map_layers()
        self.map_status.configure(text=f"{edge.id} tersimpan: {STATUS_LABELS[status]}, {self._direction_text(edge)}")

    def _reset_selected_edge(self):
        edge = self.edge_by_id[self.selected_edge_id]
        self.conditions.setdefault("edge_conditions", {}).pop(edge.id, None)
        self.conditions.setdefault("edge_directions", {}).pop(edge.id, None)
        self._save_conditions()
        self._refresh_road_table()
        self._select_edge(edge.id, focus_map=False)
        self.map_status.configure(text=f"{edge.id} dikembalikan normal")

    def _reset_all_conditions(self):
        if not messagebox.askyesno("Reset semua kondisi", "Kembalikan semua jalan ke kondisi normal?"):
            return
        self.conditions = {"edge_conditions": {}, "edge_directions": {}, "last_modified": ""}
        self._save_conditions()
        self._refresh_road_table()
        self._select_edge(self.selected_edge_id, focus_map=False)
        self.map_status.configure(text="Semua kondisi jalan sudah normal")

    def _on_status_change(self, label: str):
        status = STATUS_BY_LABEL.get(label, "NORMAL")
        severity = STATUS_DEFAULT_SEVERITY.get(status, 1.0)
        self.severity_v.set(severity)
        self.severity_label.configure(text=f"{severity:.1f}x")

    def _on_table_select(self, _):
        # BUGFIX: cek flag SEBELUM melakukan apapun; flag di-reset via after_idle
        # sehingga Treeview.selection_set() di dalam _select_table_row tidak
        # memicu callback ini ulang sebelum flag sempat di-reset.
        if self.syncing_table:
            return
        selection = self.road_table.selection()
        if not selection:
            return
        edge_id = self.road_table.item(selection[0], "values")[0]
        # Tandai bahwa kita sedang memproses; set flag SEBELUM _select_edge
        self.syncing_table = True
        try:
            self._select_edge(edge_id)
        finally:
            # Reset flag setelah semua event Tk idle selesai diproses
            self.after_idle(self._reset_syncing_table)

    def _refresh_road_table(self):
        if not hasattr(self, "road_table"):
            return
        for item in self.road_table.get_children():
            self.road_table.delete(item)
        for edge in self.edges:
            self.road_table.insert(
                "",
                "end",
                values=(
                    edge.id,
                    STATUS_LABELS.get(self._edge_status(edge.id), "Normal"),
                    self._direction_text(edge),
                ),
            )

    def _select_table_row(self, edge_id: str):
        if not hasattr(self, "road_table"):
            return
        # BUGFIX: syncing_table sudah di-set True oleh _on_table_select sebelum
        # memanggil _select_edge; tidak perlu diubah lagi di sini.
        for item in self.road_table.get_children():
            if self.road_table.item(item, "values")[0] == edge_id:
                self.road_table.selection_set(item)
                self.road_table.see(item)
                break

    def _reset_syncing_table(self):
        """Reset flag syncing_table setelah semua idle event selesai."""
        self.syncing_table = False

    def _fit_edge(self, edge):
        # BUGFIX: _select_edge sudah memanggil _refresh_map_layers();
        # _fit_edge tidak perlu memanggil ulang untuk menghindari double-render.
        pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _scenario_from_value(self, value: str) -> Scenario:
        return next((scenario for scenario in Scenario if scenario.value == value), Scenario.NORMAL)

    def _set_pick_target(self, target: str):
        self.pick_target = target
        if target == "start":
            self.pick_start_btn.configure(
                fg_color=PRIMARY, hover_color=PRIMARY_DARK, text_color="#ffffff"
            )
            self.pick_goal_btn.configure(
                fg_color=SIDEBAR2, hover_color=CARD, text_color=MUTED
            )
        else:
            self.pick_goal_btn.configure(
                fg_color=PRIMARY, hover_color=PRIMARY_DARK, text_color="#ffffff"
            )
            self.pick_start_btn.configure(
                fg_color=SIDEBAR2, hover_color=CARD, text_color=MUTED
            )

    def _on_node_click(self, node_id: str):
        label = self._node_label(self.node_by_id[node_id])
        if self.pick_target == "start":
            self.start_v.set(label)
        else:
            self.goal_v.set(label)
            self.event_v.set(label)
        try:
            self.tabs.set("🗺 Rute")
        except Exception:
            pass

    def _direction_from_choice(self, edge) -> str:
        choice = self.direction_v.get()
        if len(self.direction_choices) >= 3 and choice == self.direction_choices[1]:
            return "ONE_WAY_FORWARD"
        if len(self.direction_choices) >= 3 and choice == self.direction_choices[2]:
            return "ONE_WAY_REVERSE"
        return "TWO_WAY"

    def _direction_text(self, edge) -> str:
        direction = self._edge_direction(edge)
        if direction == "ONE_WAY_FORWARD":
            return f"{edge.from_node}->{edge.to_node}"
        if direction == "ONE_WAY_REVERSE":
            return f"{edge.to_node}->{edge.from_node}"
        return "2 arah"

    def _node_label(self, node) -> str:
        return f"{node.id} - {node.name}"

    def _id_from_label(self, label: str) -> str:
        return label.split(" - ", 1)[0].strip()

    def _edge_label(self, edge) -> str:
        return f"{edge.id} - {edge.from_node} ke {edge.to_node}"

    def _edge_id_from_label(self, label: str) -> str:
        return label.split(" - ", 1)[0].strip()

    def _route_summary(self, result: dict) -> str:
        names = [self.node_by_id[node_id].name for node_id in result["path"]]
        return (
            f"Rute ditemukan ({result['scenario']})\n"
            f"Jalur ID   : {' -> '.join(result['path'])}\n"
            f"Jalur nama : {' -> '.join(names)}\n"
            f"Jarak jalan: {result['total_dist_m']:.0f} m\n"
            f"Bobot efek : {result['total_cost']:.0f}\n"
            f"ETA        : {result['eta_minutes']:.1f} menit"
        )

    def _update_metrics(self, result: dict):
        self.metric_labels["dist"].configure(text=f"{result['total_dist_m']:.0f} m")
        self.metric_labels["cost"].configure(text=f"{result['total_cost']:.0f}")
        self.metric_labels["eta"].configure(text=f"{result['eta_minutes']:.1f} mnt")
        self.metric_labels["iter"].configure(text=str(result["iterations"]))

    def _clear_metrics(self):
        for label in self.metric_labels.values():
            label.configure(text="-")

    def _set_output(self, widget, text: str):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", text)
        widget.configure(state="disabled")


if __name__ == "__main__":
    App().mainloop()
