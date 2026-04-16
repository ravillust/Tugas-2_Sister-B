import tkinter as tk
from tkinter import ttk
import threading
import queue
import time
import math
from datetime import datetime
from collections import deque
from dataclasses import dataclass, field
from typing import List, Dict
import random

# BAGIAN 1: DEFINISI STRUKTUR DATA DAN KOMPONEN DASAR
# Palet warna
COLORS = {
    'bg_dark':      '#ffffff',   'bg_panel':     '#f8f9fa',   'bg_card':      '#ffffff',
    'bg_input':     '#f0f0f0',   'border':       '#d0d0d0',   'text_primary': '#1a1a1a',
    'text_secondary':'#555555',  'text_muted':   '#888888',   'accent_rr':    '#0052cc',
    'accent_ps':    '#28a745',   'success':      '#28a745',   'warning':      '#ff9800',
    'error':        '#d32f2f',
}
MODEL_COLORS = {'rr': '#0052cc', 'ps': '#28a745'}

@dataclass
class Message:
    """Struktur pesan dalam sistem"""
    sender_id: str
    receiver_id: str
    content: str
    timestamp: float
    message_id: int

    def __repr__(self):
        return f"Msg({self.sender_id}->{self.receiver_id}: {self.content[:20]})"


@dataclass
class CommunicationMetric:
    """Metrik untuk mengukur performa komunikasi"""
    total_messages: int = 0
    total_time: float = 0.0
    throughput: float = 0.0
    avg_latency: float = 0.0
    min_latency: float = float('inf')
    max_latency: float = 0.0
    success_count: int = 0
    error_count: int = 0
    message_delivery_time: List[float] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)

    def update(self, delivery_time: float, success: bool = True):
        """Update semua metrik setelah satu pengiriman pesan"""
        self.message_delivery_time.append(delivery_time)
        self.total_messages += 1
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
        self.avg_latency = sum(self.message_delivery_time) / len(self.message_delivery_time)
        self.min_latency = min(self.min_latency, delivery_time)
        self.max_latency = max(self.max_latency, delivery_time)
        elapsed = time.time() - self.start_time
        if elapsed > 0:
            self.throughput = self.total_messages / elapsed

    def reset(self):
        """Reset semua metrik"""
        self.total_messages = self.total_time = self.throughput = self.avg_latency = 0
        self.min_latency = float('inf')
        self.max_latency = self.success_count = self.error_count = 0
        self.message_delivery_time = []
        self.start_time = time.time()


class Node:
    """Representasi node dalam sistem terdistribusi"""
    def __init__(self, node_id: str, node_type: str = "normal"):
        self.node_id = node_id
        self.node_type = node_type
        self.message_log = deque(maxlen=100)
        self.lock = threading.Lock()
        self.active = True
        self.processing = False  # State untuk animasi
        self.processing_time = random.uniform(0.01, 0.05)
        self.messages_received = 0

    def receive_message(self, message: Message, timestamp: float):
        """Terima pesan dan catat ke log"""
        with self.lock:
            self.messages_received += 1
            self.processing = True
            self.message_log.append({
                'message': message,
                'received_time': timestamp,
                'latency': (timestamp - message.timestamp) * 1000
            })

    def process_message(self, message: Message) -> str:
        """Proses pesan dan hasilkan respons"""
        time.sleep(self.processing_time)
        self.processing = False
        return f"[{self.node_id}] Resp: {message.content}"



# BAGIAN 2: IMPLEMENTASI MODEL KOMUNIKASI
class CommunicationModel:
    """Base class untuk model komunikasi"""
    def __init__(self, name="Model"):
        self.name = name
        self.nodes: Dict[str, Node] = {}
        self.metrics = CommunicationMetric()
        self.lock = threading.Lock()
        self.event_callback = None
    
    def add_node(self, node: Node):
        self.nodes[node.node_id] = node

class RequestResponseModel(CommunicationModel):
    """Model Request-Response (Sinkron) - Pengirim menunggu respons"""
    def send_request(self, sender_id: str, receiver_id: str, content: str) -> str:
        if receiver_id not in self.nodes:
            return "ERROR: Receiver tidak ditemukan"
        msg_id = self.metrics.total_messages + 1
        message = Message(sender_id=sender_id, receiver_id=receiver_id, content=content,
                         timestamp=time.time(), message_id=msg_id)
        self.event_callback and self.event_callback('send', sender_id, receiver_id, content)
        receiver = self.nodes[receiver_id]
        receiver.receive_message(message, time.time())
        response = receiver.process_message(message)
        self.event_callback and self.event_callback('response', receiver_id, sender_id, response)
        with self.lock:
            self.metrics.update((time.time() - message.timestamp) * 1000, success=True)
        return response

class PublishSubscribeModel(CommunicationModel):
    """Model Publish-Subscribe (Asinkron) - Publisher tidak tahu subscribers"""
    def __init__(self, name="Publish-Subscribe"):
        super().__init__(name)
        self.topics: Dict[str, List[str]] = {}
        self.message_queue = queue.Queue()
        self.running = True
        threading.Thread(target=self._message_processor, daemon=True).start()

    def subscribe(self, node_id: str, topic: str):
        if topic not in self.topics:
            self.topics[topic] = []
        if node_id not in self.topics[topic]:
            self.topics[topic].append(node_id)

    def publish(self, publisher_id: str, topic: str, content: str):
        message = Message(sender_id=publisher_id, receiver_id=topic, content=content,
                         timestamp=time.time(), message_id=self.metrics.total_messages + 1)
        self.event_callback and self.event_callback('publish', publisher_id, topic, content)
        self.message_queue.put((topic, message))

    def _message_processor(self):
        while self.running:
            try:
                topic, message = self.message_queue.get(timeout=0.5)
                if topic in self.topics:
                    for subscriber_id in self.topics[topic]:
                        if subscriber_id in self.nodes:
                            subscriber = self.nodes[subscriber_id]
                            subscriber.receive_message(message, time.time())
                            self.event_callback and self.event_callback('deliver', message.sender_id, subscriber_id, message.content)
                            subscriber.process_message(message)
                with self.lock:
                    self.metrics.update((time.time() - message.timestamp) * 1000, success=True)
                self.message_queue.task_done()
            except queue.Empty:
                continue

    def stop(self):
        self.running = False


