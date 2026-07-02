import tkinter as tk
from pathlib import Path
from tkinter import filedialog
import applemango_dms.config as config
from applemango_dms.ui.workplace_menu import build_sidebar_nav
from applemango_dms.utils.images import load_svg_photo

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
    pending_count_var = tk.StringVar(value="업로드 대기 파일 (0)")

    split = tk.Frame(board, bg="#ffffff")
    split.pack(fill="both", expand=True, padx=10, pady=0)
    split.grid_columnconfigure(0, weight=75)
    split.grid_columnconfigure(1, weight=15)
    split.grid_rowconfigure(0, weight=1)

    left_col = tk.Frame(split, bg="#ffffff")
    left_col.grid(row=0, column=0, sticky="nsew")
    right_col = tk.Frame(split, bg="#ffffff")
    right_col.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

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
        # Placeholder until row-3 selection list is implemented.
        return None

    def clear_all_files():
        selected_files.clear()
        pending_count_var.set("업로드 대기 파일 (0)")

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

    gap = 10
    total_width = max(600, split.winfo_width())
    usable_width = max(200, total_width - gap)
    right_width = max(100, int(usable_width * (1.5 / 9.0)))
    left_width = max(180, usable_width - right_width)
    split.grid_columnconfigure(0, minsize=left_width, weight=0)
    split.grid_columnconfigure(1, minsize=right_width, weight=0)

    drop_area.delete("all")
    drop_width = max(790, drop_area.winfo_width())
    drop_height = max(100, drop_area.winfo_height())
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
    detail_width = left_width
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

    # Row-2 / Row-3 shared column widths (percent).
    table_col_widths_pct = [2.5, 15, 25, 10, 10, 10, 7.5, 7.5, 10, 2.5]
    row2_headers = [
        "",
        "원본 파일명",
        "저장 파일명 미리보기",
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
    left_detail_card.unchecked_icon_ref = unchecked_icon
    left_detail_card.checked_icon_ref = checked_icon

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

    def toggle_row2_select_all(_event=None):
        nonlocal select_all_checked
        select_all_checked = not select_all_checked
        if select_icon_id is not None:
            next_icon = checked_icon if select_all_checked else unchecked_icon
            if next_icon is not None:
                left_detail_card.itemconfigure(select_icon_id, image=next_icon)
        elif select_text_id is not None:
            left_detail_card.itemconfigure(select_text_id, text="☑" if select_all_checked else "□")

    left_detail_card.tag_bind("row2_select_toggle", "<Button-1>", toggle_row2_select_all)

    for idx, header_text in enumerate(row2_headers):
        if idx in (0, 9) or not header_text:
            continue
        left_detail_card.create_text(
            col_centers[idx],
            row2_center_y,
            text=header_text,
            fill="#000000",
            font=app._font(10),
            anchor="center",
        )

    right_card.delete("all")
    right_width = min(150, right_card.winfo_width())
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
