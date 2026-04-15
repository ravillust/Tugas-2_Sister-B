import tkinter as tk
from tkinter import ttk, scrolledtext, font as tkfont
import threading
import queue
import time
import math
from datetime import datetime
from collections import deque
from dataclasses import dataclass, field
from typing import List, Dict, Callable, Tuple, Optional
import random

# BAGIAN 1: DEFINISI STRUKTUR DATA DAN KOMPONEN DASAR
# Palet warna
COLORS = {
    'bg_dark':      '#ffffff',   # putih
    'bg_panel':     '#f8f9fa',   # abu-abu sangat ringan
    'bg_card':      '#ffffff',   # putih
    'bg_input':     '#f0f0f0',   # abu-abu ringan
    'border':       '#d0d0d0',   # abu-abu medium
    'text_primary': '#1a1a1a',   # hitam
    'text_secondary':'#555555',  # abu-abu gelap
    'text_muted':   '#888888',   # abu-abu medium
    'accent_rr':    '#0052cc',   # biru tua - Request-Response
    'accent_ps':    '#28a745',   # hijau tua - Pub-Sub
    'accent_mp':    '#7030a0',   # ungu tua - Message Passing
    'accent_rpc':   '#d9480f',   # oranye tua - RPC
    'accent_gold':  '#b8860b',   # emas tua
    'success':      '#28a745',
    'warning':      '#ff9800',
    'error':        '#d32f2f',
    'node_idle':    '#f5f5f5',   # abu-abu ringan
    'node_active':  '#0052cc',   # biru aktif
    'node_process': '#2196f3',   # biru process
    'arrow_color':  '#0052cc',
}

MODEL_COLORS = {
    'rr':  COLORS['accent_rr'],
    'ps':  COLORS['accent_ps'],
}

MODEL_TAGS = {
    'rr':  'rr',
    'ps':  'ps',
}

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
        self.total_messages = 0
        self.total_time = 0.0
        self.throughput = 0.0
        self.avg_latency = 0.0
        self.min_latency = float('inf')
        self.max_latency = 0.0
        self.success_count = 0
        self.error_count = 0
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
class RequestResponseModel:
    """
    Model Request-Response (Sinkron)
    - Pengirim mengirim request dan MENUNGGU respons
    - Komunikasi satu-ke-satu, blocking
    
    CONTOH DUNIA NYATA:
    1. Smartphone + AC Remote: User tekan tombol → request → AC on/off → respons
    2. ATM + Bank Server: Withdrawal request → wait approval → money dispensed
    3. Browser + Web Server: HTTP GET request → wait → HTML response
    """
    def __init__(self, name="Request-Response"):
        self.name = name
        self.nodes: Dict[str, Node] = {}
        self.metrics = CommunicationMetric()
        self.lock = threading.Lock()
        self.event_callback = None  # Callback untuk animasi UI

    def add_node(self, node: Node):
        self.nodes[node.node_id] = node

    def send_request(self, sender_id: str, receiver_id: str, content: str) -> str:
        """Pengirim mengirim request dan menunggu respons (blocking)"""
        if receiver_id not in self.nodes:
            return "ERROR: Receiver tidak ditemukan"

        msg_id = self.metrics.total_messages + 1
        message = Message(
            sender_id=sender_id,
            receiver_id=receiver_id,
            content=content,
            timestamp=time.time(),
            message_id=msg_id
        )

        if self.event_callback:
            self.event_callback('send', sender_id, receiver_id, content)

        receiver = self.nodes[receiver_id]
        receiver.receive_message(message, time.time())
        response = receiver.process_message(message)

        if self.event_callback:
            self.event_callback('response', receiver_id, sender_id, response)

        delivery_time = (time.time() - message.timestamp) * 1000
        with self.lock:
            self.metrics.update(delivery_time, success=True)

        return response


