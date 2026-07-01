import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from applemango_dms.ui.workplace_menu import build_sidebar_nav

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
        drop_area.scale("drop_icon", center_x, center_y, 0.75, 0.75)
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
