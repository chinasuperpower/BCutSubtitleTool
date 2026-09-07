# -*- coding: utf-8 -*-
import json
import os
import sys
import shutil
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

if getattr(sys, 'frozen', False):
    TOOL_DIR = Path(sys.executable).resolve().parent
else:
    TOOL_DIR = Path(__file__).resolve().parent
PORTABLE_FFMPEG = TOOL_DIR / "ffmpeg" / "bin" / "ffmpeg.exe"
FFMPEG_BIN_DIR = TOOL_DIR / "ffmpeg" / "bin"
if FFMPEG_BIN_DIR.exists():
    os.environ["PATH"] = str(FFMPEG_BIN_DIR) + os.pathsep + os.environ.get("PATH", "")

try:
    from pydub import AudioSegment
    if PORTABLE_FFMPEG.exists():
        AudioSegment.converter = str(PORTABLE_FFMPEG)
        FFMPEG_READY = True
        FFMPEG_MSG = "已加载便携版ffmpeg"
    else:
        FFMPEG_READY = False
        FFMPEG_MSG = "未检测到ffmpeg，音频导出不可用"
except ImportError:
    AudioSegment = None
    FFMPEG_READY = False
    FFMPEG_MSG = "pydub未安装，音频导出不可用"

try:
    from PIL import Image, ImageTk
    PILLOW_READY = True
except ImportError:
    Image = None
    ImageTk = None
    PILLOW_READY = False

MICRO_SEC = 1_000_000
MS_PER_SEC = 1000
DEFAULT_DRAFT_ROOT = Path.home() / "Documents" / "Bcut Drafts"
CONFIG_FILE = TOOL_DIR / "config.json"

def load_saved_draft_root():
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            saved = cfg.get("draft_root", "")
            if saved and Path(saved).exists():
                return saved
    except:
        pass
    return ""

def save_draft_root(path):
    try:
        cfg = {}
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        cfg["draft_root"] = str(path)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except:
        pass

def format_srt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms >= 1000:
        ms = 999
    return "{:02d}:{:02d}:{:02d},{:03d}".format(h, m, s, ms)

