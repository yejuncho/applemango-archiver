import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from datetime import datetime
import re
from tkinter import filedialog
import applemango_dms.config as config
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
    pending_count_var = tk.StringVar(value="업로드 대기 파일 (0)")
    refresh_row3_rows = lambda: None

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

    drop_area = tk.Canvas(left_col, height=102, bg="#ffffff", highlightthickness=0, bd=0, cursor="hand2")
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

    def remove_selected_placeholder():
        if not selected_row_keys:
            return
        selected_files[:] = [path for path in selected_files if path not in selected_row_keys]
        selected_row_keys.clear()
        pending_count_var.set(f"업로드 대기 파일 ({len(selected_files)})")
        refresh_row3_rows()

    def clear_all_files():
        selected_files.clear()
        selected_row_keys.clear()
        pending_count_var.set("업로드 대기 파일 (0)")
        refresh_row3_rows()

    def start_upload_placeholder():
        # Placeholder until upload flow is finalized.
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
        drop_area.scale("drop_icon", center_x, center_y, 0.5, 0.5)
    else:
        drop_area.create_text(center_x, center_y, text="\U0001F4E4", fill="#5c667f", font=("Segoe UI Emoji", 24))

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
    table_col_widths_pct = [2.5, 40, 10, 10, 10, 7.5, 7.5, 10, 2.5]
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
    left_detail_card.unchecked_icon_ref = unchecked_icon
    left_detail_card.checked_icon_ref = checked_icon
    left_detail_card.checked_white_icon_ref = checked_white_icon

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
    invalid_windows_chars = re.compile(r'[<>:"/\\|?*]')
    font_measure_cache = {}

    def format_size_bytes(size_bytes):
        units = ["B", "KB", "MB", "GB", "TB"]
        value = float(size_bytes)
        unit_idx = 0
        while value >= 1024.0 and unit_idx < len(units) - 1:
            value /= 1024.0
            unit_idx += 1
        if unit_idx == 0:
            return f"{int(value)} {units[unit_idx]}"
        return f"{value:.1f} {units[unit_idx]}"

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
        try:
            stats = path_obj.stat()
            modified = datetime.fromtimestamp(stats.st_mtime).strftime("%Y-%m-%d")
            size_text = format_size_bytes(stats.st_size)
        except OSError:
            modified = "-"
            size_text = "-"

        suffix = path_obj.suffix
        ext_text = suffix[1:].upper() if suffix.startswith(".") else (suffix.upper() if suffix else "-")
        doc_type = "기타"
        tags = ""

        return {
            "row_key": str(path_obj),
            "checked": str(path_obj) in selected_row_keys,
            "original_name": path_obj.name,
            "date": modified,
            "document_type": doc_type,
            "tags": tags,
            "size": size_text,
            "status": "대기",
            "progress": "0%",
            "icon_key": pick_file_format_icon_key(path_obj),
            "file_ext": ext_text,
        }

    def get_row_data():
        selected_row_keys.intersection_update(selected_files)
        if not selected_files:
            return []
        return [metadata_row_from_path(file_path) for file_path in selected_files]

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
            row_canvas.bind("<Button-1>", lambda event, key=row_key: select_row_item(key, event), add="+")

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

            row_canvas.create_text(local_col_centers[2], table_row_height // 2, text=row_values["date"], fill=row_primary_text_color, font=app._font(9), anchor="center")
            row_canvas.create_text(local_col_centers[3], table_row_height // 2, text=row_values["document_type"], fill=row_primary_text_color, font=app._font(9), anchor="center")
            row_canvas.create_text(local_col_centers[4], table_row_height // 2, text=row_values["tags"], fill=row_primary_text_color, font=app._font(9), anchor="center")
            row_canvas.create_text(local_col_centers[5], table_row_height // 2, text=row_values["size"], fill=row_primary_text_color, font=app._font(9), anchor="center")
            row_canvas.create_text(local_col_centers[6], table_row_height // 2, text=row_values["status"], fill=row_primary_text_color, font=app._font(9), anchor="center")
            row_canvas.create_text(local_col_centers[7], table_row_height // 2, text=row_values["progress"], fill=row_primary_text_color, font=app._font(9), anchor="center")

        update_row2_select_icon()

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

    drop_area.bind("<Button-1>", lambda _event: pick_files())
    if TkinterDnD is not None and hasattr(drop_area, "drop_target_register"):
        drop_area.drop_target_register(DND_FILES)
        drop_area.dnd_bind("<<Drop>>", handle_drop)
