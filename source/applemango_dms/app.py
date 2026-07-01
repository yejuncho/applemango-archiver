import os
import re
import shutil
import threading
import random
import tkinter as tk
import tkinter.font as tkfont
import ctypes
from io import BytesIO

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
    WorkspaceStack,
)

from applemango_dms.ui.settings import (
    show_mapped_drives_window,
)

from applemango_dms.utils.windows import (
    apply_window_icon,
)

from applemango_dms.utils.images import (
    load_svg_photo,
)

class SequenceArchiverApp:
    def __init__(self):
        self.root = TkinterDnD.Tk() if TkinterDnD is not None else tk.Tk()
        apply_window_icon(self.root)
        self.ui_font_family = self._initialize_ui_font_family()
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
        self.ui_icon_photos = {}
        self.login_icon_photos = {}
        self.login_connectivity = {
            "dot_canvas": None,
            "dot_item": None,
            "label": None,
            "job": None,
            "running": False,
        }
        self._load_login_icon_photos()
        self._load_ui_icon_photos()

    def _initialize_ui_font_family(self):
        preferred_family = "Pretendard"
        font_path = config.PROJECT_ROOT / "assets" / "fonts" / "PretendardVariable.ttf"

        if os.name == "nt" and font_path.exists():
            try:
                FR_PRIVATE = 0x10
                added = ctypes.windll.gdi32.AddFontResourceExW(str(font_path), FR_PRIVATE, 0)
                if added > 0:
                    ctypes.windll.user32.SendMessageW(0xFFFF, 0x001D, 0, 0)
            except Exception:
                pass

        try:
            families = set(tkfont.families(self.root))
            for candidate in ("Pretendard Variable", "Pretendard", "PretendardVariable"):
                if candidate in families:
                    preferred_family = candidate
                    break
        except Exception:
            pass

        for name in (
            "TkDefaultFont",
            "TkTextFont",
            "TkMenuFont",
            "TkHeadingFont",
            "TkTooltipFont",
            "TkIconFont",
            "TkCaptionFont",
            "TkSmallCaptionFont",
        ):
            try:
                tkfont.nametofont(name).configure(family=preferred_family)
            except Exception:
                pass

        return preferred_family

    def _font(self, size, weight="normal"):
        if weight and weight != "normal":
            return (self.ui_font_family, size, weight)
        return (self.ui_font_family, size)

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
            config.PROJECT_ROOT / "assets" / "images" / "applemango_mission.png",
            config.PROJECT_ROOT / "assets" / "images" / "phileo.png",
            config.PROJECT_ROOT / "assets" / "images" / "hansomang.png",
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

    def _load_startup_logo_photo(self, max_width, max_height):
        if Image is None or ImageTk is None:
            return None

        path = config.PROJECT_ROOT / "assets" / "images" / "hiscom.png"
        if not path.exists():
            return None

        try:
            image = Image.open(path)
            resized = self._resize_image_fit(image, max_width=max_width, max_height=max_height)
            return ImageTk.PhotoImage(resized)
        except Exception:
            return None

    def _load_random_login_logo_photo(self, max_width, max_height):
        if Image is None or ImageTk is None:
            return None

        image_root = config.PROJECT_ROOT / "assets" / "images"
        png_paths = sorted(image_root.glob("*.png"))
        if not png_paths:
            return None

        # Randomly pick from up to five PNG logo files in assets/images.
        candidate_pool = png_paths[:5]
        selected_path = random.choice(candidate_pool)

        try:
            image = Image.open(selected_path)
            resized = self._resize_image_fit(image, max_width=max_width, max_height=max_height)
            return ImageTk.PhotoImage(resized)
        except Exception:
            return None

    def _load_icon_photo(self, path, max_width, max_height):
        if not path.exists():
            return None

        if Image is not None and ImageTk is not None:
            if path.suffix.lower() == ".svg":
                try:
                    resvg = __import__("resvg_py")
                    svg_source = path.read_text(encoding="utf-8")
                    # Lucide SVGs commonly use currentColor; replace with app icon tone.
                    svg_source = svg_source.replace("currentColor", "#5a647f")
                    png_bytes = resvg.svg_to_bytes(svg_string=svg_source)
                    image = Image.open(BytesIO(png_bytes))
                    resized = self._resize_image_fit(image, max_width=max_width, max_height=max_height)
                    return ImageTk.PhotoImage(resized)
                except Exception:
                    pass

            try:
                image = Image.open(path)
                resized = self._resize_image_fit(image, max_width=max_width, max_height=max_height)
                return ImageTk.PhotoImage(resized)
            except Exception:
                pass

            try:
                cairosvg = __import__("cairosvg")
                png_bytes = cairosvg.svg2png(url=str(path), output_width=max_width, output_height=max_height)
                image = Image.open(BytesIO(png_bytes))
                return ImageTk.PhotoImage(image)
            except Exception:
                pass

        try:
            return tk.PhotoImage(file=str(path))
        except Exception:
            return None

    def _load_login_icon_photos(self):
        icon_dir = config.PROJECT_ROOT / "assets" / "icons" / "login"
        icon_specs = {
            "username": "username.svg",
            "password": "password.svg",
            "password_visible": "password_visible.svg",
            "password_invisible": "password_invisible.svg",
        }

        photos = {}
        for key, filename in icon_specs.items():
            photo = self._load_icon_photo(icon_dir / filename, max_width=18, max_height=18)
            if photo is not None:
                photos[key] = photo

        self.login_icon_photos = photos

    def _load_ui_icon_photos(self):
        icon_specs = {
            "workspace_settings": (config.PROJECT_ROOT / "assets" / "icons" / "workspace_selection" / "settings.svg", 22, 22, "#111111"),
            "workspace_back": (config.PROJECT_ROOT / "assets" / "icons" / "workspace_selection" / "back.svg", 22, 22, "#111111"),
            "workspace_selection_folder": (config.PROJECT_ROOT / "assets" / "icons" / "workspace_selection" / "folder.svg", 24, 24, "#6ea7ff"),
            "workspace_clock": (config.PROJECT_ROOT / "assets" / "icons" / "workspace_selection" / "clock.svg", 16, 16, "#111111"),
            "workspace_database": (config.PROJECT_ROOT / "assets" / "icons" / "workspace_selection" / "database.svg", 16, 16, "#111111"),
            "workspace_file_stack": (config.PROJECT_ROOT / "assets" / "icons" / "workspace_selection" / "file_stack.svg", 16, 16, "#111111"),
            "workspace_folder": (config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "folder.svg", 30, 30, "#2fa44f"),
            "workspace_file_save": (config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "file_save_blue.svg", 18, 18, None),
            "workspace_file_search": (config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "file_search_green.svg", 18, 18, None),
            "workspace_exit": (config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "exit_red.svg", 18, 18, None),
            "workspace_cloud_save": (config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "cloud_save_blue.svg", 80, 80, None),
        }

        photos = {}
        for key, (path, width, height, tint) in icon_specs.items():
            photo = load_svg_photo(path, max_width=width, max_height=height, tint=tint)
            if photo is not None:
                photos[key] = photo

        self.ui_icon_photos = photos

    def _create_icon_button(self, parent, icon_key, fallback_text, command, *, bg="#ffffff", hover_bg="#eef2fb", fg="#111111", padding=(8, 6)):
        wrapper = tk.Frame(parent, bg=bg, bd=0, highlightthickness=0)
        icon_photo = self.ui_icon_photos.get(icon_key)

        label = tk.Label(
            wrapper,
            image=icon_photo,
            text=fallback_text if icon_photo is None else "",
            bg=bg,
            fg=fg,
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        label.pack(padx=padding[0], pady=padding[1])

        def activate(_event=None):
            command()

        def set_state(active_bg):
            wrapper.configure(bg=active_bg)
            label.configure(bg=active_bg)

        for widget in (wrapper, label):
            widget.bind("<Button-1>", activate, add="+")
            widget.bind("<Enter>", lambda _event: set_state(hover_bg), add="+")
            widget.bind("<Leave>", lambda _event: set_state(bg), add="+")

        wrapper.image = icon_photo
        set_state(bg)
        return wrapper

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

    def _smooth_rounded_rect(self, canvas, x1, y1, x2, y2, radius, fill="", outline="", width=1, tags="", dash=None):
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
            fill=fill, outline=outline, width=width, tags=tags, dash=dash,
        )

    def create_login_card(self, parent, width=360, height=470, fill_top="#f9f8ff", fill_bottom="#f9f8ff", radius=22):
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
            r = radius

            # Layered soft shadow — darkest/furthest drawn first (lower z)
            self._smooth_rounded_rect(parent, x1 + 7, y1 + 9, x2 + 7, y2 + 9, r,
                                      fill="#d8d5f0", outline="", tags="cardshadow")
            self._smooth_rounded_rect(parent, x1 + 4, y1 + 5, x2 + 4, y2 + 5, r,
                                      fill="#e5e3f5", outline="", tags="cardshadow")
            self._smooth_rounded_rect(parent, x1 + 2, y1 + 2, x2 + 2, y2 + 2, r,
                                      fill="#eeedf8", outline="", tags="cardshadow")

            # Card fill then subtle border
            self._smooth_rounded_rect(parent, x1, y1, x2, y2, r,
                                      fill=fill_bottom, outline="", tags="cardfill")
            self._smooth_rounded_rect(parent, x1, y1, x2, y2, r,
                                      fill=fill_top, outline="", tags="cardfill")
            self._smooth_rounded_rect(parent, x1 + 1, y1 + 1, x2 - 1, y2 - 7, r,
                                      fill=fill_top, outline="", tags="cardfill")
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

    def create_rounded_entry(self, parent, placeholder, icon_key, is_password=False):
        wrapper = tk.Frame(parent, bg="#f9f8ff")
        canvas = tk.Canvas(wrapper, height=52, bg="#f9f8ff", highlightthickness=0, bd=0)
        canvas.pack(fill="x")

        inner = tk.Frame(canvas, bg="#ffffff")
        inner_id = canvas.create_window(10, 5, window=inner, anchor="nw", height=42)

        leading_icon = self.login_icon_photos.get(icon_key)
        icon_label = tk.Label(inner, bg="#ffffff", fg="#868cab")
        if leading_icon is not None:
            icon_label.configure(image=leading_icon)
            icon_label.image = leading_icon
        else:
            fallback_text = "👤" if icon_key == "username" else "🔒"
            icon_label.configure(text=fallback_text, font=("Segoe UI Emoji", 11))
        icon_label.pack(side="left", padx=(12, 9))

        value_var = tk.StringVar(value="")
        entry = tk.Entry(
            inner,
            textvariable=value_var,
            show="*" if is_password else "",
            font=self._font(12),
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

        placeholder_label = tk.Label(inner, text=placeholder, font=self._font(11), bg="#ffffff", fg="#a0a3b8")
        placeholder_label.place(x=42, y=9)
        placeholder_label.bind("<Button-1>", lambda _e: entry.focus_set())

        field_state = {
            "focused": False,
            "password_visible": False,
        }

        eye_label = None
        if is_password:
            eye_icon = self.login_icon_photos.get("password_visible")
            eye_label = tk.Label(inner, bg="#ffffff", fg="#8086a3", cursor="hand2")
            if eye_icon is not None:
                eye_label.configure(image=eye_icon)
                eye_label.image = eye_icon
            else:
                eye_label.configure(text="\U0001f441", font=("Segoe UI Emoji", 13))
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
                hide_icon = self.login_icon_photos.get("password_invisible")
                if hide_icon is not None:
                    eye_widget.configure(image=hide_icon, text="")
                    eye_widget.image = hide_icon
                else:
                    eye_widget.configure(text="\U0001f648")  # 🙈 = visible, click to hide
        else:
            entry_widget.configure(show="*")
            if eye_widget is not None:
                show_icon = self.login_icon_photos.get("password_visible")
                if show_icon is not None:
                    eye_widget.configure(image=show_icon, text="")
                    eye_widget.image = show_icon
                else:
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
            canvas.create_text(w // 2, h // 2, text=text, fill=text_color, font=self._font(13, "bold"), tags="btn")

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

        logo_photo = self._load_startup_logo_photo(max_width=300, max_height=180)
        self.startup_logo_image = logo_photo
        if logo_photo is not None:
            logo_label.configure(image=logo_photo)
        else:
            logo_label.configure(text="HISCOM", font=self._font(30, "bold"), fg="#1d2138")

        self.root.after(1200, self.route_from_startup)

    def route_from_startup(self):
        saved = load_saved_credentials()
        if not saved:
            self.show_login_screen()
            return

        ok, err = authenticate_to_server(saved["username"], saved["password"])
        if ok:
            update_session_login(saved["username"], saved["password"])
            self.show_workspace_selection_screen()
            return

        clear_saved_credentials()
        clear_session_login()
        self.show_login_screen(prefill_username=saved.get("username"))

        startup_msg = "저장된 로그인으로 NAS 연결에 실패했습니다.\n아이디/패스워드를 다시 입력해 주세요."
        if "1219" in str(err):
            startup_msg = (
                "이전 NAS 연결 정보와 충돌해 자동 로그인이 실패했습니다.\n"
                "연결을 정리한 뒤 로그인 화면으로 이동했습니다.\n"
                "아이디/패스워드를 다시 입력해 주세요."
            )
        messagebox.showinfo("자동 로그인 실패", startup_msg, parent=self.root)

    def show_login_screen(self, prefill_username=None):
        self._stop_login_connectivity_polling()
        self._prepare_login_layout()

        frame = tk.Frame(self.login_content, bg="#f9f8ff")
        frame.pack(fill="both", expand=True)

        logo_photo = self._load_random_login_logo_photo(max_width=280, max_height=100)
        self.logo_image = logo_photo
        if logo_photo is not None:
            tk.Label(frame, image=logo_photo, bg="#f9f8ff").pack(pady=(0, 8))
        else:
            tk.Label(frame, text="애플망고", font=self._font(25, "bold"), fg="#06012a", bg="#f9f8ff").pack(pady=(0, 0))

        tk.Label(frame, text="DMS - 데이터 관리 시스템", font=self._font(12, "bold"), fg="#06012a", bg="#f9f8ff").pack(pady=(0, 25))

        username_field = self.create_rounded_entry(frame, "사용자명", "username", is_password=False)
        username_field["wrapper"].pack(fill="x")
        tk.Frame(frame, bg="#f9f8ff", height=10).pack(fill="x")

        password_field = self.create_rounded_entry(frame, "비밀번호", "password", is_password=True)
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
            font=self._font(10),
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        ).pack(side="left")

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
                is_connection_conflict = "1219" in err

                if is_network_issue:
                    messagebox.showerror("로그인 실패", network_warning_msg, parent=self.root)
                elif is_connection_conflict:
                    messagebox.showerror(
                        "로그인 실패",
                        "기존 NAS 연결 정보와 충돌했습니다(1219).\n"
                        "연결 정보를 정리한 뒤 다시 시도해 주세요.",
                        parent=self.root,
                    )
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
            font=self._font(9),
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

        self._center_window(760, 680)
        self.root.title("애플망고 DMS - 워크스페이스 선택")
        self.clear_screen()
        self.root.configure(bg="#f8f8ff")

        _, ip_addr, status_text = self.get_connection_snapshot()
        shares = discover_server_shares(config.default_server_name)

        bg = tk.Canvas(self.root, bg="#f8f8ff", highlightthickness=0, bd=0)
        bg.pack(fill="both", expand=True)

        main_card = self.create_login_card(
            bg,
            width=702,
            height=596,
            fill_top="#ffffff",
            fill_bottom="#ffffff",
        )
        content = main_card["content"]
        redraw = main_card["redraw"]

        def on_bg_resize(event):
            self._draw_login_gradient(event.width, event.height)
            redraw(event.width // 2, event.height // 2)

        bg.bind("<Configure>", on_bg_resize)

        content.configure(bg="#ffffff")
        container = tk.Frame(content, bg="#ffffff")
        container.pack(fill="both", expand=True)

        header_row = tk.Frame(container, bg="#ffffff")
        header_row.pack(fill="x", pady=(0, 18))

        left_header = tk.Frame(header_row, bg="#ffffff")
        left_header.pack(side="left", fill="x", expand=True)

        display_name = state.session_account_name or state.session_username or "사용자"
        tk.Label(
            left_header,
            text=f"환영합니다, {display_name}님",
            font=self._font(20, "bold"),
            fg="#06012a",
            bg="#ffffff",
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            left_header,
            text="워크스페이스를 선택해주세요.",
            font=self._font(12),
            fg="#000000",
            bg="#ffffff",
            anchor="w",
        ).pack(anchor="w", pady=(6, 0))

        right_header = tk.Frame(header_row, bg="#ffffff", bd=0, highlightthickness=0)
        right_header.pack(side="right", anchor="ne")

        button_row = tk.Frame(right_header, bg="#ffffff")
        button_row.pack(anchor="e")

        self._create_icon_button(button_row, "workspace_settings", "\u2699", self.show_settings_screen, bg="#ffffff", hover_bg="#eef1fa", fg="#111111", padding=(7, 7)).pack(side="left", padx=(4, 0))
        self._create_icon_button(
            button_row,
            "workspace_back",
            "\u21aa",
            lambda: self.show_login_screen(prefill_username=state.session_username or state.session_account_name or None),
            bg="#ffffff",
            hover_bg="#eef1fa",
            fg="#111111",
            padding=(7, 7),
        ).pack(side="left", padx=(4, 0))

        list_shell = tk.Canvas(container, bg="#ffffff", highlightthickness=0, bd=0)
        list_shell.pack(fill="both", expand=True)

        stack_surface = tk.Frame(list_shell, bg="#ffffff")
        surface_window = list_shell.create_window(0, 0, window=stack_surface, anchor="nw")

        stack_canvas = tk.Canvas(stack_surface, bg="#ffffff", highlightthickness=0, bd=0)
        stack_canvas.pack(side="left", fill="both", expand=True, padx=(0, 2), pady=(2, 0))

        empty_label = None

        def enter_workspace(selected):
            drive, mapped_by_app, err = self.workspace_manager.map_workspace(selected, state.session_username, state.session_password)
            if not drive:
                messagebox.showerror("워크스페이스", f"워크스페이스 드라이브 매핑에 실패했습니다:\n{err}", parent=self.root)
                return

            self.set_workspace(selected, drive, mapped_by_app)
            self.show_main_workspace_menu()

        if not shares:
            empty_label = tk.Label(
                stack_surface,
                text="선택 가능한 워크스페이스가 없습니다.",
                bg="#ffffff",
                fg="#666666",
                font=self._font(11),
                anchor="w",
            )
            empty_label.pack(anchor="w", padx=24, pady=24)
            workspace_stack = None
        else:
            workspace_stack = WorkspaceStack(
                stack_canvas,
                shares,
                on_open=enter_workspace,
                bg="#ffffff",
                card_bg="#f8f9ff",
                meta_icon_photos={
                    "clock": self.ui_icon_photos.get("workspace_clock"),
                    "database": self.ui_icon_photos.get("workspace_database"),
                    "file_stack": self.ui_icon_photos.get("workspace_file_stack"),
                },
                folder_icon_photo=self.ui_icon_photos.get("workspace_selection_folder"),
                font_family=self.ui_font_family,
            )
            stack_body_id = stack_canvas.create_window((0, 0), window=workspace_stack, anchor="nw")
            scroll_state = {
                "target": 0.0,
                "current": 0.0,
                "job": None,
                "dragging": False,
                "last_y": None,
                "moved": False,
            }

            def sync_stack_region(total_height=None):
                body_height = total_height if total_height is not None else workspace_stack.winfo_reqheight()
                stack_canvas.configure(scrollregion=(0, 0, stack_canvas.winfo_width(), body_height + 12))

            def get_max_scroll():
                stack_canvas.update_idletasks()
                scroll_region = stack_canvas.cget("scrollregion")
                if not scroll_region:
                    return 0.0
                _x0, _y0, _x1, y1 = [float(value) for value in str(scroll_region).split()]
                viewport = float(stack_canvas.winfo_height())
                return max(0.0, y1 - viewport)

            def apply_scroll_offset(offset):
                max_scroll = get_max_scroll()
                if max_scroll <= 0:
                    stack_canvas.yview_moveto(0.0)
                    return
                clamped = max(0.0, min(max_scroll, offset))
                scroll_state["current"] = clamped
                stack_canvas.yview_moveto(clamped / max_scroll)

            def animate_scroll():
                scroll_state["job"] = None
                current = scroll_state["current"]
                target = scroll_state["target"]
                next_value = current + (target - current) * 0.24
                if abs(next_value - target) < 0.6:
                    next_value = target
                apply_scroll_offset(next_value)
                if abs(scroll_state["current"] - scroll_state["target"]) >= 0.6:
                    scroll_state["job"] = self.root.after(16, animate_scroll)

            def schedule_scroll_animation():
                if scroll_state["job"] is None:
                    scroll_state["job"] = self.root.after(16, animate_scroll)

            def add_scroll_delta(delta_pixels):
                max_scroll = get_max_scroll()
                if max_scroll <= 0:
                    return
                scroll_state["target"] = max(0.0, min(max_scroll, scroll_state["target"] + delta_pixels))
                schedule_scroll_animation()

            def on_stack_mousewheel(event):
                delta = event.delta
                if delta == 0:
                    return "break"
                add_scroll_delta(-delta / 120.0 * 44.0)
                return "break"

            def on_drag_press(event):
                scroll_state["dragging"] = True
                scroll_state["last_y"] = event.y_root
                scroll_state["moved"] = False

            def on_drag_motion(event):
                if not scroll_state["dragging"] or scroll_state["last_y"] is None:
                    return
                delta_y = event.y_root - scroll_state["last_y"]
                scroll_state["last_y"] = event.y_root
                if abs(delta_y) > 0:
                    scroll_state["moved"] = True
                    add_scroll_delta(-delta_y * 1.35)

            def on_drag_release(_event):
                scroll_state["dragging"] = False
                scroll_state["last_y"] = None
                self.root.after(0, lambda: scroll_state.__setitem__("moved", False))

            def bind_scroll_gestures(widget):
                widget.bind("<MouseWheel>", on_stack_mousewheel, add="+")
                widget.bind("<ButtonPress-1>", on_drag_press, add="+")
                widget.bind("<B1-Motion>", on_drag_motion, add="+")
                widget.bind("<ButtonRelease-1>", on_drag_release, add="+")
                for child in widget.winfo_children():
                    bind_scroll_gestures(child)

            workspace_stack.on_layout = lambda height: sync_stack_region(height)
            def on_stack_configure(event):
                stack_canvas.itemconfigure(stack_body_id, width=int(event.width * 0.91))
                stack_canvas.coords(stack_body_id, max(0, int((event.width - (event.width * 0.91)) / 2)), 0)
                sync_stack_region()
                apply_scroll_offset(scroll_state["current"])

            stack_canvas.bind("<Configure>", on_stack_configure)
            bind_scroll_gestures(workspace_stack)
            bind_scroll_gestures(stack_canvas)

            for workspace_name in shares:
                cached_meta = self.workspace_metadata_cache.get(workspace_name)
                if cached_meta:
                    workspace_stack.set_card_metadata(workspace_name, cached_meta)

        def redraw_list_shell(event=None):
            width = max(200, list_shell.winfo_width())
            height = max(200, list_shell.winfo_height())
            list_shell.itemconfigure(surface_window, width=max(180, width - 6), height=max(180, height - 2))
            list_shell.coords(surface_window, 0, 0)
            list_shell.tag_raise(surface_window)

        list_shell.bind("<Configure>", redraw_list_shell)

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
                    if workspace_stack and workspace_stack.winfo_exists():
                        workspace_stack.set_card_metadata(name, metadata)

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

    def _create_workspace_shell(self):
        self._resize(1160, 780)
        self.root.title("애플망고 DMS - 워크스페이스")
        self.clear_screen()
        self.root.configure(bg="#edf2fb")

        bg = tk.Canvas(self.root, bg="#edf2fb", highlightthickness=0, bd=0)
        bg.pack(fill="both", expand=True)

        main_card = self.create_login_card(
            bg,
            width=1060,
            height=694,
            fill_top="#ffffff",
            fill_bottom="#f4f7ff",
            radius=20,
        )
        content = main_card["content"]
        redraw = main_card["redraw"]

        def on_bg_resize(event):
            redraw(event.width // 2, event.height // 2)

        bg.bind("<Configure>", on_bg_resize)

        content.configure(bg="#ffffff")
        shell = tk.Frame(content, bg="#ffffff")
        shell.pack(fill="both", expand=True)

        header = tk.Frame(shell, bg="#ffffff", highlightthickness=0, bd=0)
        header.pack(fill="x", pady=(0, 0))

        left = tk.Frame(header, bg="#ffffff", padx=20, pady=14)
        left.pack(side="left", fill="x", expand=True)

        workspace_name = state.active_workspace or "워크스페이스"
        welcome_name = state.session_account_name or state.session_username or "사용자"

        workspace_folder_icon = self.ui_icon_photos.get("workspace_folder")
        if workspace_folder_icon is not None:
            folder_label = tk.Label(left, image=workspace_folder_icon, bg="#ffffff")
            folder_label.image = workspace_folder_icon
            folder_label.pack(side="left", padx=(0, 12), pady=(2, 0), anchor="n")
        else:
            tk.Label(left, text="\U0001F4C1", font=("Segoe UI Emoji", 19), fg="#2fa44f", bg="#ffffff").pack(side="left", padx=(0, 12), pady=(2, 0), anchor="n")
        title_block = tk.Frame(left, bg="#ffffff")
        title_block.pack(side="left", fill="x", expand=True)
        tk.Label(title_block, text=workspace_name, font=self._font(20, "bold"), fg="#1f2b4a", bg="#ffffff", anchor="w").pack(anchor="w", pady=(0, 0))

        right = tk.Frame(header, bg="#ffffff", padx=20, pady=14)
        right.pack(side="right", anchor="ne")
        info_row = tk.Frame(right, bg="#ffffff")
        info_row.pack(anchor="e")
        tk.Label(
            info_row,
            text=f"서버: {config.default_server_name}",
            font=self._font(9, "bold"),
            fg="#111111",
            bg="#ffffff",
        ).pack(side="left")
        tk.Label(
            info_row,
            text="|",
            font=self._font(9, "bold"),
            fg="#111111",
            bg="#ffffff",
        ).pack(side="left", padx=(10, 10))
        tk.Label(
            info_row,
            text=f"사용자: {welcome_name}",
            font=self._font(9, "bold"),
            fg="#111111",
            bg="#ffffff",
        ).pack(side="left")
        tk.Label(
            info_row,
            text="|",
            font=self._font(9, "bold"),
            fg="#111111",
            bg="#ffffff",
        ).pack(side="left", padx=(10, 10))
        self._create_icon_button(
            info_row,
            "workspace_back",
            "\u21aa",
            self.show_workspace_selection_screen,
            bg="#ffffff",
            hover_bg="#eef2fb",
            fg="#111111",
            padding=(7, 7),
        ).pack(side="left")

        body = tk.Frame(shell, bg="#ffffff")
        body.pack(fill="both", expand=True)

        sidebar = tk.Frame(body, bg="#edf2fb", width=250, highlightthickness=0, bd=0)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        content_area = tk.Frame(body, bg="#ffffff", highlightthickness=0, bd=0)
        content_area.pack(side="left", fill="both", expand=True)

        return {
            "bg": bg,
            "card": main_card,
            "content": content_area,
            "sidebar": sidebar,
            "shell": shell,
            "header": header,
            "body": body,
        }

    def _build_sidebar_nav(self, parent, active_key, items, icon_photos=None):
        rows = []
        top_gap = 10
        row_gap = 10
        nav_section = tk.Frame(parent, bg=parent.cget("bg"))
        nav_section.pack(fill="both", expand=True, pady=(top_gap, 0))

        def build_row(key, icon, title, desc, command, icon_fg, active_bg, is_last):
            is_active = key == active_key
            base_bg = parent.cget("bg")
            hover_bg = "#f2f5fb"
            card_bg = active_bg if is_active else "#fdfefe"

            outer = tk.Frame(nav_section, bg=base_bg)
            outer.pack(fill="x", padx=10, pady=(0, 0 if is_last else row_gap))

            card = tk.Canvas(
                outer,
                bg=base_bg,
                highlightthickness=0,
                bd=0,
                relief="flat",
                cursor="hand2",
                height=96,
            )
            card.pack(fill="x")

            def activate(_event=None):
                command()

            def apply_style(mode="normal"):
                nonlocal is_active
                if mode == "active":
                    bg_color = active_bg
                    border = "#d0d7e6"
                    icon_color = icon_fg
                    title_color = "#2b3348"
                    desc_color = "#596279"
                elif mode == "hover":
                    bg_color = hover_bg
                    border = "#d5dbe9"
                    icon_color = icon_fg
                    title_color = "#2b3348"
                    desc_color = "#596279"
                else:
                    bg_color = card_bg
                    border = "#d9deea"
                    icon_color = icon_fg
                    title_color = "#2d3448"
                    desc_color = "#677189"

                card.delete("nav")
                width = max(180, card.winfo_width())
                self._smooth_rounded_rect(card, 1, 1, width - 1, 95, 20, fill=bg_color, outline=border, width=1, tags="nav")
                icon_photo = (icon_photos or {}).get(key)
                if icon_photo is not None:
                    card.create_image(26, 31, image=icon_photo, anchor="center", tags="nav")
                else:
                    card.create_text(26, 31, text=icon, font=("Segoe UI Emoji", 18), fill=icon_color, anchor="center", tags="nav")
                card.create_text(52, 25, text=title, font=self._font(11, "bold"), fill=title_color, anchor="w", tags="nav")
                card.create_text(
                    52,
                    59,
                    text=desc,
                    font=self._font(8),
                    fill=desc_color,
                    anchor="w",
                    justify="left",
                    width=max(110, width - 72),
                    tags="nav",
                )

            card.bind("<Configure>", lambda _event: apply_style("active" if is_active else "normal"), add="+")
            card.bind("<Button-1>", activate, add="+")
            outer.bind("<Button-1>", activate, add="+")
            card.bind("<Enter>", lambda _event: apply_style("hover") if not is_active else apply_style("active"), add="+")
            card.bind("<Leave>", lambda _event: apply_style("active" if is_active else "normal"), add="+")
            outer.bind("<Enter>", lambda _event: apply_style("hover") if not is_active else apply_style("active"), add="+")
            outer.bind("<Leave>", lambda _event: apply_style("active" if is_active else "normal"), add="+")

            rows.append(card)
            apply_style("active" if is_active else "normal")
            return card

        total = len(items)
        for idx, (key, icon, title, desc, command, icon_fg) in enumerate(items):
            build_row(
                key,
                icon,
                title,
                desc,
                command,
                icon_fg,
                active_bg="#f7f9fd",
                is_last=(idx == total - 1),
            )

        return rows

    @staticmethod
    def _format_iso_date_input(raw_text):
        digits = re.sub(r"[^\d]", "", raw_text or "")[:8]
        if len(digits) > 6:
            return f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"
        if len(digits) > 4:
            return f"{digits[:4]}-{digits[4:]}"
        return digits

    def _bind_iso_date_formatter(self, var):
        state_box = {"updating": False}

        def _on_change(*_):
            if state_box["updating"]:
                return
            current = var.get()
            formatted = self._format_iso_date_input(current)
            if current != formatted:
                state_box["updating"] = True
                var.set(formatted)
                state_box["updating"] = False

        var.trace_add("write", _on_change)

    @staticmethod
    def _file_type_icon(filename):
        suffix = Path(filename).suffix.lower()
        if suffix == ".pdf":
            return "PDF", "#ef4444"
        if suffix in {".xlsx", ".xls", ".csv"}:
            return "XLS", "#16a34a"
        if suffix in {".doc", ".docx", ".hwp", ".txt"}:
            return "DOC", "#2563eb"
        if suffix in {".ppt", ".pptx"}:
            return "PPT", "#f97316"
        if suffix in {".zip", ".7z", ".rar"}:
            return "ZIP", "#6b7280"
        return "FILE", "#64748b"

    def _get_recent_workspace_files(self, workspace_name, limit=8):
        rows = self.db.search_files(workspace=workspace_name, date_prefix=None, document_type="전체", tags="", free_text="")
        return rows[: max(1, int(limit))]

    def show_main_workspace_menu(self):
        if not state.active_workspace:
            self.show_workspace_selection_screen()
            return

        self.show_save_files_screen()

    def _build_workspace_page_header(self, parent, title, subtitle):
        header = tk.Frame(parent, bg="#ffffff")
        header.pack(fill="x", padx=20, pady=(16, 12))
        tk.Label(header, text=title, font=self._font(17, "bold"), fg="#1f2540", bg="#ffffff", anchor="w").pack(fill="x", pady=(0, 4))
        tk.Label(header, text=subtitle, font=self._font(12), fg="#1f2540", bg="#ffffff", anchor="w").pack(fill="x")
        return header

    def build_destination_drive_path(self):
        drive = normalize_drive_letter(state.active_workspace_drive)
        if not drive:
            return None
        return Path(f"{drive}\\")

    def show_save_files_screen(self):
        shell = self._create_workspace_shell()
        self.root.title("애플망고 DMS - 파일 저장")

        self._build_sidebar_nav(
            shell["sidebar"],
            "save",
            [
                ("save", "\U0001F4E4", "파일 저장", "새 파일을 업로드하거나\n기존 파일을 저장합니다.", self.show_save_files_screen, "#2d6cdf"),
                ("search", "\U0001F50D", "파일 검색", "저장한 파일을 검색하고\n열람합니다.", self.show_search_files_screen, "#111111"),
                ("exit", "\u21a9", "워크스페이스 나가기", "현재 워크스페이스를 나가고\n목록으로 돌아갑니다.", self.show_workspace_exit_screen, "#d33e3e"),
            ],
            icon_photos={
                "save": self.ui_icon_photos.get("workspace_file_save"),
                "search": self.ui_icon_photos.get("workspace_file_search"),
                "exit": self.ui_icon_photos.get("workspace_exit"),
            },
        )

        outer = shell["content"]
        self._build_workspace_page_header(outer, "파일 저장", "파일을 드래그 앤 드롭하거나, 아래 버튼을 클릭하여 파일을 선택하세요.")

        board = tk.Frame(outer, bg="#ffffff", highlightthickness=1, highlightbackground="#e3e9f7", padx=14, pady=14)
        board.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        selected_files = []
        date_var = tk.StringVar(value=date.today().isoformat())
        uploaded_by_var = tk.StringVar(value=state.session_account_name or state.session_username)
        tags_var = tk.StringVar(value="")
        doc_types = self.db.get_document_types()
        doc_type_var = tk.StringVar(value=("기타" if "기타" in doc_types else doc_types[0]))
        self._bind_iso_date_formatter(date_var)

        controls = tk.Frame(board, bg="#ffffff")
        controls.pack(fill="x", pady=(0, 10))
        tk.Label(controls, text="날짜", font=self._font(9, "bold"), bg="#ffffff", fg="#4b556c").pack(side="left")
        tk.Entry(controls, textvariable=date_var, width=12).pack(side="left", padx=(6, 10))
        tk.Label(controls, text="문서 유형", font=self._font(9, "bold"), bg="#ffffff", fg="#4b556c").pack(side="left")
        ttk.Combobox(controls, textvariable=doc_type_var, values=doc_types, state="readonly", width=14).pack(side="left", padx=(6, 10))
        tk.Label(controls, text="태그", font=self._font(9, "bold"), bg="#ffffff", fg="#4b556c").pack(side="left")
        tk.Entry(controls, textvariable=tags_var, width=24).pack(side="left", padx=(6, 10))

        status_text = tk.StringVar(value="업로드 대기 파일 0개")
        tk.Label(controls, textvariable=status_text, font=self._font(9), bg="#ffffff", fg="#7a8398").pack(side="right")

        drop_wrap = tk.Frame(board, bg="#f8faff", highlightthickness=0, bd=0)
        drop_wrap.pack(fill="x", pady=(0, 12))
        drop_area = tk.Canvas(drop_wrap, height=170, bg="#f8faff", highlightthickness=0, bd=0, cursor="hand2")
        drop_area.pack(fill="x", padx=8, pady=8)

        select_btn = tk.Button(
            drop_wrap,
            text="파일 선택",
            bg="#edf0f6",
            fg="#3f495f",
            activebackground="#dde2ee",
            activeforeground="#3f495f",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=16,
            pady=5,
        )
        drop_area.create_window(0, 0, window=select_btn, anchor="center", tags="select_btn")

        pending_box = tk.Frame(board, bg="#ffffff", highlightthickness=1, highlightbackground="#e5ebf8", padx=8, pady=8)
        pending_box.pack(fill="x", pady=(0, 12))
        tk.Label(pending_box, text="업로드 대기 파일", bg="#ffffff", fg="#24345a", font=self._font(10, "bold"), anchor="w").pack(fill="x", pady=(0, 6))

        pending_tree = ttk.Treeview(pending_box, columns=("name", "preview"), show="headings", height=4)
        pending_tree.heading("name", text="원본 파일명")
        pending_tree.heading("preview", text="저장 파일명 미리보기")
        pending_tree.column("name", width=320, anchor="w")
        pending_tree.column("preview", width=460, anchor="w")
        pending_tree.pack(side="left", fill="x", expand=True)
        pending_scroll = ttk.Scrollbar(pending_box, orient="vertical", command=pending_tree.yview)
        pending_scroll.pack(side="right", fill="y")
        pending_tree.configure(yscrollcommand=pending_scroll.set)

        btn_row = tk.Frame(board, bg="#ffffff")
        btn_row.pack(fill="x", pady=(0, 12))
        tk.Button(
            btn_row,
            text="선택 항목 제거",
            width=14,
            bg="#eef2fa",
            fg="#334264",
            activebackground="#dde6f7",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=lambda: remove_selected_rows(),
        ).pack(side="left")
        tk.Button(
            btn_row,
            text="파일 저장",
            width=14,
            bg="#4a556f",
            fg="white",
            activebackground="#3f485f",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=lambda: save_files(),
        ).pack(side="left", padx=(8, 0))

        recent_wrap = tk.Frame(board, bg="#ffffff", highlightthickness=1, highlightbackground="#e5ebf8", padx=8, pady=8)
        recent_wrap.pack(fill="both", expand=True)
        tk.Label(recent_wrap, text="최근 업로드 파일", bg="#ffffff", fg="#24345a", font=self._font(10, "bold"), anchor="w").pack(fill="x", pady=(0, 6))

        recent_tree = ttk.Treeview(recent_wrap, columns=("file", "size", "updated", "menu"), show="headings", height=8)
        recent_tree.heading("file", text="파일명")
        recent_tree.heading("size", text="크기")
        recent_tree.heading("updated", text="수정일")
        recent_tree.heading("menu", text="")
        recent_tree.column("file", width=530, anchor="w")
        recent_tree.column("size", width=110, anchor="e")
        recent_tree.column("updated", width=170, anchor="w")
        recent_tree.column("menu", width=40, anchor="center")
        recent_tree.pack(side="left", fill="both", expand=True)
        recent_scroll = ttk.Scrollbar(recent_wrap, orient="vertical", command=recent_tree.yview)
        recent_scroll.pack(side="right", fill="y")
        recent_tree.configure(yscrollcommand=recent_scroll.set)

        style = ttk.Style()
        style.configure("Workspace.Treeview", rowheight=28)
        pending_tree.configure(style="Workspace.Treeview")
        recent_tree.configure(style="Workspace.Treeview")

        activity_frame = tk.Frame(board, bg="#ffffff")
        activity_frame.pack(fill="x", pady=(10, 0))
        tk.Label(activity_frame, text="작업 로그", bg="#ffffff", fg="#24345a", font=self._font(10, "bold"), anchor="w").pack(fill="x")
        activity_text = tk.Text(activity_frame, height=5, wrap="word", state="disabled", bg="#fbfcff")
        activity_text.pack(fill="x", pady=(4, 0))

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
            pending_tree.delete(*pending_tree.get_children())
            for idx, item in enumerate(selected_files):
                src = Path(item)
                pending_tree.insert("", "end", iid=f"f{idx}", values=(src.name, previews.get(item, src.name)))
            status_text.set(f"업로드 대기 파일 {len(selected_files)}개")

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
            selected = pending_tree.selection()
            if not selected:
                return
            names = {pending_tree.item(iid, "values")[0] for iid in selected}
            selected_files[:] = [item for item in selected_files if Path(item).name not in names]
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
            load_recent_files()
            refresh_file_table()

        def load_recent_files():
            recent_tree.delete(*recent_tree.get_children())
            if not state.active_workspace:
                return
            rows = self._get_recent_workspace_files(state.active_workspace, limit=8)
            for idx, row in enumerate(rows):
                archive_date, _document_type, _tags, archived_filename, _uploaded_by, file_size, _full_path = row
                icon_text, _icon_color = self._file_type_icon(archived_filename)
                size_text = self._format_size_for_display(int(file_size or 0))
                updated_text = archive_date.replace("-", "/") if isinstance(archive_date, str) else "-"
                recent_tree.insert("", "end", iid=f"recent-{idx}", values=(f"{icon_text}  {archived_filename}", size_text, updated_text, "\u22ee"))

        def redraw_drop_area(_event=None):
            drop_area.delete("all")
            width = max(360, drop_area.winfo_width())
            height = max(150, drop_area.winfo_height())
            self._smooth_rounded_rect(
                drop_area,
                6,
                6,
                width - 6,
                height - 6,
                20,
                fill="#f8faff",
                outline="#2d6cdf",
                width=2,
                dash=(4, 4),
                tags="drop_outline",
            )
            center_x = width // 2
            cloud_icon = self.ui_icon_photos.get("workspace_cloud_save")
            if cloud_icon is not None:
                drop_area.create_image(center_x, 75, image=cloud_icon, anchor="center", tags="drop_outline")
            else:
                drop_area.create_text(center_x, 75, text="\U0001F4E4", fill="#5c667f", font=("Segoe UI Emoji", 28))
            drop_area.create_text(center_x, 125, text="박스를 클릭하여 파일을 선택하세요", fill="#2f3749", font=self._font(12, "bold"))
            drop_area.coords("select_btn", center_x, 132)

        select_btn.configure(command=pick_files)
        drop_area.bind("<Button-1>", lambda _event: pick_files())
        drop_area.bind("<Configure>", redraw_drop_area)
        if TkinterDnD is not None and hasattr(drop_area, "drop_target_register"):
            drop_area.drop_target_register(DND_FILES)
            drop_area.dnd_bind("<<Drop>>", handle_drop)

        date_var.trace_add("write", refresh_file_table)
        doc_type_var.trace_add("write", refresh_file_table)
        tags_var.trace_add("write", refresh_file_table)
        redraw_drop_area()
        load_recent_files()
        refresh_file_table()

    def show_search_files_screen(self):
        shell = self._create_workspace_shell()
        self.root.title("애플망고 DMS - 파일 검색")

        self._build_sidebar_nav(
            shell["sidebar"],
            "search",
            [
                ("save", "\U0001F4E4", "파일 저장", "새 파일을 업로드하거나\n기존 파일을 저장합니다.", self.show_save_files_screen, "#2d6cdf"),
                ("search", "\U0001F50D", "파일 검색", "저장한 파일을 검색하고\n열람합니다.", self.show_search_files_screen, "#111111"),
                ("exit", "\u21a9", "워크스페이스 나가기", "현재 워크스페이스를 나가고\n목록으로 돌아갑니다.", self.show_workspace_exit_screen, "#d33e3e"),
            ],
            icon_photos={
                "save": self.ui_icon_photos.get("workspace_file_save"),
                "search": self.ui_icon_photos.get("workspace_file_search"),
                "exit": self.ui_icon_photos.get("workspace_exit"),
            },
        )

        outer = shell["content"]
        self._build_workspace_page_header(outer, "파일 검색", "지정한 파일을 검색하고 바로 열람하세요.")

        scroll_canvas = tk.Canvas(outer, bg="#ffffff", highlightthickness=0)
        scroll_canvas.pack(fill="both", expand=True)

        inner = tk.Frame(scroll_canvas, bg="#ffffff", padx=20, pady=0)
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
        self._bind_iso_date_formatter(date_entry_var)

        def _parse_date_input():
            parts = date_entry_var.get().strip().split("-")
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
        filters = tk.Frame(inner, bg="#fbfbff", highlightthickness=1, highlightbackground="#e6eaf4", padx=10, pady=8)
        filters.pack(fill="x", pady=(0, 10))

        tk.Label(filters, text="워크스페이스", bg="#fbfbff", width=16, anchor="w").grid(row=0, column=0, sticky="w", pady=3)
        tk.Entry(filters, textvariable=workspace_var, width=36, state="readonly").grid(row=0, column=1, columnspan=3, sticky="w", pady=3)

        tk.Label(filters, text="날짜 (YYYY-MM-DD)", bg="#fbfbff", width=16, anchor="w").grid(row=1, column=0, sticky="w", pady=3)
        tk.Entry(filters, textvariable=date_entry_var, width=16).grid(row=1, column=1, sticky="w", pady=3)
        tk.Label(filters, text="예: 2024-06-15 또는 2024-06 또는 2024",
             bg="#fbfbff", fg="#888888", font=self._font(8)).grid(row=1, column=2, columnspan=2, sticky="w", padx=(6, 0))

        tk.Label(filters, text="문서 유형", bg="#fbfbff", width=16, anchor="w").grid(row=2, column=0, sticky="w", pady=3)
        ttk.Combobox(filters, textvariable=doc_type_var,
                 values=["전체"] + self.db.get_document_types(),
                     state="readonly", width=24).grid(row=2, column=1, sticky="w", pady=3)

        tk.Label(filters, text="태그", bg="#fbfbff", width=16, anchor="w").grid(row=3, column=0, sticky="w", pady=3)
        tk.Entry(filters, textvariable=tags_var, width=42).grid(row=3, column=1, columnspan=3, sticky="w", pady=3)

        tk.Label(filters, text="자유 검색어", bg="#fbfbff", width=16, anchor="w").grid(row=4, column=0, sticky="w", pady=3)
        tk.Entry(filters, textvariable=free_var, width=42).grid(row=4, column=1, columnspan=3, sticky="w", pady=3)

        filter_btn_row = tk.Frame(filters, bg="#fbfbff")
        filter_btn_row.grid(row=5, column=0, columnspan=5, sticky="w", pady=(8, 2))

        # 검색 버튼은 항상 활성
        search_btn = tk.Button(filter_btn_row, text="검색", width=12,
                               bg="#4a556f", fg="white", activebackground="#3f485f",
                               relief="flat", bd=0, highlightthickness=0, cursor="hand2")
        search_btn.pack(side="left")

        # 초기화: 필터만 비움
        clear_btn = tk.Button(filter_btn_row, text="초기화", width=12,
                              bg="#d9d9d9", activebackground="#c0c0c0",
                              relief="flat", bd=0, highlightthickness=0, cursor="hand2")
        clear_btn.pack(side="left", padx=(8, 0))

        # ---- Results box (x + y scrollbars, multi-select) ----
        results_frame = tk.Frame(inner, bg="#fbfbff", highlightthickness=1, highlightbackground="#e6eaf4", padx=4, pady=6)
        results_frame.pack(fill="x", pady=(0, 10))

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
        action_row = tk.Frame(inner, bg="#fbfbff")
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
                open_file_btn.config(bg="#4a556f", fg="white", activebackground="#3f485f")
                delete_file_btn.config(bg="#4a556f", fg="white", activebackground="#3f485f")
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

    def show_workspace_exit_screen(self):
        shell = self._create_workspace_shell()
        self.root.title("애플망고 DMS - 워크스페이스 나가기")

        self._build_sidebar_nav(
            shell["sidebar"],
            "exit",
            [
                ("save", "\U0001F4E4", "파일 저장", "새 파일을 업로드하거나\n기존 파일을 저장합니다.", self.show_save_files_screen, "#2d6cdf"),
                ("search", "\U0001F50D", "파일 검색", "저장한 파일을 검색하고\n열람합니다.", self.show_search_files_screen, "#111111"),
                ("exit", "\u21a9", "워크스페이스 나가기", "현재 워크스페이스를 나가고\n목록으로 돌아갑니다.", self.show_workspace_exit_screen, "#d33e3e"),
            ],
            icon_photos={
                "save": self.ui_icon_photos.get("workspace_file_save"),
                "search": self.ui_icon_photos.get("workspace_file_search"),
                "exit": self.ui_icon_photos.get("workspace_exit"),
            },
        )

        outer = shell["content"]
        self._build_workspace_page_header(outer, "워크스페이스 나가기", "현재 작업을 마치고 워크스페이스 목록으로 돌아갑니다.")

        action_row = tk.Frame(outer, bg="#ffffff")
        action_row.pack(fill="x", padx=20, pady=(4, 0))
        tk.Button(
            action_row,
            text="나가기",
            width=14,
            bg="#d33e3e",
            fg="white",
            activebackground="#bf3232",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self.show_workspace_selection_screen,
        ).pack(side="left")

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
        settings_btn("매핑된 드라이브 관리", lambda: show_mapped_drives_window(settings_win))
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