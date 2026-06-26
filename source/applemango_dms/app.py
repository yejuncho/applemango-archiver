import os
import re
import shutil
import threading
import tkinter as tk

from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox

from datetime import date, datetime
from pathlib import Path

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

try:
    import importlib

    _tkinterdnd2 = importlib.import_module("tkinterdnd2")
    DND_FILES = _tkinterdnd2.DND_FILES
    TkinterDnD = _tkinterdnd2.TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None

import applemango_dms.config as config

import applemango_dms.state as state

from applemango_dms.db.archive_db import ArchiveDatabase

from applemango_dms.services.auth import (
    load_saved_credentials,
    save_credentials,
    clear_saved_credentials,
    authenticate_to_server,
    update_session_login,
    clear_session_login,
)

from applemango_dms.services.nas import (
    check_server_availability,
    check_local_network_connectivity,
    discover_server_shares,
    normalize_drive_letter,
)

from applemango_dms.services.workspace import (
    WorkspaceManager,
)

from applemango_dms.services.filenames import (
    FilenameBuilder,
)

from applemango_dms.ui.widgets import (
    WorkspaceCard,
)

from applemango_dms.ui.settings import (
    show_mapped_drives_window,
)

from applemango_dms.utils.windows import (
    apply_window_icon,
)

