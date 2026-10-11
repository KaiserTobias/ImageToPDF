"""Oberfläche: customtkinter + ttk.Treeview. Enthält keine Konvertierungslogik."""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

import customtkinter as ctk
from PIL import Image, ImageTk

from . import APP_NAME, __version__, converter, inspector, planner, preview, scanner
from .models import (
    IMAGE_FORMATS,
    ConflictRule,
    FitMode,
    ImageItem,
    Orientation,
    PageFormat,
    RunSummary,
)
from .settings import Settings, SettingsStore
from .texts import (
    CONFLICT_LABELS,
    FIT_LABELS,
    ORIENTATION_LABELS,
    PAGE_FORMAT_LABELS,
    STATUS_LABELS,
    T,
    label_to_enum,
)

try:  # Drag & Drop ist optional
    from tkinterdnd2 import DND_FILES, TkinterDnD  # type: ignore
    HAS_DND = True
except Exception:  # pragma: no cover
    HAS_DND = False

THUMB_H = 48
THUMB_W = 72
ROW_H = THUMB_H + 8
PREVIEW_BOX = 220

COLUMNS = ("check", "name", "subdir", "format", "res", "size", "page", "orient", "fit", "conflict", "target", "status")
CYCLE_COLUMNS = {"page", "orient", "fit", "conflict"}


