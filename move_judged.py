import os
import shutil
import sys
import re
import csv
from datetime import datetime

DEST_BASE_NAME = "Finished judgement"

MONTH_NAMES = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

def get_base_dir():
    """ดึงโฟลเดอร์ที่โปรแกรม (.exe หรือ .py) วางอยู่"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def parse_date_string(date_str):
    """แปลงข้อความวันที่ต่างๆ เช่น '8/14/2026', '10-6-2026', '2026-10-06' เป็น (month, year)"""
    if not date_str:
        return None
    date_str = date_str.strip()
    
    # รูปแบบ YYYY-MM-DD หรือ YYYYMMDD
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
    """อ่านวันที่จากเนื้อหาในไฟล์ CSV (คอลัมน์ Date)"""
    try:
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.reader(f)
            date_col_idx = None
            for row in reader:
                if not row:
                    continue
                # ค้นหาคอลัมน์ชื่อ Date ใน header
                if date_col_idx is None:
                    for idx, cell in enumerate(row):
                        if cell.strip().lower() == "date":
                            date_col_idx = idx
                            break
                    continue
                
                # อ่านค่าวันที่จากแถวข้อมูล
                if date_col_idx < len(row):
                    val = row[date_col_idx].strip()
                    parsed = parse_date_string(val)
                    if parsed:
                        return parsed
    except Exception:
        pass
    return None

def extract_date_from_filename(folder_path):
    """ลองค้นหาวันที่จากชื่อไฟล์ในโฟลเดอร์ เช่น 20260814"""
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
    """
    วิเคราะห์หาเดือนและปีของโฟลเดอร์:
    1. อ่านวันที่จากข้อมูลในไฟล์ .csv
    2. หาจากชื่อไฟล์ (เช่น _20260814_)
    3. ใช้วันที่แก้ไขล่าสุดของไฟล์ .csv
    """
    # 1. อ่านจากในไฟล์ CSV
    for csv_file in csv_files:
        res = extract_date_from_csv(csv_file)
        if res:
            return res

    # 2. อ่านจากชื่อไฟล์
    res = extract_date_from_filename(folder_path)
    if res:
        return res

    # 3. ใช้วันที่ของไฟล์ CSV
    csv_times = []
    for f in csv_files:
        try:
            csv_times.append(os.path.getmtime(f))
        except OSError:
            pass

    if csv_times:
        dt = datetime.fromtimestamp(max(csv_times))
        return dt.month, dt.year

    # 4. fallback ไปที่วันที่ของโฟลเดอร์
    dt = datetime.fromtimestamp(os.path.getmtime(folder_path))
    return dt.month, dt.year

def run_organize(base_dir):
    dest_root = os.path.join(base_dir, DEST_BASE_NAME)

    print("==================================================")
    print("      โปรแกรมจัดย้ายโฟลเดอร์ (Move Judged CSV)      ")
    print(f" ตำแหน่งที่ทำงาน: {base_dir}")
    print(f" โฟลเดอร์ปลายทาง: {DEST_BASE_NAME}")
    print("==================================================\n")

    try:
        items = os.listdir(base_dir)
    except Exception as e:
        print(f"[ERROR] ไม่สามารถอ่านโฟลเดอร์ได้: {e}")
        return

    moved_count = 0
    skipped_count = 0

    for item in items:
        item_path = os.path.join(base_dir, item)

        # ข้ามถ้าไม่ใช่โฟลเดอร์ หรือเป็นโฟลเดอร์ Finished judgement
        if not os.path.isdir(item_path):
            continue
        if item.lower() == DEST_BASE_NAME.lower():
            continue

        # ค้นหาไฟล์ .csv ทั้งหมดในโฟลเดอร์
        csv_files = []
        for root, _, files in os.walk(item_path):
            for f in files:
                if f.lower().endswith('.csv'):
                    csv_files.append(os.path.join(root, f))

        # ถ้าไม่มีไฟล์ CSV ให้ข้าม
        if not csv_files:
            continue

        # ดึงเดือนและปี
        month, year = get_folder_month_year(item_path, csv_files)
        month_str = f"{month:02d}"
        month_abbr = MONTH_NAMES[month]
        month_folder_name = f"{month_str} {month_abbr} {year}"  # ตัวอย่าง: "10 Oct 2026"

        month_dir = os.path.join(dest_root, month_folder_name)
        os.makedirs(month_dir, exist_ok=True)

        target_path = os.path.join(month_dir, item)

        try:
            if os.path.exists(target_path):
                timestamp = datetime.now().strftime("_%Y%m%d_%H%M%S")
                target_path = os.path.join(month_dir, item + timestamp)

            shutil.move(item_path, target_path)
            print(f"[OK] ย้าย '{item}' -> '{DEST_BASE_NAME}/{month_folder_name}'")
            moved_count += 1
        except Exception as e:
            print(f"[ERROR] ย้าย '{item}' ไม่สำเร็จ: {e}")
            skipped_count += 1

    print("\n--------------------------------------------------")
    print("สรุปผลการทำงาน:")
    print(f" - ย้ายสำเร็จ: {moved_count} โฟลเดอร์")
    print(f" - ข้าม/ผิดพลาด: {skipped_count} โฟลเดอร์")
    print("--------------------------------------------------")

if __name__ == "__main__":
    base_dir = get_base_dir()
    run_organize(base_dir)
    print("\nกด Enter เพื่อปิดหน้าต่าง...")
    input()
