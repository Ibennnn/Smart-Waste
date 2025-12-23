import customtkinter as ctk
import time
import threading
import socket
from ultralytics import YOLO
import cv2

# ================= GLOBAL THEME =================
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("green")

# ================= GPIO (Raspberry Pi) =================
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

# ===================== YOLO IMPORT =====================
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

try:
    import cv2
    from PIL import Image, ImageTk
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# ===================== WASTE MAPPING =====================
B3_ITEMS = [
    "cell phone", "laptop", "remote", "tv", "mouse", "refrigerator"
]
WASTE_MAP = {
    "ORGANIK": [
        "banana", "apple", "orange", "broccoli", "carrot",
        "sandwich", "hot dog", "pizza", "donut", "cake"
    ],
    "B3": B3_ITEMS,
    "ANORGANIK": [
        "bottle", "cup", "fork", "spoon", "knife", "scissors",
        "toothbrush", "keyboard", "microwave", "oven",
        "toaster", "clock", "vase"
    ]
}
WASTE_COLOR = {
    "ORGANIK": (0, 165, 255),   # ORANGE
    "ANORGANIK": (0, 255, 0),   # GREEN
    "B3": (255, 0, 0),          # RED
    "NON": (120, 120, 120)
}

# ================= SERVO CONTROLLER =================
class LidController:
    SERVO_PINS = {
        "organik": 17,
        "anorganik": 27,
        "b3": 22
    }
    def __init__(self):
        self.status = {k: "tutup" for k in self.SERVO_PINS}
        if GPIO_AVAILABLE:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            self.servo = {}
            for jenis, pin in self.SERVO_PINS.items():
                GPIO.setup(pin, GPIO.OUT)
                pwm = GPIO.PWM(pin, 50)
                pwm.start(0)
                self.servo[jenis] = pwm
        else:
            self.servo = {}

    def set_angle(self, jenis, angle):
        if not GPIO_AVAILABLE:
            print(f"[SIMULASI] {jenis} → angle {angle}")
            return
        duty = 2 + (angle / 100) * 10
        self.servo[jenis].ChangeDutyCycle(duty)
        time.sleep(0.2)
        self.servo[jenis].ChangeDutyCycle(0)

    def buka(self, jenis):
        self.set_angle(jenis, 80)
        self.status[jenis] = "buka"

    def tutup(self, jenis):
        self.set_angle(jenis, 20)
        self.status[jenis] = "tutup"

# ================= ULTRASONIC MONITOR =================
class CapacityMonitor:
    ULTRASONIC = {
        "organik": {"trig": 5, "echo": 6},
        "anorganik": {"trig": 13, "echo": 19},
        "b3": {"trig": 20, "echo": 21}
    }
    TINGGI_BAK = 25   # cm

    def __init__(self):
        if GPIO_AVAILABLE:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            for u in self.ULTRASONIC.values():
                GPIO.setup(u["trig"], GPIO.OUT)
                GPIO.setup(u["echo"], GPIO.IN)
                GPIO.output(u["trig"], False)

    def get_distance(self, trig, echo):
        if not GPIO_AVAILABLE:
            return round(5 + (time.time() % 20), 1)
        GPIO.output(trig, True)
        time.sleep(0.00001)
        GPIO.output(trig, False)
        start = time.time()
        while GPIO.input(echo) == 0:
            if time.time() - start > 0.03:
                return None
        t1 = time.time()
        while GPIO.input(echo) == 1:
            if time.time() - t1 > 0.03:
                return None
        t2 = time.time()
        return round((t2 - t1) * 17150, 1)

    def read_all(self):
        data = {}
        for jenis, u in self.ULTRASONIC.items():
            data[jenis] = self.get_distance(u["trig"], u["echo"])
        return data

    def get_percentage(self, distance):
        if distance is None:
            return 0
        filled = self.TINGGI_BAK - distance
        return max(0, min(100, int((filled / self.TINGGI_BAK) * 100)))

# ===================== UI PAGES =====================