class PublishSubscribeModel:
    """
    Model Publish-Subscribe (Asinkron)
    - Publisher tidak perlu mengetahui Subscribers
    - Decoupled, event-driven, topic-based routing
    
    CONTOH DUNIA NYATA:
    1. Smartphone Notifications: App publish "news_update" → subscribers notified
    2. Instagram Feed: User posts photo → followers subscribed to "user_posts" get notified
    3. Smart Home: Sensor publish "temperature_high" → AC, fan subscribe & react
    """
    def __init__(self, name="Publish-Subscribe"):
        self.name = name
        self.nodes: Dict[str, Node] = {}
        self.topics: Dict[str, List[str]] = {}
        self.message_queue = queue.Queue()
        self.metrics = CommunicationMetric()
        self.lock = threading.Lock()
        self.running = True
        self.event_callback = None
        self.processor_thread = threading.Thread(target=self._message_processor, daemon=True)
        self.processor_thread.start()

    def add_node(self, node: Node):
        self.nodes[node.node_id] = node

    def subscribe(self, node_id: str, topic: str):
        """Node berlangganan topic tertentu"""
        if topic not in self.topics:
            self.topics[topic] = []
        if node_id not in self.topics[topic]:
            self.topics[topic].append(node_id)

    def publish(self, publisher_id: str, topic: str, content: str):
        """Publisher menerbitkan pesan ke topic (non-blocking)"""
        msg_id = self.metrics.total_messages + 1
        message = Message(
            sender_id=publisher_id,
            receiver_id=topic,
            content=content,
            timestamp=time.time(),
            message_id=msg_id
        )
        if self.event_callback:
            self.event_callback('publish', publisher_id, topic, content)
        self.message_queue.put((topic, message))

    def _message_processor(self):
        """Thread background: distribusikan pesan ke subscribers"""
        while self.running:
            try:
                topic, message = self.message_queue.get(timeout=0.5)
                current_time = time.time()

                if topic in self.topics:
                    for subscriber_id in self.topics[topic]:
                        if subscriber_id in self.nodes:
                            subscriber = self.nodes[subscriber_id]
                            subscriber.receive_message(message, current_time)
                            if self.event_callback:
                                self.event_callback('deliver', message.sender_id, subscriber_id, message.content)
                            subscriber.process_message(message)

                delivery_time = (time.time() - message.timestamp) * 1000
                with self.lock:
                    self.metrics.update(delivery_time, success=True)

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
        w = int(self.cget('width'))
        h = int(self.cget('height'))

        # Background gradient effect (titik-titik kecil)
        for _ in range(80):
            x = random.randint(0, w)
            y = random.randint(0, h)
            r = random.randint(1, 2)
            alpha_hex = random.choice(['e0', 'e5', 'ea'])
            self.create_oval(x-r, y-r, x+r, y+r,
                             fill=f"#{alpha_hex}{alpha_hex}{alpha_hex}",
                             outline='')

        # Gambar semua node
        for node_id, (x, y) in self.node_positions.items():
            self._draw_node(node_id, x, y)

    def _draw_node(self, node_id: str, x: float, y: float, active: bool = False):
        """Gambar satu node sebagai lingkaran berlabel"""
        r = self.NODE_RADIUS
        fill = self.accent if active else COLORS['bg_card']
        outline = self.accent
        lw = 2 if not active else 3

        # Glow effect saat aktif
        if active:
            self.create_oval(x-r-6, y-r-6, x+r+6, y+r+6,
                             fill='', outline=self.accent, width=2,
                             tags=(f"glow_{node_id}",))

        oval_id = self.create_oval(x-r, y-r, x+r, y+r,
                                   fill=fill, outline=outline, width=lw,
                                   tags=(f"node_{node_id}",))

        # Label singkat (2 baris)
        parts = node_id.split('-')
        label = parts[0] if len(parts) == 1 else f"{parts[0]}\n{'-'.join(parts[1:])}"
        self.create_text(x, y, text=label,
                         fill=COLORS['text_primary'],
                         font=("Consolas", 7, "bold"),
                         tags=(f"label_{node_id}",))
        return oval_id

    def _get_edge_point(self, x1, y1, x2, y2):
        """Hitung titik di tepi lingkaran node (bukan di tengah)"""
        r = self.NODE_RADIUS + 4
        dx = x2 - x1
        dy = y2 - y1
        dist = math.hypot(dx, dy) or 1
        return x1 + dx/dist*r, y1 + dy/dist*r

    # Animasi pengiriman pesan
    def animate_message(self, sender_id: str, receiver_id: str,
                        label: str = "msg", color: str = None):
        """Animasikan partikel pesan bergerak dari sender ke receiver"""
        try:
            if sender_id not in self.node_positions or receiver_id not in self.node_positions:
                return

            if color is None:
                color = self.accent

            sx, sy = self.node_positions[sender_id]
            rx, ry = self.node_positions[receiver_id]

            # Titik mulai dan akhir di tepi node
            x1, y1 = self._get_edge_point(sx, sy, rx, ry)
            x2, y2 = self._get_edge_point(rx, ry, sx, sy)

            # Gambar garis tipis sebagai jalur
            line_id = self.create_line(x1, y1, x2, y2,
                                       fill=color, width=1,
                                       dash=(4, 4), tags=('anim_line',))

            # Partikel pesan (lingkaran kecil)
            pr = 6
            dot_id = self.create_oval(x1-pr, y1-pr, x1+pr, y1+pr,
                                      fill=color, outline='white', width=1,
                                      tags=('anim_dot',))
            txt_id = self.create_text(x1, y1-14, text=label[:10],
                                      fill=color, font=("Consolas", 6),
                                      tags=('anim_txt',))

            # Flash node pengirim
            self._flash_node(sender_id, color)

            steps = self.ANIM_STEPS
            def step(frame_num):
                try:
                    if frame_num > steps:
                        try:
                            self.delete(dot_id)
                            self.delete(txt_id)
                            self.delete(line_id)
                        except tk.TclError:  # Canvas item already deleted
                            pass
                        self._flash_node(receiver_id, color)
                        return
                    t = frame_num / steps
                    cx = x1 + (x2-x1)*t
                    cy = y1 + (y2-y1)*t
                    try:
                        self.coords(dot_id, cx-pr, cy-pr, cx+pr, cy+pr)
                        self.coords(txt_id, cx, cy-14)
                    except tk.TclError:  # Canvas item deleted, stop animation
                        return
                    self.after(self.ANIM_DELAY, lambda: step(frame_num+1))
                except Exception:
                    pass  # Silent fail if canvas is destroyed

            step(0)
        except Exception:
            pass  # Silent fail if canvas operations fail

    def _flash_node(self, node_id: str, color: str):
        """Kedipkan node sesaat (efek aktif)"""
        try:
            items = self.find_withtag(f"node_{node_id}")
            if not items:
                return
            oid = items[0]
            try:
                self.itemconfig(oid, fill=color + 'aa')
                self.after(300, lambda: self._safe_itemconfig(oid, fill=COLORS['bg_card']))
            except tk.TclError:
                pass
        except Exception:
            pass

    def _safe_itemconfig(self, oid, **kwargs):
        """Safe itemconfig dengan error handling"""
        try:
            if kwargs.get('fill'):
                # Ensure valid 6-digit hex color
                fill_color = kwargs['fill']
                if fill_color and fill_color.startswith('#') and len(fill_color) > 7:
                    fill_color = fill_color[:7]  # Strip alpha channel
                kwargs['fill'] = fill_color
            self.itemconfig(oid, **kwargs)
        except tk.TclError:
            pass

    def highlight_node(self, node_id: str, active: bool = True):
        """Ubah warna border node"""
        items = self.find_withtag(f"node_{node_id}")
        if items:
            lw = 3 if active else 2
            self.itemconfig(items[0], width=lw)


