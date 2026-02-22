import os
import sys
import json  # 用於儲存勾選狀態
import tkinter as tk
from tkinter import messagebox, scrolledtext

# --- 核心：環境獨立化路徑設定 ---
plugin_dir = os.path.dirname(os.path.realpath(__file__))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

# 設定檔與字典路徑
CONFIG_FILE = os.path.join(plugin_dir, "config.json")
DICT_DIR = os.path.join(plugin_dir, "dictionary")

try:
    from bs4 import BeautifulSoup
    from opencc import OpenCC
except ImportError:
    print("錯誤：在外掛目錄中找不到 'bs4' 或 'opencc' 資料夾。")
    sys.exit(1)

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

        # 讀取上次儲存的勾選狀態
        self.saved_prefs = self.load_prefs()

        # --- 左側：控制區 ---
        left_frame = tk.LabelFrame(self.root, text="字典管理與排序")
        left_frame.pack(side="left", fill="y", padx=10, pady=5)

        self.listbox = tk.Listbox(left_frame, width=35, height=10, selectbackground="#0078d7")
        self.listbox.pack(padx=5, pady=5)
        self.listbox.bind('<<ListboxSelect>>', self.on_select_file)

        btn_sort_frame = tk.Frame(left_frame)
        btn_sort_frame.pack(fill="x", padx=5)
        tk.Button(btn_sort_frame, text="▲ 上移", command=self.move_up).pack(side="left", expand=True, fill="x")
        tk.Button(btn_sort_frame, text="▼ 下移", command=self.move_down).pack(side="left", expand=True, fill="x")

        btn_sel_frame = tk.Frame(left_frame)
        btn_sel_frame.pack(fill="x", padx=5, pady=5)
        tk.Button(btn_sel_frame, text="☑ 全選", command=self.select_all).pack(side="left", expand=True, fill="x")
        tk.Button(btn_sel_frame, text="☐ 全不選", command=self.deselect_all).pack(side="left", expand=True, fill="x")

        self.btn_run = tk.Button(left_frame, text="★ 執行轉換 ★", 
                                 command=self.on_run, bg="#28a745", fg="white", 
                                 font=("Arial", 12, "bold"), pady=10)
        self.btn_run.pack(fill="x", padx=5, pady=10)

        # 帶捲軸的勾選清單
        canvas_frame = tk.Frame(left_frame)
        canvas_frame.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(canvas_frame, width=220)
        self.scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.scroll_frame = tk.Frame(self.canvas)
        self.scroll_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.refresh_file_list()

        # --- 右側：編輯區 ---
        right_frame = tk.Frame(self.root)
        right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=5)
        self.edit_label = tk.Label(right_frame, text="編輯內容 (簡體[Tab]繁體):")
        self.edit_label.pack(anchor="w")
        self.text_area = scrolledtext.ScrolledText(right_frame, height=40)
        self.text_area.pack(fill="both", expand=True, pady=5)

    def load_prefs(self):
        """讀取 config.json 中的勾選紀錄"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_prefs(self):
        """將當前勾選狀態存入 config.json"""
        prefs = {f: var.get() for f, var in self.dict_enabled.items()}
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(prefs, f, ensure_ascii=False, indent=4)
        except:
            pass

    def refresh_file_list(self):
        files = [f for f in os.listdir(self.dict_dir) if f.endswith('.txt')]
        self.dict_order = sorted(files)
        for f in self.dict_order:
            self.listbox.insert(tk.END, f)
            # 優先從記憶中讀取，若無則預設為 False (或依需求改 True)
            is_enabled = self.saved_prefs.get(f, False)
            self.dict_enabled[f] = tk.BooleanVar(value=is_enabled) 
            
            with open(os.path.join(self.dict_dir, f), 'r', encoding='utf-8') as obj:
                self.dict_contents[f] = obj.read()
        
        for f in self.dict_order:
            tk.Checkbutton(self.scroll_frame, text=f, variable=self.dict_enabled[f]).pack(anchor="w")

    def select_all(self):
        for var in self.dict_enabled.values(): var.set(True)
    def deselect_all(self):
        for var in self.dict_enabled.values(): var.set(False)
    def on_select_file(self, event):
        self.save_current_edit()
        selection = self.listbox.curselection()
        if selection:
            self.current_file = self.listbox.get(selection[0])
            self.edit_label.config(text="編輯中: " + self.current_file)
            self.text_area.delete("1.0", tk.END)
            self.text_area.insert(tk.END, self.dict_contents[self.current_file])
    def save_current_edit(self):
        if self.current_file:
            self.dict_contents[self.current_file] = self.text_area.get("1.0", tk.END)
    def move_up(self):
        idx = self.listbox.curselection()
        if idx and idx[0] > 0:
            i = idx[0]
            self.dict_order[i], self.dict_order[i-1] = self.dict_order[i-1], self.dict_order[i]
            val = self.listbox.get(i); self.listbox.delete(i); self.listbox.insert(i-1, val); self.listbox.select_set(i-1)
    def move_down(self):
        idx = self.listbox.curselection()
        if idx and idx[0] < self.listbox.size() - 1:
            i = idx[0]
            self.dict_order[i], self.dict_order[i+1] = self.dict_order[i+1], self.dict_order[i]
            val = self.listbox.get(i); self.listbox.delete(i); self.listbox.insert(i+1, val); self.listbox.select_set(i+1)

    def on_run(self):
        self.save_current_edit()
        self.save_prefs()  # 關鍵：關閉前存下勾選狀態
        for f, content in self.dict_contents.items():
            with open(os.path.join(self.dict_dir, f), 'w', encoding='utf-8') as obj:
                obj.write(content.strip())
        self.success = True
        self.root.destroy()

    def show(self):
        self.root.mainloop()
        return self.success

def run(bc):
    gui = MultiDictManager(DICT_DIR)
    if not gui.show(): return 0

    cc = OpenCC('s2twp')
    final_dict = {}
    for f_name in gui.dict_order:
        if gui.dict_enabled[f_name].get():
            for line in gui.dict_contents[f_name].splitlines():
                parts = line.strip().split('\t')
                if len(parts) >= 2:
                    final_dict[parts[0]] = parts[1].split()[0]

    for file_id, href in bc.text_iter():
        html = bc.readfile(file_id)
        if not html: continue
        soup = BeautifulSoup(html, 'html.parser')
        modified = False
        for text_node in soup.find_all(string=True):
            if text_node.parent.name not in ['script', 'style']:
                original = text_node.string
                if not original: continue
                converted = cc.convert(original)
                for s, t in final_dict.items():
                    if s in original:
                        converted = converted.replace(cc.convert(s), t)
                if original != converted:
                    text_node.replace_with(converted)
                    modified = True
        if modified: bc.writefile(file_id, str(soup))
    return 0