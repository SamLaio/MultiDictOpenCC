import os
import sys
import json
import shutil
import re
import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog

# --- 環境設定 ---
plugin_dir = os.path.dirname(os.path.realpath(__file__))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

CONFIG_FILE = os.path.join(plugin_dir, "config.json")
DICT_DIR = os.path.join(plugin_dir, "dictionary")

if not os.path.exists(DICT_DIR):
    os.makedirs(DICT_DIR)

try:
    from opencc import OpenCC
except ImportError:
    print("錯誤：找不到 'opencc'。")
    sys.exit(1)

# --- 核心極速處理器 ---
class FastConverter:
    def __init__(self, mode='s2twp'):
        self.cc = OpenCC(mode)
        # 預先編譯標籤與佔位符正則，提升速度
        self.tag_re = re.compile(r'(<[^>]+>|&[a-zA-Z#0-9]+;)')
        self.place_re = re.compile(r'\uE000(\d+)\uE001')

    def process(self, data, pattern, final_dict):
        if not data: return data
        tag_storage = []
        
        # 1. 保護標籤
        def protect(m):
            tag_storage.append(m.group(0))
            return f"\uE000{len(tag_storage)-1}\uE001"
        protected = self.tag_re.sub(protect, data)
        
        # 2. OpenCC 全文轉換 (這部分最快)
        converted = self.cc.convert(protected)
        
        # 3. 自定義字典替換 (這部分如果字典大，會變慢)
        if pattern:
            converted = pattern.sub(lambda m: final_dict[m.group(0)], converted)
        
        # 4. 還原標籤
        return self.place_re.sub(lambda m: tag_storage[int(m.group(1))], converted)

