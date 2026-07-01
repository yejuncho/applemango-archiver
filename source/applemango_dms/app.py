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

from applemango_dms.ui.startup import (
    show_startup_screen as ui_show_startup_screen,
    route_from_startup as ui_route_from_startup,
)

from applemango_dms.ui.login import (
    show_login_screen as ui_show_login_screen,
    show_username_login_screen as ui_show_username_login_screen,
    show_password_login_screen as ui_show_password_login_screen,
)

from applemango_dms.ui.workspace_select import (
    show_workspace_selection_screen as ui_show_workspace_selection_screen,
)

from applemango_dms.ui.workplace_menu import (
    show_main_workspace_menu as ui_show_main_workspace_menu,
    show_workspace_exit_screen as ui_show_workspace_exit_screen,
)

from applemango_dms.ui.save_files import (
    show_save_files_screen as ui_show_save_files_screen,
)

from applemango_dms.ui.search_files import (
    show_search_files_screen as ui_show_search_files_screen,
)

from applemango_dms.ui.settings import (
    show_settings_screen as ui_show_settings_screen,
    show_change_server_name_dialog as ui_show_change_server_name_dialog,
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
        if state.is_demo_mode:
            root_path = self._get_demo_workspace_base_path() / workspace_name
        else:
            root_path = Path(fr"{config.default_server_name}\{workspace_name}")
        total_size = 0
        file_count = 0
        last_mtime = None

        stack = [str(root_path)]
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

    @staticmethod
    def _get_demo_workspace_base_path():
        return Path(os.path.expanduser("~/Documents/Applemango_Demo_Workspace"))

    def _ensure_demo_workspace_root(self):
        root = self._get_demo_workspace_base_path()
        root.mkdir(parents=True, exist_ok=True)

        has_subfolders = any(child.is_dir() for child in root.iterdir())
        if not has_subfolders:
            for default_name in ("General", "Test", "Sandbox"):
                (root / default_name).mkdir(parents=True, exist_ok=True)

        return root

    def _load_demo_workspace_names(self):
        root = self._ensure_demo_workspace_root()
        return sorted([child.name for child in root.iterdir() if child.is_dir()])

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
        state.is_demo_mode = False
        clear_session_login()
        clear_saved_credentials()
        self.show_login_screen()

    def show_startup_screen(self):
        return ui_show_startup_screen(self)

    def route_from_startup(self):
        return ui_route_from_startup(self)

    def show_login_screen(self, prefill_username=None):
        return ui_show_login_screen(self, prefill_username=prefill_username)

    def show_username_login_screen(self):
        return ui_show_username_login_screen(self)

    def show_password_login_screen(self, username):
        return ui_show_password_login_screen(self, username)

    def show_workspace_selection_screen(self):
        return ui_show_workspace_selection_screen(self)

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
        if state.is_demo_mode:
            tk.Label(
                info_row,
                text="[ LOCAL DEMO MODE ]",
                font=self._font(8, "bold"),
                fg="#5c667f",
                bg="#ffffff",
            ).pack(side="left", padx=(10, 0))
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
        return ui_show_main_workspace_menu(self)

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

    def get_workspace_root_path(self):
        if state.is_demo_mode:
            return Path(
                os.path.expanduser(
                    "~/Documents/Applemango_Demo_Workspace"
                )
            ) / state.active_workspace
        return self.build_destination_drive_path()

    def show_save_files_screen(self):
        return ui_show_save_files_screen(self)

    def show_search_files_screen(self):
        return ui_show_search_files_screen(self)

    def show_workspace_exit_screen(self):
        return ui_show_workspace_exit_screen(self)

    def show_change_server_name_dialog(self, parent_win):
        return ui_show_change_server_name_dialog(self, parent_win)

    def show_settings_screen(self):
        return ui_show_settings_screen(self)

    def run(self):
        self.show_startup_screen()
        self.root.mainloop()