# BAGIAN 3: DIAGRAM VISUAL ANIMASI (Canvas-based)
class NetworkDiagramCanvas(tk.Canvas):
    """
    Canvas untuk menggambar diagram jaringan node dan animasi alur pesan.
    Menampilkan node sebagai lingkaran dan pesan sebagai partikel bergerak.
    """
    NODE_RADIUS = 28
    ANIM_STEPS = 20      # Jumlah frame per animasi panah
    ANIM_DELAY = 30      # ms per frame

    def __init__(self, parent, model_key: str, node_layout: dict, **kwargs):
        super().__init__(parent, **kwargs)
        self.model_key = model_key
        self.node_positions = node_layout       # {node_id: (x, y)}
        self.node_canvas_ids = {}               # {node_id: canvas_item_id}
        self.active_animations = []
        self.accent = MODEL_COLORS.get(model_key, '#58a6ff')
        self._draw_static()

    # Gambar elemen statis (background, node)
    def _draw_static(self):
        """Gambar latar belakang dan semua node"""
        self.delete("all")
        w, h = int(self.cget('width')), int(self.cget('height'))
        for _ in range(80):
            x, y, r = random.randint(0, w), random.randint(0, h), random.randint(1, 2)
            self.create_oval(x-r, y-r, x+r, y+r, fill=f"#{random.choice(['e0', 'e5', 'ea'])}{random.choice(['e0', 'e5', 'ea'])}{random.choice(['e0', 'e5', 'ea'])}", outline='')
        for node_id, (x, y) in self.node_positions.items():
            self._draw_node(node_id, x, y)

    def _draw_node(self, node_id: str, x: float, y: float, active: bool = False):
        """Gambar satu node sebagai lingkaran berlabel"""
        r = self.NODE_RADIUS
        fill = self.accent if active else COLORS['bg_card']
        lw = 2 if not active else 3
        if active:
            self.create_oval(x-r-6, y-r-6, x+r+6, y+r+6, fill='', outline=self.accent, width=2, tags=(f"glow_{node_id}",))
        self.create_oval(x-r, y-r, x+r, y+r, fill=fill, outline=self.accent, width=lw, tags=(f"node_{node_id}",))
        parts = node_id.split('-')
        label = parts[0] if len(parts) == 1 else f"{parts[0]}\n{'-'.join(parts[1:])}"
        self.create_text(x, y, text=label, fill=COLORS['text_primary'], font=("Consolas", 7, "bold"), tags=(f"label_{node_id}",))

    def _get_edge_point(self, x1, y1, x2, y2):
        """Hitung titik di tepi lingkaran node (bukan di tengah)"""
        r = self.NODE_RADIUS + 4
        dx = x2 - x1
        dy = y2 - y1
        dist = math.hypot(dx, dy) or 1
        return x1 + dx/dist*r, y1 + dy/dist*r

    def animate_message(self, sender_id: str, receiver_id: str, label: str = "msg", color: str = None):
        """Animasikan partikel pesan bergerak dari sender ke receiver"""
        try:
            if sender_id not in self.node_positions or receiver_id not in self.node_positions:
                return
            color = color or self.accent
            sx, sy = self.node_positions[sender_id]
            rx, ry = self.node_positions[receiver_id]
            x1, y1 = self._get_edge_point(sx, sy, rx, ry)
            x2, y2 = self._get_edge_point(rx, ry, sx, sy)
            
            line_id = self.create_line(x1, y1, x2, y2, fill=color, width=1, dash=(4, 4), tags=('anim_line',))
            pr = 6
            dot_id = self.create_oval(x1-pr, y1-pr, x1+pr, y1+pr, fill=color, outline='white', width=1, tags=('anim_dot',))
            txt_id = self.create_text(x1, y1-14, text=label[:10], fill=color, font=("Consolas", 6), tags=('anim_txt',))
            
            self._flash_node(sender_id, color)
            steps = self.ANIM_STEPS
            def step(f):
                if f > steps:
                    for oid in (dot_id, txt_id, line_id):
                        try: self.delete(oid)
                        except: pass
                    self._flash_node(receiver_id, color)
                    return
                t = f / steps
                cx, cy = x1 + (x2-x1)*t, y1 + (y2-y1)*t
                try:
                    self.coords(dot_id, cx-pr, cy-pr, cx+pr, cy+pr)
                    self.coords(txt_id, cx, cy-14)
                    self.after(self.ANIM_DELAY, lambda: step(f+1))
                except: pass
            step(0)
        except: pass

    def _flash_node(self, node_id: str, color: str):
        """Kedipkan node sesaat"""
        try:
            items = self.find_withtag(f"node_{node_id}")
            if items:
                self.itemconfig(items[0], fill=color + 'aa')
                self.after(300, lambda: self._safe_itemconfig(items[0], fill=COLORS['bg_card']))
        except: pass

    def _safe_itemconfig(self, oid, **kw):
        """Safe itemconfig"""
        try:
            if 'fill' in kw and kw['fill'] and kw['fill'].startswith('#'):
                kw['fill'] = kw['fill'][:7]
            self.itemconfig(oid, **kw)
        except: pass

    def highlight_node(self, node_id: str, active: bool = True):
        """Ubah warna border node"""
        items = self.find_withtag(f"node_{node_id}")
        if items:
            lw = 3 if active else 2
            self.itemconfig(items[0], width=lw)