class SequenceArchiverApp:
    def __init__(self):
        self.root = TkinterDnD.Tk() if TkinterDnD is not None else tk.Tk()
        apply_window_icon(self.root)
        self.root.geometry("640x500")
        self.root.configure(bg="white")
        self.root.resizable(True, True)

        self.db = ArchiveDatabase(config.archive_db_path)
        self.filename_builder = FilenameBuilder()
        self.workspace_manager = WorkspaceManager()
        self.workspace_drive_mapped_by_app = False
        self.workspace_metadata_cache = {}
        self.login_card = None
        self.login_content = None
        self.login_bg_canvas = None
        self.login_username_value = ""
        self.logo_image = None
        self.startup_logo_image = None
        self.login_connectivity = {
            "dot_canvas": None,
            "dot_item": None,
            "label": None,
            "job": None,
            "running": False,
        }

    @staticmethod
    def _format_size_for_display(size_bytes):
        gb = 1024 ** 3
        mb = 1024 ** 2
        if size_bytes >= gb:
            return f"{size_bytes / gb:.1f} GB"
        return f"{size_bytes / mb:.1f} MB"

    def _collect_workspace_filesystem_stats(self, workspace_name):
        root_path = fr"{config.default_server_name}\{workspace_name}"
        total_size = 0
        file_count = 0
        last_mtime = None

        stack = [root_path]
        while stack:
            current = stack.pop()
            try:
                with os.scandir(current) as entries:
                    for entry in entries:
                        try:
                            stat = entry.stat(follow_symlinks=False)
                        except OSError:
                            continue

                        if last_mtime is None or stat.st_mtime > last_mtime:
                            last_mtime = stat.st_mtime

                        if entry.is_file(follow_symlinks=False):
                            file_count += 1
                            total_size += int(stat.st_size)
                        elif entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
            except OSError:
                continue

        last_modified_text = datetime.fromtimestamp(last_mtime).strftime("%Y/%m/%d") if last_mtime else "정보 없음"
        return {
            "last_modified": last_modified_text,
            "size_bytes": total_size,
            "size_text": self._format_size_for_display(total_size),
            "fs_file_count": file_count,
        }

    def _build_workspace_metadata(self, workspace_name):
        fs_stats = self._collect_workspace_filesystem_stats(workspace_name)
        try:
            db_count = self.db.count_files_by_workspace(workspace_name)
            file_count = db_count
        except Exception:
            file_count = fs_stats["fs_file_count"]

        return {
            "last_modified": fs_stats["last_modified"],
            "size_text": fs_stats["size_text"],
            "file_count": file_count,
        }

    def _resize(self, w, h):
        self.root.geometry(f"{w}x{h}")

    def clear_screen(self):
        for child in self.root.winfo_children():
            child.destroy()

    @staticmethod
    def _blend_hex(c1, c2, ratio):
        c1 = c1.lstrip("#")
        c2 = c2.lstrip("#")
        r1, g1, b1 = int(c1[0:2], 16), int(c1[2:4], 16), int(c1[4:6], 16)
        r2, g2, b2 = int(c2[0:2], 16), int(c2[2:4], 16), int(c2[4:6], 16)
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _draw_login_gradient(self, width, height):
        if not self.login_bg_canvas or not self.login_bg_canvas.winfo_exists():
            return
        self.login_bg_canvas.delete("grad")
        lines = 80
        top = "#f8f8ff"
        bottom = "#ede9ff"
        step_h = max(1, int(height / lines))
        for i in range(lines):
            ratio = (i / max(1, lines - 1)) ** 1.25
            color = self._blend_hex(top, bottom, ratio)
            y0 = i * step_h
            y1 = min(height, y0 + step_h + 1)
            self.login_bg_canvas.create_rectangle(0, y0, width, y1, fill=color, outline=color, tags="grad")

    @staticmethod
    def _resize_image_fit(image, max_width, max_height):
        if Image is None:
            return None

        src_w, src_h = image.size
        if src_w <= 0 or src_h <= 0:
            return image

        scale = min(max_width / src_w, max_height / src_h)
        scale = max(0.05, scale)
        new_size = (max(1, int(src_w * scale)), max(1, int(src_h * scale)))
        if new_size == image.size:
            return image

        return image.resize(new_size, Image.LANCZOS)

    def _load_logo_photo(self, max_width, max_height):
        if Image is None or ImageTk is None:
            return None

        candidate_paths = [
            Path(config.logo_path),
            config.PROJECT_ROOT / "assets" / "images" / "applemango_logo.png",
            config.PROJECT_ROOT / "assets" / "images" / "hiscom_logo.png",
        ]

        for path in candidate_paths:
            if not path.exists():
                continue
            try:
                image = Image.open(path)
                resized = self._resize_image_fit(image, max_width=max_width, max_height=max_height)
                return ImageTk.PhotoImage(resized)
            except Exception:
                continue

        return None

    def _set_login_connectivity_status(self, connected, text):
        dot_canvas = self.login_connectivity.get("dot_canvas")
        dot_item = self.login_connectivity.get("dot_item")
        label = self.login_connectivity.get("label")
        if not dot_canvas or not dot_item or not label:
            return
        if not dot_canvas.winfo_exists() or not label.winfo_exists():
            return

        color = "#2ca24d" if connected else "#d23b3b"
        dot_canvas.itemconfigure(dot_item, fill=color, outline=color)
        label.configure(text=text, fg="#8d90a6")

    def _refresh_login_connectivity_once(self):
        self.login_connectivity["job"] = None
        if self.login_connectivity.get("running"):
            return

        self.login_connectivity["running"] = True

        def worker():
            connected, status_text = check_local_network_connectivity(config.default_server_name)

            def apply_result():
                self.login_connectivity["running"] = False
                self._set_login_connectivity_status(connected, status_text)

            self.root.after(0, apply_result)

        threading.Thread(target=worker, daemon=True).start()

    def _start_login_connectivity_polling(self):
        self._stop_login_connectivity_polling()

        def schedule_next():
            self._refresh_login_connectivity_once()
            dot_canvas = self.login_connectivity.get("dot_canvas")
            if dot_canvas and dot_canvas.winfo_exists():
                self.login_connectivity["job"] = self.root.after(5000, schedule_next)

        self.login_connectivity["job"] = self.root.after(120, schedule_next)

    def _stop_login_connectivity_polling(self):
        job = self.login_connectivity.get("job")
        if job:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass
        self.login_connectivity["job"] = None
        self.login_connectivity["running"] = False

    def _center_window(self, width, height):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = max(0, (sw - width) // 2)
        y = max(0, (sh - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _draw_rounded_rect(self, canvas, x1, y1, x2, y2, radius, fill, outline, width=1, tags=""):
        r = max(1, int(min(radius, (x2 - x1) / 2, (y2 - y1) / 2)))

        canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline="", tags=tags)
        canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline="", tags=tags)

        canvas.create_oval(x1, y1, x1 + 2 * r, y1 + 2 * r, fill=fill, outline="", tags=tags)
        canvas.create_oval(x2 - 2 * r, y1, x2, y1 + 2 * r, fill=fill, outline="", tags=tags)
        canvas.create_oval(x1, y2 - 2 * r, x1 + 2 * r, y2, fill=fill, outline="", tags=tags)
        canvas.create_oval(x2 - 2 * r, y2 - 2 * r, x2, y2, fill=fill, outline="", tags=tags)

        if width > 0:
            canvas.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90, style="arc", outline=outline, width=width, tags=tags)
            canvas.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90, style="arc", outline=outline, width=width, tags=tags)
            canvas.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90, style="arc", outline=outline, width=width, tags=tags)
            canvas.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90, style="arc", outline=outline, width=width, tags=tags)

            canvas.create_line(x1 + r, y1, x2 - r, y1, fill=outline, width=width, tags=tags)
            canvas.create_line(x1 + r, y2, x2 - r, y2, fill=outline, width=width, tags=tags)
            canvas.create_line(x1, y1 + r, x1, y2 - r, fill=outline, width=width, tags=tags)
            canvas.create_line(x2, y1 + r, x2, y2 - r, fill=outline, width=width, tags=tags)

    def _draw_horizontal_gradient_rounded(self, canvas, x1, y1, x2, y2, radius, start_color, end_color, tags=""):
        r = max(1, int(min(radius, (x2 - x1) / 2, (y2 - y1) / 2)))
        width_px = max(1, int(x2 - x1))
        for i in range(width_px):
            ratio = i / max(1, width_px - 1)
            color = self._blend_hex(start_color, end_color, ratio)
            x = x1 + i
            if i < r:
                dx = r - i
                dy = int(r - max(0.0, (r * r - dx * dx)) ** 0.5)
            elif i > width_px - r:
                dx = i - (width_px - r)
                dy = int(r - max(0.0, (r * r - dx * dx)) ** 0.5)
            else:
                dy = 0
            canvas.create_line(x, y1 + dy, x, y2 - dy, fill=color, tags=tags)

    def _smooth_rounded_rect(self, canvas, x1, y1, x2, y2, radius, fill="", outline="", width=1, tags=""):
        """Smooth rounded rectangle using B-spline polygon — no rough arc joints."""
        r = max(2, min(radius, int((x2 - x1) / 2), int((y2 - y1) / 2)))
        pts = [
            x1 + r, y1,
            x2 - r, y1,
            x2,     y1,
            x2,     y1 + r,
            x2,     y2 - r,
            x2,     y2,
            x2 - r, y2,
            x1 + r, y2,
            x1,     y2,
            x1,     y2 - r,
            x1,     y1 + r,
            x1,     y1,
        ]
        return canvas.create_polygon(
            pts, smooth=True, splinesteps=48,
            fill=fill, outline=outline, width=width, tags=tags,
        )

    def create_login_card(self, parent, width=360, height=470):
        """Draw the card as smooth polygons directly on parent canvas.
        No rectangular Frame/Canvas widget is used, so corners are always clean.
        """
        content = tk.Frame(parent, bg="#f9f8ff")
        content_id = parent.create_window(0, 0, window=content, anchor="center")

        def redraw(cx, cy):
            parent.delete("cardshadow")
            parent.delete("cardfill")
            parent.delete("cardborder")

            x1, y1 = cx - width // 2, cy - height // 2
            x2, y2 = cx + width // 2, cy + height // 2
            r = 22

            # Layered soft shadow — darkest/furthest drawn first (lower z)
            self._smooth_rounded_rect(parent, x1 + 7, y1 + 9, x2 + 7, y2 + 9, r,
                                      fill="#d8d5f0", outline="", tags="cardshadow")
            self._smooth_rounded_rect(parent, x1 + 4, y1 + 5, x2 + 4, y2 + 5, r,
                                      fill="#e5e3f5", outline="", tags="cardshadow")
            self._smooth_rounded_rect(parent, x1 + 2, y1 + 2, x2 + 2, y2 + 2, r,
                                      fill="#eeedf8", outline="", tags="cardshadow")

            # Card fill then subtle border
            self._smooth_rounded_rect(parent, x1, y1, x2, y2, r,
                                      fill="#f9f8ff", outline="", tags="cardfill")
            self._smooth_rounded_rect(parent, x1, y1, x2, y2, r,
                                      fill="", outline="#e4e6f0", width=1, tags="cardborder")

            # Resize and re-center content frame, then raise above all card shapes
            parent.itemconfigure(content_id, width=width - 56, height=height - 56)
            parent.coords(content_id, cx, cy)
            parent.tag_raise(content_id)

        return {
            "card": None,
            "content": content,
            "size": (width, height),
            "redraw": redraw,
        }

    def _prepare_login_layout(self):
        target_w = 420
        target_h = 560
        self._center_window(target_w, target_h)
        self.root.title("애플망고 DMS - 로그인")
        self.clear_screen()
        self.root.configure(bg="#f8f8ff")

        bg = tk.Canvas(self.root, bg="#f8f8ff", highlightthickness=0, bd=0)
        bg.pack(fill="both", expand=True)
        self.login_bg_canvas = bg

        card_info = self.create_login_card(bg)
        content = card_info["content"]
        card_redraw = card_info["redraw"]

        def on_bg_resize(event):
            self._draw_login_gradient(event.width, event.height)
            card_redraw(event.width // 2, event.height // 2)

        bg.bind("<Configure>", on_bg_resize)

        self.login_card = None
        self.login_content = content

    def create_rounded_entry(self, parent, placeholder, icon_text, is_password=False):
        wrapper = tk.Frame(parent, bg="#f9f8ff")
        canvas = tk.Canvas(wrapper, height=52, bg="#f9f8ff", highlightthickness=0, bd=0)
        canvas.pack(fill="x")

        inner = tk.Frame(canvas, bg="#ffffff")
        inner_id = canvas.create_window(10, 5, window=inner, anchor="nw", height=42)

        icon_label = tk.Label(inner, text=icon_text, font=("Segoe UI Emoji", 11), bg="#ffffff", fg="#868cab")
        icon_label.pack(side="left", padx=(12, 9))

        value_var = tk.StringVar(value="")
        entry = tk.Entry(
            inner,
            textvariable=value_var,
            show="*" if is_password else "",
            font=("Segoe UI", 12),
            bd=0,
            relief="flat",
            highlightthickness=0,
            bg="#ffffff",
            fg="#1d2138",
            insertbackground="#06012a",
            insertontime=600,
            insertofftime=400,
            insertwidth=2,
        )
        entry.pack(side="left", fill="both", expand=True, pady=8)

        # clicking anywhere in the field area focuses the entry
        canvas.bind("<Button-1>", lambda _e: entry.focus_set())
        inner.bind("<Button-1>", lambda _e: entry.focus_set())
        icon_label.bind("<Button-1>", lambda _e: entry.focus_set())

        placeholder_label = tk.Label(inner, text=placeholder, font=("Segoe UI", 11), bg="#ffffff", fg="#a0a3b8")
        placeholder_label.place(x=42, y=9)
        placeholder_label.bind("<Button-1>", lambda _e: entry.focus_set())

        field_state = {
            "focused": False,
            "password_visible": False,
        }

        eye_label = None
        if is_password:
            # Simple emoji: 👁 = password hidden (click to reveal), 🙈 = visible (click to hide)
            eye_label = tk.Label(
                inner, text="\U0001f441",
                font=("Segoe UI Emoji", 13),
                bg="#ffffff", fg="#8086a3", cursor="hand2",
            )
            eye_label.pack(side="right", padx=(6, 12))
            eye_label.bind("<Button-1>", lambda _e: self.toggle_password_visibility(entry, field_state, eye_label))

        def redraw_field(border_color):
            canvas.delete("field")
            w = max(40, canvas.winfo_width())
            h = max(40, canvas.winfo_height())
            # smooth fill then smooth border as two separate polygons
            self._smooth_rounded_rect(canvas, 1, 1, w - 1, h - 1, 16,
                                      fill="#ffffff", outline="", width=0, tags="field")
            self._smooth_rounded_rect(canvas, 1, 1, w - 1, h - 1, 16,
                                      fill="", outline=border_color, width=1, tags="field")
            canvas.tag_lower("field")  # keep shapes behind the inner frame window
            canvas.itemconfigure(inner_id, width=max(10, w - 20))

        def update_placeholder(*_args):
            if value_var.get() or field_state["focused"]:
                placeholder_label.place_forget()
            else:
                placeholder_label.place(x=42, y=9)

        def on_focus_in(_event):
            field_state["focused"] = True
            redraw_field("#06012a")
            placeholder_label.place_forget()  # always hide so cursor is visible

        def on_focus_out(_event):
            field_state["focused"] = False
            redraw_field("#e4e6f0")
            update_placeholder()  # re-show only if field is empty

        canvas.bind("<Configure>", lambda _e: redraw_field("#06012a" if field_state["focused"] else "#e4e6f0"))
        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)
        value_var.trace_add("write", update_placeholder)

        redraw_field("#e4e6f0")
        update_placeholder()

        return {
            "wrapper": wrapper,
            "entry": entry,
            "var": value_var,
            "get_value": lambda: value_var.get().strip(),
            "set_value": lambda value: value_var.set(value),
            "focus": lambda: entry.focus_set(),
            "eye": eye_label,
        }

    def toggle_password_visibility(self, entry_widget, field_state, eye_widget=None):
        field_state["password_visible"] = not field_state["password_visible"]
        if field_state["password_visible"]:
            entry_widget.configure(show="")
            if eye_widget is not None:
                eye_widget.configure(text="\U0001f648")  # 🙈 = visible, click to hide
        else:
            entry_widget.configure(show="*")
            if eye_widget is not None:
                eye_widget.configure(text="\U0001f441")  # 👁 = hidden, click to reveal

    def _create_primary_login_button(self, parent, text, command):
        canvas = tk.Canvas(parent, height=52, bg="#f9f8ff", highlightthickness=0, bd=0, cursor="arrow")

        state = {
            "enabled": False,
            "hover": False,
        }

        def render():
            canvas.delete("btn")
            w = max(120, canvas.winfo_width())
            h = max(52, canvas.winfo_height())

            if state["enabled"]:
                start = "#06012a"
                end = "#2a2559" if not state["hover"] else "#37306c"
                border = "#19144a"
                text_color = "white"
                cursor = "hand2"
            else:
                start = "#b8bdd1"
                end = "#c5c9d9"
                border = "#b8bdd1"
                text_color = "#f6f7fb"
                cursor = "arrow"

            canvas.configure(cursor=cursor)
            self._draw_horizontal_gradient_rounded(canvas, 1, 1, w - 1, h - 1, 16, start, end, tags="btn")
            self._draw_rounded_rect(canvas, 1, 1, w - 1, h - 1, 16, fill="", outline=border, width=1, tags="btn")
            canvas.create_text(w // 2, h // 2, text=text, fill=text_color, font=("Segoe UI", 13, "bold"), tags="btn")

        def on_enter(_event):
            state["hover"] = True
            render()

        def on_leave(_event):
            state["hover"] = False
            render()

        def on_click(_event):
            if state["enabled"]:
                command()

        canvas.bind("<Configure>", lambda _e: render())
        canvas.bind("<Enter>", on_enter)
        canvas.bind("<Leave>", on_leave)
        canvas.bind("<Button-1>", on_click)

        def set_enabled(enabled):
            state["enabled"] = bool(enabled)
            if not state["enabled"]:
                state["hover"] = False
            render()

        canvas.set_enabled = set_enabled
        render()
        return canvas

    def get_connection_snapshot(self):
        is_connected, ip_addr = check_server_availability(config.default_server_name)
        status = "연결됨" if is_connected else "연결 불가"
        return is_connected, ip_addr, status

    def set_workspace(self, workspace, drive_letter, mapped_by_app):
        state.active_workspace = workspace
        state.active_workspace_drive = drive_letter
        self.workspace_drive_mapped_by_app = mapped_by_app

    def clear_workspace(self, unmap_if_needed=False):

        if unmap_if_needed and self.workspace_drive_mapped_by_app and state.active_workspace_drive:
            self.workspace_manager.unmap_drive(state.active_workspace_drive)

        state.active_workspace = ""
        state.active_workspace_drive = ""
        self.workspace_drive_mapped_by_app = False

    def logout_and_return_to_login(self):
        # Ensure mapped workspace drive is released before logging out.
        self.clear_workspace(unmap_if_needed=True)
        clear_session_login()
        clear_saved_credentials()
        self.show_login_screen()

    def show_startup_screen(self):
        self._stop_login_connectivity_polling()
        self._center_window(420, 560)
        self.root.title("애플망고 DMS")
        self.clear_screen()
        self.root.configure(bg="white")

        shell = tk.Frame(self.root, bg="white")
        shell.pack(fill="both", expand=True)

        logo_label = tk.Label(shell, bg="white")
        logo_label.place(relx=0.5, rely=0.45, anchor="center")

        logo_photo = self._load_logo_photo(max_width=300, max_height=180)
        self.startup_logo_image = logo_photo
        if logo_photo is not None:
            logo_label.configure(image=logo_photo)
        else:
            logo_label.configure(text="HISCOM", font=("Segoe UI", 30, "bold"), fg="#1d2138")

        self.root.after(1200, self.route_from_startup)

    def route_from_startup(self):
        saved = load_saved_credentials()
        if not saved:
            self.show_login_screen()
            return

        ok, _ = authenticate_to_server(saved["username"], saved["password"])
        if ok:
            update_session_login(saved["username"], saved["password"])
            self.show_workspace_selection_screen()
            return

        clear_saved_credentials()
        clear_session_login()
        self.show_login_screen()

    def show_login_screen(self, prefill_username=None):
        self._stop_login_connectivity_polling()
        self._prepare_login_layout()

        frame = tk.Frame(self.login_content, bg="#f9f8ff")
        frame.pack(fill="both", expand=True)

        logo_photo = self._load_logo_photo(max_width=170, max_height=80)
        self.logo_image = logo_photo
        if logo_photo is not None:
            tk.Label(frame, image=logo_photo, bg="#f9f8ff").pack(pady=(0, 8))
        else:
            tk.Label(frame, text="애플망고", font=("Segoe UI", 25, "bold"), fg="#06012a", bg="#f9f8ff").pack(pady=(0, 0))

        tk.Label(frame, text="DMS - 데이터 관리 시스템", font=("Segoe UI", 10), fg="#8d90a6", bg="#f9f8ff").pack(pady=(0, 32))

        username_field = self.create_rounded_entry(frame, "사용자명", "👤", is_password=False)
        username_field["wrapper"].pack(fill="x")
        tk.Frame(frame, bg="#f9f8ff", height=10).pack(fill="x")

        password_field = self.create_rounded_entry(frame, "비밀번호", "🔒", is_password=True)
        password_field["wrapper"].pack(fill="x")

        remembered = load_saved_credentials()
        if prefill_username:
            username_field["set_value"](str(prefill_username).strip())
        elif remembered and remembered.get("username") and not username_field["get_value"]():
            username_field["set_value"](remembered["username"])

        remember_var = tk.BooleanVar(value=remembered is not None)
        remember_row = tk.Frame(frame, bg="#f9f8ff")
        remember_row.pack(fill="x", pady=(12, 16))

        tk.Checkbutton(
            remember_row,
            text="로그인 정보 저장",
            variable=remember_var,
            bg="#f9f8ff",
            activebackground="#f9f8ff",
            fg="#3f4563",
            selectcolor="#f9f8ff",
            font=("Segoe UI", 10),
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        ).pack(side="right")

        def submit_login():
            username = username_field["get_value"]()
            password = password_field["get_value"]()
            if not username or not password:
                messagebox.showerror("로그인", "사용자명과 비밀번호를 입력하세요.", parent=self.root)
                return

            network_warning_msg = (
                "파일 서버(NAS)에 연결할 수 없습니다.\n\n"
                "사내 네트워크에 연결되어 있는지 확인한 후 다시 시도해 주세요."
            )

            is_network_connected, _ = check_local_network_connectivity(config.default_server_name)
            if not is_network_connected:
                messagebox.showerror("로그인 실패", network_warning_msg, parent=self.root)
                return

            ok, err = authenticate_to_server(username, password)
            if not ok:
                clear_session_login()
                is_network_issue = (
                    "64" in err
                    or "67" in err
                    or "53" in err
                    or "The specified network name is no longer available" in err
                    or "지정된 네트워크 이름을 더 이상 사용할 수 없습니다" in err
                    or "The network name cannot be found" in err
                    or "네트워크 이름을 찾을 수 없습니다" in err
                )
                is_invalid_credentials = (
                    "1326" in err
                    or "Logon failure" in err
                    or "unknown user name or bad password" in err
                    or "사용자 이름 또는 암호가 올바르지 않습니다" in err
                )

                if is_network_issue:
                    messagebox.showerror("로그인 실패", network_warning_msg, parent=self.root)
                elif is_invalid_credentials:
                    messagebox.showerror("로그인 실패", "아이디/패스워드를 확인해주세요.", parent=self.root)
                else:
                    messagebox.showerror("로그인 실패", err, parent=self.root)
                return

            update_session_login(username, password)
            if remember_var.get():
                save_credentials(username, password)
            else:
                clear_saved_credentials()

            self.show_workspace_selection_screen()

        login_btn = self._create_primary_login_button(frame, "로그인", submit_login)
        login_btn.pack(fill="x")

        connectivity_row = tk.Frame(frame, bg="#f9f8ff")
        connectivity_row.pack(fill="x", pady=(14, 0), side="bottom")

        connectivity_center = tk.Frame(connectivity_row, bg="#f9f8ff")
        connectivity_center.pack(anchor="center")

        dot_canvas = tk.Canvas(connectivity_center, width=10, height=10, bg="#f9f8ff", highlightthickness=0, bd=0)
        dot_item = dot_canvas.create_oval(1, 1, 9, 9, fill="#d23b3b", outline="#d23b3b")
        dot_canvas.pack(side="left", pady=(0, 1))

        status_label = tk.Label(
            connectivity_center,
            text="NAS 연결 불가",
            font=("Segoe UI", 9),
            fg="#8d90a6",
            bg="#f9f8ff",
            anchor="w",
        )
        status_label.pack(side="left", padx=(6, 0))

        self.login_connectivity["dot_canvas"] = dot_canvas
        self.login_connectivity["dot_item"] = dot_item
        self.login_connectivity["label"] = status_label
        self._start_login_connectivity_polling()

        def update_login_button(*_args):
            has_username = bool(username_field["get_value"]())
            has_password = bool(password_field["get_value"]())
            login_btn.set_enabled(has_username and has_password)

        username_field["var"].trace_add("write", update_login_button)
        password_field["var"].trace_add("write", update_login_button)
        username_field["entry"].bind("<Return>", lambda _e: password_field["focus"]())
        password_field["entry"].bind("<Return>", lambda _e: submit_login())
        update_login_button()

        self.root.after(30, username_field["focus"])

    def show_username_login_screen(self):
        self.show_login_screen()

    def show_password_login_screen(self, username):
        self.show_login_screen(prefill_username=username)

    def show_workspace_selection_screen(self):
        self._stop_login_connectivity_polling()
        # Unmap current workspace drive when returning to selection (one-drive-at-a-time)
        if state.active_workspace_drive and self.workspace_drive_mapped_by_app:
            self.workspace_manager.unmap_drive(state.active_workspace_drive)
        state.active_workspace = ""
        state.active_workspace_drive = ""
        self.workspace_drive_mapped_by_app = False

        self._resize(760, 680)
        self.root.title("애플망고 DMS - 워크스페이스 선택")
        self.clear_screen()

        _, ip_addr, status_text = self.get_connection_snapshot()
        shares = discover_server_shares(config.default_server_name)

        container = tk.Frame(self.root, padx=24, pady=20, bg="white")
        container.pack(fill="both", expand=True)

        tk.Label(container, text="워크스페이스 선택", font=("Segoe UI", 18, "bold"), bg="white").pack(anchor="w", pady=(0, 10))
        tk.Label(container, text=f"서버: {config.default_server_name}", font=("Segoe UI", 10), bg="white", fg="#3c3c3c", anchor="w").pack(fill="x")
        tk.Label(container, text=f"상태: {status_text}", font=("Segoe UI", 10), bg="white", fg="#3c3c3c", anchor="w").pack(fill="x", pady=(2, 0))
        tk.Label(
            container,
            text=f"로그인 사용자: {state.session_account_name or state.session_username}",
            font=("Segoe UI", 10),
            bg="white",
            fg="#3c3c3c",
            anchor="w",
        ).pack(fill="x", pady=(2, 10))

        action_row = tk.Frame(container, bg="white")
        action_row.pack(fill="x", pady=(0, 10))
        tk.Button(action_row, text="설정", width=12, bg="#d9d9d9", activebackground="#c0c0c0",
                  relief="flat", bd=0, cursor="hand2", command=self.show_settings_screen).pack(side="left")
        tk.Button(action_row, text="로그아웃", width=12, bg="#d9d9d9", activebackground="#c0c0c0",
                  relief="flat", bd=0, cursor="hand2", command=self.logout_and_return_to_login).pack(side="left", padx=(8, 0))

        cards_shell = tk.Frame(container, bg="white")
        cards_shell.pack(fill="both", expand=True)

        cards_canvas = tk.Canvas(cards_shell, bg="white", highlightthickness=0)
        cards_scroll = ttk.Scrollbar(cards_shell, orient="vertical", command=cards_canvas.yview)
        cards_canvas.configure(yscrollcommand=cards_scroll.set)
        cards_scroll.pack(side="right", fill="y")
        cards_canvas.pack(side="left", fill="both", expand=True)

        cards_body = tk.Frame(cards_canvas, bg="white")
        cards_body_id = cards_canvas.create_window((0, 0), window=cards_body, anchor="nw")

        cards_body.bind("<Configure>", lambda _e: cards_canvas.configure(scrollregion=cards_canvas.bbox("all")))
        cards_canvas.bind("<Configure>", lambda e: cards_canvas.itemconfigure(cards_body_id, width=e.width))
        cards_canvas.bind("<MouseWheel>", lambda e: cards_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        workspace_cards = {}

        def enter_workspace(selected):
            drive, mapped_by_app, err = self.workspace_manager.map_workspace(selected, state.session_username, state.session_password)
            if not drive:
                messagebox.showerror("워크스페이스", f"워크스페이스 드라이브 매핑에 실패했습니다:\n{err}", parent=self.root)
                return

            self.set_workspace(selected, drive, mapped_by_app)
            self.show_main_workspace_menu()

        if not shares:
            tk.Label(cards_body, text="선택 가능한 워크스페이스가 없습니다.", bg="white", fg="#666666", font=("Segoe UI", 11)).pack(anchor="w", pady=(8, 0))
            return

        for workspace_name in shares:
            card = WorkspaceCard(cards_body, workspace_name, on_click=enter_workspace)
            card.pack(fill="x", pady=6)
            workspace_cards[workspace_name] = card

            cached_meta = self.workspace_metadata_cache.get(workspace_name)
            if cached_meta:
                card.set_metadata(cached_meta)

        to_load = [name for name in shares if name not in self.workspace_metadata_cache]
        if not to_load:
            return

        def load_metadata_worker(workspace_names):
            for workspace_name in workspace_names:
                try:
                    meta = self._build_workspace_metadata(workspace_name)
                except Exception:
                    meta = {
                        "last_modified": "정보 없음",
                        "size_text": "0.0 MB",
                        "file_count": 0,
                    }
                self.workspace_metadata_cache[workspace_name] = meta

                def apply_metadata(name=workspace_name, metadata=meta):
                    card = workspace_cards.get(name)
                    if card and card.winfo_exists():
                        card.set_metadata(metadata)

                self.root.after(0, apply_metadata)

        threading.Thread(target=load_metadata_worker, args=(to_load,), daemon=True).start()

    def build_header(self, parent, title):
        _, ip_addr, status_text = self.get_connection_snapshot()

        header = tk.LabelFrame(parent, text=title, bg="white", padx=14, pady=10)
        header.pack(fill="x", pady=(0, 10))

        tk.Label(header, text=f"로그인 계정: {state.session_account_name or state.session_username}", bg="white", anchor="w").pack(fill="x", pady=2)
        tk.Label(header, text=f"서버 이름: {config.default_server_name}", bg="white", anchor="w").pack(fill="x", pady=2)
        tk.Label(header, text=f"서버 IP: {ip_addr}", bg="white", anchor="w").pack(fill="x", pady=2)
        tk.Label(header, text=f"현재 워크스페이스: {state.active_workspace or '선택 안 됨'}", bg="white", anchor="w").pack(fill="x", pady=2)
        tk.Label(header, text=f"매핑 드라이브: {state.active_workspace_drive or '매핑 안 됨'}", bg="white", anchor="w").pack(fill="x", pady=2)
        tk.Label(header, text=f"연결 상태: {status_text}", bg="white", anchor="w").pack(fill="x", pady=2)

    def show_main_workspace_menu(self):
        if not state.active_workspace:
            self.show_workspace_selection_screen()
            return

        self._resize(500, 480)
        self.root.title("애플망고 DMS - 워크스페이스 메뉴")
        self.clear_screen()

        page = tk.Frame(self.root, bg="white", padx=24, pady=20)
        page.pack(fill="both", expand=True)
        self.build_header(page, "워크스페이스 메뉴")

        button_frame = tk.Frame(page, bg="white")
        button_frame.pack(pady=(8, 0))

        def menu_btn(label, command, color="#d9d9d9", fg="black"):
            tk.Button(
                button_frame, text=label, width=22,
                bg=color, activebackground="#c0c0c0",
                fg=fg, activeforeground=fg,
                relief="flat", bd=0, highlightthickness=0,
                cursor="hand2", command=command,
            ).pack(pady=4)

        menu_btn("파일 저장", self.show_save_files_screen)
        menu_btn("파일 검색", self.show_search_files_screen)
        menu_btn("워크스페이스 종료", self.show_workspace_selection_screen)
        menu_btn("로그아웃", self.logout_and_return_to_login)

    def build_destination_drive_path(self):
        drive = normalize_drive_letter(state.active_workspace_drive)
        if not drive:
            return None
        return Path(f"{drive}\\")

    def show_save_files_screen(self):
        self._resize(760, 680)
        self.root.title("애플망고 DMS - 파일 저장")
        self.clear_screen()

        # ---- outer frame: fixed header + scrollable body ----
        outer = tk.Frame(self.root, bg="white")
        outer.pack(fill="both", expand=True)

        header_frame = tk.Frame(outer, bg="white", padx=14, pady=8)
        header_frame.pack(fill="x")
        self.build_header(header_frame, "파일 저장")

        # scrollable canvas
        scroll_canvas = tk.Canvas(outer, bg="white", highlightthickness=0)
        v_scroll = ttk.Scrollbar(outer, orient="vertical", command=scroll_canvas.yview)
        scroll_canvas.configure(yscrollcommand=v_scroll.set)
        v_scroll.pack(side="right", fill="y")
        scroll_canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(scroll_canvas, bg="white", padx=14, pady=8)
        inner_id = scroll_canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner_resize(event):
            scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all"))
            scroll_canvas.itemconfigure(inner_id, width=scroll_canvas.winfo_width())

        inner.bind("<Configure>", _on_inner_resize)
        scroll_canvas.bind("<Configure>", lambda e: scroll_canvas.itemconfigure(inner_id, width=e.width))
        scroll_canvas.bind("<MouseWheel>", lambda e: scroll_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        # ---- state ----
        selected_files = []
        date_var = tk.StringVar(value=date.today().isoformat())
        uploaded_by_var = tk.StringVar(value=state.session_account_name or state.session_username)
        workspace_var = tk.StringVar(value=state.active_workspace)
        tags_var = tk.StringVar(value="")
        doc_types = self.db.get_document_types()
        doc_type_var = tk.StringVar(value=("기타" if "기타" in doc_types else doc_types[0]))

        # ---- A. Add Files ----
        row_a = tk.LabelFrame(inner, text="A. 파일 추가", bg="white", padx=10, pady=8)
        row_a.pack(fill="x", pady=(0, 8))

        add_buttons = tk.Frame(row_a, bg="white")
        add_buttons.pack(fill="x", pady=(0, 8))

        drop_area = tk.Canvas(row_a, height=60, bg="white", highlightthickness=0, bd=0, cursor="hand2")
        drop_area.pack(fill="x", pady=(0, 6))
        drop_area.create_rectangle(4, 4, 700, 56, dash=(3, 3), outline="#9a9a9a", width=1)
        drop_area.create_text(352, 30, text="클릭해서 파일 추가 또는 파일/폴더를 여기로 드롭",
                              fill="#666666", font=("Segoe UI", 10))

        file_count_var = tk.StringVar(value="선택된 파일 0개")
        tk.Label(row_a, textvariable=file_count_var, bg="white", fg="#555555", anchor="w").pack(fill="x", pady=(0, 3))

        file_table_frame = tk.Frame(row_a, bg="white")
        file_table_frame.pack(fill="x")

        file_tree = ttk.Treeview(file_table_frame, columns=("name", "source", "preview"), show="headings", height=6)
        file_tree.heading("name", text="원본 파일명")
        file_tree.heading("source", text="원본 경로")
        file_tree.heading("preview", text="저장 파일명 미리보기")
        file_tree.column("name", width=150, anchor="w")
        file_tree.column("source", width=270, anchor="w")
        file_tree.column("preview", width=270, anchor="w")
        file_tree.pack(side="left", fill="x", expand=True)

        file_scroll = ttk.Scrollbar(file_table_frame, orient="vertical", command=file_tree.yview)
        file_scroll.pack(side="right", fill="y")
        file_tree.configure(yscrollcommand=file_scroll.set)

        # ---- B. Metadata / Tags ----
        row_b = tk.LabelFrame(inner, text="B. 메타데이터 / 태그", bg="white", padx=10, pady=8)
        row_b.pack(fill="x", pady=(0, 8))

        grid = tk.Frame(row_b, bg="white")
        grid.pack(fill="x")

        tk.Label(grid, text="날짜 (YYYY-MM-DD)", bg="white", width=20, anchor="w").grid(row=0, column=0, sticky="w", pady=2)
        tk.Entry(grid, textvariable=date_var, width=20).grid(row=0, column=1, sticky="w", pady=2)

        tk.Label(grid, text="업로드 사용자", bg="white", width=20, anchor="w").grid(row=1, column=0, sticky="w", pady=2)
        tk.Entry(grid, textvariable=uploaded_by_var, width=20, state="readonly").grid(row=1, column=1, sticky="w", pady=2)

        tk.Label(grid, text="워크스페이스", bg="white", width=20, anchor="w").grid(row=2, column=0, sticky="w", pady=2)
        tk.Entry(grid, textvariable=workspace_var, width=20, state="readonly").grid(row=2, column=1, sticky="w", pady=2)

        tk.Label(grid, text="문서 유형", bg="white", width=20, anchor="w").grid(row=3, column=0, sticky="w", pady=2)
        ttk.Combobox(grid, textvariable=doc_type_var, values=doc_types, state="readonly", width=20).grid(row=3, column=1, sticky="w", pady=2)

        tk.Label(grid, text="추가 태그", bg="white", width=20, anchor="w").grid(row=4, column=0, sticky="w", pady=2)
        tk.Entry(grid, textvariable=tags_var, width=50).grid(row=4, column=1, sticky="w", pady=2)

        tk.Label(row_b, text="예: 봄학기, 3학년, 운영회의",
                 bg="white", fg="#666666", anchor="w").pack(fill="x", pady=(4, 0))

        # ---- C. Filename Preview ----
        row_c = tk.LabelFrame(inner, text="C. 파일명 미리보기", bg="white", padx=10, pady=8)
        row_c.pack(fill="x", pady=(0, 8))
        tk.Label(
            row_c,
            text="형식: YYYY-MM-DD__문서유형__태그__원본파일명.ext  (태그가 비어 있으면 생략)",
            bg="white", anchor="w", justify="left",
        ).pack(fill="x")

        # ---- D. Save ----
        row_d = tk.LabelFrame(inner, text="D. 저장", bg="white", padx=10, pady=8)
        row_d.pack(fill="x", pady=(0, 8))

        control_row = tk.Frame(row_d, bg="white")
        control_row.pack(fill="x", pady=(0, 8))
        tk.Button(control_row, text="파일 저장", width=16, bg="#4caf50", fg="white",
                  activebackground="#43a047", relief="flat", bd=0, cursor="hand2",
                  command=lambda: save_files()).pack(side="left")

        tk.Label(row_d, text="작업 로그", bg="white", anchor="w").pack(fill="x")
        activity_frame = tk.Frame(row_d, bg="white")
        activity_frame.pack(fill="x")

        activity_text = tk.Text(activity_frame, height=7, wrap="word", state="disabled")
        activity_text.pack(side="left", fill="x", expand=True)
        activity_scroll = ttk.Scrollbar(activity_frame, orient="vertical", command=activity_text.yview)
        activity_scroll.pack(side="right", fill="y")
        activity_text.configure(yscrollcommand=activity_scroll.set)

        back_row = tk.Frame(row_d, bg="white")
        back_row.pack(fill="x", pady=(8, 0))
        tk.Button(back_row, text="뒤로", width=16, bg="#d9d9d9", activebackground="#c0c0c0",
                  relief="flat", bd=0, cursor="hand2",
                  command=self.show_main_workspace_menu).pack(side="left")

        # ---- helper functions ----
        def append_log(text):
            stamp = datetime.now().strftime("%H:%M:%S")
            activity_text.config(state="normal")
            activity_text.insert("end", f"[{stamp}] {text}\n")
            activity_text.see("end")
            activity_text.config(state="disabled")

        def build_preview_map():
            previews = {}
            destination = self.build_destination_drive_path()
            reserved = set()
            for path in selected_files:
                candidate = self.filename_builder.build_filename(
                    date_var.get().strip(), doc_type_var.get(), tags_var.get(), Path(path).name)
                previews[path] = self.filename_builder.ensure_unique_name(
                    destination, candidate, reserved) if destination else candidate
            return previews

        def refresh_file_table(*_):
            previews = build_preview_map()
            file_tree.delete(*file_tree.get_children())
            for idx, item in enumerate(selected_files):
                src = Path(item)
                file_tree.insert("", "end", iid=f"f{idx}",
                                 values=(src.name, str(src), previews.get(item, src.name)))
            file_count_var.set(f"선택된 파일 {len(selected_files)}개")

        def add_file_paths(paths):
            normalized = []
            for raw in paths:
                candidate = str(raw).strip().strip("{}")
                if candidate and Path(candidate).is_file():
                    normalized.append(str(Path(candidate)))
            if not normalized:
                return
            seen = set(selected_files)
            for item in normalized:
                if item not in seen:
                    selected_files.append(item)
                    seen.add(item)
            refresh_file_table()

        def add_folder_paths(folder_paths):
            discovered = []
            for raw in folder_paths:
                folder_candidate = str(raw).strip().strip("{}")
                folder = Path(folder_candidate)
                if folder_candidate and folder.is_dir():
                    discovered.extend(str(p) for p in folder.rglob("*") if p.is_file())
            add_file_paths(discovered)

        def remove_selected_rows():
            selected = file_tree.selection()
            if not selected:
                return
            paths = [file_tree.item(iid, "values")[1] for iid in selected]
            selected_files[:] = [item for item in selected_files if item not in paths]
            refresh_file_table()

        def pick_files():
            files = filedialog.askopenfilenames(parent=self.root, title="파일 추가")
            if files:
                add_file_paths(files)

        def pick_folder():
            folder = filedialog.askdirectory(parent=self.root, title="폴더 추가")
            if folder:
                add_folder_paths([folder])

        def handle_drop(event):
            dropped = self.root.tk.splitlist(event.data)
            file_items, folder_items = [], []
            for item in dropped:
                normalized = str(item).strip().strip("{}")
                if not normalized:
                    continue
                path_obj = Path(normalized)
                if path_obj.is_file():
                    file_items.append(normalized)
                elif path_obj.is_dir():
                    folder_items.append(normalized)
            if file_items:
                add_file_paths(file_items)
            if folder_items:
                add_folder_paths(folder_items)
            return event.action if hasattr(event, "action") else None

        def save_files():
            if not selected_files:
                messagebox.showerror("파일 저장", "저장할 파일을 1개 이상 추가하세요.", parent=self.root)
                return
            try:
                archive_date = datetime.strptime(date_var.get().strip(), "%Y-%m-%d").date().isoformat()
            except ValueError:
                messagebox.showerror("파일 저장", "날짜 형식은 YYYY-MM-DD 이어야 합니다.", parent=self.root)
                return
            if not state.active_workspace:
                messagebox.showerror("파일 저장", "활성 워크스페이스가 없습니다.", parent=self.root)
                return
            destination = self.build_destination_drive_path()
            if not destination or not destination.exists() or not destination.is_dir():
                messagebox.showerror("파일 저장", "매핑된 워크스페이스 드라이브를 사용할 수 없습니다.", parent=self.root)
                return
            for source in selected_files:
                if not Path(source).is_file():
                    messagebox.showerror("파일 저장", f"파일을 찾을 수 없습니다:\n{source}", parent=self.root)
                    return

            previews = build_preview_map()
            saved_count = 0
            failures = []

            for source in selected_files:
                src = Path(source)
                archived_name = previews.get(source, src.name)
                dst = destination / archived_name
                try:
                    shutil.copy2(src, dst)
                    size = dst.stat().st_size if dst.exists() else 0
                    self.db.insert_file_record({
                        "workspace": state.active_workspace,
                        "original_filename": src.name,
                        "archived_filename": archived_name,
                        "full_path": str(dst),
                        "document_type": doc_type_var.get(),
                        "tags": tags_var.get().strip(),
                        "uploaded_by": uploaded_by_var.get(),
                        "archive_date": archive_date,
                        "archived_at": datetime.now().isoformat(timespec="seconds"),
                        "file_ext": src.suffix,
                        "file_size": size,
                        "source_path": str(src),
                    })
                    saved_count += 1
                    append_log(f"저장 완료: {archived_name}")
                except Exception as exc:
                    failures.append(f"{src.name}: {exc}")
                    append_log(f"저장 실패: {src.name} ({exc})")

            if saved_count and not failures:
                messagebox.showinfo("파일 저장", f"{saved_count}개 파일을 저장했습니다.", parent=self.root)
            elif saved_count and failures:
                messagebox.showwarning("파일 저장",
                    f"{saved_count}개 저장 완료.\n{len(failures)}개 저장 실패.\n\n" + "\n".join(failures[:8]),
                    parent=self.root)
            else:
                messagebox.showerror("파일 저장", "저장된 파일이 없습니다.\n\n" + "\n".join(failures[:8]),
                                     parent=self.root)
            refresh_file_table()

        tk.Button(add_buttons, text="파일 추가", width=14, bg="#d9d9d9", activebackground="#c0c0c0",
                  relief="flat", bd=0, cursor="hand2", command=pick_files).pack(side="left")
        tk.Button(add_buttons, text="폴더 추가", width=14, bg="#d9d9d9", activebackground="#c0c0c0",
                  relief="flat", bd=0, cursor="hand2", command=pick_folder).pack(side="left", padx=(8, 0))
        tk.Button(add_buttons, text="선택 항목 제거", width=14, bg="#d9d9d9", activebackground="#c0c0c0",
                  relief="flat", bd=0, cursor="hand2", command=remove_selected_rows).pack(side="left", padx=(8, 0))

        drop_area.bind("<Button-1>", lambda _event: pick_files())
        if TkinterDnD is not None and hasattr(drop_area, "drop_target_register"):
            drop_area.drop_target_register(DND_FILES)
            drop_area.dnd_bind("<<Drop>>", handle_drop)

        date_var.trace_add("write", refresh_file_table)
        doc_type_var.trace_add("write", refresh_file_table)
        tags_var.trace_add("write", refresh_file_table)
        refresh_file_table()

    def show_search_files_screen(self):
        self._resize(760, 680)
        self.root.title("애플망고 DMS - 파일 검색")
        self.clear_screen()

        # ---- outer frame: fixed header + scrollable body ----
        outer = tk.Frame(self.root, bg="white")
        outer.pack(fill="both", expand=True)

        header_frame = tk.Frame(outer, bg="white", padx=14, pady=8)
        header_frame.pack(fill="x")
        self.build_header(header_frame, "파일 검색")

        scroll_canvas = tk.Canvas(outer, bg="white", highlightthickness=0)
        v_scroll = ttk.Scrollbar(outer, orient="vertical", command=scroll_canvas.yview)
        scroll_canvas.configure(yscrollcommand=v_scroll.set)
        v_scroll.pack(side="right", fill="y")
        scroll_canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(scroll_canvas, bg="white", padx=14, pady=8)
        inner_id = scroll_canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner_resize(event):
            scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all"))
            scroll_canvas.itemconfigure(inner_id, width=scroll_canvas.winfo_width())

        inner.bind("<Configure>", _on_inner_resize)
        scroll_canvas.bind("<Configure>", lambda e: scroll_canvas.itemconfigure(inner_id, width=e.width))
        scroll_canvas.bind("<MouseWheel>", lambda e: scroll_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        # ---- state ----
        workspace_var = tk.StringVar(value=state.active_workspace)
        date_entry_var = tk.StringVar(value="")
        doc_type_var = tk.StringVar(value="전체")
        tags_var = tk.StringVar(value="")
        free_var = tk.StringVar(value="")

        # ---- date auto-formatter (YYYY/MM/DD in one box) ----
        _date_updating = [False]

        def _auto_format_date(*_):
            if _date_updating[0]:
                return
            raw = date_entry_var.get()
            digits = re.sub(r"[^\d]", "", raw)[:8]
            if len(digits) > 6:
                formatted = f"{digits[:4]}/{digits[4:6]}/{digits[6:]}"
            elif len(digits) > 4:
                formatted = f"{digits[:4]}/{digits[4:]}"
            else:
                formatted = digits
            if raw != formatted:
                _date_updating[0] = True
                date_entry_var.set(formatted)
                _date_updating[0] = False

        date_entry_var.trace_add("write", _auto_format_date)

        def _parse_date_input():
            parts = date_entry_var.get().strip().split("/")
            year  = parts[0].strip() if len(parts) > 0 else ""
            month = parts[1].strip() if len(parts) > 1 else ""
            day   = parts[2].strip() if len(parts) > 2 else ""
            return year, month, day

        def _build_date_prefix():
            year, month, day = _parse_date_input()
            if not year:
                return None
            if not re.fullmatch(r"\d{4}", year):
                raise ValueError("연도는 4자리(YYYY)여야 합니다.")
            if month:
                if not month.isdigit() or not (1 <= int(month) <= 12):
                    raise ValueError("월은 01-12 범위여야 합니다.")
                month = f"{int(month):02d}"
            if day:
                if not month:
                    raise ValueError("일을 입력하려면 월을 먼저 입력하세요.")
                if not day.isdigit() or not (1 <= int(day) <= 31):
                    raise ValueError("일은 01-31 범위여야 합니다.")
                day = f"{int(day):02d}"
            if year and month and day:
                return f"{year}-{month}-{day}"
            if year and month:
                return f"{year}-{month}"
            return year

        # ---- Search Filters box (contains Search + Clear buttons) ----
        filters = tk.LabelFrame(inner, text="검색 필터", bg="white", padx=10, pady=8)
        filters.pack(fill="x", pady=(0, 8))

        tk.Label(filters, text="워크스페이스", bg="white", width=16, anchor="w").grid(row=0, column=0, sticky="w", pady=3)
        tk.Entry(filters, textvariable=workspace_var, width=36, state="readonly").grid(row=0, column=1, columnspan=3, sticky="w", pady=3)

        tk.Label(filters, text="날짜 (YYYY/MM/DD)", bg="white", width=16, anchor="w").grid(row=1, column=0, sticky="w", pady=3)
        tk.Entry(filters, textvariable=date_entry_var, width=16).grid(row=1, column=1, sticky="w", pady=3)
        tk.Label(filters, text="예: 2024/06/15 또는 2024/06 또는 2024",
                 bg="white", fg="#888888", font=("Segoe UI", 8)).grid(row=1, column=2, columnspan=2, sticky="w", padx=(6, 0))

        tk.Label(filters, text="문서 유형", bg="white", width=16, anchor="w").grid(row=2, column=0, sticky="w", pady=3)
        ttk.Combobox(filters, textvariable=doc_type_var,
                 values=["전체"] + self.db.get_document_types(),
                     state="readonly", width=24).grid(row=2, column=1, sticky="w", pady=3)

        tk.Label(filters, text="태그", bg="white", width=16, anchor="w").grid(row=3, column=0, sticky="w", pady=3)
        tk.Entry(filters, textvariable=tags_var, width=42).grid(row=3, column=1, columnspan=3, sticky="w", pady=3)

        tk.Label(filters, text="자유 검색어", bg="white", width=16, anchor="w").grid(row=4, column=0, sticky="w", pady=3)
        tk.Entry(filters, textvariable=free_var, width=42).grid(row=4, column=1, columnspan=3, sticky="w", pady=3)

        filter_btn_row = tk.Frame(filters, bg="white")
        filter_btn_row.grid(row=5, column=0, columnspan=5, sticky="w", pady=(8, 2))

        # 검색 버튼은 항상 활성
        search_btn = tk.Button(filter_btn_row, text="검색", width=12,
                               bg="#4caf50", fg="white", activebackground="#43a047",
                               relief="flat", bd=0, highlightthickness=0, cursor="hand2")
        search_btn.pack(side="left")

        # 초기화: 필터만 비움
        clear_btn = tk.Button(filter_btn_row, text="초기화", width=12,
                              bg="#d9d9d9", activebackground="#c0c0c0",
                              relief="flat", bd=0, highlightthickness=0, cursor="hand2")
        clear_btn.pack(side="left", padx=(8, 0))

        # ---- Results box (x + y scrollbars, multi-select) ----
        results_frame = tk.LabelFrame(inner, text="검색 결과", bg="white", padx=4, pady=6)
        results_frame.pack(fill="x", pady=(0, 8))

        cols = ("archive_date", "document_type", "tags", "archived_filename", "uploaded_by", "size", "full_path")
        table = ttk.Treeview(results_frame, columns=cols, show="headings", height=14, selectmode="extended")
        table.heading("archive_date", text="보관 날짜")
        table.heading("document_type", text="문서 유형")
        table.heading("tags", text="태그")
        table.heading("archived_filename", text="저장 파일명")
        table.heading("uploaded_by", text="업로드 사용자")
        table.heading("size", text="크기")
        table.heading("full_path", text="전체 경로")

        table.column("archive_date", width=95,  anchor="w", minwidth=80)
        table.column("document_type", width=110, anchor="w", minwidth=90)
        table.column("tags", width=140,          anchor="w", minwidth=100)
        table.column("archived_filename", width=200, anchor="w", minwidth=150)
        table.column("uploaded_by", width=100,   anchor="w", minwidth=80)
        table.column("size", width=80,           anchor="e", minwidth=60)
        table.column("full_path", width=320,     anchor="w", minwidth=200)
        table.grid(row=0, column=0, sticky="nsew")

        ytable_scroll = ttk.Scrollbar(results_frame, orient="vertical", command=table.yview)
        ytable_scroll.grid(row=0, column=1, sticky="ns")
        table.configure(yscrollcommand=ytable_scroll.set)

        xtable_scroll = ttk.Scrollbar(results_frame, orient="horizontal", command=table.xview)
        xtable_scroll.grid(row=1, column=0, sticky="ew")
        table.configure(xscrollcommand=xtable_scroll.set)

        results_frame.grid_rowconfigure(0, weight=1)
        results_frame.grid_columnconfigure(0, weight=1)

        # ---- bottom action buttons ----
        action_row = tk.Frame(inner, bg="white")
        action_row.pack(fill="x", pady=(0, 8))

        open_file_btn = tk.Button(action_row, text="파일 열기", width=14,
                                  bg="#d9d9d9", fg="black", activebackground="#c0c0c0",
                                  relief="flat", bd=0, cursor="hand2")
        open_file_btn.pack(side="left")

        delete_file_btn = tk.Button(action_row, text="파일 삭제", width=14,
                                    bg="#d9d9d9", fg="black", activebackground="#c0c0c0",
                                    relief="flat", bd=0, cursor="hand2")
        delete_file_btn.pack(side="left", padx=(8, 0))

        tk.Button(action_row, text="새로고침", width=12, bg="#d9d9d9", activebackground="#c0c0c0",
                  relief="flat", bd=0, cursor="hand2",
                  command=lambda: run_search()).pack(side="left", padx=(8, 0))

        tk.Button(action_row, text="뒤로", width=12, bg="#d9d9d9", activebackground="#c0c0c0",
                  relief="flat", bd=0, cursor="hand2",
                  command=self.show_main_workspace_menu).pack(side="left", padx=(8, 0))

        # ---- logic ----
        def clear_results():
            table.delete(*table.get_children())

        def run_search():
            clear_results()
            if not state.active_workspace:
                messagebox.showerror("파일 검색", "활성 워크스페이스가 없습니다.", parent=self.root)
                return
            try:
                date_prefix = _build_date_prefix()
            except ValueError as exc:
                messagebox.showerror("파일 검색", str(exc), parent=self.root)
                return

            rows = self.db.search_files(
                workspace=state.active_workspace,
                date_prefix=date_prefix,
                document_type=doc_type_var.get(),
                tags=tags_var.get().strip(),
                free_text=free_var.get().strip(),
            )

            stale_paths = []
            for idx, row in enumerate(rows):
                archive_date, document_type, tags, archived_filename, uploaded_by, file_size, full_path = row
                if not Path(full_path).exists():
                    stale_paths.append(full_path)
                    continue
                size_text = f"{int(file_size):,}" if isinstance(file_size, int) else str(file_size or "")
                table.insert("", "end", iid=f"r{idx}",
                             values=(archive_date, document_type, tags, archived_filename,
                                     uploaded_by, size_text, full_path))

            if stale_paths:
                self.db.delete_file_records_by_paths(state.active_workspace, stale_paths)
            _update_action_buttons()

        def clear_filters_only():
            # 필터만 초기화
            date_entry_var.set("")
            doc_type_var.set("전체")
            tags_var.set("")
            free_var.set("")

        def _get_selected_paths():
            return [table.item(iid, "values")[6] for iid in table.selection() if table.item(iid, "values")]

        def _update_action_buttons(*_):
            has_selection = bool(table.selection())
            if has_selection:
                open_file_btn.config(bg="#4caf50", fg="white", activebackground="#43a047")
                delete_file_btn.config(bg="#4caf50", fg="white", activebackground="#43a047")
            else:
                open_file_btn.config(bg="#d9d9d9", fg="black", activebackground="#c0c0c0")
                delete_file_btn.config(bg="#d9d9d9", fg="black", activebackground="#c0c0c0")

        def open_files():
            paths = _get_selected_paths()
            if not paths:
                return
            for target in paths:
                path = Path(target)
                if not path.exists():
                    messagebox.showerror("파일 열기", f"파일을 찾을 수 없습니다:\n{target}", parent=self.root)
                    continue
                try:
                    os.startfile(str(path))
                except OSError as exc:
                    messagebox.showerror("파일 열기", str(exc), parent=self.root)

        def delete_files():
            paths = _get_selected_paths()
            if not paths:
                return
            count = len(paths)
            names = "\n".join(Path(p).name for p in paths[:10])
            if count > 10:
                names += f"\n... 외 {count - 10}개"
            confirmed = messagebox.askyesno(
                "파일 삭제",
                f"정말로 {count}개 파일을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.\n\n{names}",
                parent=self.root,
            )
            if not confirmed:
                return
            errors = []
            deleted_paths = []
            for target in paths:
                path = Path(target)
                try:
                    path.unlink(missing_ok=True)
                    deleted_paths.append(str(path))
                except OSError as exc:
                    errors.append(f"{path.name}: {exc}")
            if deleted_paths:
                self.db.delete_file_records_by_paths(state.active_workspace, deleted_paths)
            if errors:
                messagebox.showerror("파일 삭제", "일부 파일 삭제에 실패했습니다:\n\n" + "\n".join(errors), parent=self.root)
            run_search()

        table.bind("<<TreeviewSelect>>", _update_action_buttons)
        table.bind("<Double-1>", lambda _event: open_files())

        search_btn.config(command=run_search)
        clear_btn.config(command=clear_filters_only)
        open_file_btn.config(command=open_files)
        delete_file_btn.config(command=delete_files)

        _update_action_buttons()

    def show_change_server_name_dialog(self, parent_win):
        dialog = tk.Toplevel(parent_win)
        dialog.title("서버 이름 변경")
        dialog.geometry("380x190")
        dialog.configure(bg="white")
        dialog.transient(parent_win)

        body = tk.Frame(dialog, bg="white", padx=16, pady=14)
        body.pack(fill="both", expand=True)

        current_name = config.default_server_name.lstrip("\\")
        tk.Label(body, text=f"현재 서버 이름: {current_name or '(없음)'}", bg="white", anchor="w").pack(fill="x", pady=(0, 8))

        tk.Label(body, text="새 서버 이름", bg="white", anchor="w").pack(fill="x")
        new_server_var = tk.StringVar(value="")
        entry = tk.Entry(body, textvariable=new_server_var)
        entry.pack(fill="x", pady=(2, 10))

        button_row = tk.Frame(body, bg="white")
        button_row.pack(fill="x")

        apply_btn = tk.Button(
            button_row,
            text="적용",
            width=12,
            state="disabled",
            bg="#d9d9d9",
            fg="black",
            activebackground="#c0c0c0",
            relief="flat",
            bd=0,
            cursor="hand2",
        )
        apply_btn.pack(side="left")

        tk.Button(
            button_row,
            text="취소",
            width=12,
            bg="#d9d9d9",
            activebackground="#c0c0c0",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=dialog.destroy,
        ).pack(side="left", padx=(8, 0))

        def update_apply_button(*_):
            has_name = bool(new_server_var.get().strip())
            if has_name:
                apply_btn.config(state="normal", bg="#4caf50", fg="white", activebackground="#43a047")
            else:
                apply_btn.config(state="disabled", bg="#d9d9d9", fg="black", activebackground="#c0c0c0")

        def apply_server_name():

            cleaned = new_server_var.get().strip().lstrip("\\")
            if not cleaned:
                return

            if state.active_workspace_drive and self.workspace_drive_mapped_by_app:
                self.workspace_manager.unmap_drive(state.active_workspace_drive)

            config.default_server_name = f"\\\\{cleaned}"
            self.clear_workspace(unmap_if_needed=False)
            messagebox.showinfo("설정", f"서버 이름이 {config.default_server_name}(으)로 변경되었습니다.", parent=dialog)
            dialog.destroy()
            self.show_workspace_selection_screen()

        new_server_var.trace_add("write", update_apply_button)
        apply_btn.config(command=apply_server_name)
        update_apply_button()
        entry.focus_set()

    def show_settings_screen(self):
        settings_win = tk.Toplevel(self.root)
        settings_win.title("애플망고 DMS - 설정")
        settings_win.geometry("260x300")
        settings_win.configure(bg="white")
        settings_win.transient(self.root)

        page = tk.Frame(settings_win, bg="white", padx=16, pady=16)
        page.pack(fill="both", expand=True)

        button_column = tk.Frame(page, bg="white")
        button_column.pack(expand=True)

        def settings_btn(label, command):
            tk.Button(
                button_column,
                text=label,
                width=22,
                bg="#d9d9d9",
                activebackground="#c0c0c0",
                relief="flat",
                bd=0,
                cursor="hand2",
                command=command,
            ).pack(pady=4)

        settings_btn("서버 이름 변경", lambda: self.show_change_server_name_dialog(settings_win))
        settings_btn("매핑된 드라이브 보기", lambda: show_mapped_drives_window(settings_win))
        settings_btn(
            "문서 유형 관리",
            lambda: messagebox.showinfo("문서 유형", "문서 유형 관리 기능은 추후 제공됩니다.", parent=settings_win),
        )
        settings_btn(
            "저장된 로그인 정보 삭제",
            lambda: (clear_saved_credentials(), messagebox.showinfo("설정", "저장된 로그인 정보를 삭제했습니다.", parent=settings_win)),
        )
        settings_btn("닫기", settings_win.destroy)

    def run(self):
        self.show_startup_screen()
        self.root.mainloop()