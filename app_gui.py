import os
import shutil
import sys
import re
import csv
import json
import time
import threading
from datetime import datetime, date
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from PIL import Image
import pystray

CONFIG_FILE_NAME = "config.json"
MONTH_NAMES = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Dark Modern Color Palette
BG_DARK = "#090d16"         # พื้นหลังหลักเข้มเท่ Obsidian
PANEL_BG = "#131b2e"        # พื้นหลังการ์ด / กรอบ
PANEL_BORDER = "#1f2d47"    # เส้นขอบการ์ด
TEXT_MAIN = "#f1f5f9"       # ข้อความหลัก ขาวนวล
TEXT_MUTED = "#8e9eb5"      # ข้อความรอง สีเทา
CYAN_ACCENT = "#38bdf8"     # ฟ้าไฮไลต์ Cyber Cyan
GREEN_RUN = "#10b981"       # เขียวสด Emerald
GREEN_BG = "#064e3b"        # พื้นหลังเขียวเข้ม
RED_STOP = "#f43f5e"        # แดง Rose / Crimson
INPUT_BG = "#0c1220"        # ช่องกรอกข้อมูล
INPUT_BORDER = "#2a3b5c"    # ขอบช่องกรอก

def get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_resource_path(filename):
    if hasattr(sys, '_MEIPASS'):
        cand = os.path.join(sys._MEIPASS, filename)
        if os.path.exists(cand):
            return cand
    return os.path.join(get_app_dir(), filename)

def parse_date_string(date_str):
    if not date_str:
        return None
    date_str = date_str.strip()
    
    # รูปแบบ YYYY-MM-DD หรือ YYYY/MM/DD
    m = re.match(r'^(\d{4})[-/](\d{1,2})[-/](\d{1,2})', date_str)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12:
            return month, year
            
    # รูปแบบ M/D/YYYY หรือ M-D-YYYY (เช่น 8/14/2026, 10-6-2026)
    m = re.match(r'^(\d{1,2})[-/](\d{1,2})[-/](\d{4})', date_str)
    if m:
        month, year = int(m.group(1)), int(m.group(3))
        if 1 <= month <= 12:
            return month, year

    return None

def extract_date_from_csv(csv_path):
    try:
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.reader(f)
            date_col_idx = None
            for row in reader:
                if not row:
                    continue
                if date_col_idx is None:
                    for idx, cell in enumerate(row):
                        if cell.strip().lower() == "date":
                            date_col_idx = idx
                            break
                    continue
                
                if date_col_idx < len(row):
                    val = row[date_col_idx].strip()
                    parsed = parse_date_string(val)
                    if parsed:
                        return parsed
    except Exception:
        pass
    return None

def extract_date_from_filename(folder_path):
    try:
        for fname in os.listdir(folder_path):
            m = re.search(r'20\d{2}(0[1-9]|1[0-2])([0-3]\d)', fname)
            if m:
                year = int(fname[m.start():m.start()+4])
                month = int(fname[m.start()+4:m.start()+6])
                return month, year
    except Exception:
        pass
    return None

def get_folder_month_year(folder_path, csv_files):
    for csv_file in csv_files:
        res = extract_date_from_csv(csv_file)
        if res:
            return res

    res = extract_date_from_filename(folder_path)
    if res:
        return res

    csv_times = []
    for f in csv_files:
        try:
            csv_times.append(os.path.getmtime(f))
        except OSError:
            pass

    if csv_times:
        dt = datetime.fromtimestamp(max(csv_times))
        return dt.month, dt.year

    dt = datetime.fromtimestamp(os.path.getmtime(folder_path))
    return dt.month, dt.year


class DarkModernGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Auto Move Judged CSV - Dark Edition")
        self.geometry("820x680")
        self.minsize(740, 580)
        self.configure(bg=BG_DARK)

        self.app_dir = get_app_dir()
        self.config_path = os.path.join(self.app_dir, CONFIG_FILE_NAME)
        self.ico_path = get_resource_path("app_icon.ico")
        self.png_path = get_resource_path("app_icon.png")

        # Set Icon for Window
        if os.path.exists(self.ico_path):
            try:
                self.iconbitmap(self.ico_path)
            except Exception:
                pass

        self.is_running = False
        self.worker_thread = None
        self.tray_icon = None

        self.load_config()
        self.create_widgets()
        self.setup_system_tray()

        # จัดการการพับหน้าต่าง (Minimize to System Tray)
        self.bind("<Unmap>", self.on_window_unmap)

        # กดปิด (X) ให้ปิดโปรแกรมทันที
        self.protocol("WM_DELETE_WINDOW", self.on_exit_app)

    def load_config(self):
        default_source = self.app_dir
        default_dest = os.path.join(self.app_dir, "Finished judgement")
        today_str = date.today().isoformat()

        self.config = {
            "source_dir": default_source,
            "dest_dir": default_dest,
            "interval_sec": 10,
            "today_date": today_str,
            "today_count": 0,
            "total_count": 0
        }

        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self.config.update(loaded)
            except Exception:
                pass

        if self.config.get("today_date") != today_str:
            self.config["today_date"] = today_str
            self.config["today_count"] = 0
            self.save_config()

    def save_config(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

    def setup_system_tray(self):
        try:
            if os.path.exists(self.png_path):
                tray_img = Image.open(self.png_path)
            elif os.path.exists(self.ico_path):
                tray_img = Image.open(self.ico_path)
            else:
                tray_img = Image.new("RGBA", (64, 64), (56, 189, 248, 255))

            menu = pystray.Menu(
                pystray.MenuItem('เปิดหน้าต่าง (Open)', self.tray_restore, default=True),
                pystray.MenuItem('เริ่มทำงาน (Run)', self.tray_start),
                pystray.MenuItem('หยุดทำงาน (Stop)', self.tray_stop),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('ปิดโปรแกรม (Exit)', self.tray_exit)
            )

            self.tray_icon = pystray.Icon(
                "MoveJudgedCSV",
                tray_img,
                "Auto Move Judged CSV (กำลังทำงาน)",
                menu
            )
            # รัน Tray ใน background thread
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception as e:
            print("System tray initialization error:", e)

    def on_window_unmap(self, event):
        # เมื่อผู้ใช้กดปุ่ม Minimize (_) หน้าต่างจะเปลี่ยนสถานะเป็น 'iconic'
        if event.widget == self:
            if self.state() == 'iconic':
                # ซ่อนจาก Taskbar ไปอยู่ที่ Hidden Icon (System Tray)
                self.withdraw()
                if self.tray_icon:
                    try:
                        self.tray_icon.notify("โปรแกรมถูกพับเก็บไว้ที่ System Tray ป้องกันการปิดโดยไม่ตั้งใจ", "Move Judged CSV")
                    except Exception:
                        pass

    def tray_restore(self, icon=None, item=None):
        self.after(0, self._restore_main_window)

    def _restore_main_window(self):
        self.deiconify()
        self.state('normal')
        self.lift()
        self.focus_force()

    def tray_start(self, icon=None, item=None):
        self.after(0, self.start_loop)

    def tray_stop(self, icon=None, item=None):
        self.after(0, self.stop_loop)

    def tray_exit(self, icon=None, item=None):
        self.after(0, self.on_exit_app)

    def on_exit_app(self):
        # ปิดโปรแกรมทันทีตามที่ผู้ใช้ต้องการ
        self.is_running = False
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.destroy()
        os._exit(0)

    def create_widgets(self):
        # Top Header Bar
        header = tk.Frame(self, bg="#0d1424", height=65)
        header.pack(fill="x")

        title_box = tk.Frame(header, bg="#0d1424")
        title_box.pack(side="left", padx=20, pady=12)

        tk.Label(
            title_box, 
            text="⚡ AUTO MOVE JUDGED CSV", 
            font=("Segoe UI", 16, "bold"), 
            fg=CYAN_ACCENT, 
            bg="#0d1424"
        ).pack(anchor="w")

        tk.Label(
            title_box, 
            text="Continuous Folder Monitoring & Monthly Auto-Organizer", 
            font=("Segoe UI", 9), 
            fg=TEXT_MUTED, 
            bg="#0d1424"
        ).pack(anchor="w")

        # Container
        body = tk.Frame(self, bg=BG_DARK, padx=16, pady=12)
        body.pack(fill="both", expand=True)

        # 1. Path Configuration Card
        path_card = tk.LabelFrame(
            body, 
            text=" ⚙️ การตั้งค่าพาธโฟลเดอร์ (Folder Paths) ", 
            font=("Segoe UI", 10, "bold"),
            bg=PANEL_BG, 
            fg=CYAN_ACCENT, 
            bd=1, 
            relief="solid",
            padx=14, 
            pady=10
        )
        path_card.pack(fill="x", pady=(0, 10))

        # Source
        tk.Label(path_card, text="โฟลเดอร์ที่จะ Search (ต้นทาง):", font=("Segoe UI", 9, "bold"), fg=TEXT_MAIN, bg=PANEL_BG).grid(row=0, column=0, sticky="w", pady=4)
        self.source_var = tk.StringVar(value=self.config.get("source_dir", ""))
        src_entry = tk.Entry(path_card, textvariable=self.source_var, font=("Segoe UI", 9), bg=INPUT_BG, fg=TEXT_MAIN, insertbackground=CYAN_ACCENT, bd=1, relief="solid")
        src_entry.grid(row=0, column=1, sticky="ew", padx=8, pady=4)
        btn_src = tk.Button(path_card, text="📂 เลือกโฟลเดอร์", font=("Segoe UI", 8, "bold"), bg="#1e293b", fg=CYAN_ACCENT, activebackground="#334155", activeforeground=TEXT_MAIN, bd=1, relief="solid", padx=8, command=self.browse_source)
        btn_src.grid(row=0, column=2, pady=4)

        # Dest
        tk.Label(path_card, text="โฟลเดอร์ที่จะ Cut ไป (ปลายทาง):", font=("Segoe UI", 9, "bold"), fg=TEXT_MAIN, bg=PANEL_BG).grid(row=1, column=0, sticky="w", pady=4)
        self.dest_var = tk.StringVar(value=self.config.get("dest_dir", ""))
        dest_entry = tk.Entry(path_card, textvariable=self.dest_var, font=("Segoe UI", 9), bg=INPUT_BG, fg=TEXT_MAIN, insertbackground=CYAN_ACCENT, bd=1, relief="solid")
        dest_entry.grid(row=1, column=1, sticky="ew", padx=8, pady=4)
        btn_dest = tk.Button(path_card, text="📂 เลือกโฟลเดอร์", font=("Segoe UI", 8, "bold"), bg="#1e293b", fg=CYAN_ACCENT, activebackground="#334155", activeforeground=TEXT_MAIN, bd=1, relief="solid", padx=8, command=self.browse_dest)
        btn_dest.grid(row=1, column=2, pady=4)

        # Interval
        int_frame = tk.Frame(path_card, bg=PANEL_BG)
        int_frame.grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))
        tk.Label(int_frame, text="ความถี่ตรวจสอบรอบใหม่: ทุกๆ ", font=("Segoe UI", 9), fg=TEXT_MUTED, bg=PANEL_BG).pack(side="left")
        self.interval_var = tk.IntVar(value=self.config.get("interval_sec", 10))
        spin = tk.Spinbox(int_frame, from_=3, to=300, width=4, textvariable=self.interval_var, font=("Segoe UI", 9, "bold"), bg=INPUT_BG, fg=CYAN_ACCENT, insertbackground=CYAN_ACCENT, bd=1, relief="solid")
        spin.pack(side="left", padx=4)
        tk.Label(int_frame, text="วินาที (เมื่อพนักงานตรวจเสร็จและมีไฟล์ .CSV ระบบจะดึงอัตโนมัติ)", font=("Segoe UI", 9), fg=TEXT_MUTED, bg=PANEL_BG).pack(side="left")

        path_card.columnconfigure(1, weight=1)

        # 2. Status & Dashboard
        dash_card = tk.LabelFrame(
            body, 
            text=" 📊 สถานะการทำงาน & สถิติ (Dashboard) ", 
            font=("Segoe UI", 10, "bold"),
            bg=PANEL_BG, 
            fg=CYAN_ACCENT, 
            bd=1, 
            relief="solid",
            padx=14, 
            pady=10
        )
        dash_card.pack(fill="x", pady=(0, 10))

        # Top row of dashboard: Status badge & Big Action Button
        top_dash = tk.Frame(dash_card, bg=PANEL_BG)
        top_dash.pack(fill="x", pady=(0, 8))

        self.lbl_status = tk.Label(
            top_dash, 
            text="● ระบบหยุดทำงาน (STOPPED)", 
            font=("Segoe UI", 11, "bold"), 
            bg="#1e293b", 
            fg="#94a3b8",
            padx=12, 
            pady=5, 
            bd=1, 
            relief="solid"
        )
        self.lbl_status.pack(side="left")

        self.btn_toggle = tk.Button(
            top_dash, 
            text="▶ เริ่มการทำงาน (START RUN)", 
            font=("Segoe UI", 11, "bold"), 
            bg="#059669", 
            fg="#ffffff", 
            activebackground="#10b981", 
            activeforeground="#ffffff", 
            bd=0, 
            padx=20, 
            pady=6, 
            cursor="hand2",
            command=self.toggle_run
        )
        self.btn_toggle.pack(side="right")

        # Stat counter cards
        stats_box = tk.Frame(dash_card, bg=PANEL_BG)
        stats_box.pack(fill="x", pady=4)

        # Card 1: Today
        c_today = tk.Frame(stats_box, bg="#0d1829", bd=1, relief="solid", padx=18, pady=10)
        c_today.pack(side="left", fill="both", expand=True, padx=(0, 8))
        tk.Label(c_today, text="ดึงวันนี้ (TODAY)", font=("Segoe UI", 10, "bold"), fg=CYAN_ACCENT, bg="#0d1829").pack(anchor="w")
        self.lbl_today = tk.Label(c_today, text=str(self.config.get("today_count", 0)), font=("Segoe UI", 24, "bold"), fg="#ffffff", bg="#0d1829")
        self.lbl_today.pack(anchor="w")
        tk.Label(c_today, text="โฟลเดอร์ (รีเซ็ตอัตโนมัติเมื่อขึ้นวันใหม่)", font=("Segoe UI", 8), fg=TEXT_MUTED, bg="#0d1829").pack(anchor="w")

        # Card 2: Total
        c_total = tk.Frame(stats_box, bg="#0d231e", bd=1, relief="solid", padx=18, pady=10)
        c_total.pack(side="left", fill="both", expand=True, padx=(8, 0))
        tk.Label(c_total, text="ดึงสะสมทั้งหมด (TOTAL)", font=("Segoe UI", 10, "bold"), fg="#34d399", bg="#0d231e").pack(anchor="w")
        self.lbl_total = tk.Label(c_total, text=str(self.config.get("total_count", 0)), font=("Segoe UI", 24, "bold"), fg="#ffffff", bg="#0d231e")
        self.lbl_total.pack(anchor="w")
        tk.Label(c_total, text="โฟลเดอร์สะสมทั้งหมด", font=("Segoe UI", 8), fg=TEXT_MUTED, bg="#0d231e").pack(anchor="w")

        # 3. Activity Log Box
        log_card = tk.LabelFrame(
            body, 
            text=" 📜 ประวัติการทำงานสด (Live Activity Log) ", 
            font=("Segoe UI", 10, "bold"),
            bg=PANEL_BG, 
            fg=CYAN_ACCENT, 
            bd=1, 
            relief="solid",
            padx=10, 
            pady=8
        )
        log_card.pack(fill="both", expand=True)

        self.txt_log = scrolledtext.ScrolledText(
            log_card, 
            wrap="word", 
            font=("Consolas", 9), 
            bg="#060911", 
            fg="#94a3b8", 
            insertbackground=CYAN_ACCENT,
            bd=1, 
            relief="solid", 
            height=9
        )
        self.txt_log.pack(fill="both", expand=True)

        log_foot = tk.Frame(log_card, bg=PANEL_BG)
        log_foot.pack(fill="x", pady=(6, 0))
        
        tk.Label(
            log_foot, 
            text="💡 ทริค: เมื่อกดปุ่ม Minimize (_) โปรแกรมจะซ่อนไปที่ Hidden Icons (System Tray) ป้องกันคนปิด", 
            font=("Segoe UI", 8), 
            fg=TEXT_MUTED, 
            bg=PANEL_BG
        ).pack(side="left")

        tk.Button(
            log_foot, 
            text="ล้างประวัติ", 
            font=("Segoe UI", 8), 
            bg="#1e293b", 
            fg=TEXT_MAIN, 
            activebackground="#334155", 
            activeforeground=TEXT_MAIN, 
            bd=1, 
            relief="solid", 
            padx=8, 
            command=self.clear_log
        ).pack(side="right")

        self.log_message("ระบบพร้อมทำงาน! กดปุ่ม 'เริ่มการทำงาน' เพื่อเริ่มการดึงโฟลเดอร์วนลูป")

    def browse_source(self):
        sel = filedialog.askdirectory(initialdir=self.source_var.get() or self.app_dir)
        if sel:
            self.source_var.set(os.path.normpath(sel))

    def browse_dest(self):
        sel = filedialog.askdirectory(initialdir=self.dest_var.get() or self.app_dir)
        if sel:
            self.dest_var.set(os.path.normpath(sel))

    def clear_log(self):
        self.txt_log.delete("1.0", tk.END)

    def log_message(self, text, is_success=False, is_error=False):
        now_str = datetime.now().strftime("%H:%M:%S")
        self.txt_log.insert(tk.END, f"[{now_str}] {text}\n")
        self.txt_log.see(tk.END)

    def toggle_run(self):
        if not self.is_running:
            self.start_loop()
        else:
            self.stop_loop()

    def start_loop(self):
        if self.is_running:
            return
        src = self.source_var.get().strip()
        dst = self.dest_var.get().strip()

        if not src or not os.path.exists(src):
            messagebox.showerror("ข้อผิดพลาด", "ไม่พบโฟลเดอร์ต้นทาง กรุณาเลือกโฟลเดอร์ให้ถูกต้อง")
            return
        if not dst:
            messagebox.showerror("ข้อผิดพลาด", "กรุณาระบุโฟลเดอร์ปลายทาง")
            return

        self.config["source_dir"] = src
        self.config["dest_dir"] = dst
        try:
            self.config["interval_sec"] = max(3, int(self.interval_var.get()))
        except ValueError:
            self.config["interval_sec"] = 10
        self.save_config()

        self.is_running = True
        self.btn_toggle.config(
            text="⏹ หยุดการทำงาน (STOP)", 
            bg=RED_STOP, 
            activebackground="#e11d48"
        )
        self.lbl_status.config(
            text=f"● กำลังทำงาน (วนรอบทุก {self.config['interval_sec']} วิ)", 
            bg=GREEN_BG, 
            fg="#6ee7b7"
        )
        self.log_message(f"เริ่มการมอนิเตอร์วนลูป: ตรวจสอบทุกๆ {self.config['interval_sec']} วินาที")

        self.worker_thread = threading.Thread(target=self.run_worker, daemon=True)
        self.worker_thread.start()

    def stop_loop(self):
        self.is_running = False
        self.btn_toggle.config(
            text="▶ เริ่มการทำงาน (START RUN)", 
            bg="#059669", 
            activebackground=GREEN_RUN
        )
        self.lbl_status.config(
            text="● ระบบหยุดทำงาน (STOPPED)", 
            bg="#1e293b", 
            fg="#94a3b8"
        )
        self.log_message("หยุดการทำงานวนลูปแล้ว")

    def run_worker(self):
        while self.is_running:
            try:
                self.process_cycle()
            except Exception as e:
                self.after(0, self.log_message, f"[ERROR] ข้อผิดพลาดระหว่างสแกน: {e}")

            interval = self.config.get("interval_sec", 10)
            steps = int(interval * 2)
            for _ in range(steps):
                if not self.is_running:
                    break
                time.sleep(0.5)

    def process_cycle(self):
        today_str = date.today().isoformat()
        if self.config.get("today_date") != today_str:
            self.config["today_date"] = today_str
            self.config["today_count"] = 0
            self.after(0, self.update_stat_labels)
            self.save_config()

        source_dir = self.config.get("source_dir")
        dest_dir = self.config.get("dest_dir")

        if not os.path.exists(source_dir):
            return

        try:
            items = os.listdir(source_dir)
        except Exception:
            return

        for item in items:
            if not self.is_running:
                break

            item_path = os.path.join(source_dir, item)
            if not os.path.isdir(item_path):
                continue

            try:
                abs_item = os.path.abspath(item_path).lower()
                abs_dest = os.path.abspath(dest_dir).lower()
                if abs_item == abs_dest or abs_dest.startswith(abs_item + os.sep):
                    continue
            except Exception:
                pass

            csv_files = []
            for root, _, files in os.walk(item_path):
                for f in files:
                    if f.lower().endswith(".csv"):
                        csv_files.append(os.path.join(root, f))

            if not csv_files:
                continue

            # ตรวจสอบว่ามีโปรแกรมอื่นเปิดหรือเขียนไฟล์ CSV ค้างอยู่หรือไม่
            if self.is_folder_locked(csv_files):
                continue

            # วิเคราะห์หาเดือนและปี
            month, year = get_folder_month_year(item_path, csv_files)
            month_str = f"{month:02d}"
            month_abbr = MONTH_NAMES[month]
            month_folder_name = f"{month_str} {month_abbr} {year}"  # e.g. "10 Oct 2026"

            target_month_dir = os.path.join(dest_dir, month_folder_name)
            os.makedirs(target_month_dir, exist_ok=True)

            target_path = os.path.join(target_month_dir, item)

            try:
                if os.path.exists(target_path):
                    ts = datetime.now().strftime("_%Y%m%d_%H%M%S")
                    target_path = os.path.join(target_month_dir, item + ts)

                shutil.move(item_path, target_path)

                self.config["today_count"] = self.config.get("today_count", 0) + 1
                self.config["total_count"] = self.config.get("total_count", 0) + 1
                self.save_config()

                log_txt = f"✔️ [CUT] '{item}' ➔ '{month_folder_name}'"
                self.after(0, self.log_message, log_txt)
                self.after(0, self.update_stat_labels)

            except PermissionError:
                pass
            except Exception as e:
                self.after(0, self.log_message, f"❌ [ERROR] '{item}': {e}")

    def is_folder_locked(self, csv_files):
        for f in csv_files:
            try:
                with open(f, "a"):
                    pass
            except (IOError, PermissionError):
                return True
        return False

    def update_stat_labels(self):
        self.lbl_today.config(text=str(self.config.get("today_count", 0)))
        self.lbl_total.config(text=str(self.config.get("total_count", 0)))

if __name__ == "__main__":
    app = DarkModernGUI()
    app.mainloop()