# Konfigurasi posisi node untuk diagram
DIAGRAM_LAYOUTS = {
    'rr': {'ATM-Terminal-1': (90, 100), 'ATM-Terminal-2': (90, 220), 'Bank-Server': (330, 160)},
    'ps': {'Temperature-Sensor': (90, 160), 'AC-Unit': (340, 70), 'Fan': (340, 160), 'Mobile-App': (340, 250)},
}

# BAGIAN 4: GRAFIK BATANG (Bar Chart Canvas)

class BarChartCanvas(tk.Canvas):
    """Canvas mini untuk menampilkan bar chart metrik"""

    def __init__(self, parent, title: str, **kwargs):
        super().__init__(parent, **kwargs)
        self.title = title
        self.data: Dict[str, float] = {}

    def update_data(self, data: Dict[str, float]):
        """Perbarui data dan redraw"""
        self.data = data
        self._redraw()

    def _redraw(self):
        self.delete("all")
        w, h = int(self.cget('width')), int(self.cget('height'))
        self.create_text(w//2, 12, text=self.title, fill=COLORS['text_secondary'], font=("Consolas", 8, "bold"))
        if not self.data:
            return
        max_val, n, pad = max(self.data.values()) or 1, len(self.data), 8
        bar_w, bar_h = (w - pad*(n+1)) // n, h - 45
        for i, (key, val) in enumerate(self.data.items()):
            bx, fill_h = pad + i*(bar_w + pad), int((val / max_val) * bar_h)
            by_top, color = h - 20 - fill_h, MODEL_COLORS.get(key, '#0052cc')
            self.create_rectangle(bx+2, by_top+2, bx+bar_w+2, h-18, fill='#e8e8e8', outline='')
            self.create_rectangle(bx, by_top, bx+bar_w, h-20, fill=color, outline=color, width=1)
            lbl = f"{val:.1f}" if val < 100 else f"{val:.0f}"
            self.create_text(bx + bar_w//2, by_top - 5, text=lbl, fill=color, font=("Consolas", 7))
            self.create_text(bx + bar_w//2, h-8, text={'rr':'RR','ps':'PS'}.get(key, key), 
                           fill=COLORS['text_secondary'], font=("Consolas", 7))

# BAGIAN 5: INTERFACE GRAFIS UTAMA
class DistributedSystemSimulatorGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Simulasi Komunikasi Sistem Terdistribusi v2.0")
        self.root.geometry("1300x820")
        self.root.configure(bg=COLORS['bg_dark'])
        self.root.resizable(True, True)

        self.log_messages = []
        self.is_running = False
        self.running = True
        self.models: Dict = {}
        self.diagrams: Dict[str, NetworkDiagramCanvas] = {}

        self._setup_styles()
        self._initialize_models()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        self._start_metric_updater()

    def _mk_label(self, parent, text=None, **kw) -> tk.Label:
        """Helper: buat label dengan default styling"""
        if text is not None:
            kw['text'] = text
        lbl = tk.Label(parent, bg=kw.pop('bg', COLORS['bg_panel']), 
                       fg=kw.pop('fg', COLORS['text_secondary']), **kw)
        return lbl
    
    def _mk_btn(self, parent, text, cmd, style='normal', **kw) -> tk.Button:
        """Helper: buat button dengan styling"""
        if style == 'run':
            return tk.Button(parent, text=text, command=cmd, bg=COLORS['accent_rr'], fg='white',
                           font=("Helvetica", 9, "bold"), relief=tk.FLAT, bd=0, padx=10, pady=7,
                           activebackground='#79c0ff', cursor='hand2', **kw)
        return tk.Button(parent, text=text, command=cmd, bg=COLORS['bg_input'], 
                        fg=COLORS['text_secondary'], font=("Helvetica", 8), relief=tk.FLAT, 
                        bd=0, padx=10, pady=6, activebackground=COLORS['bg_card'], cursor='hand2', **kw)

    def _mk_section(self, parent, text):
        """Helper: buat section header"""
        self._mk_label(parent, text, bg=COLORS['bg_panel'], fg=COLORS['accent_rr'], 
                      font=("Helvetica", 8, "bold")).pack(anchor=tk.W, padx=12, pady=(12, 4))
        tk.Frame(parent, bg=COLORS['border'], height=1).pack(fill=tk.X, padx=12)

    # Inisialisasi
    def _setup_styles(self):
        """Konfigurasi ttk styles untuk dark theme"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Helper untuk style label
        label_styles = {
            'Dark.TLabel': (COLORS['bg_dark'], COLORS['text_primary'], ("Consolas", 9)),
            'Title.TLabel': (COLORS['bg_dark'], COLORS['text_primary'], ("Consolas", 13, "bold")),
            'Sub.TLabel': (COLORS['bg_panel'], COLORS['text_secondary'], ("Consolas", 8)),
            'Metric.TLabel': (COLORS['bg_card'], COLORS['text_primary'], ("Consolas", 10, "bold")),
            'MetricVal.TLabel': (COLORS['bg_card'], COLORS['accent_rr'], ("Consolas", 11, "bold")),
        }
        for lbl_style, (bg, fg, font) in label_styles.items():
            style.configure(lbl_style, background=bg, foreground=fg, font=font)

        # Frames
        for name, bg in [('Dark.TFrame', COLORS['bg_dark']), ('Panel.TFrame', COLORS['bg_panel']), ('Card.TFrame', COLORS['bg_card'])]:
            style.configure(name, background=bg)

        # Buttons & Controls
        style.configure('Run.TButton', background=COLORS['accent_rr'], foreground='white', font=("Consolas", 9, "bold"), borderwidth=0)
        style.map('Run.TButton', background=[('active', '#79c0ff'), ('disabled', '#30363d')], foreground=[('disabled', COLORS['text_muted'])])
        style.configure('Clear.TButton', background=COLORS['bg_input'], foreground=COLORS['text_secondary'], font=("Consolas", 9), borderwidth=0)
        style.configure('Dark.TRadiobutton', background=COLORS['bg_panel'], foreground=COLORS['text_primary'], font=("Consolas", 9), indicatorcolor=COLORS['accent_rr'])
        style.map('Dark.TRadiobutton', background=[('active', COLORS['bg_card'])])
        style.configure('Dark.TScale', background=COLORS['bg_panel'], troughcolor=COLORS['bg_input'], sliderthickness=14)
        style.configure('Dark.TSpinbox', background=COLORS['bg_input'], foreground=COLORS['text_primary'], font=("Consolas", 9))

        # Notebook & Treeview
        style.configure('Dark.TNotebook', background=COLORS['bg_dark'], borderwidth=0)
        style.configure('Dark.TNotebook.Tab', background=COLORS['bg_panel'], foreground=COLORS['text_secondary'], font=("Consolas", 9), padding=[10, 5])
        style.map('Dark.TNotebook.Tab', background=[('selected', COLORS['bg_card'])], foreground=[('selected', COLORS['text_primary'])])
        style.configure('Dark.Treeview', background=COLORS['bg_card'], foreground=COLORS['text_primary'], fieldbackground=COLORS['bg_card'], font=("Consolas", 9), rowheight=24)
        style.configure('Dark.Treeview.Heading', background=COLORS['bg_input'], foreground=COLORS['text_primary'], font=("Consolas", 9, "bold"))
        style.map('Dark.Treeview', background=[('selected', COLORS['accent_rr'] + '44')])

        # Labelframe
        style.configure('Dark.TLabelframe', background=COLORS['bg_panel'], foreground=COLORS['text_secondary'], font=("Consolas", 8), borderwidth=1, relief='solid')
        style.configure('Dark.TLabelframe.Label', background=COLORS['bg_panel'], foreground=COLORS['accent_rr'])

    def _initialize_models(self):
        """Inisialisasi 2 model komunikasi dengan real-world scenarios"""
        models_config = {
            'rr': {
                'class': RequestResponseModel,
                'name': 'Request-Response',
                'nodes': [('Bank-Server', 'server'), ('ATM-Terminal-1', 'client'), ('ATM-Terminal-2', 'client')]
            },
            'ps': {
                'class': PublishSubscribeModel,
                'name': 'Publish-Subscribe',
                'nodes': [('Temperature-Sensor', 'publisher'), ('AC-Unit', 'subscriber'), ('Fan', 'subscriber'), ('Mobile-App', 'subscriber')],
                'subscriptions': [('AC-Unit', 'temperature_alert'), ('Fan', 'temperature_alert'), ('Mobile-App', 'sensor_status')]
            }
        }
        for key, cfg in models_config.items():
            model = cfg['class'](cfg['name'])
            for node_id, node_type in cfg['nodes']:
                model.add_node(Node(node_id, node_type))
            if 'subscriptions' in cfg:
                for node_id, topic in cfg['subscriptions']:
                    model.subscribe(node_id, topic)
            self.models[key] = model


    # Build UI
    def _build_ui(self):
        self._build_header()
        self._build_body()

    def _build_header(self):
        header = tk.Frame(self.root, bg=COLORS['bg_panel'], highlightbackground=COLORS['border'], highlightthickness=1)
        header.pack(fill=tk.X, padx=0, pady=0)
        tk.Label(header, text="◈  SIMULASI MODEL KOMUNIKASI SISTEM TERDISTRIBUSI  ◈",
                bg=COLORS['bg_panel'], fg=COLORS['accent_rr'], font=("Helvetica", 12, "bold")).pack(side=tk.LEFT, padx=20, pady=10)
        for key, label, color in [('rr', 'Request-Response', COLORS['accent_rr']), ('ps', 'Pub-Subscribe', COLORS['accent_ps'])]:
            tk.Label(header, text=f"● {label}", bg=COLORS['bg_panel'], fg=color, font=("Helvetica", 8)).pack(side=tk.LEFT, padx=8, pady=10)

    def _build_body(self):
        body = tk.Frame(self.root, bg=COLORS['bg_dark'])
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        # Kiri: panel kontrol
        self._build_left_panel(body)

        # Kanan: notebook tab
        self._build_right_panel(body)

    def _build_left_panel(self, parent):
        left = tk.Frame(parent, bg=COLORS['bg_panel'], highlightbackground=COLORS['border'],
                        highlightthickness=1, width=210)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        left.pack_propagate(False)

        # --- Model selection ---
        self._mk_section(left, "▸ MODEL KOMUNIKASI")
        self.model_var = tk.StringVar(value="rr")
        for key, label, color in [('rr', '⬡ Request-Response', COLORS['accent_rr']),
                                   ('ps', '⬡ Publish-Subscribe', COLORS['accent_ps'])]:
            tk.Radiobutton(left, text=label, variable=self.model_var, value=key,
                          command=self._on_model_changed, bg=COLORS['bg_panel'], fg=color,
                          selectcolor=COLORS['bg_card'], activebackground=COLORS['bg_card'],
                          activeforeground=color, font=("Helvetica", 8),
                          indicatoron=True, bd=0, pady=2).pack(anchor=tk.W, padx=16, pady=2)

        # --- Kontrol simulasi ---
        self._mk_section(left, "▸ KONTROL SIMULASI")
        self._mk_label(left, "Kecepatan (msg/sec):", font=("Helvetica", 8)).pack(anchor=tk.W, padx=12, pady=(8, 0))
        self.speed_var = tk.IntVar(value=5)
        tk.Scale(left, from_=1, to=20, orient=tk.HORIZONTAL, variable=self.speed_var,
                bg=COLORS['bg_panel'], fg=COLORS['text_primary'], highlightbackground=COLORS['bg_panel'],
                troughcolor=COLORS['bg_input'], activebackground=COLORS['accent_rr'],
                font=("Helvetica", 7)).pack(fill=tk.X, padx=12)

        self._mk_label(left, "Jumlah Pesan:", font=("Helvetica", 8)).pack(anchor=tk.W, padx=12, pady=(8, 2))
        self.msg_count_var = tk.StringVar(value="8")
        tk.Spinbox(left, from_=1, to=50, textvariable=self.msg_count_var,
                  bg=COLORS['bg_input'], fg=COLORS['text_primary'], insertbackground=COLORS['text_primary'],
                  highlightbackground=COLORS['border'], font=("Helvetica", 9), width=8, bd=0).pack(padx=12, pady=(0, 8))

        self.run_btn = self._mk_btn(left, "▶  JALANKAN SIMULASI", self._run_simulation, 'run')
        self.run_btn.pack(fill=tk.X, padx=12, pady=(4, 4))
        self._mk_btn(left, "⬛  BERSIHKAN LOG", self._clear_logs).pack(fill=tk.X, padx=12, pady=2)
        self._mk_btn(left, "⟳  RESET METRIK", self._reset_metrics).pack(fill=tk.X, padx=12, pady=2)

        # --- Status & Info ---
        self._mk_section(left, "▸ STATUS")
        self.status_var = tk.StringVar(value="● Idle — siap menjalankan simulasi")
        self._mk_label(left, textvariable=self.status_var, font=("Helvetica", 7), wraplength=180,
                      justify=tk.LEFT).pack(anchor=tk.W, padx=12, pady=6)

        self._mk_section(left, "▸ KETERANGAN")
        self.info_var = tk.StringVar(value="")
        self._mk_label(left, textvariable=self.info_var, fg=COLORS['text_muted'], font=("Helvetica", 7),
                      wraplength=180, justify=tk.LEFT).pack(anchor=tk.W, padx=12, pady=4)
        self._update_model_info()

    def _build_right_panel(self, parent):
        right = tk.Frame(parent, bg=COLORS['bg_dark'])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Notebook dengan 3 tab
        nb = ttk.Notebook(right, style='Dark.TNotebook')
        nb.pack(fill=tk.BOTH, expand=True)
        self.notebook = nb

        # Tab 1: Diagram + Log
        self.tab_sim = tk.Frame(nb, bg=COLORS['bg_dark'])
        nb.add(self.tab_sim, text=" 📡 Simulasi & Diagram ")

        # Tab 2: Perbandingan
        self.tab_cmp = tk.Frame(nb, bg=COLORS['bg_dark'])
        nb.add(self.tab_cmp, text=" 📊 Perbandingan Model ")

        self._build_simulation_tab()
        self._build_comparison_tab()

    # Tab 1: Simulasi & Diagram
    def _build_simulation_tab(self):
        p = self.tab_sim

        # Atas: Diagram animasi
        top = tk.Frame(p, bg=COLORS['bg_dark'])
        top.pack(fill=tk.X, padx=0, pady=(0, 4))

        # Label diagram
        tk.Label(top, text="DIAGRAM ALUR JARINGAN  |  Animasi Pengiriman Pesan",
                 bg=COLORS['bg_dark'], fg=COLORS['text_muted'],
                 font=("Helvetica", 8)).pack(anchor=tk.W, padx=6, pady=(4, 2))

        # Frame diagram (semua 4 model, ditampilkan via raise)
        self.diagram_frame = tk.Frame(top, bg=COLORS['bg_dark'])
        self.diagram_frame.pack(fill=tk.X, padx=4)

        model_names = {
            'rr':  'REQUEST - RESPONSE',
            'ps':  'PUBLISH - SUBSCRIBE',
        }

        self.diagram_containers = {}
        for key in ['rr', 'ps']:
            container = tk.Frame(self.diagram_frame,
                                 bg=COLORS['bg_panel'],
                                 highlightbackground=MODEL_COLORS[key],
                                 highlightthickness=1)
            container.place(relwidth=1, relheight=1)

            tk.Label(container,
                     text=f"[ {model_names[key]} ]",
                     bg=COLORS['bg_panel'],
                     fg=MODEL_COLORS[key],
                     font=("Helvetica", 8, "bold")).pack(anchor=tk.W, padx=8, pady=4)

            layout = DIAGRAM_LAYOUTS[key]
            canvas = NetworkDiagramCanvas(
                container, model_key=key,
                node_layout=layout,
                width=440, height=300,
                bg=COLORS['bg_panel'],
                highlightthickness=0
            )
            canvas.pack(padx=8, pady=(0, 8))

            self.diagrams[key] = canvas
            self.diagram_containers[key] = container

        # Set RR sebagai default
        self.diagram_containers['rr'].lift()
        self.diagram_frame.configure(height=340)
        self.diagram_frame.pack_propagate(False)

        # Hubungkan callback animasi
        self._attach_callbacks()

        # Bawah: Metrik real-time + log
        bot = tk.Frame(p, bg=COLORS['bg_dark'])
        bot.pack(fill=tk.BOTH, expand=True, padx=0)

        # Metrik cards
        metric_row = tk.Frame(bot, bg=COLORS['bg_dark'])
        metric_row.pack(fill=tk.X, padx=4, pady=(0, 4))

        self.metric_cards = {}
        for label, key in [
            ("TOTAL PESAN", "total"),
            ("AVG LATENCY (ms)", "latency"),
            ("MIN LATENCY (ms)", "min_lat"),
            ("MAX LATENCY (ms)", "max_lat"),
            ("THROUGHPUT (msg/s)", "throughput"),
            ("SUCCESS RATE (%)", "success"),
        ]:
            card = tk.Frame(metric_row, bg=COLORS['bg_card'],
                            highlightbackground=COLORS['border'],
                            highlightthickness=1)
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
            tk.Label(card, text=label,
                     bg=COLORS['bg_card'], fg=COLORS['text_muted'],
                     font=("Helvetica", 7)).pack(pady=(6, 0))
            val_lbl = tk.Label(card, text="—",
                               bg=COLORS['bg_card'], fg=COLORS['accent_rr'],
                               font=("Helvetica", 11, "bold"))
            val_lbl.pack(pady=(0, 6))
            self.metric_cards[key] = val_lbl

        # Log komunikasi
        tk.Label(bot, text="LOG KOMUNIKASI",
                 bg=COLORS['bg_dark'], fg=COLORS['text_muted'],
                 font=("Helvetica", 8)).pack(anchor=tk.W, padx=6)

        log_frame = tk.Frame(bot, bg=COLORS['bg_card'],
                             highlightbackground=COLORS['border'],
                             highlightthickness=1)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(2, 4))

        self.log_text = tk.Text(
            log_frame,
            bg=COLORS['bg_dark'], fg=COLORS['text_primary'],
            insertbackground=COLORS['text_primary'],
            font=("Helvetica", 8),
            relief=tk.FLAT, bd=0,
            state=tk.DISABLED
        )
        sb = tk.Scrollbar(log_frame, command=self.log_text.yview,
                          bg=COLORS['bg_input'])
        self.log_text.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Warna tag log
        for key, color in MODEL_COLORS.items():
            self.log_text.tag_config(key, foreground=color)
        self.log_text.tag_config("info",    foreground=COLORS['text_secondary'])
        self.log_text.tag_config("success", foreground=COLORS['success'])
        self.log_text.tag_config("error",   foreground=COLORS['error'])
        self.log_text.tag_config("warn",    foreground=COLORS['warning'])

    # Tab 2: Perbandingan
    def _build_comparison_tab(self):
        p = self.tab_cmp

        tk.Label(p, text="PERBANDINGAN PERFORMA SEMUA MODEL KOMUNIKASI",
                 bg=COLORS['bg_dark'], fg=COLORS['text_primary'],
                 font=("Helvetica", 10, "bold")).pack(pady=(12, 6))

        tk.Label(p,
                 text="Jalankan simulasi pada setiap model lalu klik 'Perbarui Perbandingan' untuk melihat analisis berdampingan.",
                 bg=COLORS['bg_dark'], fg=COLORS['text_muted'],
                 font=("Helvetica", 8)).pack(pady=(0, 8))

        # Tombol refresh
        tk.Button(p, text="⟳  PERBARUI PERBANDINGAN",
                  command=self._refresh_comparison,
                  bg=COLORS['accent_rr'], fg='white',
                  font=("Helvetica", 9, "bold"),
                  relief=tk.FLAT, bd=0, padx=14, pady=7,
                  cursor='hand2').pack(pady=(0, 12))

        # Tabel perbandingan (Treeview)
        cols = ("Model", "Total Pesan", "Avg Latency (ms)",
                "Min Latency (ms)", "Max Latency (ms)",
                "Throughput (msg/s)", "Success Rate (%)", "Sinkron?")
        tree_frame = tk.Frame(p, bg=COLORS['bg_dark'])
        tree_frame.pack(fill=tk.X, padx=12, pady=(0, 12))

        self.compare_tree = ttk.Treeview(tree_frame, columns=cols,
                                          show='headings',
                                          style='Dark.Treeview', height=5)
        col_widths = [160, 95, 130, 130, 130, 130, 110, 80]
        for col, w in zip(cols, col_widths):
            self.compare_tree.heading(col, text=col)
            self.compare_tree.column(col, width=w, anchor=tk.CENTER)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                             command=self.compare_tree.yview)
        self.compare_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.compare_tree.pack(fill=tk.X)

        # Baris grafik batang
        chart_row = tk.Frame(p, bg=COLORS['bg_dark'])
        chart_row.pack(fill=tk.BOTH, expand=True, padx=12)

        self.chart_latency = BarChartCanvas(
            chart_row, "Avg Latency (ms)",
            width=280, height=180, bg=COLORS['bg_panel'],
            highlightbackground=COLORS['border'], highlightthickness=1
        )
        self.chart_latency.pack(side=tk.LEFT, padx=(0, 6), pady=4, fill=tk.BOTH, expand=True)

        self.chart_throughput = BarChartCanvas(
            chart_row, "Throughput (msg/s)",
            width=280, height=180, bg=COLORS['bg_panel'],
            highlightbackground=COLORS['border'], highlightthickness=1
        )
        self.chart_throughput.pack(side=tk.LEFT, padx=(0, 6), pady=4, fill=tk.BOTH, expand=True)

        self.chart_total = BarChartCanvas(
            chart_row, "Total Pesan Diproses",
            width=280, height=180, bg=COLORS['bg_panel'],
            highlightbackground=COLORS['border'], highlightthickness=1
        )
        self.chart_total.pack(side=tk.LEFT, pady=4, fill=tk.BOTH, expand=True)

        # Analisis teks otomatis
        tk.Label(p, text="ANALISIS",
                 bg=COLORS['bg_dark'], fg=COLORS['text_muted'],
                 font=("Helvetica", 8, "bold")).pack(anchor=tk.W, padx=12, pady=(8, 2))

        self.analysis_text = tk.Text(
            p, bg=COLORS['bg_card'], fg=COLORS['text_secondary'],
            font=("Helvetica", 8), relief=tk.FLAT, bd=0,
            height=6, state=tk.DISABLED
        )
        self.analysis_text.pack(fill=tk.X, padx=12, pady=(0, 8))
        for key, color in MODEL_COLORS.items():
            self.analysis_text.tag_config(key, foreground=color)

    # Logika simulasi
    def _format_metric(self, value, is_count=False):
        """Helper: format metric value"""
        if isinstance(value, float):
            return f"{value:.2f}" if not is_count else f"{value:.0f}"
        return str(value) if value is not None else "—"

    def _get_metric_values(self, model):
        """Helper: ekstrak semua metric dari model"""
        m = model.metrics
        return {
            "total": m.total_messages,
            "latency": m.avg_latency if m.total_messages > 0 else None,
            "min_lat": m.min_latency if m.min_latency < float('inf') else None,
            "max_lat": m.max_latency if m.total_messages > 0 else None,
            "throughput": m.throughput if m.total_messages > 0 else None,
            "success": (m.success_count / max(m.total_messages, 1) * 100) if m.total_messages > 0 else None,
        }

    def _attach_callbacks(self):
        """Hubungkan callback animasi dari model ke diagram"""
        def make_cb(model_key):
            def cb(event_type, from_id, to_id, content):
                diagram = self.diagrams.get(model_key)
                if diagram:
                    short = str(content)[:12]
                    self.root.after(0, lambda: diagram.animate_message(from_id, to_id, label=short, color=MODEL_COLORS[model_key]))
            return cb
        self.models['rr'].event_callback  = make_cb('rr')
        self.models['ps'].event_callback  = make_cb('ps')

    def _on_model_changed(self):
        """Angkat diagram model yang dipilih ke depan"""
        key = self.model_var.get()
        self.diagram_containers[key].lift()
        self._update_model_info()
        self._log(f"Model aktif: {self.models[key].name}", "info")

    def _update_model_info(self):
        """Update keterangan singkat model di panel kiri"""
        infos = {
            'rr':  "Sinkron. Client menunggu respons server sebelum lanjut.",
            'ps':  "Asinkron. Publisher tidak tahu siapa yang subscribe.",
        }
        self.info_var.set(infos.get(self.model_var.get(), ""))

    def _run_simulation(self):
        """Mulai simulasi di thread terpisah"""
        if self.is_running:
            self._log("Simulasi sedang berjalan, harap tunggu.", "warn")
            return
        self.is_running = True
        self.run_btn.configure(state=tk.DISABLED, text="▶  BERJALAN...")
        self.status_var.set("● Running — simulasi aktif...")

        model_key  = self.model_var.get()
        msg_count  = int(self.msg_count_var.get())
        speed      = int(self.speed_var.get())

        t = threading.Thread(
            target=self._execute_simulation,
            args=(model_key, msg_count, speed),
            daemon=True
        )
        t.start()

    def _execute_simulation(self, model_key: str, msg_count: int, speed: int):
        """Eksekusi simulasi sesuai model yang dipilih"""
        model = self.models[model_key]
        delay = 1.0 / speed

        self._log(f"\n{'═'*65}", "info")
        self._log(f"  ▶ MULAI: {model.name}  |  {msg_count} pesan  |  {speed} msg/sec", model_key)
        self._log(f"{'═'*65}", "info")

        start = time.time()

        try:
            if model_key == 'rr':
                self._sim_rr(model, msg_count, delay)
            elif model_key == 'ps':
                self._sim_ps(model, msg_count, delay)
        except Exception as e:
            self._log(f"ERROR: {e}", "error")

        elapsed = time.time() - start
        self._log(f"\n  ✓ SELESAI dalam {elapsed:.2f} detik", "success")
        self._log(f"  Total: {model.metrics.total_messages} pesan | "
                  f"Avg Latency: {model.metrics.avg_latency:.2f} ms | "
                  f"Throughput: {model.metrics.throughput:.2f} msg/s", "success")
        self._log(f"{'═'*65}\n", "info")

        self.is_running = False
        self.root.after(0, lambda: (
            self.run_btn.configure(state=tk.NORMAL, text="▶  JALANKAN SIMULASI"),
            self.status_var.set("● Idle — simulasi selesai")
        ))

    def _sim_rr(self, model, msg_count, delay):
        for i in range(msg_count):
            atm = ["ATM-Terminal-1", "ATM-Terminal-2"][i % 2]
            req = f"Withdrawal: Rp {(i+1)*100000:,}"
            resp = model.send_request(atm, "Bank-Server", req)
            self._log(f"  [RR] {atm} → Bank-Server : {req}", 'rr')
            self._log(f"       ← {resp[:50]}", 'rr')
            time.sleep(delay)

    def _sim_ps(self, model, msg_count, delay):
        for i in range(max(msg_count // 2, 1)):
            temp = 28 + (i % 5)
            model.publish("Temperature-Sensor", "temperature_alert", f"Temp: {temp}°C")
            self._log(f"  [PS] Sensor → topic:temperature_alert : {temp}°C", 'ps')
            time.sleep(delay)
            model.publish("Temperature-Sensor", "sensor_status", f"Reading #{i+1} OK")
            self._log(f"  [PS] Sensor → topic:sensor_status : Reading #{i+1}", 'ps')
            time.sleep(delay)

    # Perbandingan
    def _refresh_comparison(self):
        """Isi tabel perbandingan dan perbarui grafik"""
        for row in self.compare_tree.get_children():
            self.compare_tree.delete(row)

        model_info = {'rr': ("Request-Response", "Ya"), 'ps': ("Publish-Subscribe", "Tidak")}
        lat_data = {}
        thr_data = {}
        tot_data = {}

        for key, (name, sinkron) in model_info.items():
            vals = self._get_metric_values(self.models[key])
            total = vals["total"]
            avg_lat = f"{vals['latency']:.2f}" if vals['latency'] else "—"
            min_lat = f"{vals['min_lat']:.2f}" if vals['min_lat'] else "—"
            max_lat = f"{vals['max_lat']:.2f}" if vals['max_lat'] else "—"
            thr = f"{vals['throughput']:.2f}" if vals['throughput'] else "—"
            success = f"{vals['success']:.1f}" if vals['success'] else "—"

            self.compare_tree.insert('', tk.END, values=(name, total, avg_lat, min_lat, max_lat, thr, success, sinkron), tags=(key,))
            self.compare_tree.tag_configure(key, foreground=MODEL_COLORS[key])

            if total > 0:
                lat_data[key] = vals['latency']
                thr_data[key] = vals['throughput']
                tot_data[key] = float(total)

        self.chart_latency.update_data(lat_data)
        self.chart_throughput.update_data(thr_data)
        self.chart_total.update_data(tot_data)
        self._generate_analysis(lat_data, thr_data, tot_data)

    def _generate_analysis(self, lat: dict, thr: dict, tot: dict):
        """Buat analisis otomatis berdasarkan hasil simulasi"""
        txt = self.analysis_text
        txt.configure(state=tk.NORMAL)
        txt.delete("1.0", tk.END)
        if not lat:
            txt.insert(tk.END, "Belum ada data. Jalankan simulasi pada setiap model terlebih dahulu.")
            txt.configure(state=tk.DISABLED)
            return
        fastest, slowest = min(lat, key=lat.get), max(lat, key=lat.get)
        names = {'rr': 'Request-Response', 'ps': 'Pub-Subscribe'}
        txt.insert(tk.END, f"• Latency TERENDAH: ", "info")
        txt.insert(tk.END, f"{names[fastest]} ({lat[fastest]:.2f} ms)\n", fastest)
        txt.insert(tk.END, f"• Latency TERTINGGI: ", "info")
        txt.insert(tk.END, f"{names[slowest]} ({lat[slowest]:.2f} ms)\n", slowest)
        if thr:
            highest = max(thr, key=thr.get)
            txt.insert(tk.END, f"• Throughput TERTINGGI: ", "info")
            txt.insert(tk.END, f"{names[highest]} ({thr[highest]:.2f} msg/s)\n", highest)
        txt.configure(state=tk.DISABLED)

    # Utilitas
    def _log(self, message: str, tag: str = "info"):
        """Tulis ke log dengan timestamp"""
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        def insert():
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, f"[{ts}] {message}\n", tag)
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)
        self.root.after(0, insert)

    def _clear_logs(self):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _reset_metrics(self):
        [m.metrics.reset() for m in self.models.values()]
        self._log("Semua metrik direset.", "warn")

    def _start_metric_updater(self):
        def loop():
            while self.running:
                try:
                    self.root.after(0, self._update_metrics_display)
                    time.sleep(0.5)
                except: pass
        threading.Thread(target=loop, daemon=True).start()

    def _on_closing(self):
        """Handle window close event dengan proper cleanup"""
        self.running = False
        self.is_running = False
        for model in self.models.values():
            if hasattr(model, 'stop'):
                try:
                    model.stop()
                except Exception:
                    pass
        self.root.destroy()

    def _update_metrics_display(self):
        """Perbarui kartu metrik sesuai model aktif"""
        key = self.model_var.get()
        model = self.models[key]
        m = model.metrics
        color = MODEL_COLORS[key]

        vals = self._get_metric_values(model)
        display_vals = {
            "total": self._format_metric(vals["total"], is_count=True),
            "latency": self._format_metric(vals["latency"]) if vals["latency"] else "—",
            "min_lat": self._format_metric(vals["min_lat"]) if vals["min_lat"] else "—",
            "max_lat": self._format_metric(vals["max_lat"]) if vals["max_lat"] else "—",
            "throughput": self._format_metric(vals["throughput"]) if vals["throughput"] else "—",
            "success": self._format_metric(vals["success"]) if vals["success"] else "—",
        }
        for k, v in display_vals.items():
            self.metric_cards[k].configure(text=v, fg=color)


# BAGIAN 6: ENTRY POINT
if __name__ == "__main__":
    root = tk.Tk()
    app = DistributedSystemSimulatorGUI(root)
    root.mainloop()