# --- GUI 管理類別 ---
class MultiDictManager:
    def __init__(self, dict_dir):
        self.root = tk.Tk()
        self.root.title("MultiDictOpenCC")
        self.root.geometry("850x750")
        self.dict_dir = dict_dir
        self.dict_contents = {}
        self.dict_order = []
        self.dict_enabled = {}
        self.current_file = None
        self.success = False
        self.saved_prefs = self.load_prefs()
        self.setup_gui()

    def load_prefs(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f: return json.load(f)
            except: return {}
        return {}

    def setup_gui(self):
        left = tk.LabelFrame(self.root, text="1. 字典管理"); left.pack(side="left", fill="y", padx=10, pady=5)
        self.listbox = tk.Listbox(left, width=35, height=10); self.listbox.pack(padx=5, pady=5)
        self.listbox.bind('<<ListboxSelect>>', self.on_select_file)
        
        f1 = tk.Frame(left); f1.pack(fill="x")
        tk.Button(f1, text="➕ 新增", command=self.add_new_dict).pack(side="left", expand=True, fill="x")
        tk.Button(f1, text="▲", command=self.move_up).pack(side="left", expand=True, fill="x")
        tk.Button(f1, text="▼", command=self.move_down).pack(side="left", expand=True, fill="x")
        
        self.btn_run = tk.Button(left, text="★ 啟動轉換 ★", command=self.on_run, bg="#d32f2f", fg="white", font=("Arial", 12, "bold"), pady=10)
        self.btn_run.pack(fill="x", padx=5, pady=10)
        
        self.check_container = tk.Frame(left); self.check_container.pack(fill="both", expand=True)
        self.init_check_list()
        self.refresh_file_list()
        
        right = tk.Frame(self.root); right.pack(side="right", fill="both", expand=True, padx=10, pady=5)
        self.text_area = scrolledtext.ScrolledText(right, height=40); self.text_area.pack(fill="both", expand=True)

    def init_check_list(self):
        self.canvas = tk.Canvas(self.check_container, width=220); self.scrollbar = tk.Scrollbar(self.check_container, command=self.canvas.yview)
        self.scroll_frame = tk.Frame(self.canvas); self.canvas.create_window((0,0), window=self.scroll_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set); self.canvas.pack(side="left", fill="both", expand=True); self.scrollbar.pack(side="right", fill="y")
        self.scroll_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

    def refresh_file_list(self):
        files = sorted([f for f in os.listdir(self.dict_dir) if f.endswith('.txt')])
        self.dict_order = files
        for f in files:
            self.listbox.insert(tk.END, f)
            if f not in self.dict_enabled: self.dict_enabled[f] = tk.BooleanVar(value=self.saved_prefs.get(f, False))
            with open(os.path.join(self.dict_dir, f), 'r', encoding='utf-8') as obj: self.dict_contents[f] = obj.read()
            tk.Checkbutton(self.scroll_frame, text=f, variable=self.dict_enabled[f]).pack(anchor="w")

    def on_select_file(self, e):
        self.save_edit()
        sel = self.listbox.curselection()
        if sel:
            self.current_file = self.listbox.get(sel[0])
            self.text_area.delete("1.0", tk.END); self.text_area.insert(tk.END, self.dict_contents[self.current_file])

    def save_edit(self):
        if self.current_file: self.dict_contents[self.current_file] = self.text_area.get("1.0", tk.END)

    def add_new_dict(self):
        p = filedialog.askopenfilename(filetypes=[("Text", "*.txt")])
        if p: shutil.copy(p, os.path.join(self.dict_dir, os.path.basename(p))); self.listbox.delete(0, tk.END); self.refresh_file_list()

    def move_up(self):
        i = self.listbox.curselection()
        if i and i[0] > 0:
            idx = i[0]; self.dict_order[idx], self.dict_order[idx-1] = self.dict_order[idx-1], self.dict_order[idx]
            v = self.listbox.get(idx); self.listbox.delete(idx); self.listbox.insert(idx-1, v); self.listbox.select_set(idx-1)

    def move_down(self):
        i = self.listbox.curselection()
        if i and i[0] < self.listbox.size()-1:
            idx = i[0]; self.dict_order[idx], self.dict_order[idx+1] = self.dict_order[idx+1], self.dict_order[idx]
            v = self.listbox.get(idx); self.listbox.delete(idx); self.listbox.insert(idx+1, v); self.listbox.select_set(idx+1)

    def on_run(self):
        self.save_edit()
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f: json.dump({f: v.get() for f, v in self.dict_enabled.items()}, f, ensure_ascii=False, indent=4)
        for f, c in self.dict_contents.items():
            with open(os.path.join(self.dict_dir, f), 'w', encoding='utf-8') as obj: obj.write(c.strip())
        self.success = True; self.root.destroy()

    def show(self): self.root.mainloop(); return self.success

def run(bc):
    gui = MultiDictManager(DICT_DIR)
    if not gui.show(): return 0
    
    # --- 1. 字典與 OpenCC 預備 ---
    cc_main = OpenCC('s2twp')
    final_dict = {}
    for f in gui.dict_order:
        if gui.dict_enabled[f].get():
            for line in gui.dict_contents[f].splitlines():
                p = line.strip().split('\t')
                if len(p) >= 2:
                    k = cc_main.convert(p[0]) # 字典 Key 轉成繁體以便匹配
                    final_dict[k] = p[1].split()[0]
    
    pattern = None
    if final_dict:
        # 按照長度降序排列
        keys = sorted(final_dict.keys(), key=len, reverse=True)
        pattern = re.compile("|".join(map(re.escape, keys)))

    # --- 2. 核心處理器 ---
    processor = FastConverter('s2twp')

    # --- 3. 獲取所有檔案 ---
    targets = [fid for fid, _ in bc.text_iter()]
    for entry in bc.manifest_iter():
        fid, href, mtype = entry[0], entry[1], entry[2]
        if 'ncx' in mtype.lower() or 'nav' in mtype.lower() or 'nav' in fid.lower():
            targets.append(fid)

    # --- 4. 批次處理 ---
    for fid in set(targets):
        try:
            content = bc.readfile(fid)
            if content:
                # 直接處理並寫回
                bc.writefile(fid, processor.process(content, pattern, final_dict))
        except: pass

    return 0