class HomePage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.pack(fill="both", expand=True)
        self.build_ui()

    def build_ui(self):
        main = ctk.CTkFrame(self, fg_color="#66bb6a")
        main.pack(fill="both", expand=True)
        content = ctk.CTkFrame(main, width=1100, height=520, fg_color="#e8f5e9", corner_radius=20)
        content.place(relx=0.5, rely=0.5, anchor="center")
        # LEFT PANEL
        left = ctk.CTkFrame(content, width=520, height=480, fg_color="white", corner_radius=20)
        left.place(x=20, y=20)
        ctk.CTkLabel(left, text="Recycling\nIs The Future", font=("Segoe UI", 40, "bold"), text_color="#1b5e20", justify="left").place(x=40, y=60)
        ctk.CTkLabel(left, text=(
            "Aplikasi pemilah sampah otomatis berbasis teknologi\n"
            "cerdas untuk memilah sampah organik, anorganik,\n"
            "dan B3 secara efisien dan berkelanjutan."
        ), font=("Segoe UI", 15), text_color="#2e7d32", justify="left").place(x=40, y=180)
        ctk.CTkButton(left, text="READ MORE", command=self.app.show_readmore, fg_color="#43a047", hover_color="#2e7d32", font=("Segoe UI", 14, "bold"), width=160, height=45).place(x=40, y=280)
        # RIGHT PANEL
        right = ctk.CTkFrame(content, width=520, height=480, fg_color="transparent")
        right.place(x=580, y=20)
        bins = [("♻️", "ORGANIC", "#2e7d32"), ("🧴", "ANORGANIK", "#f9a825"), ("☣️", "B3", "#c62828")]
        x_positions = [40, 200, 360]
        for i, (icon, label, color) in enumerate(bins):
            card = ctk.CTkFrame(right, width=140, height=260, fg_color=color, corner_radius=20)
            card.place(x=x_positions[i], y=130)
            ctk.CTkLabel(card, text=icon, font=("Segoe UI Emoji", 50), text_color="white").place(relx=0.5, y=90, anchor="center")
            ctk.CTkLabel(card, text=label, font=("Segoe UI", 14, "bold"), text_color="white").place(relx=0.5, y=200, anchor="center")

class ReadMorePage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.pack(fill="both", expand=True)
        self.build_ui()

    def build_ui(self):
        main = ctk.CTkFrame(self, fg_color="#66bb6a")
        main.pack(fill="both", expand=True)
        content = ctk.CTkFrame(main, width=1100, height=560, fg_color="#e8f5e9", corner_radius=25)
        content.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(content, text="ABOUT SMART WASTE SORTING SYSTEM", font=("Segoe UI", 30, "bold"), text_color="#1b5e20").pack(pady=(25, 15))
        box = ctk.CTkFrame(content, fg_color="white", corner_radius=20)
        box.pack(padx=40, pady=10, fill="both", expand=True)
        description = (
            "Smart Waste Sorting System merupakan sebuah aplikasi pemilah sampah otomatis "
            "berbasis kecerdasan buatan (Artificial Intelligence) yang dirancang untuk "
            "meningkatkan efisiensi dan akurasi dalam proses pengelompokan sampah.\n\n"
            "Sistem ini mengintegrasikan teknologi Computer Vision menggunakan algoritma "
            "YOLOv8 untuk mendeteksi dan mengklasifikasikan jenis sampah secara real-time "
            "melalui kamera. Sampah yang terdeteksi akan dikategorikan ke dalam tiga "
            "kelompok utama, yaitu sampah Organik, Anorganik, dan B3 (Bahan Berbahaya dan "
            "Beracun).\n\n"
            "Untuk mendukung proses pengelolaan yang optimal, sistem dilengkapi dengan "
            "sensor ultrasonik yang berfungsi untuk memantau kapasitas setiap bak sampah. "
            "Informasi tingkat kepenuhan bak ditampilkan dalam bentuk persentase dan "
            "indikator status sehingga memudahkan pengguna dalam melakukan pengosongan "
            "sampah secara tepat waktu.\n\n"
            "Aplikasi ini dibangun menggunakan bahasa pemrograman Python dengan antarmuka "
            "grafis berbasis CustomTkinter yang modern dan responsif. Selain itu, sistem "
            "dirancang agar dapat berjalan baik pada komputer maupun perangkat "
            "Raspberry Pi, sehingga fleksibel untuk diimplementasikan pada berbagai "
            "skala lingkungan seperti kampus, sekolah, maupun area publik.\n\n"
            "Dengan adanya Smart Waste Sorting System, diharapkan dapat meningkatkan "
            "kesadaran masyarakat terhadap pentingnya pengelolaan sampah yang benar, "
            "mengurangi kesalahan pemilahan, serta mendukung terciptanya lingkungan "
            "yang bersih, sehat, dan berkelanjutan."
        )
        ctk.CTkLabel(box, text=description, font=("Segoe UI", 15), text_color="#2e7d32", justify="left", wraplength=980).pack(padx=30, pady=30)
        ctk.CTkButton(content, text="BACK TO HOME", command=self.app.show_home, fg_color="#43a047", hover_color="#2e7d32", font=("Segoe UI", 14, "bold"), width=180, height=45).pack(pady=(10, 20))

class LidPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.pack(fill="both", expand=True)
        if not hasattr(self.app, "lid_controller"):
            self.app.lid_controller = LidController()
        self.build_ui()

    def build_ui(self):
        main = ctk.CTkFrame(self, fg_color="#66bb6a")
        main.pack(fill="both", expand=True)
        container = ctk.CTkFrame(main, width=1100, height=520, fg_color="#f1f8e9", corner_radius=25)
        container.place(relx=0.5, rely=0.5, anchor="center")
        title = ctk.CTkLabel(container, text="LID CONTROL SYSTEM", font=("Segoe UI", 28, "bold"), text_color="#1b5e20")
        title.pack(pady=20)
        card_area = ctk.CTkFrame(container, fg_color="transparent")
        card_area.pack(expand=True)
        bins = [("🍃 ORGANIK", "organik", "#2e7d32"), ("🧴 ANORGANIK", "anorganik", "#f9a825"), ("☣️ B3", "b3", "#c62828")]
        for name, key, color in bins:
            self.create_bin_card(card_area, name, key, color)

    def create_bin_card(self, parent, title, key, color):
        card = ctk.CTkFrame(parent, width=300, height=320, fg_color="white", corner_radius=20)
        card.pack(side="left", padx=15, pady=10)
        ctk.CTkLabel(card, text=title, font=("Segoe UI", 18, "bold"), text_color=color).pack(pady=15)
        status_label = ctk.CTkLabel(card, text="Status: TUTUP", font=("Segoe UI", 14), text_color="#424242")
        status_label.pack(pady=5)
        slider = ctk.CTkSlider(card, from_=0, to=100, width=220, command=lambda v: self.on_slider(key, v))
        slider.set(20)
        slider.pack(pady=15)
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(pady=10)
        ctk.CTkButton(btn_frame, text="BUKA", fg_color="#43a047", width=90, command=lambda: self.open_lid(key, status_label, slider)).pack(side="left", padx=8)
        ctk.CTkButton(btn_frame, text="TUTUP", fg_color="#e53935", width=90, command=lambda: self.close_lid(key, status_label, slider)).pack(side="left", padx=8)

    def on_slider(self, jenis, value):
        self.app.lid_controller.set_angle(jenis, value)

    def open_lid(self, jenis, label, slider):
        slider.set(80)
        self.app.lid_controller.buka(jenis)
        label.configure(text="Status: BUKA")

    def close_lid(self, jenis, label, slider):
        slider.set(20)
        self.app.lid_controller.tutup(jenis)
        label.configure(text="Status: TUTUP")