def _human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def _open_folder(path: Path) -> None:
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.store = SettingsStore()
        self.settings: Settings = self.store.load()
        ctk.set_appearance_mode(self.settings.appearance)
        ctk.set_default_color_theme("blue")

        self.title(f"{APP_NAME} {__version__}")
        self.geometry("1340x880")
        self.minsize(1050, 720)

        self.items: list[ImageItem] = []
        self.iid_to_item: dict[str, ImageItem] = {}
        self.item_to_iid: dict[int, str] = {}
        self.photos: dict[str, ImageTk.PhotoImage] = {}
        self.queue: queue.Queue = queue.Queue()
        self.worker: Optional[threading.Thread] = None
        self.cancel_event = threading.Event()
        self.busy = False
        self.preview_image: Optional[ctk.CTkImage] = None
        self.last_progress_item: Optional[ImageItem] = None

        self.source_var = tk.StringVar()
        self.target_var = tk.StringVar()
        self.target_mode = tk.StringVar(value="beside")
        self.format_vars = {f: tk.BooleanVar(value=(f in self.settings.formats)) for f in IMAGE_FORMATS}
        self.open_after_var = tk.BooleanVar(value=self.settings.open_target_after)
        self.dark_var = tk.BooleanVar(value=ctk.get_appearance_mode() == "Dark")
        self.status_var = tk.StringVar(value=T["ready"])

        self._build_ui()
        self._style_treeview()
        self._setup_dnd()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll_queue)

    # ------------------------------------------------------------------ Aufbau
    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- Kopfbereich: Quelle, Formate, Ziel
        top = ctk.CTkFrame(self, corner_radius=12)
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        top.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top, text=T["source"], anchor="w").grid(row=0, column=0, padx=(14, 8), pady=(12, 4), sticky="w")
        self.source_entry = ctk.CTkEntry(top, textvariable=self.source_var, placeholder_text=T["drop_hint"], state="readonly")
        self.source_entry.grid(row=0, column=1, padx=4, pady=(12, 4), sticky="ew")
        ctk.CTkButton(top, text=T["browse"], width=130, command=self._choose_source).grid(row=0, column=2, padx=(4, 14), pady=(12, 4))

        ctk.CTkLabel(top, text=T["formats"], anchor="w").grid(row=1, column=0, padx=(14, 8), pady=4, sticky="w")
        fmt_frame = ctk.CTkFrame(top, fg_color="transparent")
        fmt_frame.grid(row=1, column=1, columnspan=2, sticky="w", padx=0, pady=4)
        for i, f in enumerate(IMAGE_FORMATS):
            ctk.CTkCheckBox(fmt_frame, text=f.upper(), variable=self.format_vars[f], width=80).grid(row=0, column=i, padx=(4, 12), pady=2)

        ctk.CTkRadioButton(top, text=T["target_beside"], variable=self.target_mode, value="beside",
                           command=self._on_target_change).grid(row=2, column=0, columnspan=3, padx=14, pady=(6, 2), sticky="w")
        ctk.CTkRadioButton(top, text=T["target_dir"], variable=self.target_mode, value="dir",
                           command=self._on_target_change).grid(row=3, column=0, columnspan=3, padx=14, pady=(2, 2), sticky="w")
        self.target_entry = ctk.CTkEntry(top, textvariable=self.target_var, state="readonly")
        self.target_entry.grid(row=4, column=1, padx=4, pady=(2, 12), sticky="ew")
        self.target_button = ctk.CTkButton(top, text=T["browse"], width=130, command=self._choose_target)
        self.target_button.grid(row=4, column=2, padx=(4, 14), pady=(2, 12))

        action = ctk.CTkFrame(top, fg_color="transparent")
        action.grid(row=4, column=0, padx=(14, 8), pady=(2, 12), sticky="w")
        self.scan_button = ctk.CTkButton(action, text=T["scan"], width=170, command=self._start_scan)
        self.scan_button.grid(row=0, column=0)

        # Hell/Dunkel oben rechts
        ctk.CTkSwitch(top, text=T["appearance"], variable=self.dark_var, command=self._toggle_appearance).grid(
            row=1, column=2, padx=(4, 14), pady=4, sticky="e")

        # --- Tabelle
        table = ctk.CTkFrame(self, corner_radius=12)
        table.grid(row=1, column=0, sticky="nsew", padx=12, pady=6)
        table.grid_columnconfigure(0, weight=1)
        table.grid_rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(table, columns=COLUMNS, show="tree headings", selectmode="extended", height=8)
        headings = {
            "#0": (T["col_thumb"], 80, "center"),
            "check": (T["col_check"], 32, "center"),
            "name": (T["col_name"], 150, "w"),
            "subdir": (T["col_subdir"], 110, "w"),
            "format": (T["col_format"], 70, "center"),
            "res": (T["col_resolution"], 95, "center"),
            "size": (T["col_filesize"], 75, "e"),
            "page": (T["col_page"], 108, "center"),
            "orient": (T["col_orientation"], 100, "center"),
            "fit": (T["col_fit"], 95, "center"),
            "conflict": (T["col_conflict"], 100, "center"),
            "target": (T["col_target"], 180, "w"),
            "status": (T["col_status"], 130, "w"),
        }
        for col, (text, width, anchor) in headings.items():
            self.tree.heading(col, text=text, anchor="w" if anchor == "w" else "center")
            self.tree.column(col, width=width, minwidth=max(30, width - 30), anchor=anchor, stretch=(col in ("target", "name", "subdir")))
        self.tree.column("#0", stretch=False)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=(10, 0))
        vsb = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.grid(row=0, column=1, sticky="ns", padx=(0, 10), pady=(10, 0))
        hsb.grid(row=1, column=0, sticky="ew", padx=(10, 0))

        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._update_preview())
        self.tree.bind("<Control-a>", lambda e: self._select_all())
        self.tree.bind("<space>", lambda e: self._toggle_selected())

        # --- Bearbeitungsleiste
        bar = ctk.CTkFrame(table, fg_color="transparent")
        bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(6, 8))
        ctk.CTkLabel(bar, text=T["edit_bar"] + ":", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=(2, 10))
        self.bar_page = ctk.CTkOptionMenu(bar, values=list(PAGE_FORMAT_LABELS.values()), width=120, command=lambda _: self._on_bar_page_change())
        self.bar_page.set(PAGE_FORMAT_LABELS[self.settings.page_format_enum])
        self.bar_orient = ctk.CTkOptionMenu(bar, values=list(ORIENTATION_LABELS.values()), width=115)
        self.bar_orient.set(ORIENTATION_LABELS[self.settings.orientation_enum])
        self.bar_fit = ctk.CTkOptionMenu(bar, values=list(FIT_LABELS.values()), width=110)
        self.bar_fit.set(FIT_LABELS[self.settings.fit_enum])
        self.bar_conflict = ctk.CTkOptionMenu(bar, values=list(CONFLICT_LABELS.values()), width=120)
        self.bar_conflict.set(CONFLICT_LABELS[self.settings.conflict_rule_enum])
        for i, w in enumerate((self.bar_page, self.bar_orient, self.bar_fit, self.bar_conflict), start=1):
            w.grid(row=0, column=i, padx=4)
        ctk.CTkButton(bar, text=T["apply"], width=90, command=self._apply_bar).grid(row=0, column=5, padx=(10, 4))
        ctk.CTkButton(bar, text=T["select_all"], width=105, fg_color="gray40", hover_color="gray30", command=self._select_all).grid(row=0, column=6, padx=4)
        ctk.CTkButton(bar, text=T["enable_rows"], width=90, fg_color="gray40", hover_color="gray30", command=lambda: self._set_enabled(True)).grid(row=0, column=7, padx=4)
        ctk.CTkButton(bar, text=T["disable_rows"], width=90, fg_color="gray40", hover_color="gray30", command=lambda: self._set_enabled(False)).grid(row=0, column=8, padx=4)
        ctk.CTkButton(bar, text=T["save_default"], width=150, fg_color="#2e7d32", hover_color="#1b5e20", command=self._save_default).grid(row=0, column=9, padx=(10, 2))
        ctk.CTkLabel(bar, text=T["hint_doubleclick"], text_color="gray60", font=ctk.CTkFont(size=11)).grid(row=1, column=0, columnspan=10, sticky="w", padx=2, pady=(4, 0))
        self._on_bar_page_change()

        # --- Fußbereich: Vorschau + Konvertierung
        bottom = ctk.CTkFrame(self, corner_radius=12)
        bottom.grid(row=2, column=0, sticky="ew", padx=12, pady=(6, 12))
        bottom.grid_columnconfigure(1, weight=1)

        pv = ctk.CTkFrame(bottom, fg_color="transparent")
        pv.grid(row=0, column=0, padx=12, pady=10, sticky="nw")
        ctk.CTkLabel(pv, text=T["preview"], font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w")
        self.preview_label = ctk.CTkLabel(pv, text="", width=PREVIEW_BOX, height=PREVIEW_BOX)
        self.preview_label.grid(row=1, column=0, pady=(4, 0))

        info = ctk.CTkFrame(bottom, fg_color="transparent")
        info.grid(row=0, column=1, padx=6, pady=10, sticky="nsew")
        info.grid_columnconfigure(0, weight=1)
        self.preview_info = ctk.CTkLabel(info, text=T["preview_none"], anchor="w", justify="left", wraplength=520)
        self.preview_info.grid(row=0, column=0, sticky="w")
        self.preview_warn = ctk.CTkLabel(info, text="", anchor="w", justify="left", text_color="#e6a100", wraplength=520)
        self.preview_warn.grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.preview_notes = ctk.CTkLabel(info, text="", anchor="w", justify="left", text_color="gray60", wraplength=520)
        self.preview_notes.grid(row=2, column=0, sticky="w", pady=(4, 0))

        run = ctk.CTkFrame(bottom, fg_color="transparent")
        run.grid(row=0, column=2, padx=12, pady=10, sticky="ne")
        self.convert_button = ctk.CTkButton(run, text=T["convert"], width=200, height=40, font=ctk.CTkFont(size=15, weight="bold"), command=self._start_convert)
        self.convert_button.grid(row=0, column=0, pady=(0, 6))
        self.cancel_button = ctk.CTkButton(run, text=T["cancel"], width=200, fg_color="gray40", hover_color="gray30", state="disabled", command=self._cancel)
        self.cancel_button.grid(row=1, column=0, pady=(0, 10))
        self.progress = ctk.CTkProgressBar(run, width=200)
        self.progress.set(0)
        self.progress.grid(row=2, column=0, pady=(0, 6))
        ctk.CTkCheckBox(run, text=T["open_after"], variable=self.open_after_var).grid(row=3, column=0, sticky="w")
        ctk.CTkLabel(run, textvariable=self.status_var, text_color="gray60", wraplength=200, justify="left").grid(row=4, column=0, sticky="w", pady=(8, 0))

    def _style_treeview(self) -> None:
        dark = ctk.get_appearance_mode() == "Dark"
        bg = "#1f1f1f" if dark else "#ffffff"
        fg = "#e6e6e6" if dark else "#1a1a1a"
        head_bg = "#2b2b2b" if dark else "#e8e8e8"
        sel = "#1f538d" if dark else "#3b8ed0"
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background=bg, foreground=fg, fieldbackground=bg, rowheight=ROW_H, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=head_bg, foreground=fg, relief="flat", font=("Segoe UI", 10, "bold"), padding=6)
        style.map("Treeview", background=[("selected", sel)], foreground=[("selected", "#ffffff")])
        style.map("Treeview.Heading", background=[("active", head_bg)])
        self.tree.tag_configure("red", foreground="#ff6b6b" if dark else "#c62828")
        self.tree.tag_configure("yellow", foreground="#ffd54f" if dark else "#b26a00")
        self.tree.tag_configure("green", foreground="#81c784" if dark else "#2e7d32")
        self.tree.tag_configure("disabled", foreground="#777777" if dark else "#9e9e9e")

    def _setup_dnd(self) -> None:
        if not HAS_DND:
            return
        try:
            TkinterDnD._require(self)
            self.drop_target_register(DND_FILES)  # type: ignore[attr-defined]
            self.dnd_bind("<<Drop>>", self._on_drop)  # type: ignore[attr-defined]
        except Exception:
            pass

    # ------------------------------------------------------------- Ereignisse
    def _on_drop(self, event) -> None:
        try:
            paths = self.tk.splitlist(event.data)
        except Exception:
            paths = [event.data]
        for p in paths:
            p = Path(str(p).strip("{}"))
            if p.is_dir():
                self.source_var.set(str(p))
                self._start_scan()
                return

    def _choose_source(self) -> None:
        d = filedialog.askdirectory(title=T["source"], initialdir=self.source_var.get() or None, mustexist=True)
        if d:
            self.source_var.set(str(Path(d)))

    def _choose_target(self) -> None:
        d = filedialog.askdirectory(title=T["col_target"], initialdir=self.target_var.get() or self.source_var.get() or None, mustexist=True)
        if d:
            self.target_var.set(str(Path(d)))
            self.target_mode.set("dir")
            self._on_target_change()

    def _on_target_change(self) -> None:
        self._replan()

    def _toggle_appearance(self) -> None:
        mode = "dark" if self.dark_var.get() else "light"
        ctk.set_appearance_mode(mode)
        self.settings.appearance = mode
        self._style_treeview()
        self._update_preview()

    def _on_bar_page_change(self) -> None:
        original = label_to_enum(PAGE_FORMAT_LABELS, self.bar_page.get()) == PageFormat.ORIGINAL
        state = "disabled" if original else "normal"
        self.bar_orient.configure(state=state)
        self.bar_fit.configure(state=state)

    def _select_all(self) -> str:
        self.tree.selection_set(self.tree.get_children())
        return "break"

    def _selected_items(self) -> list[ImageItem]:
        return [self.iid_to_item[i] for i in self.tree.selection() if i in self.iid_to_item]

    def _on_tree_click(self, event) -> Optional[str]:
        if self.tree.identify_region(event.x, event.y) != "cell":
            return None
        col = self.tree.identify_column(event.x)
        iid = self.tree.identify_row(event.y)
        if col == "#1" and iid:  # Häkchen-Spalte
            item = self.iid_to_item[iid]
            item.enabled = not item.enabled
            self._replan()
            return "break"
        return None

    def _toggle_selected(self) -> str:
        for it in self._selected_items():
            it.enabled = not it.enabled
        self._replan()
        return "break"

    def _on_tree_double_click(self, event) -> Optional[str]:
        if self.busy or self.tree.identify_region(event.x, event.y) != "cell":
            return None
        col_id = self.tree.identify_column(event.x)
        iid = self.tree.identify_row(event.y)
        if not iid:
            return None
        idx = int(col_id[1:]) - 1
        if idx < 0 or idx >= len(COLUMNS):
            return None
        col = COLUMNS[idx]
        if col not in CYCLE_COLUMNS:
            return None
        item = self.iid_to_item[iid]
        if col == "page":
            item.page_format = _next(list(PageFormat), item.page_format)
        elif item.page_format == PageFormat.ORIGINAL:
            return "break"
        elif col == "orient":
            item.orientation = _next(list(Orientation), item.orientation)
        elif col == "fit":
            item.fit = _next(list(FitMode), item.fit)
        elif col == "conflict":
            item.conflict_rule = _next(list(ConflictRule), item.conflict_rule)
        item.result = None
        self._replan()
        self._update_preview()
        return "break"

    def _apply_bar(self) -> None:
        sel = self._selected_items()
        if not sel:
            return
        page = label_to_enum(PAGE_FORMAT_LABELS, self.bar_page.get())
        orient = label_to_enum(ORIENTATION_LABELS, self.bar_orient.get())
        fit = label_to_enum(FIT_LABELS, self.bar_fit.get())
        rule = label_to_enum(CONFLICT_LABELS, self.bar_conflict.get())
        for it in sel:
            it.page_format, it.orientation, it.fit, it.conflict_rule = page, orient, fit, rule
            it.result = None
        self._replan()
        self._update_preview()

    def _set_enabled(self, value: bool) -> None:
        for it in self._selected_items():
            it.enabled = value
        self._replan()

    def _save_default(self) -> None:
        self.settings.page_format = label_to_enum(PAGE_FORMAT_LABELS, self.bar_page.get()).value
        self.settings.orientation = label_to_enum(ORIENTATION_LABELS, self.bar_orient.get()).value
        self.settings.fit = label_to_enum(FIT_LABELS, self.bar_fit.get()).value
        self.settings.conflict_rule = label_to_enum(CONFLICT_LABELS, self.bar_conflict.get()).value
        if self._persist_settings():
            self.status_var.set(T["default_saved_fallback"] if self.store.used_fallback else T["default_saved"])

    def _persist_settings(self, quiet: bool = False) -> bool:
        self.settings.formats = [f for f, v in self.format_vars.items() if v.get()] or list(IMAGE_FORMATS)
        self.settings.open_target_after = self.open_after_var.get()
        self.settings.appearance = "dark" if self.dark_var.get() else "light"
        try:
            self.store.save(self.settings)
            return True
        except OSError:
            if not quiet:
                messagebox.showwarning(T["error_title"], T["settings_save_failed"], parent=self)
            return False

    def _on_close(self) -> None:
        self.cancel_event.set()
        try:
            self._persist_settings(quiet=True)
        finally:
            self.destroy()

    # ------------------------------------------------------------------ Suche
    def _current_target_dir(self) -> Optional[Path]:
        if self.target_mode.get() == "dir" and self.target_var.get():
            return Path(self.target_var.get())
        return None

    def _start_scan(self) -> None:
        if self.busy:
            return
        src = self.source_var.get()
        if not src or not Path(src).is_dir():
            messagebox.showinfo(APP_NAME, T["no_source"], parent=self)
            return
        formats = [f for f, v in self.format_vars.items() if v.get()]
        if not formats:
            messagebox.showinfo(APP_NAME, T["no_formats"], parent=self)
            return
        if self.target_mode.get() == "dir" and not self.target_var.get():
            messagebox.showinfo(APP_NAME, T["no_target"], parent=self)
            return

        self._clear_table()
        self._set_busy(True)
        self.status_var.set(T["scanning"].format(n=0))
        root = Path(src)
        exclude = self._current_target_dir()
        defaults = (self.settings.page_format_enum, self.settings.orientation_enum,
                    self.settings.fit_enum, self.settings.conflict_rule_enum)

        def work() -> None:
            try:
                for p in scanner.scan(root, formats, exclude):
                    if self.cancel_event.is_set():
                        break
                    it = ImageItem(source=p, root=root, page_format=defaults[0], orientation=defaults[1],
                                   fit=defaults[2], conflict_rule=defaults[3])
                    try:
                        it.info = inspector.inspect(p)
                        it.thumbnail = inspector.thumbnail(p, 256)
                    except inspector.ImageTooLarge:
                        it.error = "too_large"
                    except inspector.ImageUnreadable as exc:
                        it.error = str(exc)
                    self.queue.put(("item", it))
            finally:
                self.queue.put(("scan_done", None))

        self.cancel_event.clear()
        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def _clear_table(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self.items.clear()
        self.iid_to_item.clear()
        self.item_to_iid.clear()
        self.photos.clear()
        self.progress.set(0)
        self._update_preview()

    # ------------------------------------------------------------ Konvertieren
    def _start_convert(self) -> None:
        if self.busy:
            return
        self._replan()
        todo = [it for it in self.items if it.enabled and it.is_convertible]
        if not todo:
            messagebox.showinfo(APP_NAME, T["nothing_to_convert"], parent=self)
            return
        for it in self.items:
            it.result = None
        self._set_busy(True)
        self.cancel_event.clear()
        self.progress.set(0)
        self.last_progress_item = None

        def progress(i: int, n: int, item: ImageItem) -> None:
            self.queue.put(("progress", (i, n, item)))

        def work() -> None:
            summary = converter.run(self.items, cancel=self.cancel_event, progress=progress)
            self.queue.put(("convert_done", summary))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def _cancel(self) -> None:
        self.cancel_event.set()
        self.status_var.set(T["cancel"] + "…")

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.scan_button.configure(state=state)
        self.convert_button.configure(state=state)
        self.cancel_button.configure(state="normal" if busy else "disabled")

    # ---------------------------------------------------------- Warteschlange
    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "item":
                    self._add_item(payload)
                elif kind == "scan_done":
                    self._set_busy(False)
                    self._replan()
                    n = len(self.items)
                    self.status_var.set(T["scan_done"].format(n=n) if n else T["scan_none"])
                elif kind == "progress":
                    i, n, item = payload
                    if self.last_progress_item is not None:
                        self._refresh_row(self.last_progress_item)
                    self.last_progress_item = item
                    self.progress.set((i - 1) / max(n, 1))
                    self.status_var.set(T["progress"].format(i=i, n=n, name=item.name))
                elif kind == "convert_done":
                    self._finish_convert(payload)
        except queue.Empty:
            pass
        self.after(80, self._poll_queue)

    def _finish_convert(self, summary: RunSummary) -> None:
        self._set_busy(False)
        self.progress.set(1.0 if not summary.cancelled else self.progress.get())
        for it in self.items:  # Ergebnisse anzeigen; neu geplant wird erst bei der nächsten Änderung
            self._refresh_row(it)
        self._update_preview()
        msg = T["summary"].format(created=summary.created, skipped=summary.skipped, failed=summary.failed)
        if summary.cancelled:
            msg += T["summary_cancelled"]
        if summary.errors:
            lines = "\n".join(f"• {p.name}: {m}" for p, m in summary.errors[:30])
            if len(summary.errors) > 30:
                lines += f"\n… und {len(summary.errors) - 30} weitere"
            msg += T["summary_errors"].format(errors=lines)
        self.status_var.set(T["summary_title"] + ": " + msg.splitlines()[0])
        messagebox.showinfo(T["summary_title"], msg, parent=self)
        if self.open_after_var.get() and summary.created:
            _open_folder(self._current_target_dir() or Path(self.source_var.get()))

    # ----------------------------------------------------------------- Tabelle
    def _add_item(self, item: ImageItem) -> None:
        self.items.append(item)
        iid = self.tree.insert("", "end", text="", values=self._row_values(item), tags=self._row_tags(item))
        self.iid_to_item[iid] = item
        self.item_to_iid[id(item)] = iid
        if item.thumbnail is not None:
            thumb = item.thumbnail.copy()
            thumb.thumbnail((THUMB_W, THUMB_H), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(thumb)
            self.photos[iid] = photo
            self.tree.item(iid, image=photo)
        self.status_var.set(T["scanning"].format(n=len(self.items)))

    def _replan(self) -> None:
        if not self.items:
            return
        planner.plan(self.items, self._current_target_dir())
        for it in self.items:
            self._refresh_row(it)

    def _refresh_row(self, item: ImageItem) -> None:
        iid = self.item_to_iid.get(id(item))
        if iid:
            self.tree.item(iid, values=self._row_values(item), tags=self._row_tags(item))

    def _row_tags(self, item: ImageItem) -> tuple[str, ...]:
        if not item.enabled:
            return ("disabled",)
        level = item.worst_level()
        return (level,) if level != "ok" else ()

    def _row_values(self, item: ImageItem) -> tuple:
        info = item.info
        original = item.page_format == PageFormat.ORIGINAL
        res = f"{info.width} × {info.height}" if info else "–"
        target = item.effective_target or item.target
        status = "  ".join(STATUS_LABELS[s] for s in item.statuses())
        return (
            "☑" if item.enabled else "☐",
            item.name,
            str(item.relative_dir) if str(item.relative_dir) != "." else "",
            item.source.suffix.lstrip(".").upper(),
            res,
            _human_size(item.size_bytes),
            PAGE_FORMAT_LABELS[item.page_format],
            "–" if original else ORIENTATION_LABELS[item.orientation],
            "–" if original else FIT_LABELS[item.fit],
            CONFLICT_LABELS[item.conflict_rule],
            str(target) if target else "",
            status,
        )

    # ---------------------------------------------------------------- Vorschau
    def _update_preview(self) -> None:
        sel = self._selected_items()
        item = sel[0] if sel else None
        dark = ctk.get_appearance_mode() == "Dark"
        if item is None:
            img, lay = preview.render(ImageItem(source=Path("."), root=Path(".")), PREVIEW_BOX, dark)
            self.preview_info.configure(text=T["preview_none"])
            self.preview_warn.configure(text="")
            self.preview_notes.configure(text="")
        else:
            img, lay = preview.render(item, PREVIEW_BOX, dark)
            self._fill_preview_text(item, lay)
        self.preview_image = ctk.CTkImage(light_image=img, dark_image=img, size=(PREVIEW_BOX, PREVIEW_BOX))
        self.preview_label.configure(image=self.preview_image)

    def _fill_preview_text(self, item: ImageItem, lay) -> None:
        notes = []
        if item.error == "too_large":
            notes.append(T["too_large_note"])
        elif item.error:
            notes.append(T["error_note"].format(msg=item.error))
        if item.path_too_long:
            notes.append(T["path_too_long_note"])
        if item.conflict and item.result is None:
            notes.append(T["conflict_note"])
        if item.info and item.info.animated:
            notes.append(T["animated_note"])
        self.preview_notes.configure(text="\n".join(notes))

        if lay is None or item.info is None:
            self.preview_info.configure(text=item.name)
            self.preview_warn.configure(text="")
            return
        mm = 25.4 / 72
        if item.page_format == PageFormat.ORIGINAL:
            dpi = item.info.dpi
            text = T["preview_original"].format(dpi=f"{dpi:g}" if dpi else "96")
            if not dpi:
                text += T["preview_dpi_fallback"]
            text += " · " + T["preview_info"].format(fmt="", w=f"{lay.page_w * mm:.0f}", h=f"{lay.page_h * mm:.0f}", m=0).lstrip(" ·")
        else:
            fmt = f"{PAGE_FORMAT_LABELS[item.page_format]} {ORIENTATION_LABELS[Orientation.LANDSCAPE if lay.is_landscape else Orientation.PORTRAIT]}"
            text = T["preview_info"].format(fmt=fmt, w=f"{lay.page_w * mm:.0f}", h=f"{lay.page_h * mm:.0f}", m=f"{lay.margin * mm:.0f}")
        if item.info.frames > 1:
            text += T["preview_pages"].format(n=item.info.frames)
        self.preview_info.configure(text=f"{item.name}\n{text}")
        self.preview_warn.configure(text=T["preview_crop_warning"] if lay.cropped else "")


def _next(values: list, current):
    try:
        return values[(values.index(current) + 1) % len(values)]
    except ValueError:
        return values[0]


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
