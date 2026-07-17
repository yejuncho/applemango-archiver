import os
import re
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

from applemango_dms.db.sqlite import ArchiveDatabase

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

from applemango_dms.ui.header_controls import (
    build_header_controls,
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
        self._force_fullscreen = False
        self._window_controls_refreshers = []
        apply_window_icon(self.root)
        self.ui_font_family = self._initialize_ui_font_family()
        self.root.geometry("640x500")
        self.root.configure(bg="white")
        self.root.resizable(True, True)
        self._apply_fullscreen_mode()
        self.root.protocol("WM_DELETE_WINDOW", self.exit_application)

        self.db = None
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
        if self._force_fullscreen:
            self._apply_fullscreen_mode()
            return
        try:
            if self.root.state() == "zoomed":
                return
        except Exception:
            pass
        self.root.geometry(f"{w}x{h}")

    def register_window_controls_refresher(self, callback):
        if callable(callback):
            self._window_controls_refreshers.append(callback)

    def _notify_window_controls_changed(self):
        kept = []
        for callback in self._window_controls_refreshers:
            try:
                callback()
                kept.append(callback)
            except Exception:
                continue
        self._window_controls_refreshers = kept

    def is_fullscreen(self):
        return bool(self._force_fullscreen)

    def _set_fullscreen(self, enabled):
        self._force_fullscreen = bool(enabled)
        try:
            self.root.attributes("-fullscreen", self._force_fullscreen)
        except Exception:
            try:
                self.root.state("zoomed" if self._force_fullscreen else "normal")
            except Exception:
                pass

        if not self._force_fullscreen:
            try:
                self.root.state("zoomed")
            except Exception:
                pass

        self._notify_window_controls_changed()

    def toggle_fullscreen(self):
        self._set_fullscreen(not self._force_fullscreen)

    def _is_file_operation_active(self):
        for flag_name in (
            "is_file_operation_active",
            "file_operation_active",
            "is_uploading",
            "upload_in_progress",
            "save_in_progress",
        ):
            if bool(getattr(self, flag_name, False)):
                return True
        return False

    def exit_application(self):
        if self._is_file_operation_active():
            should_exit = messagebox.askyesno(
                "종료 확인",
                "파일 작업이 아직 진행 중입니다. 지금 종료하면 업로드 또는 저장 작업이 중단될 수 있습니다. 종료하시겠습니까?",
                parent=self.root,
            )
            if not should_exit:
                return

        try:
            self.clear_workspace(unmap_if_needed=True)
        except Exception:
            pass

        try:
            clear_session_login()
        except Exception:
            pass

        try:
            close_method = getattr(self.db, "close", None)
            if callable(close_method):
                close_method()
        except Exception:
            pass

        self.root.destroy()

    def _apply_fullscreen_mode(self):
        self._set_fullscreen(False)

    def clear_screen(self):
        for child in self.root.winfo_children():
            child.destroy()

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
            config.PROJECT_ROOT / "assets" / "logos" / "applemango_logo.png",
            config.PROJECT_ROOT / "assets" / "logos" / "hiscom_logo.png",
            config.PROJECT_ROOT / "assets" / "logos" / "applemango_mission.png",
            config.PROJECT_ROOT / "assets" / "logos" / "phileo.png",
            config.PROJECT_ROOT / "assets" / "logos" / "hansomang.png",
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

        path = config.PROJECT_ROOT / "assets" / "logos" / "hiscom.png"
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

        image_root = config.PROJECT_ROOT / "assets" / "logos"
        png_paths = sorted(image_root.glob("*.png"))
        if not png_paths:
            return None

        # Randomly pick from up to five PNG logo files in assets/logos.
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
            "checked": "checked.svg",
            "unchecked": "unchecked.svg",
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
            "header_settings": (config.PROJECT_ROOT / "assets" / "icons" / "workspace_selection" / "settings.svg", 22, 22, "#111111"),
            "header_logout": (config.PROJECT_ROOT / "assets" / "icons" / "workspace_selection" / "logout.svg", 22, 22, "#111111"),
            "header_home": (config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "home.svg", 22, 22, "#111111"),
            "workspace_selection_folder": (config.PROJECT_ROOT / "assets" / "icons" / "workspace_selection" / "folder.svg", 24, 24, "#6ea7ff"),
            "workspace_clock": (config.PROJECT_ROOT / "assets" / "icons" / "workspace_selection" / "clock.svg", 16, 16, "#111111"),
            "workspace_database": (config.PROJECT_ROOT / "assets" / "icons" / "workspace_selection" / "database.svg", 16, 16, "#111111"),
            "workspace_file_stack": (config.PROJECT_ROOT / "assets" / "icons" / "workspace_selection" / "file_stack.svg", 16, 16, "#111111"),
            "window_minimize": (config.PROJECT_ROOT / "assets" / "icons" / "header_controls" / "minimize.svg", 22, 22, "#111111"),
            "window_fullscreen_enter": (config.PROJECT_ROOT / "assets" / "icons" / "header_controls" / "fullscreen.svg", 22, 22, "#111111"),
            "window_fullscreen_exit": (config.PROJECT_ROOT / "assets" / "icons" / "header_controls" / "exit_fullscreen.svg", 22, 22, "#111111"),
            "window_close": (config.PROJECT_ROOT / "assets" / "icons" / "header_controls" / "exit_program.svg", 22, 22, None),
            "window_close_hover": (config.PROJECT_ROOT / "assets" / "icons" / "header_controls" / "exit_program_red.svg", 22, 22, None),
            "workspace_folder": (config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "folder.svg", 30, 30, "#2fa44f"),
            "workspace_file_save": (config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "file_save_blue.svg", 18, 18, None),
            "workspace_file_search": (config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "file_search_green.svg", 18, 18, None),
            "workspace_exit": (config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "exit_red.svg", 18, 18, None),
            "workspace_storage": (config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "storage.svg", 18, 18, None),
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
        if self._force_fullscreen:
            self._apply_fullscreen_mode()
            return
        try:
            if self.root.state() == "zoomed":
                return
        except Exception:
            pass
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = max(0, (sw - width) // 2)
        y = max(0, (sh - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

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

    def create_card(self, parent, width=360, height=470, fill_top="#ffffff", fill_bottom="#ffffff", radius=22):
        content = tk.Frame(parent, bg="#ffffff")
        content_id = parent.create_window(0, 0, window=content, anchor="center")

        def redraw(cx, cy):
            parent.delete("cardshadow")
            parent.delete("cardfill")
            parent.delete("cardborder")

            x1, y1 = cx - width // 2, cy - height // 2
            x2, y2 = cx + width // 2, cy + height // 2
            r = radius

            self._smooth_rounded_rect(parent, x1 + 7, y1 + 9, x2 + 7, y2 + 9, r, fill="#d8d5f0", outline="", tags="cardshadow")
            self._smooth_rounded_rect(parent, x1 + 4, y1 + 5, x2 + 4, y2 + 5, r, fill="#e5e3f5", outline="", tags="cardshadow")
            self._smooth_rounded_rect(parent, x1 + 2, y1 + 2, x2 + 2, y2 + 2, r, fill="#eeedf8", outline="", tags="cardshadow")

            self._smooth_rounded_rect(parent, x1, y1, x2, y2, r, fill=fill_bottom, outline="", tags="cardfill")
            self._smooth_rounded_rect(parent, x1, y1, x2, y2, r, fill=fill_top, outline="", tags="cardfill")
            self._smooth_rounded_rect(parent, x1 + 1, y1 + 1, x2 - 1, y2 - 7, r, fill=fill_top, outline="", tags="cardfill")
            self._smooth_rounded_rect(parent, x1, y1, x2, y2, r, fill="", outline="#e4e6f0", width=1, tags="cardborder")

            parent.itemconfigure(content_id, width=width - 56, height=height - 56)
            parent.coords(content_id, cx, cy)
            parent.tag_raise(content_id)

        return {
            "card": None,
            "content": content,
            "size": (width, height),
            "redraw": redraw,
        }

    def get_connection_snapshot(self):
        is_connected, ip_addr = check_server_availability(config.default_server_name)
        status = "연결됨" if is_connected else "연결 불가"
        return is_connected, ip_addr, status

    @staticmethod
    def _get_demo_workspace_base_path():
        return config.DEMO_WORKSPACES_DIR

    def _ensure_demo_workspace_root(self):
        root = self._get_demo_workspace_base_path()
        if not root.exists() or not root.is_dir():
            raise FileNotFoundError("No local demo directory found")

        return root

    def _load_demo_workspace_names(self):
        root = self._ensure_demo_workspace_root()
        return sorted([child.name for child in root.iterdir() if child.is_dir()])

    def set_workspace(self, workspace, drive_letter, mapped_by_app):
        state.active_workspace = workspace
        state.active_workspace_drive = drive_letter
        self.workspace_drive_mapped_by_app = mapped_by_app
        state.active_workspace_id = self._ensure_workspace_context(workspace)

    def clear_workspace(self, unmap_if_needed=False):

        if unmap_if_needed and self.workspace_drive_mapped_by_app and state.active_workspace_drive:
            self.workspace_manager.unmap_drive(state.active_workspace_drive)

        state.active_workspace = ""
        state.active_workspace_id = None
        state.active_workspace_drive = ""
        self.workspace_drive_mapped_by_app = False

    def logout_and_return_to_login(self):
        # Ensure mapped workspace drive is released before logging out.
        self.clear_workspace(unmap_if_needed=True)
        state.is_demo_mode = False
        clear_session_login()
        clear_saved_credentials()
        self.show_login_screen()

    def leave_workspace_to_selection(self):
        self.clear_workspace(unmap_if_needed=True)
        self.show_workspace_selection_screen()

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

    def _resolve_archive_db_path(self):
        if state.is_demo_mode:
            return Path(config.DEMO_DB_PATH)
        return Path(config.archive_db_path)

    def _resolve_workspace_share_path(self, workspace_name):
        normalized_name = str(workspace_name or "").strip()
        if not normalized_name:
            raise ValueError("Workspace name is required.")

        if state.is_demo_mode:
            return self._ensure_demo_workspace_root() / normalized_name

        return Path(fr"{config.default_server_name}\{normalized_name}")

    def _ensure_workspace_context(self, workspace_name):
        if self.db is None:
            raise RuntimeError("Database is not initialized.")

        share_path = self._resolve_workspace_share_path(workspace_name)
        return self.db.ensure_workspace(
            workspace_name,
            share_path,
            config.DEFAULT_DOCUMENT_TYPES,
        )

    def _initialize_demo_data(self):
        root = self._ensure_demo_workspace_root()
        workspace_names = sorted([child.name for child in root.iterdir() if child.is_dir()])
        for workspace_name in workspace_names:
            self.db.ensure_workspace(
                workspace_name,
                root / workspace_name,
                config.DEFAULT_DOCUMENT_TYPES,
            )

        return True

    def ensure_database_ready(self):
        target_path = self._resolve_archive_db_path()
        current_path = Path(self.db.db_path) if self.db is not None else None

        if state.is_demo_mode:
            try:
                self._ensure_demo_workspace_root()
            except Exception as exc:
                messagebox.showerror("데이터베이스 오류", str(exc), parent=self.root)
                return False

        if current_path == target_path:
            if state.is_demo_mode:
                try:
                    return self._initialize_demo_data()
                except Exception as exc:
                    messagebox.showerror(
                        "데이터베이스 오류",
                        f"데모 데이터 초기화에 실패했습니다.\n오류: {exc}",
                        parent=self.root,
                    )
                    return False
            return True

        try:
            self.db = ArchiveDatabase(target_path)
            if state.is_demo_mode:
                self._initialize_demo_data()
            return True
        except Exception as exc:
            messagebox.showerror(
                "데이터베이스 오류",
                f"데이터베이스 파일을 준비하지 못했습니다.\n경로: {target_path}\n오류: {exc}",
                parent=self.root,
            )
            return False

    def show_workspace_selection_screen(self):
        if not self.ensure_database_ready():
            return
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
        self._resize(1372, 900)
        self.root.title("애플망고 DMS - 워크스페이스")
        self.clear_screen()
        self.root.configure(bg="#ffffff")

        bg = tk.Canvas(self.root, bg="#ffffff", highlightthickness=0, bd=0)
        bg.pack(fill="both", expand=True)

        main_card = self.create_card(
            bg,
            width=1272,
            height=798,
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
        controls = build_header_controls(self, right, context="workspace", bg="#ffffff")
        controls.pack(anchor="e")

        body = tk.Frame(shell, bg="#ffffff")
        body.pack(fill="both", expand=True)

        sidebar_shell = tk.Canvas(body, bg="#ffffff", width=225, highlightthickness=0, bd=0)
        sidebar_shell.pack(side="left", fill="y", padx=(12, 0), pady=(10, 12))

        sidebar = tk.Frame(sidebar_shell, bg="#ffffff")
        sidebar_window_id = sidebar_shell.create_window(0, 0, window=sidebar, anchor="nw")

        def redraw_sidebar(_event=None):
            sidebar_shell.delete("sidepanel")
            width = max(170, sidebar_shell.winfo_width())
            height = max(220, sidebar_shell.winfo_height())
            self._smooth_rounded_rect(
                sidebar_shell,
                1,
                1,
                width - 1,
                height - 1,
                24,
                fill="#ffffff",
                outline="#dfe5ee",
                width=1,
                tags="sidepanel",
            )
            sidebar_shell.coords(sidebar_window_id, 6, 6)
            sidebar_shell.itemconfigure(sidebar_window_id, width=max(10, width - 12), height=max(10, height - 12))
            sidebar_shell.tag_lower("sidepanel")

        sidebar_shell.bind("<Configure>", redraw_sidebar)

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
            return self._get_demo_workspace_base_path() / state.active_workspace
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