# Konfigurasi posisi node untuk setiap diagram model
DIAGRAM_LAYOUTS = {
    'rr': {
        'ATM-Terminal-1': (90, 100),
        'ATM-Terminal-2': (90, 220),
        'Bank-Server':    (330, 160),
    },
    'ps': {
        'Temperature-Sensor': (90, 160),
        'AC-Unit':            (340, 70),
        'Fan':                (340, 160),
        'Mobile-App':         (340, 250),
    },
    'mp': {
        'Node-A': (90, 80),
        'Node-B': (310, 80),
        'Node-C': (200, 240),
    },
    'rpc': {
        'Client-RPC-1': (90, 100),
        'Client-RPC-2': (90, 220),
        'Server-RPC':   (330, 160),
    },
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
        w = int(self.cget('width'))
        h = int(self.cget('height'))

        self.create_text(w//2, 12, text=self.title,
                         fill=COLORS['text_secondary'],
                         font=("Consolas", 8, "bold"))

        if not self.data:
            return

        max_val = max(self.data.values()) or 1
        bar_area_top = 25
        bar_area_bot = h - 20
        bar_h = bar_area_bot - bar_area_top
        n = len(self.data)
        pad = 8
        bar_w = (w - pad*(n+1)) // n

        for i, (key, val) in enumerate(self.data.items()):
            bx = pad + i*(bar_w + pad)
            fill_h = int((val / max_val) * bar_h)
            by_top = bar_area_bot - fill_h

            color = MODEL_COLORS.get(key, '#0052cc')
            # Bar shadow
            self.create_rectangle(bx+2, by_top+2, bx+bar_w+2, bar_area_bot+2,
                                  fill='#e8e8e8', outline='')
            # Bar fill
            self.create_rectangle(bx, by_top, bx+bar_w, bar_area_bot,
                                  fill=color, outline=color, width=1)

            # Label nilai
            label_val = f"{val:.1f}" if val < 100 else f"{val:.0f}"
            self.create_text(bx + bar_w//2, by_top - 5,
                             text=label_val,
                             fill=color, font=("Consolas", 7))
            # Label model
            short = {'rr':'RR','ps':'PS','mp':'MP','rpc':'RPC'}.get(key, key)
            self.create_text(bx + bar_w//2, bar_area_bot + 10,
                             text=short,
                             fill=COLORS['text_secondary'],
                             font=("Consolas", 7))

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
        self.running = True  # Flag untuk thread safety
        self.models: Dict = {}
        self.diagrams: Dict[str, NetworkDiagramCanvas] = {}

        self._setup_styles()
        self._initialize_models()
        self._build_ui()

        # Setup close handler
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        # Periodik update metrik
        self._start_metric_updater()

    # Inisialisasi
    def _setup_styles(self):
        """Konfigurasi ttk styles untuk dark theme"""
        style = ttk.Style()
        style.theme_use('clam')

        style.configure('Dark.TFrame', background=COLORS['bg_dark'])
        style.configure('Panel.TFrame', background=COLORS['bg_panel'])
        style.configure('Card.TFrame', background=COLORS['bg_card'])

        style.configure('Dark.TLabel',
                        background=COLORS['bg_dark'],
                        foreground=COLORS['text_primary'],
                        font=("Consolas", 9))
        style.configure('Title.TLabel',
                        background=COLORS['bg_dark'],
                        foreground=COLORS['text_primary'],
                        font=("Consolas", 13, "bold"))
        style.configure('Sub.TLabel',
                        background=COLORS['bg_panel'],
                        foreground=COLORS['text_secondary'],
                        font=("Consolas", 8))
        style.configure('Metric.TLabel',
                        background=COLORS['bg_card'],
                        foreground=COLORS['text_primary'],
                        font=("Consolas", 10, "bold"))
        style.configure('MetricVal.TLabel',
                        background=COLORS['bg_card'],
                        foreground=COLORS['accent_rr'],
                        font=("Consolas", 11, "bold"))

        style.configure('Run.TButton',
                        background=COLORS['accent_rr'],
                        foreground='white',
                        font=("Consolas", 9, "bold"),
                        borderwidth=0)
        style.map('Run.TButton',
                  background=[('active', '#79c0ff'), ('disabled', '#30363d')],
                  foreground=[('disabled', COLORS['text_muted'])])

        style.configure('Clear.TButton',
                        background=COLORS['bg_input'],
                        foreground=COLORS['text_secondary'],
                        font=("Consolas", 9),
                        borderwidth=0)

        style.configure('Dark.TRadiobutton',
                        background=COLORS['bg_panel'],
                        foreground=COLORS['text_primary'],
                        font=("Consolas", 9),
                        indicatorcolor=COLORS['accent_rr'])
        style.map('Dark.TRadiobutton',
                  background=[('active', COLORS['bg_card'])])

        style.configure('Dark.TNotebook',
                        background=COLORS['bg_dark'],
                        borderwidth=0)
        style.configure('Dark.TNotebook.Tab',
                        background=COLORS['bg_panel'],
                        foreground=COLORS['text_secondary'],
                        font=("Consolas", 9),
                        padding=[10, 5])
        style.map('Dark.TNotebook.Tab',
                  background=[('selected', COLORS['bg_card'])],
                  foreground=[('selected', COLORS['text_primary'])])

        style.configure('Dark.TScale',
                        background=COLORS['bg_panel'],
                        troughcolor=COLORS['bg_input'],
                        sliderthickness=14)

        style.configure('Dark.TLabelframe',
                        background=COLORS['bg_panel'],
                        foreground=COLORS['text_secondary'],
                        font=("Consolas", 8),
                        borderwidth=1,
                        relief='solid')
        style.configure('Dark.TLabelframe.Label',
                        background=COLORS['bg_panel'],
                        foreground=COLORS['accent_rr'])

        style.configure('Dark.Treeview',
                        background=COLORS['bg_card'],
                        foreground=COLORS['text_primary'],
                        fieldbackground=COLORS['bg_card'],
                        font=("Consolas", 9),
                        rowheight=24)
        style.configure('Dark.Treeview.Heading',
                        background=COLORS['bg_input'],
                        foreground=COLORS['text_primary'],
                        font=("Consolas", 9, "bold"))
        style.map('Dark.Treeview',
                  background=[('selected', COLORS['accent_rr'] + '44')])

        style.configure('Dark.TSpinbox',
                        background=COLORS['bg_input'],
                        foreground=COLORS['text_primary'],
                        font=("Consolas", 9))

    def _initialize_models(self):
        """Inisialisasi 2 model komunikasi dengan real-world scenarios"""
        # --- Request-Response: ATM Scenario ---
        rr = RequestResponseModel("Request-Response")
        rr.add_node(Node("Bank-Server", "server"))
        rr.add_node(Node("ATM-Terminal-1", "client"))
        rr.add_node(Node("ATM-Terminal-2", "client"))
        self.models['rr'] = rr

        # --- Publish-Subscribe: Smart Home Scenario ---
        ps = PublishSubscribeModel("Publish-Subscribe")
        ps.add_node(Node("Temperature-Sensor", "publisher"))
        ps.add_node(Node("AC-Unit", "subscriber"))
        ps.add_node(Node("Fan", "subscriber"))
        ps.add_node(Node("Mobile-App", "subscriber"))
        ps.subscribe("AC-Unit", "temperature_alert")
        ps.subscribe("Fan", "temperature_alert")
        ps.subscribe("Mobile-App", "sensor_status")
        self.models['ps'] = ps


    # Build UI
    def _build_ui(self):
        self._build_header()
        self._build_body()

    def _build_header(self):
        header = tk.Frame(self.root, bg=COLORS['bg_panel'],
                          highlightbackground=COLORS['border'],
                          highlightthickness=1)
        header.pack(fill=tk.X, padx=0, pady=0)

        tk.Label(header,
                 text="◈  SIMULASI MODEL KOMUNIKASI SISTEM TERDISTRIBUSI  ◈",
                 bg=COLORS['bg_panel'], fg=COLORS['accent_rr'],
                 font=("Helvetica", 12, "bold")).pack(side=tk.LEFT, padx=20, pady=10)

        # Badge model warna
        for key, label, color in [
            ('rr',  'Request-Response', COLORS['accent_rr']),
            ('ps',  'Pub-Subscribe',    COLORS['accent_ps']),
            ('mp',  'Msg Passing',      COLORS['accent_mp']),
            ('rpc', 'RPC',              COLORS['accent_rpc']),
        ]:
            tk.Label(header, text=f"● {label}",
                     bg=COLORS['bg_panel'], fg=color,
                     font=("Helvetica", 8)).pack(side=tk.LEFT, padx=8, pady=10)

    def _build_body(self):
        body = tk.Frame(self.root, bg=COLORS['bg_dark'])
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        # Kiri: panel kontrol
        self._build_left_panel(body)

        # Kanan: notebook tab
        self._build_right_panel(body)

    def _build_left_panel(self, parent):
        left = tk.Frame(parent, bg=COLORS['bg_panel'],
                        highlightbackground=COLORS['border'],
                        highlightthickness=1, width=210)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        left.pack_propagate(False)

        def section(text):
            tk.Label(left, text=text,
                     bg=COLORS['bg_panel'], fg=COLORS['accent_rr'],
                     font=("Helvetica", 8, "bold")).pack(anchor=tk.W, padx=12, pady=(12, 4))
            tk.Frame(left, bg=COLORS['border'], height=1).pack(fill=tk.X, padx=12)

        # --- Model selection ---
        section("▸ MODEL KOMUNIKASI")
        self.model_var = tk.StringVar(value="rr")
        for key, label, color in [
            ('rr',  '⬡ Request-Response',      COLORS['accent_rr']),
            ('ps',  '⬡ Publish-Subscribe',      COLORS['accent_ps']),
        ]:
            rb = tk.Radiobutton(
                left, text=label, variable=self.model_var, value=key,
                command=self._on_model_changed,
                bg=COLORS['bg_panel'], fg=color,
                selectcolor=COLORS['bg_card'],
                activebackground=COLORS['bg_card'],
                activeforeground=color,
                font=("Helvetica", 8),
                indicatoron=True, bd=0, pady=2
            )
            rb.pack(anchor=tk.W, padx=16, pady=2)

        # --- Kontrol simulasi ---
        section("▸ KONTROL SIMULASI")

        tk.Label(left, text="Kecepatan (msg/sec):",
                 bg=COLORS['bg_panel'], fg=COLORS['text_secondary'],
                 font=("Helvetica", 8)).pack(anchor=tk.W, padx=12, pady=(8, 0))
        self.speed_var = tk.IntVar(value=5)
        speed_scale = tk.Scale(left, from_=1, to=20,
                               orient=tk.HORIZONTAL,
                               variable=self.speed_var,
                               bg=COLORS['bg_panel'], fg=COLORS['text_primary'],
                               highlightbackground=COLORS['bg_panel'],
                               troughcolor=COLORS['bg_input'],
                               activebackground=COLORS['accent_rr'],
                               font=("Helvetica", 7))
        speed_scale.pack(fill=tk.X, padx=12)

        tk.Label(left, text="Jumlah Pesan:",
                 bg=COLORS['bg_panel'], fg=COLORS['text_secondary'],
                 font=("Helvetica", 8)).pack(anchor=tk.W, padx=12, pady=(8, 2))
        self.msg_count_var = tk.StringVar(value="8")
        count_spin = tk.Spinbox(
            left, from_=1, to=50, textvariable=self.msg_count_var,
            bg=COLORS['bg_input'], fg=COLORS['text_primary'],
            insertbackground=COLORS['text_primary'],
            highlightbackground=COLORS['border'],
            font=("Helvetica", 9), width=8, bd=0
        )
        count_spin.pack(padx=12, pady=(0, 8))

        # Buttons
        self.run_btn = tk.Button(
            left, text="▶  JALANKAN SIMULASI",
            command=self._run_simulation,
            bg=COLORS['accent_rr'], fg='white',
            font=("Helvetica", 9, "bold"),
            relief=tk.FLAT, bd=0, padx=10, pady=7,
            activebackground='#79c0ff', cursor='hand2'
        )
        self.run_btn.pack(fill=tk.X, padx=12, pady=(4, 4))

        tk.Button(
            left, text="⬛  BERSIHKAN LOG",
            command=self._clear_logs,
            bg=COLORS['bg_input'], fg=COLORS['text_secondary'],
            font=("Helvetica", 8), relief=tk.FLAT, bd=0, padx=10, pady=6,
            activebackground=COLORS['bg_card'], cursor='hand2'
        ).pack(fill=tk.X, padx=12, pady=2)

        tk.Button(
            left, text="⟳  RESET METRIK",
            command=self._reset_metrics,
            bg=COLORS['bg_input'], fg=COLORS['text_secondary'],
            font=("Helvetica", 8), relief=tk.FLAT, bd=0, padx=10, pady=6,
            activebackground=COLORS['bg_card'], cursor='hand2'
        ).pack(fill=tk.X, padx=12, pady=2)

        # --- Status ---
        section("▸ STATUS")
        self.status_var = tk.StringVar(value="● Idle — siap menjalankan simulasi")
        tk.Label(left, textvariable=self.status_var,
                 bg=COLORS['bg_panel'], fg=COLORS['text_secondary'],
                 font=("Helvetica", 7), wraplength=180,
                 justify=tk.LEFT).pack(anchor=tk.W, padx=12, pady=6)

        # --- Info model ---
        section("▸ KETERANGAN")
        self.info_var = tk.StringVar(value="")
        tk.Label(left, textvariable=self.info_var,
                 bg=COLORS['bg_panel'], fg=COLORS['text_muted'],
                 font=("Helvetica", 7), wraplength=180,
                 justify=tk.LEFT).pack(anchor=tk.W, padx=12, pady=4)
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
        tk.Label(p, text="ANALISIS OTOMATIS",
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
    def _attach_callbacks(self):
        """Hubungkan callback animasi dari model ke diagram"""
        def make_cb(model_key):
            def cb(event_type, from_id, to_id, content):
                diagram = self.diagrams.get(model_key)
                if diagram:
                    short = str(content)[:12]
                    self.root.after(0, lambda: diagram.animate_message(
                        from_id, to_id, label=short,
                        color=MODEL_COLORS[model_key]
                    ))
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
        atm_terminals = ["ATM-Terminal-1", "ATM-Terminal-2"]
        for i in range(msg_count):
            atm = atm_terminals[i % 2]
            req = f"Withdrawal: Rp {(i+1)*100000:,}"
            resp = model.send_request(atm, "Bank-Server", req)
            self._log(f"  [RR] {atm} → Bank-Server : {req}", 'rr')
            self._log(f"       ← {resp[:50]}", 'rr')
            time.sleep(delay)

    def _sim_ps(self, model, msg_count, delay):
        half = max(msg_count // 2, 1)
        for i in range(half):
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
        # Kosongkan tabel
        for row in self.compare_tree.get_children():
            self.compare_tree.delete(row)

        model_info = {
            'rr':  ("Request-Response", "Ya"),
            'ps':  ("Publish-Subscribe", "Tidak"),
        }

        lat_data = {}
        thr_data = {}
        tot_data = {}

        for key, (name, sinkron) in model_info.items():
            m = self.models[key].metrics
            total     = m.total_messages
            avg_lat   = f"{m.avg_latency:.2f}" if total > 0 else "—"
            min_lat   = f"{m.min_latency:.2f}" if m.min_latency < float('inf') else "—"
            max_lat   = f"{m.max_latency:.2f}" if total > 0 else "—"
            thr       = f"{m.throughput:.2f}" if total > 0 else "—"
            success   = f"{(m.success_count/(total or 1))*100:.1f}" if total > 0 else "—"

            self.compare_tree.insert('', tk.END, values=(
                name, total, avg_lat, min_lat, max_lat, thr, success, sinkron
            ), tags=(key,))

            self.compare_tree.tag_configure(key, foreground=MODEL_COLORS[key])

            if total > 0:
                lat_data[key] = m.avg_latency
                thr_data[key] = m.throughput
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
            txt.insert(tk.END,
                       "Belum ada data. Jalankan simulasi pada setiap model terlebih dahulu, "
                       "lalu klik 'Perbarui Perbandingan'.")
            txt.configure(state=tk.DISABLED)
            return

        fastest = min(lat, key=lat.get)
        slowest = max(lat, key=lat.get)
        highest_thr = max(thr, key=thr.get) if thr else None

        names = {
            'rr':'Request-Response','ps':'Pub-Subscribe',
            'mp':'Message Passing','rpc':'RPC'
        }

        txt.insert(tk.END, f"• Model dengan latency TERENDAH: ", "info")
        txt.insert(tk.END, f"{names[fastest]} ({lat[fastest]:.2f} ms)\n", fastest)

        txt.insert(tk.END, f"• Model dengan latency TERTINGGI: ", "info")
        txt.insert(tk.END, f"{names[slowest]} ({lat[slowest]:.2f} ms)\n", slowest)

        if highest_thr:
            txt.insert(tk.END, f"• Throughput TERTINGGI: ", "info")
            txt.insert(tk.END, f"{names[highest_thr]} ({thr[highest_thr]:.2f} msg/s)\n", highest_thr)

        sinkron = [k for k in lat if k in ('rr', 'rpc')]
        asinkron = [k for k in lat if k in ('ps', 'mp')]
        if sinkron and asinkron:
            avg_s = sum(lat[k] for k in sinkron) / len(sinkron)
            avg_a = sum(lat[k] for k in asinkron) / len(asinkron)
            winner = "SINKRON" if avg_s < avg_a else "ASINKRON"
            txt.insert(tk.END,
                       f"• Avg latency Sinkron: {avg_s:.2f} ms vs Asinkron: {avg_a:.2f} ms "
                       f"→ model {winner} lebih cepat dalam simulasi ini.\n", "info")

        txt.configure(state=tk.DISABLED)

    # Utilitas
    def _log(self, message: str, tag: str = "info"):
        """Tulis ke log dengan timestamp"""
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        line = f"[{ts}] {message}\n"

        def insert():
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, line, tag)
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)
        self.root.after(0, insert)

    def _clear_logs(self):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)
        self._log("Log dibersihkan.", "info")

    def _reset_metrics(self):
        for model in self.models.values():
            model.metrics.reset()
        self._log("Semua metrik direset.", "warn")
        self._update_metrics_display()

    def _start_metric_updater(self):
        """Perbarui tampilan metrik setiap 500ms"""
        def loop():
            while self.running:
                try:
                    self.root.after(0, self._update_metrics_display)
                    time.sleep(0.5)
                except Exception:
                    pass  # Silent fail if root is destroyed
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
        m = self.models[key].metrics
        color = MODEL_COLORS[key]

        vals = {
            "total":      str(m.total_messages),
            "latency":    f"{m.avg_latency:.2f}" if m.total_messages > 0 else "—",
            "min_lat":    f"{m.min_latency:.2f}" if m.min_latency < float('inf') else "—",
            "max_lat":    f"{m.max_latency:.2f}" if m.total_messages > 0 else "—",
            "throughput": f"{m.throughput:.2f}" if m.total_messages > 0 else "—",
            "success":    f"{(m.success_count/max(m.total_messages,1))*100:.1f}" if m.total_messages > 0 else "—",
        }
        for k, v in vals.items():
            self.metric_cards[k].configure(text=v, fg=color)


# BAGIAN 6: ENTRY POINT
if __name__ == "__main__":
    root = tk.Tk()
    app = DistributedSystemSimulatorGUI(root)
    root.mainloop()