def format_duration_ms(ms):
    seconds = ms / 1000.0
    if seconds < 60:
        return "{:.1f}s".format(seconds)
    m = int(seconds // 60)
    s = seconds % 60
    return "{}m{:.1f}s".format(m, s)

def parse_srt_time(time_str):
    hms, ms = time_str.split(",")
    h, m, s = map(int, hms.split(":"))
    return h * 3600 + m * 60 + s + int(ms) / 1000

def format_draft_time(timestamp):
    try:
        dt = datetime.fromtimestamp(timestamp / 10000000 - 62135596800) if timestamp > 1e16 else datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M")
    except:
        return str(timestamp)

def load_bjson(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def save_bjson(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def format_timeline(ms):
    seconds = ms / 1000.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    milli = int((seconds % 1) * 1000)
    return "{:02d}:{:02d}:{:02d}.{:03d}".format(h, m, s, milli)

def get_timeline(bjson_data):
    timeline_widget = bjson_data.get("timelineWidget", {})
    if isinstance(timeline_widget, dict):
        return timeline_widget.get("timeline", {})
    return {}

def get_tts_map(bjson_data):
    timeline_widget = bjson_data.get("timelineWidget", {})
    if isinstance(timeline_widget, dict):
        tts = timeline_widget.get("tts", {})
        if isinstance(tts, dict):
            return tts
    return {}

def extract_tracks(bjson_data):
    timeline = get_timeline(bjson_data)
    tracks = []
    caption_tracks = timeline.get("captionTracks", [])
    if isinstance(caption_tracks, list):
        for idx, track in enumerate(caption_tracks):
            captions = track.get("captions", []) if isinstance(track, dict) else []
            count = len(captions) if isinstance(captions, list) else 0
            tracks.append({
                "id": "caption-{}".format(idx),
                "kind": "caption",
                "index": idx,
                "title": "字幕 {} ({})".format(idx + 1, count),
                "raw": track,
                "clip_count": count
            })
    audio_tracks = timeline.get("audioTracks", [])
    if isinstance(audio_tracks, list):
        for idx, track in enumerate(audio_tracks):
            audio_clips = track.get("audioClips", []) if isinstance(track, dict) else []
            count = len(audio_clips) if isinstance(audio_clips, list) else 0
            tracks.append({
                "id": "audio-{}".format(idx),
                "kind": "audio",
                "index": idx,
                "title": "音轨 {} ({})".format(idx + 1, count),
                "raw": track,
                "clip_count": count
            })
    return tracks

def extract_clips_from_track(track_info, search_text="", bjson_data=None):
    clips = []
    tts_map = get_tts_map(bjson_data) if bjson_data else {}
    caption_by_uid = {}
    if bjson_data:
        timeline = get_timeline(bjson_data)
        for ct in timeline.get("captionTracks", []):
            for cap in ct.get("captions", []):
                uid = cap.get("uid", "")
                if uid:
                    caption_by_uid[uid] = cap
    if track_info["kind"] == "caption":
        captions = track_info["raw"].get("captions", []) if isinstance(track_info["raw"], dict) else []
        for idx, cap in enumerate(captions):
            if not isinstance(cap, dict):
                continue
            uid = cap.get("uid", "")
            text = cap.get("captionText", "") or ""
            in_ms = cap.get("inPoint", 0)
            out_ms = cap.get("outPoint", in_ms + 1)
            dur_ms = max(0, out_ms - in_ms)
            audio_uid = tts_map.get(uid, "") if uid else ""
            has_audio = bool(audio_uid)
            display = text if text.strip() else "(空字幕)"
            search_target = (text + display + "caption").lower()
            if search_text and search_text.lower() not in search_target:
                continue
            clips.append({
                "id": "caption-{}-{}".format(track_info["index"], idx),
                "index": idx,
                "type": "caption",
                "start_ms": in_ms,
                "duration_ms": dur_ms,
                "end_ms": out_ms,
                "text": text,
                "display_name": display,
                "has_audio": has_audio,
                "source_path": "",
                "uid": uid,
                "audio_uid": audio_uid,
                "raw": cap
            })
    elif track_info["kind"] == "audio":
        audio_clips = track_info["raw"].get("audioClips", []) if isinstance(track_info["raw"], dict) else []
        for idx, clip in enumerate(audio_clips):
            if not isinstance(clip, dict):
                continue
            uid = clip.get("uid", "")
            source_path = clip.get("sourcePath", "")
            in_ms = clip.get("inPoint", 0)
            out_ms = clip.get("outPoint", in_ms + 1)
            dur_ms = max(0, out_ms - in_ms)
            asset_info = clip.get("assetInfo", {}) if isinstance(clip.get("assetInfo"), dict) else {}
            display_name = asset_info.get("displayName", "") or source_path or "音频片段"
            linked_caption_uid = ""
            for audio_uid, cap_uid in tts_map.items():
                if audio_uid == uid:
                    linked_caption_uid = cap_uid
                    break
            linked_text = ""
            if linked_caption_uid and linked_caption_uid in caption_by_uid:
                linked_text = caption_by_uid[linked_caption_uid].get("captionText", "")
            display = linked_text if linked_text.strip() else display_name
            search_target = (display + display_name + source_path + "audio").lower()
            if search_text and search_text.lower() not in search_target:
                continue
            clips.append({
                "id": "audio-{}-{}".format(track_info["index"], idx),
                "index": idx,
                "type": "audio",
                "start_ms": in_ms,
                "duration_ms": dur_ms,
                "end_ms": out_ms,
                "text": linked_text,
                "display_name": display,
                "has_audio": True,
                "source_path": source_path,
                "uid": uid,
                "linked_caption_uid": linked_caption_uid,
                "raw": clip
            })
    clips.sort(key=lambda c: c["start_ms"])
    return clips

def export_srt(subs, out_path, remove_formatting=False):
    lines = []
    for idx, sub in enumerate(subs, start=1):
        t1 = format_srt_time(sub["start_sec"])
        t2 = format_srt_time(sub["end_sec"])
        text = sub["text"]
        if remove_formatting:
            text = text.replace("\n", " ").strip()
        lines.append(str(idx))
        lines.append(t1 + " --> " + t2)
        lines.append(text)
        lines.append("")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def read_srt(srt_path):
    with open(srt_path, "r", encoding="utf-8") as f:
        raw = f.read()
    blocks = [b.strip() for b in raw.split("\n\n") if b.strip()]
    items = []
    for blk in blocks:
        lines = [l.strip() for l in blk.splitlines() if l.strip()]
        if len(lines) < 3:
            continue
        time_line = lines[1]
        t_start_str, t_end_str = time_line.split("-->")
        t_start = parse_srt_time(t_start_str.strip())
        t_end = parse_srt_time(t_end_str.strip())
        text = "\n".join(lines[2:])
        items.append({"start_sec": t_start, "end_sec": t_end, "text": text})
    return items

def find_latest_bjson(draft_dir):
    latest_path = None
    latest_mtime = -1
    if not draft_dir or not Path(draft_dir).exists():
        return None
    for f in Path(draft_dir).iterdir():
        if f.is_file() and f.suffix.lower() == ".bjson":
            try:
                mtime = f.stat().st_mtime
                if mtime >= latest_mtime:
                    latest_mtime = mtime
                    latest_path = f
            except:
                continue
    return latest_path

def resolve_audio_file(source_path, draft_dir):
    if not source_path:
        return None
    p = Path(source_path)
    draft = Path(draft_dir)
    if p.is_absolute() and p.exists():
        return p
    candidate = draft / p
    if candidate.exists():
        return candidate
    candidate = draft / "media" / p
    if candidate.exists():
        return candidate
    candidate = draft / "media" / p.name
    if candidate.exists():
        return candidate
    media_dir = draft / "media"
    if media_dir.exists():
        for f in media_dir.rglob("*"):
            if f.is_file():
                if f.name == p.name or f.stem == p.stem:
                    return f
    try:
        for f in draft.rglob("*"):
            if f.is_file() and f.name == p.name:
                return f
    except:
        pass
    return None

def scan_drafts(draft_root):
    drafts = []
    if not draft_root or not Path(draft_root).exists():
        return drafts
    root = Path(draft_root)
    draft_info_file = root / "draftInfo.json"
    if draft_info_file.exists():
        try:
            with open(draft_info_file, "r", encoding="utf-8") as f:
                info = json.load(f)
            draft_infos = info.get("draftInfos", [])
            for item in draft_infos:
                draft_id = item.get("id", "")
                if not draft_id:
                    continue
                draft_dir = root / draft_id
                if not draft_dir.exists():
                    continue
                bjson_path = find_latest_bjson(draft_dir)
                if not bjson_path:
                    continue
                name = item.get("name", "") or draft_id
                modify_time = item.get("modifyTime", 0)
                if modify_time > 1e12:
                    try:
                        modify_time = modify_time / 1000
                    except:
                        modify_time = bjson_path.stat().st_mtime
                cover = draft_dir / "cover.jpg"
                if not cover.exists():
                    for ext in ("*.png", "*.jpeg", "*.webp"):
                        covers = list(draft_dir.glob(ext))
                        if covers:
                            cover = covers[0]
                            break
                drafts.append({
                    "id": draft_id,
                    "name": name,
                    "path": draft_dir,
                    "bjson_path": bjson_path,
                    "modify_time": modify_time,
                    "cover": cover if cover and cover.exists() else None
                })
            drafts.sort(key=lambda d: d["modify_time"], reverse=True)
            return drafts
        except Exception as e:
            print("draftInfo.json 解析失败，回退到文件夹扫描:", e)
    direct_bjson = find_latest_bjson(root)
    if direct_bjson:
        cover = root / "cover.jpg"
        drafts.append({
            "id": str(root),
            "name": root.name,
            "path": root,
            "bjson_path": direct_bjson,
            "modify_time": direct_bjson.stat().st_mtime,
            "cover": cover if cover.exists() else None
        })
        return drafts
    for item in root.iterdir():
        if not item.is_dir():
            continue
        bjson = find_latest_bjson(item)
        if not bjson:
            continue
        try:
            mtime = bjson.stat().st_mtime
            name = item.name
            cover = item / "cover.jpg"
            drafts.append({
                "id": str(item),
                "name": name,
                "path": item,
                "bjson_path": bjson,
                "modify_time": mtime,
                "cover": cover if cover.exists() else None
            })
        except:
            continue
    drafts.sort(key=lambda d: d["modify_time"], reverse=True)
    return drafts

C_BG = "#f8fafc"
C_CARD = "#ffffff"
C_BORDER = "#e2e8f0"
C_TEXT = "#1e293b"
C_TEXT2 = "#64748b"
C_ACCENT = "#16a34a"
C_ACCENT_LT = "#dcfce7"
C_ACCENT_BG = "#f0fdf4"
C_SEL_BORDER = "#22c55e"
C_DANGER = "#dc2626"
C_WARN = "#d97706"
C_HEADER = "#1e293b"
C_HEADER_TXT = "#f1f5f9"
C_STATUSBAR = "#f1f5f9"
C_LOG_BG = "#0f172a"
C_LOG_TXT = "#94a3b8"

class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)
        widget.bind("<ButtonPress>", self._hide)

    def _show(self, event=None):
        if self.tip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 16
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry("+{}+{}".format(x, y))
        tw.attributes("-topmost", True)
        frame = tk.Frame(tw, bg=C_HEADER, padx=10, pady=6)
        frame.pack()
        tk.Label(frame, text=self.text, bg=C_HEADER, fg=C_HEADER_TXT,
                 font=("Microsoft YaHei", 9), justify=tk.LEFT, wraplength=300).pack()
        tw.update_idletasks()

    def _hide(self, event=None):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()

def tip(widget, text):
    Tooltip(widget, text)

class BCutBoxGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("必剪字幕导出工具")
        self.root.geometry("1240x780")
        self.root.minsize(980, 640)
        self.root.configure(bg=C_BG)

        auto_path = load_saved_draft_root()
        if not auto_path and DEFAULT_DRAFT_ROOT.exists():
            auto_path = str(DEFAULT_DRAFT_ROOT)
        if not auto_path:
            alt_path = Path.home() / "AppData" / "Local" / "Bilibili" / "必剪" / "draft"
            if alt_path.exists():
                auto_path = str(alt_path)
        self.draft_root = auto_path
        self.drafts = []
        self.selected_draft = None
        self.bjson_data = None
        self.tracks = []
        self.selected_track_id = None
        self.clips = []
        self.clip_search_text = tk.StringVar()
        self.remove_formatting = tk.BooleanVar(value=False)
        self.align_subtitle_audio = tk.BooleanVar(value=True)
        self.selected_audio_track = tk.StringVar()
        self.log_visible = tk.BooleanVar(value=True)
        self._cover_refs = []

        self._setup_style()
        self._build_header()
        self._build_main()
        self._build_statusbar()
        self._build_log()
        self._log_startup()
        if self.draft_root:
            self.root.after(200, self._refresh_draft_list)

    def _setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=C_BG, foreground=C_TEXT, font=("Microsoft YaHei", 9))
        style.configure("TFrame", background=C_BG)
        style.configure("Card.TFrame", background=C_CARD, relief="solid", borderwidth=1)
        style.configure("TLabel", background=C_BG, foreground=C_TEXT, font=("Microsoft YaHei", 9))
        style.configure("Card.TLabel", background=C_CARD, foreground=C_TEXT)
        style.configure("Title.TLabel", background=C_HEADER, foreground=C_HEADER_TXT, font=("Microsoft YaHei", 12, "bold"))
        style.configure("SubTitle.TLabel", background=C_CARD, foreground=C_TEXT2, font=("Microsoft YaHei", 8))
        style.configure("Hint.TLabel", background=C_CARD, foreground=C_TEXT2, font=("Microsoft YaHei", 8))
        style.configure("Status.TLabel", background=C_STATUSBAR, foreground=C_TEXT2, font=("Microsoft YaHei", 8))
        style.configure("TButton", font=("Microsoft YaHei", 9), padding=(10, 4))
        style.configure("Accent.TButton", font=("Microsoft YaHei", 9, "bold"), foreground=C_ACCENT, padding=(10, 4))
        style.configure("Danger.TButton", font=("Microsoft YaHei", 9), foreground=C_DANGER, padding=(8, 3))
        style.configure("Small.TButton", font=("Microsoft YaHei", 8), padding=(6, 2))
        style.configure("Track.TButton", font=("Microsoft YaHei", 9), padding=(8, 3))
        style.configure("TrackActive.TButton", font=("Microsoft YaHei", 9, "bold"), foreground=C_ACCENT, padding=(8, 3))
        style.configure("TEntry", padding=4)
        style.configure("TCombobox", padding=3)
        style.configure("TProgressbar", thickness=18, background=C_ACCENT, troughcolor="#e2e8f0", bordercolor="#e2e8f0", lightcolor=C_ACCENT, darkcolor=C_ACCENT)
        style.configure("Vertical.TScrollbar", background=C_BG, arrowcolor=C_TEXT2)
        style.configure("Header.TButton", background=C_HEADER, foreground=C_HEADER_TXT, font=("Microsoft YaHei", 9), padding=(8, 3), borderwidth=0)
        style.map("Header.TButton", background=[("active", "#334155")])

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="使用说明", command=self._show_help, accelerator="F1")
        help_menu.add_separator()
        help_menu.add_command(label="关于", command=self._show_about)
        menubar.add_cascade(label="帮助", menu=help_menu)
        self.root.config(menu=menubar)
        self.root.bind("<F1>", lambda e: self._show_help())

    def _build_header(self):
        header = tk.Frame(self.root, bg=C_HEADER, height=44)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)
        tk.Label(header, text="  必剪字幕导出工具", bg=C_HEADER, fg=C_HEADER_TXT,
                 font=("Microsoft YaHei", 12, "bold")).pack(side=tk.LEFT)
        tk.Label(header, text="v1.0  ", bg=C_HEADER, fg="#64748b",
                 font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        btn_frame = tk.Frame(header, bg=C_HEADER)
        btn_frame.pack(side=tk.RIGHT, padx=8)
        self._btn(btn_frame, "使用说明", self._show_help, style="header").pack(side=tk.LEFT, padx=4)
        self._btn(btn_frame, "关于", self._show_about, style="header").pack(side=tk.LEFT, padx=4)

    def _build_main(self):
        main = tk.Frame(self.root, bg=C_BG)
        main.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        self._build_left(main)
        self._build_center(main)
        self._build_right(main)

    def _build_left(self, parent):
        left = tk.Frame(parent, bg=C_CARD, highlightbackground=C_BORDER, highlightthickness=1)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        left.configure(width=280)
        left.grid_propagate(False)

        top = tk.Frame(left, bg=C_CARD)
        top.pack(fill=tk.X, padx=8, pady=(8, 4))
        tk.Label(top, text="草稿列表", bg=C_CARD, fg=C_TEXT, font=("Microsoft YaHei", 10, "bold")).pack(side=tk.LEFT)
        b_ref = self._btn(top, "刷新", self._refresh_draft_list, style="default")
        b_ref.pack(side=tk.RIGHT)
        tip(b_ref, "重新扫描草稿目录")

        dir_frame = tk.Frame(left, bg=C_CARD)
        dir_frame.pack(fill=tk.X, padx=8, pady=(0, 4))
        self.dir_label = tk.Label(dir_frame, text="未选择目录", bg=C_CARD, fg=C_TEXT2,
                                   font=("Microsoft YaHei", 8), wraplength=200, justify=tk.LEFT)
        self.dir_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        b_pick = self._btn(dir_frame, "...", self._pick_draft_root, style="default", width=3)
        b_pick.pack(side=tk.RIGHT)
        tip(b_pick, "选择必剪草稿根目录\n通常在 文档/Bcut Drafts")

        search_frame = tk.Frame(left, bg=C_CARD)
        search_frame.pack(fill=tk.X, padx=8, pady=(0, 6))
        tk.Label(search_frame, text="搜索:", bg=C_CARD, fg=C_TEXT2, font=("Microsoft YaHei", 8)).pack(side=tk.LEFT)
        self.draft_search = tk.Entry(search_frame, bg="#f1f5f9", fg=C_TEXT, font=("Microsoft YaHei", 9),
                                      relief="flat", insertbackground=C_TEXT)
        self.draft_search.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0), ipady=3)
        self.draft_search.bind("<KeyRelease>", lambda e: self._refresh_draft_list())

        self.draft_canvas = tk.Canvas(left, bg=C_CARD, highlightthickness=0)
        self.draft_scroll = ttk.Scrollbar(left, orient="vertical", command=self.draft_canvas.yview)
        self.draft_inner = tk.Frame(self.draft_canvas, bg=C_CARD)
        self.draft_inner.bind("<Configure>", lambda e: self.draft_canvas.configure(scrollregion=self.draft_canvas.bbox("all")))
        self._draft_win = self.draft_canvas.create_window((0, 0), window=self.draft_inner, anchor="nw")
        self.draft_canvas.bind("<Configure>", lambda e: self.draft_canvas.itemconfig(self._draft_win, width=e.width))
        self.draft_canvas.configure(yscrollcommand=self.draft_scroll.set)
        self.draft_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0))
        self.draft_scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 2))
        def _draft_wheel(event):
            self.draft_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.draft_canvas.bind("<MouseWheel>", _draft_wheel)
        self.draft_inner.bind("<MouseWheel>", _draft_wheel)

    def _build_center(self, parent):
        center = tk.Frame(parent, bg=C_CARD, highlightbackground=C_BORDER, highlightthickness=1)
        center.grid(row=0, column=1, sticky="nsew", padx=4)

        top = tk.Frame(center, bg=C_CARD)
        top.pack(fill=tk.X, padx=8, pady=(8, 4))
        tk.Label(top, text="轨道与片段", bg=C_CARD, fg=C_TEXT, font=("Microsoft YaHei", 10, "bold")).pack(side=tk.LEFT)
        b_del = self._btn(top, "删除轨道", self._delete_track, style="danger")
        b_del.pack(side=tk.RIGHT)
        tip(b_del, "删除当前选中的轨道\n自动备份原文件后直接修改\n轨道多时按住Shift+滚轮左右滑动")

        self.track_bar = tk.Frame(center, bg=C_CARD)
        self.track_bar.pack(fill=tk.X, padx=8, pady=(0, 4))
        # 字幕轨道行
        cap_row = tk.Frame(self.track_bar, bg=C_CARD)
        cap_row.pack(fill=tk.X, pady=1)
        tk.Label(cap_row, text="字幕", bg=C_CARD, fg=C_ACCENT, font=("Microsoft YaHei", 8, "bold"), width=4).pack(side=tk.LEFT)
        cap_scroll = tk.Frame(cap_row, bg=C_CARD)
        cap_scroll.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        self.cap_canvas = tk.Canvas(cap_scroll, bg=C_CARD, highlightthickness=0, height=28)
        self.cap_hscroll = ttk.Scrollbar(cap_scroll, orient="horizontal", command=self.cap_canvas.xview)
        self.cap_buttons_frame = tk.Frame(self.cap_canvas, bg=C_CARD)
        self.cap_buttons_frame.bind("<Configure>", lambda e: self.cap_canvas.configure(scrollregion=self.cap_canvas.bbox("all")))
        self.cap_canvas.create_window((0, 0), window=self.cap_buttons_frame, anchor="nw")
        self.cap_canvas.configure(xscrollcommand=self.cap_hscroll.set)
        self.cap_canvas.pack(side=tk.TOP, fill=tk.X, expand=True)
        self.cap_hscroll.pack(side=tk.BOTTOM, fill=tk.X)
        # 音频轨道行
        aud_row = tk.Frame(self.track_bar, bg=C_CARD)
        aud_row.pack(fill=tk.X, pady=1)
        tk.Label(aud_row, text="音频", bg=C_CARD, fg=C_WARN, font=("Microsoft YaHei", 8, "bold"), width=4).pack(side=tk.LEFT)
        aud_scroll = tk.Frame(aud_row, bg=C_CARD)
        aud_scroll.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        self.aud_canvas = tk.Canvas(aud_scroll, bg=C_CARD, highlightthickness=0, height=28)
        self.aud_hscroll = ttk.Scrollbar(aud_scroll, orient="horizontal", command=self.aud_canvas.xview)
        self.aud_buttons_frame = tk.Frame(self.aud_canvas, bg=C_CARD)
        self.aud_buttons_frame.bind("<Configure>", lambda e: self.aud_canvas.configure(scrollregion=self.aud_canvas.bbox("all")))
        self.aud_canvas.create_window((0, 0), window=self.aud_buttons_frame, anchor="nw")
        self.aud_canvas.configure(xscrollcommand=self.aud_hscroll.set)
        self.aud_canvas.pack(side=tk.TOP, fill=tk.X, expand=True)
        self.aud_hscroll.pack(side=tk.BOTTOM, fill=tk.X)

        search_bar = tk.Frame(center, bg=C_CARD)
        search_bar.pack(fill=tk.X, padx=8, pady=(0, 4))
        tk.Label(search_bar, text="筛选:", bg=C_CARD, fg=C_TEXT2, font=("Microsoft YaHei", 8)).pack(side=tk.LEFT)
        self.clip_search = tk.Entry(search_bar, textvariable=self.clip_search_text, bg="#f1f5f9", fg=C_TEXT,
                                     font=("Microsoft YaHei", 9), relief="flat", insertbackground=C_TEXT)
        self.clip_search.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0), ipady=3)
        self.clip_search.bind("<KeyRelease>", lambda e: self._refresh_clip_list())
        tip(self.clip_search, "输入关键词筛选片段内容")

        list_frame = tk.Frame(center, bg=C_CARD)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.clip_canvas = tk.Canvas(list_frame, bg=C_CARD, highlightthickness=0)
        self.clip_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.clip_canvas.yview)
        self.clip_inner = tk.Frame(self.clip_canvas, bg=C_CARD)
        self.clip_inner.bind("<Configure>", lambda e: self.clip_canvas.configure(scrollregion=self.clip_canvas.bbox("all")))
        self.clip_canvas.create_window((0, 0), window=self.clip_inner, anchor="nw")
        self.clip_canvas.configure(yscrollcommand=self.clip_scroll.set)
        self.clip_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.clip_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.clip_header = tk.Frame(center, bg=C_CARD)
        self.clip_header.pack(fill=tk.X, padx=8, pady=(0, 4))
        self.clip_info_label = tk.Label(self.clip_header, text="未加载草稿", bg=C_CARD, fg=C_TEXT2,
                                         font=("Microsoft YaHei", 8))
        self.clip_info_label.pack(side=tk.LEFT)

    def _build_right(self, parent):
        right = tk.Frame(parent, bg=C_BG, width=260)
        right.grid(row=0, column=2, sticky="nsew", padx=(4, 0))
        right.grid_propagate(False)

        self._build_subtitle_card(right)
        self._build_audio_card(right)
        self._build_tips_card(right)

    def _build_subtitle_card(self, parent):
        card = tk.Frame(parent, bg=C_CARD, highlightbackground=C_BORDER, highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 6))
        hd = tk.Frame(card, bg=C_CARD)
        hd.pack(fill=tk.X, padx=8, pady=(6, 2))
        tk.Label(hd, text="字幕", bg=C_CARD, fg=C_TEXT, font=("Microsoft YaHei", 10, "bold")).pack(side=tk.LEFT)

        row1 = tk.Frame(card, bg=C_CARD)
        row1.pack(fill=tk.X, padx=8, pady=2)
        cb1 = tk.Checkbutton(row1, text="去除格式", variable=self.remove_formatting, bg=C_CARD,
                              font=("Microsoft YaHei", 9), activebackground=C_CARD)
        cb1.pack(side=tk.LEFT)
        tip(cb1, "导出SRT时去除HTML格式标签\n如 <i> <b> <font> 等，只保留纯文本")
        b_import = self._btn(row1, "导入 SRT", self._import_subtitle, style="default")
        b_import.pack(side=tk.RIGHT)
        tip(b_import, "将SRT字幕文件导入到草稿\n支持新建轨道或覆盖现有字幕")

        row2 = tk.Frame(card, bg=C_CARD)
        row2.pack(fill=tk.X, padx=8, pady=(2, 6))
        cb2 = tk.Checkbutton(row2, text="对齐音频", variable=self.align_subtitle_audio, bg=C_CARD,
                              font=("Microsoft YaHei", 9), activebackground=C_CARD)
        cb2.pack(side=tk.LEFT)
        tip(cb2, "导出SRT时用TTS音频的实际时间替换字幕时间\n使字幕与语音完全同步（需使用了文本朗读）")
        b_export = self._btn(row2, "导出 SRT", self._export_subtitle, style="default")
        b_export.pack(side=tk.RIGHT)
        tip(b_export, "将当前字幕轨道导出为SRT文件")

    def _build_audio_card(self, parent):
        card = tk.Frame(parent, bg=C_CARD, highlightbackground=C_BORDER, highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 6))
        hd = tk.Frame(card, bg=C_CARD)
        hd.pack(fill=tk.X, padx=8, pady=(6, 2))
        tk.Label(hd, text="音频", bg=C_CARD, fg=C_TEXT, font=("Microsoft YaHei", 10, "bold")).pack(side=tk.LEFT)

        row1 = tk.Frame(card, bg=C_CARD)
        row1.pack(fill=tk.X, padx=8, pady=2)
        tk.Label(row1, text="目标轨:", bg=C_CARD, fg=C_TEXT2, font=("Microsoft YaHei", 8)).pack(side=tk.LEFT)
        self.audio_track_combo = ttk.Combobox(row1, textvariable=self.selected_audio_track, state="readonly", width=14)
        self.audio_track_combo.pack(side=tk.LEFT, padx=(4, 0))
        tip(self.audio_track_combo, "选择要导出的音频轨道")

        row2 = tk.Frame(card, bg=C_CARD)
        row2.pack(fill=tk.X, padx=8, pady=2)
        self.ffmpeg_status_label = tk.Label(row2, text="引擎: 检测中...", bg=C_CARD, fg=C_TEXT2,
                                             font=("Microsoft YaHei", 8))
        self.ffmpeg_status_label.pack(side=tk.LEFT)

        row3 = tk.Frame(card, bg=C_CARD)
        row3.pack(fill=tk.X, padx=8, pady=(2, 4))
        for fmt, lbl in [("wav", "WAV"), ("m4a", "M4A"), ("mp3", "MP3")]:
            b = self._btn(row3, lbl, lambda f=fmt: self._export_audio(f), style="default")
            b.pack(side=tk.LEFT, padx=(0, 4), ipadx=6)
            tip(b, "导出为{}格式\n拼接该轨道所有音频片段".format(lbl))

        row4 = tk.Frame(card, bg=C_CARD)
        row4.pack(fill=tk.X, padx=8, pady=(0, 6))
        self.audio_progress = ttk.Progressbar(row4, mode="determinate", maximum=100)
        self.audio_progress.pack(fill=tk.X)
        self.audio_progress_label = tk.Label(card, text="", bg=C_CARD, fg=C_TEXT2, font=("Microsoft YaHei", 8))
        self.audio_progress_label.pack(fill=tk.X, padx=8, pady=(0, 4))

    def _build_tips_card(self, parent):
        card = tk.Frame(parent, bg=C_ACCENT_BG, highlightbackground=C_ACCENT_LT, highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 6))
        tk.Label(card, text="快捷提示", bg=C_ACCENT_BG, fg=C_ACCENT,
                 font=("Microsoft YaHei", 9, "bold")).pack(anchor="w", padx=8, pady=(6, 2))
        tips = [
            "草稿目录: 文档/Bcut Drafts",
            "双击片段查看详细信息",
            "导入字幕后弹出另存为新文件",
            "删除轨道自动备份后直接修改原文件",
            "按 F1 查看完整使用说明",
        ]
        for t in tips:
            tk.Label(card, text="• " + t, bg=C_ACCENT_BG, fg=C_TEXT2,
                     font=("Microsoft YaHei", 8), anchor="w", justify=tk.LEFT).pack(anchor="w", padx=12, pady=1)
        tk.Frame(card, bg=C_ACCENT_BG, height=4).pack()

    def _build_statusbar(self):
        bar = tk.Frame(self.root, bg=C_STATUSBAR, height=24)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        bar.pack_propagate(False)
        self.status_label = tk.Label(bar, text="就绪", bg=C_STATUSBAR, fg=C_TEXT2,
                                      font=("Microsoft YaHei", 8), anchor="w")
        self.status_label.pack(side=tk.LEFT, padx=8)
        self.status_right = tk.Label(bar, text="", bg=C_STATUSBAR, fg=C_TEXT2,
                                      font=("Microsoft YaHei", 8), anchor="e")
        self.status_right.pack(side=tk.RIGHT, padx=8)

    def _build_log(self):
        container = tk.Frame(self.root, bg=C_LOG_BG, height=100)
        container.pack(fill=tk.X, side=tk.BOTTOM)
        container.pack_propagate(False)
        self.log_container = container

        hd = tk.Frame(container, bg=C_LOG_BG, height=20)
        hd.pack(fill=tk.X)
        hd.pack_propagate(False)
        tk.Label(hd, text=" 操作日志", bg=C_LOG_BG, fg=C_LOG_TXT,
                 font=("Microsoft YaHei", 8, "bold")).pack(side=tk.LEFT)
        b_toggle = tk.Button(hd, text="隐藏", bg=C_LOG_BG, fg=C_LOG_TXT, font=("Microsoft YaHei", 8),
                             relief="flat", cursor="hand2", command=self._toggle_log)
        b_toggle.pack(side=tk.RIGHT, padx=4)
        self.log_toggle_btn = b_toggle

        self.log_text = tk.Text(container, bg=C_LOG_BG, fg=C_LOG_TXT, font=("Consolas", 9),
                                 relief="flat", wrap=tk.WORD, height=5)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
        self.log_text.configure(state=tk.DISABLED)

    def _toggle_log(self):
        if self.log_visible.get():
            self.log_container.configure(height=24)
            self.log_text.pack_forget()
            self.log_toggle_btn.configure(text="显示")
            self.log_visible.set(False)
        else:
            self.log_container.configure(height=100)
            self.log_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
            self.log_toggle_btn.configure(text="隐藏")
            self.log_visible.set(True)

    def log(self, msg):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)
        self.root.update_idletasks()

    def _log_startup(self):
        self.log("=" * 50)
        self.log("  必剪字幕导出工具 启动完成")
        self.log("  工具目录: " + str(TOOL_DIR))
        self.log("  ffmpeg: " + FFMPEG_MSG)
        self.log("  Pillow: " + ("已安装" if PILLOW_READY else "未安装（封面不显示）"))
        self.log("=" * 50)
        self.log("")
        if self.draft_root:
            self.log("已加载草稿目录: " + self.draft_root)
        else:
            self.log("未找到草稿目录，请点击左上角「...」选择必剪草稿目录")
            self.log("默认路径: " + str(DEFAULT_DRAFT_ROOT))
        self._update_statusbar()
        if FFMPEG_READY:
            self.ffmpeg_status_label.config(text="引擎: 已就绪", fg=C_ACCENT)
        else:
            self.ffmpeg_status_label.config(text="引擎: 未就绪", fg=C_DANGER)

    def _update_statusbar(self):
        parts = []
        parts.append("草稿: {}个".format(len(self.drafts)))
        if self.selected_draft:
            parts.append("当前: " + self.selected_draft["name"])
        if self.selected_track_id:
            track = next((t for t in self.tracks if t["id"] == self.selected_track_id), None)
            if track:
                parts.append("轨道: " + track["title"])
        parts.append("片段: {}个".format(len(self.clips)))
        self.status_label.config(text="  |  ".join(parts))
        self.status_right.config(text="ffmpeg: {} | Pillow: {}".format(
            "就绪" if FFMPEG_READY else "未就绪", "已装" if PILLOW_READY else "未装"))

    def _pick_draft_root(self):
        initial = self.draft_root if self.draft_root else str(Path.home())
        path = filedialog.askdirectory(title="选择必剪草稿根目录（包含 draftInfo.json 的文件夹）", initialdir=initial)
        if not path:
            return
        self.draft_root = path
        save_draft_root(path)
        self.dir_label.config(text=path)
        self.log("已选择草稿目录: " + path)
        self._refresh_draft_list()

    def _refresh_draft_list(self):
        if not self.draft_root:
            self.drafts = []
            self._render_drafts()
            return
        search = self.draft_search.get().strip().lower() if hasattr(self, 'draft_search') else ""
        all_drafts = scan_drafts(self.draft_root)
        if search:
            all_drafts = [d for d in all_drafts if search in d["name"].lower()]
        self.drafts = all_drafts
        self.dir_label.config(text=self.draft_root)
        self._render_drafts()
        self._update_statusbar()
        self.log("扫描到 {} 个草稿".format(len(self.drafts)))

    def _render_drafts(self):
        for w in self.draft_inner.winfo_children():
            w.destroy()
        self._cover_refs = []
        if not self.drafts:
            tk.Label(self.draft_inner, text="暂无草稿\n\n请确认目录正确\n或点击「...」重新选择",
                     bg=C_CARD, fg=C_TEXT2, font=("Microsoft YaHei", 9), justify=tk.CENTER).pack(pady=40)
            return
        for draft in self.drafts:
            self._create_draft_card(draft)

    def _create_draft_card(self, draft):
        is_selected = self.selected_draft and self.selected_draft["id"] == draft["id"]
        bg = C_ACCENT_BG if is_selected else C_CARD
        border = C_SEL_BORDER if is_selected else C_BORDER
        card = tk.Frame(self.draft_inner, bg=bg, highlightbackground=border,
                        highlightthickness=2 if is_selected else 1, cursor="hand2")
        card.pack(fill=tk.X, padx=4, pady=3)

        cover_frame = tk.Frame(card, bg="#1e293b", height=56)
        cover_frame.pack(fill=tk.X)
        cover_frame.pack_propagate(False)
        if draft["cover"] and PILLOW_READY:
            try:
                pil_img = Image.open(str(draft["cover"]))
                max_w, max_h = 260, 56
                orig_w, orig_h = pil_img.size
                ratio = min(max_w / orig_w, max_h / orig_h)
                new_w = max(1, int(orig_w * ratio))
                new_h = max(1, int(orig_h * ratio))
                pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
                img = ImageTk.PhotoImage(pil_img)
                self._cover_refs.append(img)
                lbl = tk.Label(cover_frame, image=img, bg="#1e293b")
                lbl.pack(expand=True)
                lbl.bind("<Button-1>", lambda e, d=draft: self._select_draft(d))
            except:
                tk.Label(cover_frame, text="封面", bg="#1e293b", fg="#475569", font=("Microsoft YaHei", 8)).pack(expand=True)
        elif draft["cover"]:
            tk.Label(cover_frame, text="封面(需Pillow)", bg="#1e293b", fg="#475569", font=("Microsoft YaHei", 7)).pack(expand=True)
        else:
            tk.Label(cover_frame, text="无封面", bg="#1e293b", fg="#475569", font=("Microsoft YaHei", 8)).pack(expand=True)

        info = tk.Frame(card, bg=bg)
        info.pack(fill=tk.X, padx=6, pady=4)
        name_color = C_ACCENT if is_selected else C_TEXT
        tk.Label(info, text=draft["name"][:24], bg=bg, fg=name_color,
                 font=("Microsoft YaHei", 9, "bold"), anchor="w").pack(fill=tk.X)
        time_str = format_draft_time(draft["modify_time"])
        tk.Label(info, text=time_str, bg=bg, fg=C_TEXT2, font=("Microsoft YaHei", 8), anchor="w").pack(fill=tk.X)

        btns = tk.Frame(card, bg=bg)
        btns.pack(fill=tk.X, padx=4, pady=(0, 4))
        btn_info = [
            ("重命名", lambda d=draft: self._rename_draft(d), "default",
             "修改草稿显示名称\n仅更新draftInfo.json中的name，不改变文件夹名"),
            ("复制", lambda d=draft: self._duplicate_draft(d), "default",
             "复制整个草稿文件夹作为备份\n生成「名称_副本」，修改草稿前建议先复制"),
            ("删除", lambda d=draft: self._delete_draft(d), "danger",
             "永久删除整个草稿文件夹\n含bjson、封面、媒体文件，不可恢复，请先备份"),
        ]
        for text, cmd, st, tip_text in btn_info:
            b = self._btn(btns, text, cmd, style=st)
            b.pack(side=tk.LEFT, padx=2)
            tip(b, tip_text)
        card.bind("<Button-1>", lambda e, d=draft: self._select_draft(d))
        info.bind("<Button-1>", lambda e, d=draft: self._select_draft(d))

    def _select_draft(self, draft):
        self.selected_draft = draft
        try:
            self.bjson_data = load_bjson(str(draft["bjson_path"]))
        except Exception as e:
            messagebox.showerror("错误", "加载bjson失败:\n" + str(e))
            return
        self.tracks = extract_tracks(self.bjson_data)
        self.selected_track_id = self.tracks[0]["id"] if self.tracks else None
        self._render_drafts()
        self._refresh_track_buttons()
        self._refresh_audio_track_combo()
        self._refresh_clip_list()
        self.log("已加载草稿: " + draft["name"])
        self.log("  轨道数: {} (字幕{} 音频{})".format(
            len(self.tracks),
            sum(1 for t in self.tracks if t["kind"] == "caption"),
            sum(1 for t in self.tracks if t["kind"] == "audio")))
        self._update_statusbar()

    def _refresh_track_buttons(self):
        for w in self.cap_buttons_frame.winfo_children():
            w.destroy()
        for w in self.aud_buttons_frame.winfo_children():
            w.destroy()
        if not self.tracks:
            tk.Label(self.cap_buttons_frame, text="无", bg=C_CARD, fg=C_TEXT2, font=("Microsoft YaHei", 8)).pack(side=tk.LEFT)
            tk.Label(self.aud_buttons_frame, text="无", bg=C_CARD, fg=C_TEXT2, font=("Microsoft YaHei", 8)).pack(side=tk.LEFT)
            return
        def _hscroll(event, canvas):
            if event.state & 0x0001:
                canvas.xview_scroll(int(-1*(event.delta/120)), "units")
        for track in self.tracks:
            is_active = track["id"] == self.selected_track_id
            if track["kind"] == "caption":
                parent = self.cap_buttons_frame
                canvas = self.cap_canvas
            else:
                parent = self.aud_buttons_frame
                canvas = self.aud_canvas
            b = self._btn(parent, track["title"],
                          lambda t=track: self._select_track(t["id"]),
                          style="track_on" if is_active else "track")
            b.pack(side=tk.LEFT, padx=2)
            b.bind("<MouseWheel>", lambda e, c=canvas: _hscroll(e, c))
            tip(b, "{} - {}个片段".format("字幕轨道" if track["kind"] == "caption" else "音频轨道", track["clip_count"]))

    def _select_track(self, track_id):
        self.selected_track_id = track_id
        self._refresh_track_buttons()
        self._refresh_clip_list()
        self._update_statusbar()

    def _refresh_clip_list(self):
        for w in self.clip_inner.winfo_children():
            w.destroy()
        self.clips = []
        if not self.selected_track_id:
            self.clip_info_label.config(text="未加载草稿")
            return
        track = next((t for t in self.tracks if t["id"] == self.selected_track_id), None)
        if not track:
            return
        search = self.clip_search_text.get()
        self.clips = extract_clips_from_track(track, search, self.bjson_data)
        self.clip_info_label.config(text="{} - 共 {} 个片段{}".format(
            track["title"], len(self.clips), "（已筛选）" if search else ""))
        if not self.clips:
            tk.Label(self.clip_inner, text="该轨道暂无片段" + ("\n或无匹配筛选结果" if search else ""),
                     bg=C_CARD, fg=C_TEXT2, font=("Microsoft YaHei", 9), justify=tk.CENTER).pack(pady=30)
            return
        for idx, clip in enumerate(self.clips):
            self._create_clip_row(idx, clip)
        self._update_statusbar()

    def _create_clip_row(self, idx, clip):
        bg = C_ACCENT_BG if idx % 2 == 0 else C_CARD
        row = tk.Frame(self.clip_inner, bg=bg, cursor="hand2")
        row.pack(fill=tk.X)

        tk.Label(row, text="{:>3}".format(idx + 1), bg=bg, fg=C_TEXT2,
                 font=("Consolas", 9), width=4).pack(side=tk.LEFT, padx=(4, 2))
        start_str = format_timeline(clip["start_ms"])
        tk.Label(row, text=start_str, bg=bg, fg=C_ACCENT, font=("Consolas", 9), width=11).pack(side=tk.LEFT)
        tk.Label(row, text="→", bg=bg, fg=C_TEXT2, font=("Consolas", 8)).pack(side=tk.LEFT, padx=2)
        dur = format_duration_ms(clip["duration_ms"])
        tk.Label(row, text=dur, bg=bg, fg=C_TEXT2, font=("Consolas", 8), width=7).pack(side=tk.LEFT)
        text = clip["display_name"][:50]
        tk.Label(row, text=text, bg=bg, fg=C_TEXT, font=("Microsoft YaHei", 9),
                 anchor="w", justify=tk.LEFT).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        if clip["has_audio"]:
            tk.Label(row, text="♪", bg=bg, fg=C_ACCENT, font=("Microsoft YaHei", 10, "bold")).pack(side=tk.RIGHT, padx=4)
        cb = lambda e, c=clip: self._show_clip_detail(c)
        row.bind("<Double-Button-1>", cb)
        for child in row.winfo_children():
            child.bind("<Double-Button-1>", cb)
        tip(row, "双击查看详细信息\n起始: {}\n时长: {}\n{}".format(
            format_timeline(clip["start_ms"]),
            format_duration_ms(clip["duration_ms"]),
            "关联TTS音频" if clip["has_audio"] else "无关联音频"))

    def _show_clip_detail(self, clip):
        info = "片段详情\n\n"
        info += "类型: {}\n".format("字幕" if clip["type"] == "caption" else "音频")
        info += "起始: {}\n".format(format_timeline(clip["start_ms"]))
        info += "结束: {}\n".format(format_timeline(clip["end_ms"]))
        info += "时长: {}\n".format(format_duration_ms(clip["duration_ms"]))
        if clip["type"] == "caption":
            info += "字幕内容:\n{}\n".format(clip["text"] or "(空)")
            info += "关联音频: {}\n".format("是" if clip["has_audio"] else "否")
        else:
            info += "源文件: {}\n".format(clip.get("source_path", "") or "(未知)")
            if clip.get("text"):
                info += "关联字幕: {}\n".format(clip["text"])
        messagebox.showinfo("片段详情", info)

    def _refresh_audio_track_combo(self):
        values = []
        timeline = get_timeline(self.bjson_data) if self.bjson_data else {}
        audio_tracks = timeline.get("audioTracks", [])
        for i, t in enumerate(audio_tracks):
            values.append("音轨 {} ({})".format(i + 1, len(t.get("audioClips", []))))
        self.audio_track_combo["values"] = values
        if values and not self.selected_audio_track.get():
            self.selected_audio_track.set(values[0])

    def _export_subtitle(self):
        if not self.bjson_data:
            messagebox.showwarning("提示", "请先加载一个草稿。")
            return
        timeline = get_timeline(self.bjson_data)
        caption_tracks = timeline.get("captionTracks", [])
        if not caption_tracks:
            messagebox.showwarning("提示", "该草稿没有字幕轨道。")
            return
        tts_map = get_tts_map(self.bjson_data)
        audio_clips_by_uid = {}
        for at in timeline.get("audioTracks", []):
            for ac in at.get("audioClips", []):
                uid = ac.get("uid", "")
                if uid:
                    audio_clips_by_uid[uid] = ac
        subs = []
        align = self.align_subtitle_audio.get()
        for ct in caption_tracks:
            for cap in ct.get("captions", []):
                if not isinstance(cap, dict):
                    continue
                text = cap.get("captionText", "") or ""
                in_ms = cap.get("inPoint", 0)
                out_ms = cap.get("outPoint", in_ms + 1)
                if align:
                    uid = cap.get("uid", "")
                    audio_uid = tts_map.get(uid, "") if uid else ""
                    if audio_uid and audio_uid in audio_clips_by_uid:
                        ac = audio_clips_by_uid[audio_uid]
                        in_ms = ac.get("inPoint", in_ms)
                        out_ms = ac.get("outPoint", out_ms)
                subs.append({"start_sec": in_ms / 1000.0, "end_sec": out_ms / 1000.0, "text": text})
        subs.sort(key=lambda s: s["start_sec"])
        if not subs:
            messagebox.showwarning("提示", "没有可导出的字幕。")
            return
        default_name = self.selected_draft["name"] + "_字幕.srt"
        out_path = filedialog.asksaveasfilename(
            title="导出 SRT 字幕",
            initialdir=str(self.selected_draft["path"]),
            initialfile=default_name,
            defaultextension=".srt",
            filetypes=[("SRT 字幕", "*.srt")]
        )
        if not out_path:
            return
        try:
            export_srt(subs, out_path, self.remove_formatting.get())
            self.log("✅ 字幕导出完成: " + out_path)
            self.log("   共 {} 条字幕{}".format(len(subs), "（已对齐音频）" if align else ""))
            messagebox.showinfo("成功", "导出完成！\n共 {} 条字幕{}\n文件: {}".format(
                len(subs), "（已对齐音频）" if align else "", out_path))
        except Exception as e:
            self.log("❌ 导出失败: " + str(e))
            messagebox.showerror("失败", str(e))

    def _import_subtitle(self):
        if not self.bjson_data or not self.selected_draft:
            messagebox.showwarning("提示", "请先加载一个草稿。")
            return
        srt_path = filedialog.askopenfilename(
            title="选择 SRT 字幕文件",
            initialdir=self.draft_root,
            filetypes=[("SRT 字幕", "*.srt"), ("所有文件", "*.*")]
        )
        if not srt_path:
            return
        try:
            srt_items = read_srt(Path(srt_path))
            if not srt_items:
                messagebox.showwarning("提示", "SRT 文件中没有字幕。")
                return
            timeline = get_timeline(self.bjson_data)
            caption_tracks = timeline.get("captionTracks", [])
            has_existing = any(len(t.get("captions", [])) > 0 for t in caption_tracks if isinstance(t, dict))
            mode = "overwrite"
            if has_existing:
                choice = messagebox.askyesnocancel(
                    "导入模式",
                    "该草稿已有字幕。请选择导入方式：\n\n"
                    "【是】覆盖当前字幕轨道\n"
                    "【否】新建一条字幕轨道\n"
                    "【取消】取消导入",
                    icon="question")
                if choice is None:
                    return
                mode = "overwrite" if choice else "createNew"
            mapped = []
            for item in srt_items:
                in_ms = int(round(item["start_sec"] * 1000))
                out_ms = int(round(item["end_sec"] * 1000))
                mapped.append({
                    "assetInfo": {"itemName": item["text"]},
                    "captionText": item["text"],
                    "inPoint": in_ms, "outPoint": out_ms,
                    "opacity": 1, "scaleX": 1, "scaleY": 1,
                    "textColor": {"a": 1, "b": 1, "g": 1, "r": 1}})
            if mode == "createNew":
                caption_tracks.append({"captions": mapped, "trackType": 3})
                self.log("   模式: 新建字幕轨道")
            else:
                target_idx = 0
                for i, t in enumerate(caption_tracks):
                    if isinstance(t, dict) and len(t.get("captions", [])) > 0:
                        target_idx = i
                        break
                if caption_tracks and isinstance(caption_tracks[target_idx], dict):
                    caption_tracks[target_idx]["captions"] = mapped
                    if "trackType" not in caption_tracks[target_idx]:
                        caption_tracks[target_idx]["trackType"] = 3
                else:
                    caption_tracks.append({"captions": mapped, "trackType": 3})
                self.log("   模式: 覆盖字幕轨道 {}".format(target_idx + 1))
            timeline["captionTracks"] = caption_tracks
            if "timelineWidget" not in self.bjson_data or not isinstance(self.bjson_data["timelineWidget"], dict):
                self.bjson_data["timelineWidget"] = {}
            self.bjson_data["timelineWidget"]["timeline"] = timeline
            default_out = self.selected_draft["name"] + "_导入字幕.bjson"
            save_path = filedialog.asksaveasfilename(
                title="另存为新的 bjson（请勿覆盖原文件）",
                initialdir=str(self.selected_draft["path"]),
                initialfile=default_out,
                defaultextension=".bjson",
                filetypes=[("BJSON", "*.bjson")])
            if not save_path:
                return
            save_bjson(Path(save_path), self.bjson_data)
            self.tracks = extract_tracks(self.bjson_data)
            if mode == "createNew":
                caption_tracks_list = [t for t in self.tracks if t["kind"] == "caption"]
                if caption_tracks_list:
                    self.selected_track_id = caption_tracks_list[-1]["id"]
            self._refresh_track_buttons()
            self._refresh_clip_list()
            self._update_statusbar()
            self.log("✅ 字幕导入完成: " + save_path)
            self.log("   共 {} 条字幕{}".format(len(srt_items), "（新建轨道）" if mode == "createNew" else "（覆盖轨道）"))
            messagebox.showinfo("成功", "导入完成！\n共 {} 条字幕{}\n已保存到: {}".format(
                len(srt_items), "（新建轨道）" if mode == "createNew" else "（覆盖轨道）", save_path))
        except Exception as e:
            import traceback
            self.log("❌ 导入失败: " + str(e))
            self.log(traceback.format_exc())
            messagebox.showerror("失败", str(e))

    def _export_audio(self, fmt):
        if not self.bjson_data or not self.selected_draft:
            messagebox.showwarning("提示", "请先加载一个草稿。")
            return
        if not FFMPEG_READY or AudioSegment is None:
            messagebox.showwarning("提示", "ffmpeg 未就绪，无法导出音频。")
            return
        timeline = get_timeline(self.bjson_data)
        audio_tracks = timeline.get("audioTracks", [])
        if not audio_tracks:
            messagebox.showwarning("提示", "该草稿没有音频轨道。")
            return
        selected_title = self.selected_audio_track.get()
        target_track = None
        for i, t in enumerate(audio_tracks):
            title = "音轨 {} ({})".format(i + 1, len(t.get("audioClips", [])))
            if title == selected_title:
                target_track = t
                break
        if target_track is None:
            target_track = audio_tracks[0]
        audio_clips = target_track.get("audioClips", [])
        if not audio_clips:
            messagebox.showwarning("提示", "目标音轨没有音频片段。")
            return
        default_name = self.selected_draft["name"] + "_音频." + fmt
        out_path = filedialog.asksaveasfilename(
            title="导出音频", initialdir=str(self.selected_draft["path"]),
            initialfile=default_name, defaultextension="." + fmt,
            filetypes=[(fmt.upper() + " 音频", "*." + fmt)])
        if not out_path:
            return
        try:
            self.audio_progress["value"] = 0
            self.audio_progress_label.config(text="准备中...")
            self.root.update()
            segments = []
            total = len(audio_clips)
            for idx, clip in enumerate(audio_clips):
                self.audio_progress["value"] = int((idx / max(total, 1)) * 100)
                self.audio_progress_label.config(text="处理中 {}/{}".format(idx + 1, total))
                self.root.update()
                source_path = clip.get("sourcePath", "")
                if not source_path:
                    continue
                audio_file = resolve_audio_file(source_path, self.selected_draft["path"])
                if not audio_file:
                    self.log("   跳过片段 {}: 找不到源文件 {}".format(idx, Path(source_path).name))
                    continue
                trim_in = clip.get("trimIn", 0)
                trim_out = clip.get("trimOut", 0)
                asset_info = clip.get("assetInfo", {}) if isinstance(clip.get("assetInfo"), dict) else {}
                duration = asset_info.get("duration", 0)
                start_ms = trim_in
                end_ms = trim_out if trim_out > 0 else duration
                try:
                    audio = AudioSegment.from_file(str(audio_file))
                    piece = audio[start_ms:end_ms] if end_ms > start_ms else audio
                    segments.append(piece)
                except Exception as e:
                    self.log("   跳过片段 {}: {}".format(idx, str(e)))
            if not segments:
                messagebox.showwarning("提示", "没有找到可拼接的音频片段。")
                return
            final = AudioSegment.empty()
            for seg in segments:
                final += seg
            if not out_path.lower().endswith("." + fmt):
                out_path = out_path + "." + fmt
            self.log("   导出格式: {} | 总时长: {:.1f}s".format(fmt.upper(), len(final) / 1000.0))
            self.log("   输出路径: " + out_path)
            if fmt == "wav":
                final = final.set_frame_rate(44100).set_channels(2).set_sample_width(2)
                final.export(out_path, format="wav")
            elif fmt == "m4a":
                final.export(out_path, format="ipod")
            elif fmt == "mp3":
                final.export(out_path, format="mp3", bitrate="192k")
            if Path(out_path).exists():
                size_kb = Path(out_path).stat().st_size / 1024
                self.log("   文件大小: {:.1f} KB".format(size_kb))
            else:
                self.log("   ⚠ 文件未生成！")
            self.audio_progress["value"] = 100
            self.audio_progress_label.config(text="完成")
            self.log("✅ 音频导出完成: " + out_path)
            self.log("   拼接 {} 个片段".format(len(segments)))
            messagebox.showinfo("成功", "导出完成！\n拼接 {} 个片段\n文件: {}".format(len(segments), out_path))
        except Exception as e:
            import traceback
            self.audio_progress["value"] = 0
            self.audio_progress_label.config(text="失败")
            self.log("❌ 音频导出失败: " + str(e))
            self.log(traceback.format_exc())
            messagebox.showerror("失败", str(e))

    def _delete_track(self):
        if not self.selected_track_id or not self.bjson_data or not self.selected_draft:
            messagebox.showwarning("提示", "请先选择一个轨道。")
            return
        track = next((t for t in self.tracks if t["id"] == self.selected_track_id), None)
        if not track:
            return
        msg = "确定删除轨道「{}」？\n\n".format(track["title"])
        msg += "该轨道下的所有片段将被移除。\n\n"
        msg += "将自动备份原文件，然后直接修改原项目。\n"
        msg += "备份文件在同一目录下，文件名带_backup标识。"
        if not messagebox.askyesno("⚠ 确认删除轨道", msg, icon="warning"):
            return
        try:
            timeline = get_timeline(self.bjson_data)
            if track["kind"] == "caption":
                caption_tracks = timeline.get("captionTracks", [])
                if 0 <= track["index"] < len(caption_tracks):
                    del caption_tracks[track["index"]]
                    timeline["captionTracks"] = caption_tracks
            elif track["kind"] == "audio":
                audio_tracks = timeline.get("audioTracks", [])
                if 0 <= track["index"] < len(audio_tracks):
                    del audio_tracks[track["index"]]
                    timeline["audioTracks"] = audio_tracks
            if "timelineWidget" not in self.bjson_data or not isinstance(self.bjson_data["timelineWidget"], dict):
                self.bjson_data["timelineWidget"] = {}
            self.bjson_data["timelineWidget"]["timeline"] = timeline
            # 自动备份原文件
            orig_path = Path(self.selected_draft["bjson_path"])
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = orig_path.parent / "{}_backup_{}.bjson".format(orig_path.stem, timestamp)
            shutil.copy2(str(orig_path), str(backup_path))
            self.log("   已备份原文件: " + backup_path.name)
            # 直接写入原文件
            save_bjson(orig_path, self.bjson_data)
            self.log("✅ 轨道删除完成: " + track["title"])
            self.log("   已直接修改原文件: " + orig_path.name)
            self.tracks = extract_tracks(self.bjson_data)
            self.selected_track_id = self.tracks[0]["id"] if self.tracks else None
            self._refresh_track_buttons()
            self._refresh_audio_track_combo()
            self._refresh_clip_list()
            self._update_statusbar()
            messagebox.showinfo("成功", "轨道已删除！\n\n原文件已直接修改。\n备份文件: {}\n\n打开必剪即可看到效果。".format(backup_path.name))
        except Exception as e:
            import traceback
            self.log("❌ 删除轨道失败: " + str(e))
            self.log(traceback.format_exc())
            messagebox.showerror("失败", str(e))

    def _rename_draft(self, draft):
        new_name = simpledialog.askstring("重命名草稿", "输入新名称:", initialvalue=draft["name"], parent=self.root)
        if not new_name or new_name.strip() == draft["name"]:
            return
        new_name = new_name.strip()
        draft_info_file = Path(self.draft_root) / "draftInfo.json" if self.draft_root else None
        if draft_info_file and draft_info_file.exists():
            try:
                with open(draft_info_file, "r", encoding="utf-8") as f:
                    info = json.load(f)
                draft_infos = info.get("draftInfos", [])
                found = False
                for item in draft_infos:
                    if item.get("id", "") == draft["id"]:
                        item["name"] = new_name
                        found = True
                        break
                if not found:
                    messagebox.showerror("错误", "在 draftInfo.json 中未找到该草稿。")
                    return
                info["draftInfos"] = draft_infos
                with open(draft_info_file, "w", encoding="utf-8") as f:
                    json.dump(info, f, ensure_ascii=False, indent=2)
                self.log("✅ 重命名: {} -> {}".format(draft["name"], new_name))
                self._refresh_draft_list()
            except Exception as e:
                messagebox.showerror("失败", str(e))
        else:
            new_path = draft["path"].parent / new_name
            if new_path.exists():
                messagebox.showerror("错误", "该名称已存在！")
                return
            try:
                draft["path"].rename(str(new_path))
                self.log("✅ 重命名文件夹: {} -> {}".format(draft["name"], new_name))
                self._refresh_draft_list()
            except Exception as e:
                messagebox.showerror("失败", str(e))

    def _duplicate_draft(self, draft):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_name = draft["name"] + "_副本"
        new_id = "copy_{}".format(timestamp)
        draft_root = Path(self.draft_root) if self.draft_root else draft["path"].parent
        new_path = draft_root / new_id
        counter = 1
        while new_path.exists():
            new_id = "copy_{}_{}".format(timestamp, counter)
            new_path = draft_root / new_id
            counter += 1
        try:
            shutil.copytree(str(draft["path"]), str(new_path))
            draft_info_file = draft_root / "draftInfo.json"
            if draft_info_file.exists():
                try:
                    with open(draft_info_file, "r", encoding="utf-8") as f:
                        info = json.load(f)
                    draft_infos = info.get("draftInfos", [])
                    draft_infos.append({
                        "id": new_id,
                        "name": new_name,
                        "modifyTime": int(datetime.now().timestamp() * 1000)
                    })
                    info["draftInfos"] = draft_infos
                    with open(draft_info_file, "w", encoding="utf-8") as f:
                        json.dump(info, f, ensure_ascii=False, indent=2)
                    self.log("   已注册到 draftInfo.json")
                except Exception as e:
                    self.log("   ⚠ 更新 draftInfo.json 失败: " + str(e))
            self.log("✅ 复制草稿: {} -> {}".format(draft["name"], new_name))
            self.log("   文件夹: " + new_id)
            self._refresh_draft_list()
        except Exception as e:
            messagebox.showerror("失败", str(e))

    def _delete_draft(self, draft):
        msg = "确定删除草稿「{}」？\n\n".format(draft["name"])
        msg += "将永久删除整个草稿文件夹，包括：\n"
        msg += "  • 项目文件 (.bjson)\n"
        msg += "  • 封面图 (cover.jpg)\n"
        msg += "  • 媒体文件 (media 目录)\n\n"
        msg += "此操作不可恢复！\n建议先使用「复制」功能备份。"
        if not messagebox.askyesno("⚠ 确认删除", msg, icon="warning"):
            return
        try:
            shutil.rmtree(str(draft["path"]))
            self.log("✅ 删除草稿: " + draft["name"])
            if self.selected_draft and self.selected_draft["id"] == draft["id"]:
                self.selected_draft = None
                self.bjson_data = None
            self._refresh_draft_list()
        except Exception as e:
            messagebox.showerror("失败", str(e))

    def _show_about(self):
        year = datetime.now().year
        win = tk.Toplevel(self.root)
        win.title("关于")
        win.geometry("380x280")
        win.resizable(False, False)
        win.configure(bg=C_CARD)
        win.transient(self.root)
        win.grab_set()
        tk.Label(win, text="超哥工具箱系列", bg=C_CARD, fg=C_ACCENT,
                 font=("Microsoft YaHei", 14, "bold")).pack(pady=(20, 4))
        tk.Label(win, text="必剪字幕导出工具", bg=C_CARD, fg=C_TEXT,
                 font=("Microsoft YaHei", 12)).pack(pady=(0, 2))
        tk.Label(win, text="版本 1.0", bg=C_CARD, fg=C_TEXT2,
                 font=("Microsoft YaHei", 9)).pack(pady=(0, 12))
        tk.Frame(win, bg=C_BORDER, height=1, width=300).pack()
        info_text = (
            "\n必剪草稿字幕与音频批量处理工具\n"
            "支持 SRT 字幕导入导出、音频轨道导出\n\n"
            "运行环境: Python {}\n".format(sys.version.split()[0]) +
            "ffmpeg: {}\n".format("已就绪" if FFMPEG_READY else "未就绪") +
            "Pillow: {}\n".format("已安装" if PILLOW_READY else "未安装") +
            "\n© {} 超哥工具箱".format(year)
        )
        tk.Label(win, text=info_text, bg=C_CARD, fg=C_TEXT2,
                 font=("Microsoft YaHei", 9), justify=tk.CENTER).pack()
        self._btn(win, "确定", win.destroy, style="primary", width=10).pack(pady=12)
        self._center_window(win)

    def _center_window(self, win):
        win.update_idletasks()
        w = win.winfo_width()
        h = win.winfo_height()
        x = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - h) // 2
        win.geometry("+{}+{}".format(max(0, x), max(0, y)))

    def _btn(self, parent, text, command, style="default", width=None):
        styles = {
            "default":   {"bg": C_CARD,      "fg": C_ACCENT, "hover": C_ACCENT_LT, "font": ("Microsoft YaHei", 9)},
            "primary":   {"bg": C_ACCENT,    "fg": "white",   "hover": "#15803d",   "font": ("Microsoft YaHei", 9, "bold")},
            "danger":    {"bg": C_CARD,      "fg": C_DANGER,  "hover": "#fee2e2",   "font": ("Microsoft YaHei", 9)},
            "track":     {"bg": C_CARD,      "fg": C_TEXT,    "hover": C_ACCENT_LT, "font": ("Microsoft YaHei", 9)},
            "track_on":  {"bg": C_ACCENT,    "fg": "white",   "hover": "#15803d",   "font": ("Microsoft YaHei", 9, "bold")},
            "header":    {"bg": C_HEADER,    "fg": C_HEADER_TXT, "hover": "#334155", "font": ("Microsoft YaHei", 9)},
        }
        c = styles.get(style, styles["default"])
        btn = tk.Button(parent, text=text, bg=c["bg"], fg=c["fg"], font=c["font"],
                        relief="flat", cursor="hand2", command=command,
                        activebackground=c["hover"], activeforeground=c["fg"], bd=0)
        if width:
            btn.configure(width=width)
        btn.bind("<Enter>", lambda e: btn.configure(bg=c["hover"]))
        btn.bind("<Leave>", lambda e: btn.configure(bg=c["bg"]))
        return btn

    def _show_help(self):
        win = tk.Toplevel(self.root)
        win.title("使用说明")
        win.geometry("680x600")
        win.configure(bg=C_CARD)
        win.transient(self.root)

        nav = tk.Frame(win, bg=C_HEADER, height=36)
        nav.pack(fill=tk.X)
        nav.pack_propagate(False)
        tk.Label(nav, text="  使用说明", bg=C_HEADER, fg=C_HEADER_TXT,
                 font=("Microsoft YaHei", 11, "bold")).pack(side=tk.LEFT)

        text_frame = tk.Frame(win, bg=C_CARD)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text = tk.Text(text_frame, bg=C_CARD, fg=C_TEXT, font=("Microsoft YaHei", 10),
                        wrap=tk.WORD, yscrollcommand=scrollbar.set, relief="flat", padx=8, pady=8)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text.yview)

        help_content = """
【一、软件简介】

必剪字幕导出工具是一款针对必剪（Bcut）草稿文件的批量处理工具，可以读取必剪项目中的字幕轨道和音频轨道，实现字幕的导入导出、音频的批量拼接导出等功能。


【二、草稿目录说明】

1. 必剪默认草稿目录：
   C:\\Users\\你的用户名\\Documents\\Bcut Drafts

2. 该目录下包含：
   - draftInfo.json：草稿索引文件（记录所有草稿的名称和修改时间）
   - 多个以ID命名的草稿文件夹，每个文件夹内包含：
     * project.bjson（或其他名称的.bjson）：项目数据文件
     * cover.jpg：草稿封面图
     * media/：媒体文件目录（音频、视频等）

3. 首次启动会自动检测默认目录，也可点击左上角「...」按钮手动选择。
   选择的目录会被自动记忆，下次启动直接加载。


【三、左侧草稿列表操作】

1. 刷新：重新扫描当前目录下的所有草稿
2. 搜索：按草稿名称筛选
3. 点击草稿卡片：加载该草稿的轨道和片段数据
4. 重命名：修改草稿显示名称（仅修改draftInfo.json中的name，不改变文件夹名）
5. 复制：复制整个草稿文件夹
6. 删除：删除整个草稿文件夹（不可恢复，请谨慎操作）

注意：草稿封面图为cover.jpg，需要安装Pillow库才能显示。


【四、中间轨道与片段】

1. 轨道切换：点击轨道标签切换查看字幕轨或音轨
2. 删除轨道：删除当前选中的轨道（另存为新文件，不影响原草稿）
3. 筛选：输入关键词筛选片段内容
4. 片段列表：显示序号、起始时间、时长、内容
   - 带 ♪ 标记的字幕表示关联了TTS音频（文本朗读）
5. 双击片段：查看该片段的详细信息


【五、字幕操作】

1. 去除格式（复选框）：
   导出SRT时去除HTML格式标签（如 <i>、<b>、<font> 等），只保留纯文本。
   建议保持勾选，避免必剪不识别标签导致显示异常。

2. 对齐音频（复选框，默认勾选）：
   导出SRT时，使用TTS音频的实际起止时间替换字幕原本的时间。
   适用于使用了必剪「文本朗读」功能的场景，使字幕与语音完全同步。
   如果没有使用文本朗读，此选项无效。

3. 导入 SRT：
   将外部SRT字幕文件导入到草稿中。
   - 如果草稿已有字幕，会提示选择：
     * 覆盖当前字幕轨道：替换现有字幕
     * 新建一条字幕轨道：保留原有字幕，新增一条
   - 导入后另存为新的.bjson文件，请勿覆盖原文件

4. 导出 SRT：
   将当前草稿的所有字幕导出为SRT格式文件。
   受「去除格式」和「对齐音频」两个选项影响。


【六、音频操作】

1. 目标轨：选择要导出的音频轨道
2. 引擎状态：显示ffmpeg是否就绪（音频导出依赖ffmpeg）
3. 导出 WAV：无损波形音频，文件较大
4. 导出 M4A：AAC压缩音频，文件较小
5. 导出 MP3：MP3压缩音频，兼容性好

导出时会自动拼接该轨道下的所有音频片段，按时间顺序合并为一个完整音频文件。
如果某个片段找不到源文件，会自动跳过并在日志中提示。


【七、注意事项】

1. 所有修改操作（导入字幕、删除轨道等）都会另存为新的.bjson文件，
   请勿直接覆盖原项目文件，建议先备份。

2. 导入新的.bjson后，需要将其复制到草稿目录替换原有的.bjson文件，
   然后在必剪中重新打开草稿才能看到修改效果。

3. 音频导出功能依赖ffmpeg，工具目录下已内置便携版ffmpeg。
   如果ffmpeg未就绪，请运行工具目录下的install_ffmpeg.bat。

4. 草稿封面显示依赖Pillow库，如未安装请执行：
   pip install Pillow

5. 本工具仅读取和修改.bjson项目文件，不会修改必剪软件本身或系统设置。


【八、常见问题】

Q: 选择目录后提示没有草稿？
A: 请确认选择的是包含draftInfo.json的根目录（通常是 文档/Bcut Drafts），
   而不是单个草稿文件夹。也可以直接选择单个草稿文件夹。

Q: 导出音频提示找不到源文件？
A: 请确认草稿目录完整，media文件夹存在且包含音频文件。
   工具会自动按多种路径方式查找，找不到的片段会跳过。

Q: 重命名草稿后必剪里看不到？
A: 重命名仅修改draftInfo.json中的显示名称，不改变文件夹名。
   如果修改后必剪无法识别，请检查draftInfo.json是否被正确更新。

Q: 封面不显示？
A: 封面为cover.jpg格式，需要安装Pillow库才能在界面中显示。
   不影响字幕和音频的导出功能。
"""
        text.insert(tk.END, help_content)
        text.configure(state=tk.DISABLED)

        btn_frame = tk.Frame(win, bg=C_CARD)
        btn_frame.pack(fill=tk.X, pady=8)
        self._btn(btn_frame, "关闭", win.destroy, style="primary", width=10).pack()
        self._center_window(win)


if __name__ == "__main__":
    win = tk.Tk()
    app = BCutBoxGUI(win)
    win.mainloop()