class CapacityPage(ctk.CTkFrame):
    def __init__(self, parent, app=None):
        super().__init__(parent)
        self.app = app
        self.pack(fill="both", expand=True)
        self.monitor = CapacityMonitor()
        self.cards = {}
        self.build_ui()
        self.update_data()

    def build_ui(self):
        main = ctk.CTkFrame(self, fg_color="#66bb6a")
        main.pack(fill="both", expand=True)
        container = ctk.CTkFrame(main, width=1150, height=560, fg_color="#f1f8e9", corner_radius=30)
        container.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(container, text="WASTE CAPACITY MONITOR", font=("Segoe UI", 30, "bold"), text_color="#1b5e20").pack(pady=(25, 10))
        area = ctk.CTkFrame(container, fg_color="transparent")
        area.pack(expand=True, pady=20)
        bins = [("🍃 ORGANIK", "organik", "#2e7d32"), ("🧴 ANORGANIK", "anorganik", "#f9a825"), ("☣️ B3", "b3", "#c62828")]
        for title, key, color in bins:
            self.create_card(area, title, key, color)

    def create_card(self, parent, title, key, color):
        card = ctk.CTkFrame(parent, width=320, height=400, fg_color="white", corner_radius=25)
        card.pack(side="left", padx=25)
        ctk.CTkLabel(card, text=title, font=("Segoe UI", 20, "bold"), text_color=color).pack(pady=(20, 5))
        percent = ctk.CTkLabel(card, text="0%", font=("Segoe UI", 36, "bold"), text_color="#263238")
        percent.pack(pady=(0, 10))
        bar_container = ctk.CTkFrame(card, width=70, height=220, fg_color="#eeeeee", corner_radius=15)
        bar_container.pack(pady=10)
        bar = ctk.CTkProgressBar(bar_container, orientation="vertical", height=200, width=30, corner_radius=10, progress_color=color)
        bar.set(0)
        bar.place(relx=0.5, rely=0.5, anchor="center")
        status = ctk.CTkLabel(card, text="AMAN", font=("Segoe UI", 14, "bold"), width=150, height=32, corner_radius=12, fg_color="#e8f5e9", text_color="#2e7d32")
        status.pack(pady=(15, 8))
        distance = ctk.CTkLabel(card, text="-- cm", font=("Segoe UI", 13), text_color="#616161")
        distance.pack()
        self.cards[key] = {
            "percent": percent,
            "bar": bar,
            "status": status,
            "distance": distance
        }

    def update_data(self):
        data = self.monitor.read_all()
        for jenis, jarak in data.items():
            card = self.cards.get(jenis)
            if not card or jarak is None:
                continue
            persen = self.monitor.get_percentage(jarak)
            card["percent"].configure(text=f"{persen}%")
            card["bar"].set(persen / 100)
            card["distance"].configure(text=f"{jarak} cm")
            if persen >= 85:
                card["status"].configure(text="PENUH", fg_color="#ffebee", text_color="#c62828")
            elif persen >= 65:
                card["status"].configure(text="HAMPIR PENUH", fg_color="#fff8e1", text_color="#f9a825")
            else:
                card["status"].configure(text="AMAN", fg_color="#e8f5e9", text_color="#2e7d32")
        self.after(1200, self.update_data)

class AboutPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill="both", expand=True)
        ctk.CTkLabel(self, text="ABOUT US", font=("Segoe UI", 32, "bold")).pack(pady=40)
        ctk.CTkLabel(self, text="Smart Waste Sorting System berbasis AI & IoT.", font=("Segoe UI", 16), justify="center").pack()

