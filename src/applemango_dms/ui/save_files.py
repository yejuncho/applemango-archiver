import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk
from pathlib import Path
from datetime import datetime
import re
import time
import math
import shutil
import threading
from tkinter import filedialog
import applemango_dms.config as config
import applemango_dms.state as state
from applemango_dms.services.nas import get_mapped_network_drives, normalize_drive_letter
from applemango_dms.ui.workplace_menu import build_sidebar_nav
from applemango_dms.utils.images import load_logo_photo, load_svg_photo

try:
    import importlib

    _tkinterdnd2 = importlib.import_module("tkinterdnd2")
    DND_FILES = _tkinterdnd2.DND_FILES
    TkinterDnD = _tkinterdnd2.TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None

def show_save_files_screen(app):
    shell = app._create_workspace_shell()
    app.root.title("애플망고 DMS - 파일 저장")

    build_sidebar_nav(
        app,
        shell["sidebar"],
        "save",
        [
            ("save", "\U0001F4E4", "파일 저장", "새 파일을 업로드하거나\n기존 파일을 저장합니다.", app.show_save_files_screen, "#2d6cdf"),
            ("search", "\U0001F50D", "파일 검색", "저장한 파일을 검색하고\n열람합니다.", app.show_search_files_screen, "#111111"),
            ("exit", "\u21a9", "워크스페이스 나가기", "현재 워크스페이스를 나가고\n목록으로 돌아갑니다.", app.show_workspace_exit_screen, "#d33e3e"),
        ],
        icon_photos={
            "save": app.ui_icon_photos.get("workspace_file_save"),
            "search": app.ui_icon_photos.get("workspace_file_search"),
            "exit": app.ui_icon_photos.get("workspace_exit"),
        },
    )

    outer = shell["content"]
    app._build_workspace_page_header(outer, "파일 저장", "파일을 드래그 앤 드롭하거나, 아래 버튼을 클릭하여 파일을 선택하세요.")

    board = tk.Frame(outer, bg="#ffffff", highlightthickness=0, bd=0)
    board.pack(fill="both", expand=True, padx=0, pady=0)

    selected_files = []
    selected_row_keys = set()
    row_metadata_state = {}
    pending_count_var = tk.StringVar(value="업로드 대기 파일 (0)")
    refresh_row3_rows = lambda: None
    try:
        document_type_options = app.db.get_document_types()
    except Exception:
        document_type_options = list(config.DEFAULT_DOCUMENT_TYPES)
    if not document_type_options:
        document_type_options = list(config.DEFAULT_DOCUMENT_TYPES)

    split = tk.Frame(board, bg="#ffffff")
    split.pack(fill="both", expand=True, padx=10, pady=0)
    split.grid_anchor("nw")
    split.grid_columnconfigure(0, weight=0)
    split.grid_columnconfigure(1, weight=0)
    split.grid_columnconfigure(2, weight=1)
    split.grid_rowconfigure(0, weight=1)

    left_col = tk.Frame(split, bg="#ffffff")
    left_col.grid(row=0, column=0, sticky="nsew")
    right_col = tk.Frame(split, bg="#ffffff")
    right_col.grid(row=0, column=1, sticky="nsw", padx=(10, 0))

    drop_area = tk.Canvas(left_col, height=102, bg="#ffffff", highlightthickness=0, bd=0)
    drop_area.pack(fill="x")
    left_detail_card = tk.Canvas(left_col, height=500, bg="#ffffff", highlightthickness=0, bd=0)
    left_detail_card.pack(fill="x", pady=10)
    tk.Frame(left_col, bg="#ffffff").pack(fill="both", expand=True)

    right_card = tk.Canvas(right_col, bg="#ffffff", highlightthickness=0, bd=0)
    right_card.pack(fill="both", expand=True)

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
        pending_count_var.set(f"업로드 대기 파일 ({len(selected_files)})")
        refresh_row3_rows()

    def add_folder_paths(folder_paths):
        discovered = []
        for raw in folder_paths:
            folder_candidate = str(raw).strip().strip("{}")
            folder = Path(folder_candidate)
            if folder_candidate and folder.is_dir():
                discovered.extend(str(p) for p in folder.rglob("*") if p.is_file())
        add_file_paths(discovered)

    def pick_files():
        files = filedialog.askopenfilenames(parent=app.root, title="파일 추가")
        if files:
            add_file_paths(files)

    def pick_folder():
        folder = filedialog.askdirectory(parent=app.root, title="폴더 추가")
        if folder:
            add_folder_paths([folder])

    def is_upload_destination_safe(destination):
        if state.is_demo_mode:
            return True

        workspace_name = (state.active_workspace or "").strip().lower()
        drive_letter = normalize_drive_letter(state.active_workspace_drive)
        if not workspace_name or not drive_letter:
            return False

        mapped = get_mapped_network_drives()
        if not mapped:
            return False

        remote_unc = ""
        for mapped_drive, remote in mapped:
            if normalize_drive_letter(mapped_drive) == drive_letter:
                remote_unc = str(remote or "").rstrip("\\")
                break

        if not remote_unc:
            return False

        # UNC: \\server\share
        parts = [part for part in remote_unc.split("\\") if part]
        if len(parts) < 2:
            return False

        remote_server = parts[0].lower()
        remote_share = parts[1].lower()
        expected_server = (config.default_server_name or "").strip("\\").lower()

        if expected_server and remote_server != expected_server:
            return False
        if remote_share != workspace_name:
            return False

        destination_drive = normalize_drive_letter(getattr(destination, "drive", ""))
        if destination_drive and destination_drive != drive_letter:
            return False

        return True

    def remove_selected_placeholder():
        if not selected_row_keys:
            return
        selected_files[:] = [path for path in selected_files if path not in selected_row_keys]
        for removed_key in list(selected_row_keys):
            row_metadata_state.pop(removed_key, None)
        selected_row_keys.clear()
        pending_count_var.set(f"업로드 대기 파일 ({len(selected_files)})")
        refresh_row3_rows()

    def clear_all_files():
        selected_files.clear()
        selected_row_keys.clear()
        row_metadata_state.clear()
        pending_count_var.set("업로드 대기 파일 (0)")
        refresh_row3_rows()

    def remove_row_item(row_key):
        selected_files[:] = [path for path in selected_files if path != row_key]
        selected_row_keys.discard(row_key)
        row_metadata_state.pop(row_key, None)
        pending_count_var.set(f"업로드 대기 파일 ({len(selected_files)})")
        refresh_row3_rows()

    def set_row_upload_state(row_key, *, status_code=None, progress_ratio=None):
        row_state = row_metadata_state.setdefault(row_key, {})
        if status_code is not None:
            row_state["status_code"] = status_code
        if progress_ratio is not None:
            row_state["progress_ratio"] = max(0.0, min(1.0, float(progress_ratio)))

    def get_upload_targets():
        if selected_row_keys:
            return [path for path in selected_files if path in selected_row_keys]
        return list(selected_files)

    def start_upload_placeholder():
        targets = get_upload_targets()
        if not targets:
            return None

        destination = app.get_workspace_root_path()
        if destination is None:
            for row_key in targets:
                set_row_upload_state(row_key, status_code="failed", progress_ratio=0.0)
            refresh_row3_rows()
            return None

        if not is_upload_destination_safe(destination):
            for row_key in targets:
                set_row_upload_state(row_key, status_code="failed", progress_ratio=0.0)
            refresh_row3_rows()
            return None

        try:
            destination.mkdir(parents=True, exist_ok=True)
        except Exception:
            for row_key in targets:
                set_row_upload_state(row_key, status_code="failed", progress_ratio=0.0)
            refresh_row3_rows()
            return None

        for row_key in targets:
            set_row_upload_state(row_key, status_code="uploading", progress_ratio=0.0)
        refresh_row3_rows()

        def upload_worker(target_rows):
            reserved_names = set()
            for row_key in target_rows:
                source = Path(row_key)
                row_state = row_metadata_state.setdefault(row_key, {})
                archive_date = row_state.get("date_iso") or datetime.now().strftime("%Y-%m-%d")
                doc_type = row_state.get("document_type") or "기타"
                tags = row_state.get("tags", "")

                try:
                    if not source.exists() or not source.is_file():
                        raise FileNotFoundError(f"source missing: {source}")

                    candidate_name = source.name
                    archived_name = app.filename_builder.ensure_unique_name(destination, candidate_name, reserved_names=reserved_names)
                    destination_path = destination / archived_name

                    total_size = max(1, source.stat().st_size)
                    copied_size = 0

                    with source.open("rb") as src_f, destination_path.open("wb") as dst_f:
                        while True:
                            chunk = src_f.read(1024 * 1024)
                            if not chunk:
                                break
                            dst_f.write(chunk)
                            copied_size += len(chunk)
                            ratio = copied_size / float(total_size)
                            app.root.after(0, lambda key=row_key, r=ratio: (set_row_upload_state(key, status_code="uploading", progress_ratio=r), refresh_row3_rows()))

                    shutil.copystat(source, destination_path)

                    app.db.insert_file_record({
                        "workspace": state.active_workspace or "",
                        "original_filename": source.name,
                        "archived_filename": archived_name,
                        "full_path": str(destination_path),
                        "document_type": doc_type,
                        "tags": tags,
                        "uploaded_by": state.session_account_name or state.session_username or "",
                        "archive_date": archive_date,
                        "archived_at": datetime.now().isoformat(timespec="seconds"),
                        "file_ext": source.suffix,
                        "file_size": destination_path.stat().st_size if destination_path.exists() else 0,
                        "source_path": str(source),
                    })

                    app.root.after(0, lambda key=row_key: (set_row_upload_state(key, status_code="success", progress_ratio=1.0), refresh_row3_rows()))
                except Exception:
                    app.root.after(0, lambda key=row_key: (set_row_upload_state(key, status_code="failed", progress_ratio=0.0), refresh_row3_rows()))

        threading.Thread(target=upload_worker, args=(targets,), daemon=True).start()
        return None

    def create_rounded_action(parent, text, command, *, width, height, fill, outline, text_color, icon_photo=None, icon_fallback_text=None):
        button_canvas = tk.Canvas(parent, width=width, height=height, bg=parent.cget("bg"), highlightthickness=0, bd=0, cursor="hand2")
        if icon_photo is not None:
            # Keep a strong reference on the widget to prevent Tk image GC.
            button_canvas.icon_photo_ref = icon_photo

        def draw(mode="normal"):
            button_canvas.delete("all")
            fill_color = fill
            outline_color = outline
            if mode == "hover" and fill == "#ffffff":
                fill_color = "#f6f8fc"
            elif mode == "hover" and fill != "#ffffff":
                fill_color = "#245bc0"

            app._smooth_rounded_rect(
                button_canvas,
                1,
                1,
                width - 1,
                height - 1,
                14,
                fill=fill_color,
                outline=outline_color,
                width=1,
            )

            text_x = width // 2
            if icon_photo is not None:
                icon_x = max(12, width // 2 - 30)
                button_canvas.create_image(icon_x, height // 2, image=icon_photo, anchor="center")
                text_x = icon_x + 12
                button_canvas.create_text(text_x, height // 2, text=text, fill=text_color, font=app._font(10, "bold"), anchor="w")
            elif icon_fallback_text:
                icon_x = max(12, width // 2 - 30)
                button_canvas.create_text(icon_x, height // 2, text=icon_fallback_text, fill=text_color, font=("Segoe UI Emoji", 11), anchor="center")
                text_x = icon_x + 12
                button_canvas.create_text(text_x, height // 2, text=text, fill=text_color, font=app._font(10, "bold"), anchor="w")
            else:
                button_canvas.create_text(text_x, height // 2, text=text, fill=text_color, font=app._font(10, "bold"), anchor="center")

        button_canvas.bind("<Button-1>", lambda _event: command())
        button_canvas.bind("<Enter>", lambda _event: draw("hover"))
        button_canvas.bind("<Leave>", lambda _event: draw("normal"))
        draw("normal")
        return button_canvas

    def handle_drop(event):
        dropped = app.root.tk.splitlist(event.data)
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

    app.root.update_idletasks()

    drop_area.delete("all")
    drop_width = max(700, drop_area.winfo_width())
    drop_height = max(100, drop_area.winfo_height())

    target_left_width = drop_width
    gap = 0
    total_width = max(target_left_width + 160 + gap, split.winfo_width())
    left_width = target_left_width
    right_width = max(160, total_width - left_width - gap)
    split.grid_columnconfigure(0, minsize=left_width, weight=0)
    split.grid_columnconfigure(1, minsize=right_width, weight=0)
    split.grid_columnconfigure(2, minsize=0, weight=1)

    app._smooth_rounded_rect(
        drop_area,
        1,
        1,
        drop_width - 1,
        drop_height - 1,
        20,
        fill="#f8faff",
        outline="#b9c8e9",
        width=2.5,
        dash=(4, 4),
    )
    center_x = drop_width // 2
    center_y = drop_height // 2
    cloud_icon = app.ui_icon_photos.get("workspace_cloud_save")
    if cloud_icon is not None:
        drop_area.create_image(center_x, center_y, image=cloud_icon, anchor="center", tags="drop_icon")
        drop_area.scale("drop_icon", center_x, center_y, 0.3, 0.3)
    else:
        drop_area.create_text(center_x, center_y, text="\U0001F4E4", fill="#5c667f", font=("Segoe UI Emoji", 24))

    plus_icon = load_svg_photo(
        config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "save_files" / "plus.svg",
        max_width=12,
        max_height=12,
        tint="#ffffff",
    )

    drop_button_row = tk.Frame(drop_area, bg="#f8faff")
    add_file_btn = create_rounded_action(
        drop_button_row,
        "파일 추가",
        pick_files,
        width=108,
        height=28,
        fill="#5555d5",
        outline="#5555d5",
        text_color="#ffffff",
        icon_photo=plus_icon,
        icon_fallback_text="+",
    )
    add_file_btn.pack(side="left")

    add_folder_btn = create_rounded_action(
        drop_button_row,
        "폴더 추가",
        pick_folder,
        width=108,
        height=28,
        fill="#5555d5",
        outline="#5555d5",
        text_color="#ffffff",
        icon_photo=plus_icon,
        icon_fallback_text="+",
    )
    add_folder_btn.pack(side="left", padx=(8, 0))

    drop_area.plus_icon_ref = plus_icon
    drop_area.create_window(center_x, drop_height - 26, window=drop_button_row, anchor="center")

    left_detail_card.delete("all")
    detail_width = drop_width
    detail_height = max(100, left_detail_card.winfo_height())
    app._smooth_rounded_rect(
        left_detail_card,
        1,
        1,
        detail_width - 1,
        detail_height - 1,
        24,
        fill="#ffffff",
        outline="#d9deea",
        width=1,
    )

    # Keep requested row proportions while fitting fully inside the card.
    row_weights = [15, 7.5, 70, 7.5]
    row_colors = ["#ffffff", "#edf2fb", "#ffffff", "#edf2fb"]
    total_weight = float(sum(row_weights))
    inner_x1, inner_y1 = 2, 2
    inner_x2, inner_y2 = detail_width - 2, detail_height - 2
    inner_height = max(1, inner_y2 - inner_y1)

    row_heights = [int(inner_height * (w / total_weight)) for w in row_weights]
    allocated = sum(row_heights)
    row_heights[-1] += max(0, inner_height - allocated)

    y_cursor = inner_y1
    divider_y = []
    for idx, row_height in enumerate(row_heights):
        y_next = y_cursor + row_height
        left_detail_card.create_rectangle(
            inner_x1,
            y_cursor,
            inner_x2,
            y_next,
            fill=row_colors[idx],
            outline="",
        )
        if idx < len(row_heights) - 1:
            divider_y.append(y_next)
        y_cursor = y_next

    for y in divider_y:
        left_detail_card.create_line(inner_x1, y, inner_x2, y, fill="#d9deea", width=1)

    left_detail_card.create_rectangle(
        inner_x1,
        inner_y1,
        inner_x2,
        inner_y2,
        outline="#d9deea",
        width=1,
    )

    row1_height = row_heights[0]
    row1_center_y = inner_y1 + row1_height // 2
    row1_inner_width = max(80, inner_x2 - inner_x1 - 20)
    row1_frame = tk.Frame(left_detail_card, bg=row_colors[0])
    left_detail_card.create_window(
        inner_x1 + 10,
        row1_center_y,
        window=row1_frame,
        anchor="w",
        width=row1_inner_width,
        height=max(28, row1_height - 8),
    )

    title_label = tk.Label(
        row1_frame,
        textvariable=pending_count_var,
        bg=row_colors[0],
        fg="#1f2b4a",
        font=app._font(12, "bold"),
        anchor="w",
    )
    title_label.pack(side="left")

    center_actions = tk.Frame(row1_frame, bg=row_colors[0])
    center_actions.pack(side="left", padx=(10, 10))

    remove_btn = create_rounded_action(
        center_actions,
        "선택 삭제",
        remove_selected_placeholder,
        width=80,
        height=30,
        fill="#ffffff",
        outline="#d9deea",
        text_color="#2d3448",
    )
    remove_btn.pack(side="left")

    clear_btn = create_rounded_action(
        center_actions,
        "전체 초기화",
        clear_all_files,
        width=100,
        height=30,
        fill="#ffffff",
        outline="#d9deea",
        text_color="#2d3448",
    )
    clear_btn.pack(side="left", padx=(8, 0))

    upload_icon = load_svg_photo(
        config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "save_files" / "upload.svg",
        max_width=14,
        max_height=14,
        tint="#ffffff",
    )
    upload_btn = create_rounded_action(
        row1_frame,
        "업로드 시작",
        start_upload_placeholder,
        width=100,
        height=30,
        fill="#5555d5",
        outline="#5555d5",
        text_color="#ffffff",
        icon_photo=upload_icon,
        icon_fallback_text="⬆",
    )
    upload_btn.pack(side="right")

    # Row-2 / Row-3 shared column widths (percent). Col-3 removed; col-2 absorbs its width.
    table_col_widths_pct = [2.5, 32.5, 12.5, 12.5, 12.5, 7.5, 7.5, 10, 2.5]
    row2_headers = [
        "",
        "원본 파일명",
        "날짜",
        "문서 유형",
        "태그",
        "크기",
        "상태",
        "진행률",
        "",
    ]

    row2_top = inner_y1 + row_heights[0]
    row2_bottom = row2_top + row_heights[1]
    row2_center_y = (row2_top + row2_bottom) // 2
    row2_inner_x1 = inner_x1 + 8
    row2_inner_x2 = inner_x2 - 8
    row2_inner_width = max(1, row2_inner_x2 - row2_inner_x1)

    col_width_px = [int(row2_inner_width * (pct / 100.0)) for pct in table_col_widths_pct]
    col_width_px[-1] += max(0, row2_inner_width - sum(col_width_px))

    col_starts = []
    cursor_px = row2_inner_x1
    for width_px in col_width_px:
        col_starts.append(cursor_px)
        cursor_px += width_px

    col_centers = []
    x_cursor = row2_inner_x1
    for width_px in col_width_px:
        col_centers.append(x_cursor + (width_px / 2.0))
        x_cursor += width_px

    unchecked_icon = load_svg_photo(
        config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "save_files" / "unchecked.svg",
        max_width=14,
        max_height=14,
    )
    checked_icon = load_svg_photo(
        config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "save_files" / "checked.svg",
        max_width=14,
        max_height=14,
    )
    checked_white_icon = load_svg_photo(
        config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "save_files" / "checked_white.svg",
        max_width=14,
        max_height=14,
    )
    cancel_icon = load_svg_photo(
        config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "save_files" / "cancel.svg",
        max_width=12,
        max_height=12,
    )
    left_detail_card.unchecked_icon_ref = unchecked_icon
    left_detail_card.checked_icon_ref = checked_icon
    left_detail_card.checked_white_icon_ref = checked_white_icon
    left_detail_card.cancel_icon_ref = cancel_icon

    file_icon_dir = config.PROJECT_ROOT / "assets" / "icons" / "file_formats"
    file_format_icons = {
        "word": load_logo_photo(file_icon_dir / "icons8-word-48.png", max_width=16, max_height=16),
        "txt": load_logo_photo(file_icon_dir / "icons8-txt-48.png", max_width=16, max_height=16),
        "pdf": load_logo_photo(file_icon_dir / "icons8-pdf-40.png", max_width=16, max_height=16),
        "excel": load_logo_photo(file_icon_dir / "icons8-excel-48.png", max_width=16, max_height=16),
        "csv": load_logo_photo(file_icon_dir / "icons8-csv-48.png", max_width=16, max_height=16),
        "powerpoint": load_logo_photo(file_icon_dir / "icons8-powerpoint-48.png", max_width=16, max_height=16),
        "image": load_logo_photo(file_icon_dir / "icons8-image-file-48.png", max_width=16, max_height=16),
        "folder": load_logo_photo(file_icon_dir / "icons8-folder-48.png", max_width=16, max_height=16),
        "archive_folder": load_logo_photo(file_icon_dir / "icons8-archive-folder-48.png", max_width=16, max_height=16),
        "video": load_logo_photo(file_icon_dir / "icons8-video-48.png", max_width=16, max_height=16),
        "audio": load_logo_photo(file_icon_dir / "icons8-audio-48.png", max_width=16, max_height=16),
        "exe": load_logo_photo(file_icon_dir / "icons8-exe-48.png", max_width=16, max_height=16),
        "design": load_logo_photo(file_icon_dir / "icons8-design-48.png", max_width=16, max_height=16),
        "db": load_logo_photo(file_icon_dir / "icons8-db-48.png", max_width=16, max_height=16),
        "html": load_logo_photo(file_icon_dir / "icons8-html-48.png", max_width=16, max_height=16),
        "file": load_logo_photo(file_icon_dir / "icons8-file-48.png", max_width=16, max_height=16),
    }
    left_detail_card.file_format_icons_ref = file_format_icons

    select_all_checked = False
    select_icon_id = None
    select_text_id = None

    if unchecked_icon is not None:
        select_icon_id = left_detail_card.create_image(
            col_centers[0],
            row2_center_y,
            image=unchecked_icon,
            anchor="center",
            tags=("row2_select_toggle",),
        )
    else:
        select_text_id = left_detail_card.create_text(
            col_centers[0],
            row2_center_y,
            text="□",
            fill="#000000",
            font=app._font(10, "bold"),
            anchor="center",
            tags=("row2_select_toggle",),
        )

    col1_x1 = row2_inner_x1
    col1_x2 = row2_inner_x1 + col_width_px[0]
    left_detail_card.create_rectangle(
        col1_x1,
        row2_top,
        col1_x2,
        row2_bottom,
        fill="",
        outline="",
        tags=("row2_select_toggle",),
    )

    def update_row2_select_icon():
        if selected_files and len(selected_row_keys) == len(selected_files):
            icon_checked = True
        else:
            icon_checked = False

        if select_icon_id is not None:
            next_icon = checked_icon if icon_checked else unchecked_icon
            if next_icon is not None:
                left_detail_card.itemconfigure(select_icon_id, image=next_icon)
        elif select_text_id is not None:
            left_detail_card.itemconfigure(select_text_id, text="☑" if icon_checked else "□")

    def toggle_row2_select_all(_event=None):
        if not selected_files:
            return
        if len(selected_row_keys) == len(selected_files):
            selected_row_keys.clear()
        else:
            selected_row_keys.clear()
            selected_row_keys.update(selected_files)
        update_row2_select_icon()
        refresh_row3_rows()

    left_detail_card.tag_bind("row2_select_toggle", "<Button-1>", toggle_row2_select_all)

    for idx, header_text in enumerate(row2_headers):
        if idx in (0, 8) or not header_text:
            continue
        left_detail_card.create_text(
            col_centers[idx],
            row2_center_y,
            text=header_text,
            fill="#000000",
            font=app._font(10),
            anchor="center",
        )

    row3_top = row2_bottom
    row3_bottom = row3_top + row_heights[2]
    row3_inner_y1 = row3_top + 1
    row3_inner_y2 = row3_bottom - 1
    row3_height = max(1, row3_inner_y2 - row3_inner_y1)
    row4_top = row3_bottom
    row4_bottom = row4_top + row_heights[3]
    row4_center_y = (row4_top + row4_bottom) // 2

    row3_canvas = tk.Canvas(left_detail_card, bg=row_colors[2], highlightthickness=0, bd=0)
    left_detail_card.create_window(
        row2_inner_x1,
        row3_inner_y1,
        window=row3_canvas,
        anchor="nw",
        width=row2_inner_width,
        height=row3_height,
    )

    row3_body = tk.Frame(row3_canvas, bg=row_colors[2], highlightthickness=0, bd=0)
    row3_body_window = row3_canvas.create_window((0, 0), window=row3_body, anchor="nw")

    row3_scroll_state = {
        "target": 0.0,
        "current": 0.0,
        "job": None,
        "dragging": False,
        "last_y": None,
    }

    local_col_centers = []
    local_cursor = 0
    for width_px in col_width_px:
        local_col_centers.append(local_cursor + (width_px / 2.0))
        local_cursor += width_px

    table_row_height = 34
    font_measure_cache = {}
    current_year = time.localtime().tm_year
    row_combo_style_name = "SaveFilesRow.TCombobox"
    combo_style = ttk.Style(app.root)
    combo_style.configure(
        row_combo_style_name,
        fieldbackground="#ffffff",
        background="#ffffff",
        foreground="#1f2b4a",
        arrowsize=12,
    )

    def format_size_bytes(size_bytes):
        bytes_value = max(0, int(size_bytes or 0))
        kb = 1024.0
        mb = kb * 1024.0
        gb = mb * 1024.0
        tb = gb * 1024.0

        def ceil_one_decimal(value):
            return math.ceil(value * 10.0) / 10.0

        if bytes_value == 0:
            return "0 MB"
        if bytes_value < gb:
            mb_value = bytes_value / mb
            mb_value = max(0.1, ceil_one_decimal(mb_value))
            return f"{mb_value:.1f} MB"
        if bytes_value < tb:
            gb_value = ceil_one_decimal(bytes_value / gb)
            return f"{gb_value:.1f} GB"
        tb_value = ceil_one_decimal(bytes_value / tb)
        return f"{tb_value:.1f} TB"

    def truncate_to_pixel_width(text, max_width_px, font_spec):
        value = str(text or "")
        if max_width_px <= 0 or not value:
            return ""

        key = tuple(font_spec) if isinstance(font_spec, (list, tuple)) else str(font_spec)
        font_obj = font_measure_cache.get(key)
        if font_obj is None:
            font_obj = tkfont.Font(root=app.root, font=font_spec)
            font_measure_cache[key] = font_obj

        if font_obj.measure(value) <= max_width_px:
            return value

        ellipsis = "..."
        ellipsis_width = font_obj.measure(ellipsis)
        if ellipsis_width >= max_width_px:
            return ""

        lo, hi = 0, len(value)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            candidate = value[:mid].rstrip() + ellipsis
            if font_obj.measure(candidate) <= max_width_px:
                lo = mid
            else:
                hi = mid - 1

        return value[:lo].rstrip() + ellipsis

    def is_leap_year(year_value):
        return year_value % 4 == 0 and (year_value % 100 != 0 or year_value % 400 == 0)

    def max_day_for_month(year_value, month_value):
        if month_value in (1, 3, 5, 7, 8, 10, 12):
            return 31
        if month_value in (4, 6, 9, 11):
            return 30
        if month_value == 2:
            return 29 if is_leap_year(year_value) else 28
        return 31

    def split_month_day_digits(rest_digits):
        if not rest_digits:
            return "", ""
        if len(rest_digits) == 1:
            return rest_digits, ""

        month_two = rest_digits[:2]
        try:
            month_two_int = int(month_two)
        except ValueError:
            month_two_int = 0

        if 1 <= month_two_int <= 12:
            return month_two, rest_digits[2:4]

        month_one = rest_digits[0]
        carry_to_day = rest_digits[1:4]
        return month_one, carry_to_day

    def normalize_date_input(raw_value):
        digits = ''.join(ch for ch in str(raw_value or "") if ch.isdigit())[:8]
        if not digits:
            return "", ""

        if len(digits) < 4:
            return digits, digits

        year_digits = digits[:4]
        year_int = max(1, min(current_year, int(year_digits)))
        year_digits = f"{year_int:04d}"

        rest = digits[4:]
        if not rest:
            return year_digits, year_digits

        month_display = ""
        month_digits_for_state = ""
        day_digits_raw = ""

        if len(rest) == 1:
            # Keep single-digit month as-is while user is still typing.
            month_display = rest
            month_digits_for_state = rest
        else:
            month_two = rest[:2]
            month_two_int = int(month_two)

            if 1 <= month_two_int <= 12:
                month_display = f"{month_two_int:02d}"
                month_digits_for_state = month_display
                day_digits_raw = rest[2:4]
            else:
                # Carry the second digit to day when month two-digit value is invalid (e.g. 13 -> 01 + 3).
                month_one = rest[0]
                carry_to_day = rest[1:4]
                if month_one == "0":
                    month_display = "0"
                    month_digits_for_state = "0"
                else:
                    month_one_int = max(1, min(9, int(month_one)))
                    month_display = f"{month_one_int:02d}"
                    month_digits_for_state = month_display
                day_digits_raw = carry_to_day

        if not month_display:
            return year_digits, year_digits

        if not day_digits_raw:
            normalized_digits = year_digits + month_digits_for_state
            return normalized_digits, f"{year_digits}-{month_display}"

        if len(day_digits_raw) == 1:
            day_first = int(day_digits_raw)
            if 4 <= day_first <= 9:
                day_digits = f"0{day_first}"
                normalized_digits = year_digits + month_digits_for_state + day_digits
                return normalized_digits, f"{year_digits}-{month_display}-{day_digits}"
            normalized_digits = year_digits + month_digits_for_state + day_digits_raw
            return normalized_digits, f"{year_digits}-{month_display}-{day_digits_raw}"

        month_for_day = int(month_digits_for_state if len(month_digits_for_state) == 2 else month_display)
        day_int = int(day_digits_raw[:2])
        max_day = max_day_for_month(year_int, month_for_day)
        day_int = max(1, min(max_day, day_int))
        day_digits = f"{day_int:02d}"

        normalized_digits = year_digits + month_digits_for_state + day_digits
        return normalized_digits, f"{year_digits}-{month_display}-{day_digits}"

    def pick_file_format_icon_key(path_obj):
        ext = path_obj.suffix.lower().lstrip(".")
        if path_obj.is_dir():
            return "folder"
        if ext in {"zip", "7z", "rar", "tar", "gz"}:
            return "archive_folder"
        if ext in {"doc", "docx"}:
            return "word"
        if ext in {"txt"}:
            return "txt"
        if ext in {"pdf"}:
            return "pdf"
        if ext in {"xls", "xlsx", "xlsm"}:
            return "excel"
        if ext in {"csv"}:
            return "csv"
        if ext in {"ppt", "pptx", "pptm"}:
            return "powerpoint"
        if ext in {"jpg", "jpeg", "png", "gif", "tmp", "tif", "tiff", "webp", "svg"}:
            return "image"
        if ext in {"mp4", "mov", "avi", "wmv", "mkv"}:
            return "video"
        if ext in {"mp3", "wma", "m4a"}:
            return "audio"
        if ext in {"exe", "msi", "bat", "cmd"}:
            return "exe"
        if ext in {"psd", "ai", "indd", "xd"}:
            return "design"
        if ext in {"db", "sqlite", "mdb", "accdb"}:
            return "db"
        if ext in {"html", "htm"}:
            return "html"
        return "file"

    def metadata_row_from_path(path_text):
        path_obj = Path(path_text)
        row_key = str(path_obj)
        try:
            stats = path_obj.stat()
            modified = datetime.fromtimestamp(stats.st_mtime).strftime("%Y%m%d")
            size_text = format_size_bytes(stats.st_size)
        except OSError:
            modified = ""
            size_text = "-"

        row_state = row_metadata_state.setdefault(row_key, {})
        if "date_digits" not in row_state:
            row_state["date_digits"] = modified
        if "document_type" not in row_state:
            row_state["document_type"] = document_type_options[0] if document_type_options else "기타"
        if "tags" not in row_state:
            row_state["tags"] = ""
        if "status_code" not in row_state:
            row_state["status_code"] = "standby"
        if "progress_ratio" not in row_state:
            row_state["progress_ratio"] = 0.0
        row_state["date_digits"], date_text = normalize_date_input(row_state.get("date_digits", ""))
        row_state["date_iso"] = date_text if len(date_text) == 10 else ""

        suffix = path_obj.suffix
        ext_text = suffix[1:].upper() if suffix.startswith(".") else (suffix.upper() if suffix else "-")

        return {
            "row_key": row_key,
            "checked": row_key in selected_row_keys,
            "original_name": path_obj.name,
            "date": date_text,
            "document_type": row_state.get("document_type", "기타"),
            "tags": row_state.get("tags", ""),
            "size": size_text,
            "status_code": row_state.get("status_code", "standby"),
            "progress_ratio": float(row_state.get("progress_ratio", 0.0) or 0.0),
            "icon_key": pick_file_format_icon_key(path_obj),
            "file_ext": ext_text,
        }

    def get_row_data():
        selected_row_keys.intersection_update(selected_files)
        active_keys = set(selected_files)
        for stale_key in list(row_metadata_state.keys()):
            if stale_key not in active_keys:
                row_metadata_state.pop(stale_key, None)
        if not selected_files:
            return []
        return [metadata_row_from_path(file_path) for file_path in selected_files]

    def get_status_display(status_code):
        status_map = {
            "failed": ("실패", "#d33e3e"),
            "success": ("완료", "#2e9b53"),
            "standby": ("대기 중", "#000000"),
            "uploading": ("업로드 중", "#2d6cdf"),
        }
        return status_map.get(status_code, status_map["standby"])

    def draw_row4_summary():
        left_detail_card.delete("row4_summary")

        total_count = len(selected_files)
        status_counts = {
            "standby": 0,
            "uploading": 0,
            "success": 0,
            "failed": 0,
        }
        overall_progress = 0.0

        if total_count > 0:
            for row_key in selected_files:
                row_state = row_metadata_state.get(row_key, {})
                status_code = row_state.get("status_code", "standby")
                if status_code not in status_counts:
                    status_code = "standby"
                status_counts[status_code] += 1

                ratio = float(row_state.get("progress_ratio", 0.0) or 0.0)
                ratio = max(0.0, min(1.0, ratio))
                overall_progress += ratio

            overall_progress /= float(total_count)

        uploading_count = status_counts["uploading"]
        progress_pct_text = f"{int(round(overall_progress * 100.0))}%"

        left_start_x = row2_inner_x1 + 10
        left_detail_card.create_text(
            left_start_x,
            row4_center_y,
            text="전체 진행률",
            fill="#1f2b4a",
            font=app._font(10, "bold"),
            anchor="w",
            tags=("row4_summary",),
        )

        in_progress_text = f"{uploading_count} / {total_count} 파일 업로드 중"
        progress_text_x = left_start_x + 72
        left_detail_card.create_text(
            progress_text_x,
            row4_center_y,
            text=in_progress_text,
            fill="#2d3448",
            font=app._font(10),
            anchor="w",
            tags=("row4_summary",),
        )

        bar_x1 = row2_inner_x1 + 200
        bar_x2 = row2_inner_x1 + 430
        bar_y1 = row4_center_y - 5
        bar_y2 = row4_center_y + 5
        bar_radius = max(2, (bar_y2 - bar_y1) // 2)

        app._smooth_rounded_rect(
            left_detail_card,
            bar_x1,
            bar_y1,
            bar_x2,
            bar_y2,
            bar_radius,
            fill="#d7deea",
            outline="",
            width=0,
            tags="row4_summary",
        )

        if overall_progress > 0:
            fill_x2 = bar_x1 + max((bar_y2 - bar_y1), int((bar_x2 - bar_x1) * overall_progress))
            fill_x2 = min(bar_x2, fill_x2)
            app._smooth_rounded_rect(
                left_detail_card,
                bar_x1,
                bar_y1,
                fill_x2,
                bar_y2,
                bar_radius,
                fill="#5555d5",
                outline="",
                width=0,
                tags="row4_summary",
            )

        left_detail_card.create_text(
            bar_x2 + 8,
            row4_center_y,
            text=progress_pct_text,
            fill="#2d3448",
            font=app._font(9, "bold"),
            anchor="w",
            tags=("row4_summary",),
        )

        right_text = (
            f"대기 중 {status_counts['standby']}   "
            f"업로드 중 {status_counts['uploading']}   "
            f"완료 {status_counts['success']}   "
            f"실패 {status_counts['failed']}"
        )

        left_detail_card.create_text(
            row2_inner_x2 - 10,
            row4_center_y,
            text=right_text,
            fill="#2d3448",
            font=app._font(10),
            anchor="e",
            tags=("row4_summary",),
        )

    def is_ctrl_pressed(event):
        return bool(getattr(event, "state", 0) & 0x0004)

    def select_row_item(row_key, event=None):
        if is_ctrl_pressed(event):
            if row_key in selected_row_keys:
                selected_row_keys.remove(row_key)
            else:
                selected_row_keys.add(row_key)
        else:
            selected_row_keys.clear()
            selected_row_keys.add(row_key)
        refresh_row3_rows()
        return "break"

    def toggle_row_item_checkbox(row_key, _event=None):
        if row_key in selected_row_keys:
            selected_row_keys.remove(row_key)
        else:
            selected_row_keys.add(row_key)
        refresh_row3_rows()
        return "break"

    def sync_row3_scroll_region():
        row3_body.update_idletasks()
        body_height = max(row3_body.winfo_reqheight(), row3_height)
        row3_canvas.configure(scrollregion=(0, 0, row2_inner_width, body_height))

    def get_row3_max_scroll():
        scroll_region = row3_canvas.cget("scrollregion")
        if not scroll_region:
            return 0.0
        _x0, _y0, _x1, y1 = [float(value) for value in str(scroll_region).split()]
        viewport = float(row3_canvas.winfo_height())
        return max(0.0, y1 - viewport)

    def apply_row3_scroll(offset):
        max_scroll = get_row3_max_scroll()
        if max_scroll <= 0:
            row3_canvas.yview_moveto(0.0)
            row3_scroll_state["current"] = 0.0
            row3_scroll_state["target"] = 0.0
            return
        clamped = max(0.0, min(max_scroll, offset))
        row3_scroll_state["current"] = clamped
        row3_canvas.yview_moveto(clamped / max_scroll)

    def animate_row3_scroll():
        row3_scroll_state["job"] = None
        current = row3_scroll_state["current"]
        target = row3_scroll_state["target"]
        next_value = current + (target - current) * 0.24
        if abs(next_value - target) < 0.6:
            next_value = target
        apply_row3_scroll(next_value)
        if abs(row3_scroll_state["current"] - row3_scroll_state["target"]) >= 0.6:
            row3_scroll_state["job"] = app.root.after(16, animate_row3_scroll)

    def schedule_row3_scroll_animation():
        if row3_scroll_state["job"] is None:
            row3_scroll_state["job"] = app.root.after(16, animate_row3_scroll)

    def add_row3_scroll_delta(delta_pixels):
        max_scroll = get_row3_max_scroll()
        if max_scroll <= 0:
            return
        row3_scroll_state["target"] = max(0.0, min(max_scroll, row3_scroll_state["target"] + delta_pixels))
        schedule_row3_scroll_animation()

    def on_row3_mousewheel(event):
        if event.delta == 0:
            return "break"
        add_row3_scroll_delta(-event.delta / 120.0 * 40.0)
        return "break"

    def on_row3_drag_press(event):
        row3_scroll_state["dragging"] = True
        row3_scroll_state["last_y"] = event.y_root

    def on_row3_drag_motion(event):
        if not row3_scroll_state["dragging"] or row3_scroll_state["last_y"] is None:
            return
        delta_y = event.y_root - row3_scroll_state["last_y"]
        row3_scroll_state["last_y"] = event.y_root
        if delta_y:
            add_row3_scroll_delta(-delta_y * 1.25)

    def on_row3_drag_release(_event):
        row3_scroll_state["dragging"] = False
        row3_scroll_state["last_y"] = None

    def bind_row3_scroll_gestures(widget):
        widget.bind("<MouseWheel>", on_row3_mousewheel, add="+")
        widget.bind("<ButtonPress-1>", on_row3_drag_press, add="+")
        widget.bind("<B1-Motion>", on_row3_drag_motion, add="+")
        widget.bind("<ButtonRelease-1>", on_row3_drag_release, add="+")
        for child in widget.winfo_children():
            bind_row3_scroll_gestures(child)

    def is_in_row3_region(y_pos):
        return row3_inner_y1 <= y_pos <= row3_inner_y2

    def on_left_card_mousewheel(event):
        if is_in_row3_region(event.y):
            return on_row3_mousewheel(event)
        return None

    def on_left_card_drag_press(event):
        if is_in_row3_region(event.y):
            on_row3_drag_press(event)

    def on_left_card_drag_motion(event):
        if row3_scroll_state["dragging"]:
            on_row3_drag_motion(event)

    def on_left_card_drag_release(event):
        if row3_scroll_state["dragging"]:
            on_row3_drag_release(event)

    def render_row3_rows():
        for child in row3_body.winfo_children():
            child.destroy()

        rows = get_row_data()

        if not rows:
            empty_canvas = tk.Canvas(
                row3_body,
                width=row2_inner_width,
                height=max(56, table_row_height),
                bg=row_colors[2],
                highlightthickness=0,
                bd=0,
            )
            empty_canvas.pack(fill="x")
            bind_row3_scroll_gestures(empty_canvas)
            empty_canvas.create_text(
                row2_inner_width / 2.0,
                max(56, table_row_height) / 2.0,
                text="클라우드 아이콘을 눌러 파일/폴더를 추가하세요.",
                fill="#6b7280",
                font=app._font(10),
                anchor="center",
            )

        for row_values in rows:
            row_selected = bool(row_values["checked"])
            row_bg_color = "#5555d5" if row_selected else row_colors[2]
            row_primary_text_color = "#ffffff" if row_selected else "#1f2b4a"
            row_name_text_color = "#ffffff" if row_selected else "#000000"
            row_separator_color = "#7070e5" if row_selected else "#d9deea"

            row_canvas = tk.Canvas(
                row3_body,
                width=row2_inner_width,
                height=table_row_height,
                bg=row_bg_color,
                highlightthickness=0,
                bd=0,
            )
            row_canvas.pack(fill="x")
            bind_row3_scroll_gestures(row_canvas)
            row_canvas.create_rectangle(
                0,
                0,
                row2_inner_width,
                table_row_height,
                fill=row_bg_color,
                outline="",
            )
            row_canvas.create_line(0, table_row_height - 1, row2_inner_width, table_row_height - 1, fill=row_separator_color, width=1)

            row_key = row_values["row_key"]
            date_col_left = col_starts[2] - row2_inner_x1
            date_col_width = col_width_px[2]
            doc_col_left = col_starts[3] - row2_inner_x1
            doc_col_width = col_width_px[3]
            tags_col_left = col_starts[4] - row2_inner_x1
            tags_col_width = col_width_px[4]
            cancel_col_left = col_starts[8] - row2_inner_x1
            cancel_col_width = col_width_px[8]

            def on_row_canvas_click(
                event,
                key=row_key,
                date_left=date_col_left,
                date_width=date_col_width,
                doc_left=doc_col_left,
                doc_width=doc_col_width,
                tags_left=tags_col_left,
                tags_width=tags_col_width,
                cancel_left=cancel_col_left,
                cancel_width=cancel_col_width,
            ):
                date_right = date_left + date_width
                doc_right = doc_left + doc_width
                tags_right = tags_left + tags_width
                cancel_right = cancel_left + cancel_width
                if date_left <= event.x <= date_right:
                    return None
                if doc_left <= event.x <= doc_right:
                    return None
                if tags_left <= event.x <= tags_right:
                    return None
                if cancel_left <= event.x <= cancel_right:
                    return None
                return select_row_item(key, event)

            row_canvas.bind("<Button-1>", on_row_canvas_click, add="+")

            check_icon = (checked_white_icon or checked_icon) if row_values["checked"] else unchecked_icon
            if check_icon is not None:
                row_canvas.create_image(local_col_centers[0], table_row_height // 2, image=check_icon, anchor="center", tags=("row_item_toggle",))
            else:
                row_canvas.create_text(
                    local_col_centers[0],
                    table_row_height // 2,
                    text="☑" if row_values["checked"] else "□",
                    fill=row_name_text_color,
                    font=app._font(10, "bold"),
                    anchor="center",
                    tags=("row_item_toggle",),
                )

            col1_left_local = col_starts[0] - row2_inner_x1
            col1_right_local = col1_left_local + col_width_px[0]
            row_canvas.create_rectangle(
                col1_left_local,
                0,
                col1_right_local,
                table_row_height,
                fill="",
                outline="",
                tags=("row_item_toggle",),
            )
            row_canvas.tag_bind("row_item_toggle", "<Button-1>", lambda event, key=row_key: toggle_row_item_checkbox(key, event))

            col2_left_local = col_starts[1] - row2_inner_x1
            icon_photo = file_format_icons.get(row_values["icon_key"]) or file_format_icons.get("file")
            text_start_x = col2_left_local + 8
            if icon_photo is not None:
                row_canvas.create_image(col2_left_local + 10, table_row_height // 2, image=icon_photo, anchor="w")
                text_start_x = col2_left_local + 27
            col2_right_local = col2_left_local + col_width_px[1]
            col2_text_max_width = max(0, int(col2_right_local - text_start_x - 6))
            col2_text_value = truncate_to_pixel_width(
                row_values["original_name"],
                col2_text_max_width,
                app._font(9),
            )
            row_canvas.create_text(
                text_start_x,
                table_row_height // 2,
                text=col2_text_value,
                fill=row_name_text_color,
                font=app._font(9),
                anchor="w",
            )

            date_var = tk.StringVar(value=row_values["date"])
            date_entry_width = max(52, date_col_width - 12)
            date_entry = tk.Entry(
                row_canvas,
                textvariable=date_var,
                font=app._font(9),
                justify="center",
                bd=0,
                relief="flat",
                highlightthickness=1,
                highlightbackground="#c8d0e6",
                highlightcolor="#ffffff" if row_selected else "#5555d5",
                bg=row_bg_color,
                fg="#ffffff" if row_selected else "#1f2b4a",
                insertbackground="#ffffff" if row_selected else "#1f2b4a",
            )

            def on_date_key_release(_event, row_key=row_key, var=date_var, entry_widget=date_entry):
                normalized_digits, normalized_text = normalize_date_input(var.get())
                row_metadata_state.setdefault(row_key, {})["date_digits"] = normalized_digits
                var.set(normalized_text)
                entry_widget.icursor(tk.END)

            date_entry.bind("<KeyRelease>", on_date_key_release)
            row_canvas.create_window(
                date_col_left + (date_col_width / 2.0),
                table_row_height // 2,
                window=date_entry,
                width=date_entry_width,
                height=22,
                anchor="center",
            )

            doc_type_var = tk.StringVar(value=row_values["document_type"])
            doc_combo = ttk.Combobox(
                row_canvas,
                textvariable=doc_type_var,
                values=document_type_options,
                state="readonly",
                style=row_combo_style_name,
                justify="center",
                font=app._font(8),
            )
            doc_combo.configure(width=max(6, int((doc_col_width - 10) / 11)))

            def on_doc_combo_selected(_event, row_key=row_key, var=doc_type_var):
                row_metadata_state.setdefault(row_key, {})["document_type"] = var.get().strip() or "기타"

            doc_combo.bind("<<ComboboxSelected>>", on_doc_combo_selected)
            row_canvas.create_window(
                doc_col_left + (doc_col_width / 2.0),
                table_row_height // 2,
                window=doc_combo,
                width=max(56, doc_col_width - 10),
                height=22,
                anchor="center",
            )

            tag_var = tk.StringVar(value=row_values["tags"])
            tag_entry = tk.Entry(
                row_canvas,
                textvariable=tag_var,
                font=app._font(9),
                justify="left",
                bd=0,
                relief="flat",
                highlightthickness=1,
                highlightbackground="#c8d0e6",
                highlightcolor="#ffffff" if row_selected else "#5555d5",
                bg=row_bg_color,
                fg="#ffffff" if row_selected else "#1f2b4a",
                insertbackground="#ffffff" if row_selected else "#1f2b4a",
            )

            def on_tag_key_release(_event, row_key=row_key, var=tag_var, entry_widget=tag_entry):
                row_metadata_state.setdefault(row_key, {})["tags"] = var.get()
                entry_widget.icursor(tk.END)

            tag_entry.bind("<KeyRelease>", on_tag_key_release)
            row_canvas.create_window(
                tags_col_left + (tags_col_width / 2.0),
                table_row_height // 2,
                window=tag_entry,
                width=max(56, tags_col_width - 10),
                height=22,
                anchor="center",
            )

            row_canvas.create_text(local_col_centers[5], table_row_height // 2, text=row_values["size"], fill=row_primary_text_color, font=app._font(9), anchor="center")

            status_text, status_color = get_status_display(row_values.get("status_code"))
            row_canvas.create_text(local_col_centers[6], table_row_height // 2, text=status_text, fill=status_color, font=app._font(9, "bold"), anchor="center")

            progress_ratio = max(0.0, min(1.0, float(row_values.get("progress_ratio", 0.0))))
            progress_col_left = col_starts[7] - row2_inner_x1
            progress_col_width = col_width_px[7]
            progress_pct_text = f"{int(round(progress_ratio * 100.0))}%"

            progress_text_w = 28
            bar_x1 = progress_col_left + 4
            base_bar_x2 = progress_col_left + max(16, progress_col_width - progress_text_w - 4)
            bar_extension = int((base_bar_x2 - bar_x1) * 0.2)
            bar_x2 = min(progress_col_left + progress_col_width - progress_text_w, base_bar_x2 + bar_extension)
            bar_y1 = (table_row_height // 2) - 4
            bar_y2 = (table_row_height // 2) + 4
            bar_radius = max(2, (bar_y2 - bar_y1) // 2)

            app._smooth_rounded_rect(
                row_canvas,
                bar_x1,
                bar_y1,
                bar_x2,
                bar_y2,
                bar_radius,
                fill="#d7deea",
                outline="",
                width=0,
            )

            if progress_ratio > 0:
                fill_x2 = bar_x1 + max((bar_y2 - bar_y1), int((bar_x2 - bar_x1) * progress_ratio))
                fill_x2 = min(bar_x2, fill_x2)
                app._smooth_rounded_rect(
                    row_canvas,
                    bar_x1,
                    bar_y1,
                    fill_x2,
                    bar_y2,
                    bar_radius,
                    fill="#5555d5",
                    outline="",
                    width=0,
                )

            row_canvas.create_text(
                progress_col_left + progress_col_width - 2,
                table_row_height // 2,
                text=progress_pct_text,
                fill=row_primary_text_color,
                font=app._font(8, "bold"),
                anchor="e",
            )

            def on_cancel_click(_event, key=row_key):
                remove_row_item(key)
                return "break"

            if cancel_icon is not None:
                row_canvas.create_image(local_col_centers[8], table_row_height // 2, image=cancel_icon, anchor="center", tags=("row_cancel",))
            else:
                row_canvas.create_text(local_col_centers[8], table_row_height // 2, text="✕", fill="#8f96ad", font=app._font(10, "bold"), anchor="center", tags=("row_cancel",))

            row_canvas.create_rectangle(
                cancel_col_left,
                0,
                cancel_col_left + cancel_col_width,
                table_row_height,
                fill="",
                outline="",
                tags=("row_cancel",),
            )
            row_canvas.tag_bind("row_cancel", "<Button-1>", on_cancel_click)
            row_canvas.tag_bind("row_cancel", "<Enter>", lambda _event, canvas=row_canvas: canvas.configure(cursor="hand2"))
            row_canvas.tag_bind("row_cancel", "<Leave>", lambda _event, canvas=row_canvas: canvas.configure(cursor=""))

        update_row2_select_icon()
        draw_row4_summary()

        sync_row3_scroll_region()
        apply_row3_scroll(row3_scroll_state["current"])

    def on_row3_canvas_configure(event):
        row3_canvas.itemconfigure(row3_body_window, width=event.width)
        sync_row3_scroll_region()
        apply_row3_scroll(row3_scroll_state["current"])

    row3_canvas.bind("<Configure>", on_row3_canvas_configure)
    bind_row3_scroll_gestures(row3_canvas)
    bind_row3_scroll_gestures(row3_body)
    left_detail_card.bind("<MouseWheel>", on_left_card_mousewheel, add="+")
    left_detail_card.bind("<ButtonPress-1>", on_left_card_drag_press, add="+")
    left_detail_card.bind("<B1-Motion>", on_left_card_drag_motion, add="+")
    left_detail_card.bind("<ButtonRelease-1>", on_left_card_drag_release, add="+")
    refresh_row3_rows = render_row3_rows
    refresh_row3_rows()

    right_card.delete("all")
    right_width = min(245, right_card.winfo_width())
    right_height = min(625, right_card.winfo_height())-10
    app._smooth_rounded_rect(
        right_card,
        1,
        1,
        right_width - 1,
        right_height - 1,
        24,
        fill="#ffffff",
        outline="#d9deea",
        width=1,
    )

    # File/folder addition is available only through the dedicated buttons in the drop card.
