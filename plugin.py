import os
import sys
import json
import shutil
import re
import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog

# --- 基礎環境設定 ---
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

# --- 核心處理器 (極致優化版) ---
class UltraConverter:
    def __init__(self, final_dict, mode='s2twp'):
        self.cc = OpenCC(mode)
        self.tag_re = re.compile(r'(<[^>]+>|&[a-zA-Z#0-9]+;)')
        self.place_re = re.compile(r'\uE000(\d+)\uE001')
        self.char_map = str.maketrans({'“': '「', '”': '」', '‘': '『', '’': '』'})
        
        # 預先建立 Trie 樹 (只做一次)
        self.trie = {}
        if final_dict:
            for key, val in final_dict.items():
                node = self.trie
                for char in key:
                    node = node.setdefault(char, {})
                node['VALUE'] = val

    def process(self, data):
        if not data: return data
        tag_storage = []
        
        # 1. 保護標籤
        def protect(m):
            tag_storage.append(m.group(0))
            return f"\uE000{len(tag_storage)-1}\uE001"
        protected = self.tag_re.sub(protect, data)
        
        # 2. OpenCC 轉換
        text = self.cc.convert(protected)
        
        # 3. 引號替換 (C 級別)
        text = text.translate(self.char_map)
        
        # 4. 字典替換 (Trie 字典樹)
        if self.trie:
            text = self.fast_trie_replace(text)
            
        # 5. 成對引號修正 (最後處理 " " 與 ' ')
        text = re.sub(r'"([^"]+)"', r'「\1」', text)
        text = re.sub(r"'([^']+)'", r'『\1』', text)
        
        # 6. 還原標籤
        return self.place_re.sub(lambda m: tag_storage[int(m.group(1))], text)

    def fast_trie_replace(self, text):
        res = []
        i = 0
        length = len(text)
        trie = self.trie
        while i < length:
            best_match_val = None
            best_match_len = 0
            curr_node = trie
            for j in range(i, length):
                char = text[j]
                if char not in curr_node: break
                curr_node = curr_node[char]
                if 'VALUE' in curr_node:
                    best_match_val = curr_node['VALUE']
                    best_match_len = j - i + 1
            
            if best_match_val is not None:
                res.append(best_match_val)
                i += best_match_len
            else:
                res.append(text[i])
                i += 1
        return "".join(res)

# --- GUI 字典管理類別 (維持原樣) ---
class MultiDictManager:
    def __init__(self, dict_dir):
        self.root = tk.Tk()
        self.root.title("MultiDictOpenCC")
        self.root.geometry("850x750")
        self.dict_dir, self.dict_contents, self.dict_order, self.dict_enabled = dict_dir, {}, [], {}
        self.current_file, self.success = None, False
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
        self.btn_run = tk.Button(left, text="★ 執行 ★", command=self.on_run, bg="#0078d7", fg="white", font=("Arial", 12, "bold"), pady=10)
        self.btn_run.pack(fill="x", padx=5, pady=10)
        self.check_container = tk.Frame(left); self.check_container.pack(fill="both", expand=True)
        self.init_check_list(); self.refresh_file_list()
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

# --- Sigil 進入點 ---
def run(bc):
    gui = MultiDictManager(DICT_DIR)
    if not gui.show(): return 0
    
    # 1. 預處理字典 (Key 必須轉為繁體以匹配 OpenCC 後的結果)
    cc_main = OpenCC('s2twp')
    final_dict = {}
    for f_name in gui.dict_order:
        if gui.dict_enabled[f_name].get():
            for line in gui.dict_contents[f_name].splitlines():
                parts = line.strip().split('\t')
                if len(parts) >= 2:
                    k = cc_main.convert(parts[0])
                    final_dict[k] = parts[1].split()[0]
    
    # 2. 初始化處理器 (將字典傳入)
    processor = UltraConverter(final_dict, 's2twp')

    # 3. 批量檔案處理
    for entry in bc.manifest_iter():
        fid, href, mtype = entry[0], entry[1], entry[2]
        mtype_l = mtype.lower()
        if any(x in mtype_l for x in ['xhtml', 'xml', 'ncx']) or 'nav' in fid.lower():
            try:
                raw = bc.readfile(fid)
                if raw:
                    # 4. 呼叫單一參數的 process
                    bc.writefile(fid, processor.process(raw))
            except: continue

    return 0