# ===================== CAMERA PAGE =====================
class CameraPage(ctk.CTkFrame):
    RASPBERRY_IP = "192.168.137.33"
    PORT = 65432

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.pack(fill="both", expand=True)
        self.running = False
        self.cap = None
        self.camera_image = None
        self.connected = False
        self.sock = None  # <--- Tambahkan ini

        if YOLO_AVAILABLE:
            self.model = YOLO("yolov8n.pt")
        else:
            self.model = None

        self.build_ui()
        threading.Thread(target=self.try_connect_raspberry, daemon=True).start()

    def build_ui(self):
        main = ctk.CTkFrame(self, fg_color="#66bb6a")
        main.pack(fill="both", expand=True)

        content = ctk.CTkFrame(
            main, width=1100, height=520,
            fg_color="#e8f5e9", corner_radius=20
        )
        content.place(relx=0.5, rely=0.5, anchor="center")

        # ===== LEFT PANEL =====
        left = ctk.CTkFrame(
            content, width=420, height=480,
            fg_color="white", corner_radius=20
        )
        left.place(x=20, y=20)

        ctk.CTkLabel(
            left,
            text="AI Waste\nSorting Camera",
            font=("Segoe UI", 32, "bold"),
            text_color="#1b5e20",
            justify="left"
        ).place(x=30, y=40)

        ctk.CTkLabel(
            left,
            text=(
                "Deteksi otomatis sampah:\n"
                "• Organik\n"
                "• Anorganik\n"
                "• B3 (Elektronik)\n\n"
                "YOLOv8 + Rule Based System"
            ),
            font=("Segoe UI", 15),
            text_color="#2e7d32",
            justify="left"
        ).place(x=30, y=150)

        self.status_label = ctk.CTkLabel(
            left, text="Status: Menghubungkan ke Raspberry Pi...",
            font=("Segoe UI", 14, "bold"),
            text_color="#fbc02d"
        )
        self.status_label.place(x=30, y=300)

        self.start_btn = ctk.CTkButton(
            left, text="START CAMERA",
            fg_color="#43a047",
            hover_color="#2e7d32",
            font=("Segoe UI", 14, "bold"),
            width=180, height=45,
            command=self.start_camera,
            state="disabled"
        )
        self.start_btn.place(x=30, y=340)

        self.stop_btn = ctk.CTkButton(
            left, text="STOP CAMERA",
            fg_color="#c62828",
            hover_color="#8e0000",
            font=("Segoe UI", 14, "bold"),
            width=180, height=45,
            state="disabled",
            command=self.stop_camera
        )
        self.stop_btn.place(x=230, y=340)

        # ===== RIGHT PANEL =====
        right = ctk.CTkFrame(
            content, width=620, height=480,
            fg_color="black", corner_radius=20
        )
        right.place(x=460, y=20)

        self.camera_label = ctk.CTkLabel(
            right,
            text="Camera Not Started",
            font=("Segoe UI", 18),
            text_color="white"
        )
        self.camera_label.place(relx=0.5, rely=0.5, anchor="center")

    def try_connect_raspberry(self):
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            def set_status(text, color):
                if self.status_label.winfo_exists():
                    self.status_label.configure(text=text, text_color=color)
            self.status_label.after(0, set_status, "Status: Menghubungkan ke Raspberry Pi...", "#fbc02d")
            client.settimeout(5)
            client.connect((self.RASPBERRY_IP, self.PORT))
            # Handshake: kirim "HELLO", tunggu balasan "OK"
            client.sendall(b"HELLO")
            resp = client.recv(1024)
            if resp != b"OK":
                raise Exception("Handshake gagal")
            self.connected = True
            self.sock = client  # <--- Simpan socket di self.sock

            # Update UI di thread utama
            def enable_start():
                if self.start_btn.winfo_exists():
                    self.start_btn.configure(state="normal")
            self.status_label.after(0, set_status, "Status: Terhubung ke Raspberry Pi", "#43a047")
            self.start_btn.after(0, enable_start)
            return
        except Exception:
            self.connected = False
            def disable_start():
                if self.start_btn.winfo_exists():
                    self.start_btn.configure(state="disabled")
            self.status_label.after(0, set_status, "Status: Tidak terhubung ke Raspberry Pi", "#c62828")
            self.start_btn.after(0, disable_start)
            client.close()

    def process_frame(self, frame):
        if not self.model:
            return "non", frame
        results = self.model(frame, verbose=False)
        for r in results:
            for box in r.boxes:
                if float(box.conf[0]) < 0.5:
                    continue
                cls_id = int(box.cls[0])
                class_name = self.model.names[cls_id]
                for waste_type, items in WASTE_MAP.items():
                    if class_name in items:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        import cv2
                        cv2.rectangle(frame, (x1, y1), (x2, y2), WASTE_COLOR[waste_type], 2)
                        cv2.putText(frame, f"{waste_type} ({class_name})", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, WASTE_COLOR[waste_type], 2)
                        return waste_type.lower(), frame  # <--- ubah ke lowercase
        return "non", frame

    def camera_loop(self):
        import cv2
        from PIL import Image, ImageTk
        self.cap = cv2.VideoCapture(0)
        sock = self.sock  # <--- Pakai socket yang sudah terhubung
        last_sent = None
        last_time = 0

        while self.running and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                break
            waste_type, frame = self.process_frame(frame)
            # Kirim perintah ke Raspberry Pi jika terdeteksi
            if sock and waste_type in ["organik", "anorganik", "b3"]:
                now = time.time()
                if waste_type != last_sent or now - last_time > 3:
                    cmd = f"BUKA:{waste_type}"
                    try:
                        sock.sendall(cmd.encode())
                        print("📤 Kirim ke Raspberry:", cmd)
                        last_sent = waste_type
                        last_time = now
                    except Exception as e:
                        print("❌ Socket error:", e)
                        break
                # Tampilkan info di frame
                cv2.putText(
                    frame,
                    f"SEND: BUKA:{waste_type}",
                    (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 0),
                    2
                )
            cv2.putText(frame, f"DETEKSI: {waste_type}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, WASTE_COLOR.get(waste_type.upper(), (0,255,0)), 2)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame).resize((600, 450))
            self.camera_image = ImageTk.PhotoImage(img)
            self.camera_label.configure(image=self.camera_image, text="")
            time.sleep(0.01)
        if self.cap:
            self.cap.release()
            self.cap = None
        if self.sock:
            self.sock.close()
            self.sock = None
        self.cleanup()

    def start_camera(self):
        if not self.connected:
            self.status_label.configure(text="Status: Tidak terhubung ke Raspberry Pi", text_color="#c62828")
            return
        if self.running:
            return
        self.running = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        threading.Thread(target=self.camera_loop, daemon=True).start()
        # self.connect_to_raspberry() # Hapus jika tidak ingin input manual

    def stop_camera(self):
        self.running = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def cleanup(self):
        if self.cap:
            self.cap.release()
            self.cap = None

    def connect_to_raspberry(self):
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            print("🔌 Menghubungkan ke Raspberry Pi...")
            client.connect((self.RASPBERRY_IP, self.PORT))
            print("✅ Terhubung ke Raspberry Pi")

            while self.running:
                # ================= SIMULASI OUTPUT YOLO =================
                # GANTI bagian ini dengan hasil YOLO kamu
                label = input("Masukkan hasil YOLO (organik / anorganik / b3 / exit): ").strip().lower()

                if label == "exit":
                    print("❌ Koneksi ditutup")
                    break

                if label not in ["organik", "anorganik", "b3"]:
                    print("⚠️ Label tidak valid")
                    continue

                client.sendall(label.encode())
                print(f"📤 Dikirim ke Raspberry Pi: {label}")

                time.sleep(0.5)

        except ConnectionRefusedError:
            print("❌ Gagal terhubung. Pastikan Raspberry Pi sudah running.")
        except Exception as e:
            print(f"⚠️ Error: {e}")
        finally:
            client.close()

# ===================== MAIN APP =====================
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Smart Waste Sorting System")
        self.geometry("1200x650")
        self.resizable(False, False)
        self.build_navbar()
        self.content_frame = ctk.CTkFrame(self, fg_color="#66bb6a")
        self.content_frame.pack(fill="both", expand=True)
        self.current_page = None
        self.show_home()

    def build_navbar(self):
        navbar = ctk.CTkFrame(self, height=60, fg_color="#43a047", corner_radius=0)
        navbar.pack(fill="x", side="top")
        ctk.CTkLabel(navbar, text="SMART RECYCLE", font=("Segoe UI", 20, "bold"), text_color="white").pack(side="left", padx=30)
        menu = ctk.CTkFrame(navbar, fg_color="transparent")
        menu.pack(side="right", padx=30)
        self.nav_btn(menu, "Home", self.show_home)
        self.nav_btn(menu, "Lid", self.show_lid)
        self.nav_btn(menu, "Capacity", self.show_capacity)
        self.nav_btn(menu, "About Us", self.show_about)
        ctk.CTkButton(menu, text="CAMERA", command=self.show_camera, fg_color="#fbc02d", hover_color="#fdd835", text_color="black", font=("Segoe UI", 14, "bold"), width=110).pack(side="left", padx=10)
        # Tambahkan tombol EXIT di sini
        ctk.CTkButton(menu, text="EXIT", command=self.quit, fg_color="#e53935", hover_color="#b71c1c", text_color="white", font=("Segoe UI", 14, "bold"), width=90).pack(side="left", padx=10)

    def nav_btn(self, parent, text, cmd):
        ctk.CTkButton(parent, text=text, command=cmd, fg_color="transparent", hover_color="#66bb6a", text_color="white", font=("Segoe UI", 14), width=100).pack(side="left", padx=8)

    def clear_page(self):
        if self.current_page:
            self.current_page.destroy()
            self.current_page = None

    def show_home(self):
        self.clear_page()
        self.current_page = HomePage(self.content_frame, self)

    def show_camera(self):
        self.clear_page()
        self.current_page = CameraPage(self.content_frame, self)

    def show_lid(self):
        self.clear_page()
        self.current_page = LidPage(self.content_frame, self)

    def show_capacity(self):
        self.clear_page()
        self.current_page = CapacityPage(self.content_frame, self)

    def show_about(self):
        self.clear_page()
        self.current_page = AboutPage(self.content_frame)

    def show_readmore(self):
        self.clear_page()
        self.current_page = ReadMorePage(self.content_frame, self)

# ================= RUN APP =================
if __name__ == "__main__":
    app = App()
    app.mainloop()

    # ================= SOCKET SERVER (Raspberry Pi) =================
    import socket
    import time

    HOST = "0.0.0.0"
    PORT = 65432

    # ================= SERVO CONTROLLER =================
    class LidController:
        SERVO_PINS = {
            "organik": 17,
            "anorganik": 27,
            "b3": 22
        }
        def __init__(self):
            self.status = {k: "tutup" for k in self.SERVO_PINS}
            if GPIO_AVAILABLE:
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                self.servo = {}
                for jenis, pin in self.SERVO_PINS.items():
                    GPIO.setup(pin, GPIO.OUT)
                    pwm = GPIO.PWM(pin, 50)
                    pwm.start(0)
                    self.servo[jenis] = pwm
            else:
                self.servo = {}

        def set_angle(self, jenis, angle):
            if not GPIO_AVAILABLE:
                print(f"[SIMULASI] {jenis} → angle {angle}")
                return
            duty = 2 + (angle / 100) * 10
            self.servo[jenis].ChangeDutyCycle(duty)
            time.sleep(0.2)
            self.servo[jenis].ChangeDutyCycle(0)

        def buka(self, jenis):
            self.set_angle(jenis, 80)
            self.status[jenis] = "buka"

        def tutup(self, jenis):
            self.set_angle(jenis, 20)
            self.status[jenis] = "tutup"

    # ================= SOCKET SERVER =================
    def start_server():
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen(5)
        print(f"🔌 Menunggu koneksi di {HOST}:{PORT}...")

        lid_controller = LidController()

        while True:
            try:
                conn, addr = server.accept()
                print(f"✅ Terhubung dengan {addr}")

                # Handshake
                conn.sendall(b"HELLO")
                data = conn.recv(1024)
                if data != b"OK":
                    print("❌ Handshake gagal")
                    conn.close()
                    continue

                while True:
                    data = conn.recv(1024)
                    if not data:
                        break
                    msg = data.decode().strip()
                    if msg == "HELLO":
                        conn.sendall(b"OK")
                        continue
                    if msg.startswith("BUKA:"):
                        jenis = msg.split(":")[1]
                        if jenis in SERVO_PINS:
                            buka(jenis)
                            time.sleep(3)
                            tutup(jenis)

            except Exception as e:
                print(f"⚠️ Error: {e}")
            finally:
                conn.close()
                print(f"❌ Terputus dari {addr}")

    # ================= RUN SERVER =================
    start_server()
