import tkinter as tk
import shutil
from pathlib import Path

import applemango_dms.state as state
import applemango_dms.config as config
from applemango_dms.ui import colors
from applemango_dms.utils.images import load_svg_photo

MENU_SURFACE = colors.SURFACE
MENU_SURFACE_ALT = colors.SURFACE_ALT
MENU_TEXT_INVERSE = colors.TEXT_INVERSE
MENU_BORDER = colors.BORDER
MENU_TEXT_PRIMARY = colors.TEXT_PRIMARY
MENU_TEXT_SECONDARY = colors.TEXT_SECONDARY

MENU_NAV_ACTIVE_BG = colors.PRIMARY_PRESSED
MENU_NAV_HOVER_BG = colors.PRIMARY_HOVER
MENU_NAV_CARD_BG = MENU_SURFACE_ALT
MENU_NAV_ACTIVE_TEXT = MENU_TEXT_INVERSE
MENU_NAV_ACTIVE_SUBTEXT = colors.TEXT_ON_PRIMARY_SOFT
MENU_NAV_HOVER_TEXT = colors.TEXT_TINT_HOVER
MENU_NAV_DEFAULT_TEXT = colors.TEXT_TINT

MENU_STORAGE_BAR_BG = colors.PRIMARY
MENU_STORAGE_USAGE_FILL = colors.PRIMARY

MENU_EXIT_BUTTON_BG = colors.FAILED
MENU_EXIT_BUTTON_ACTIVE_BG = colors.FAILED_HOVER

def _directory_size_bytes(path_obj):
    root = Path(path_obj)
    if not root.exists():
        return 0

    total = 0
    for node in root.rglob("*"):
        try:
            if node.is_file():
                total += max(0, int(node.stat().st_size))
        except Exception:
            continue
    return total

def _load_workspace_icon(app, icon_key, filename, *, size=18):
    icon_dir = config.PROJECT_ROOT / "assets" / "icons" / "workspace"
    photo = app.ui_icon_photos.get(icon_key)
    if photo is None:
        photo = load_svg_photo(icon_dir / filename, max_width=size, max_height=size)
        if photo is not None:
            app.ui_icon_photos[icon_key] = photo
    return photo

def _get_workspace_nav_icon_map(app):
    return {
        "save": {
            "normal": app.ui_icon_photos.get("workspace_file_save") or _load_workspace_icon(app, "file_save_blue", "file_save_blue.svg"),
            "active": app.ui_icon_photos.get("file_save_white") or _load_workspace_icon(app, "file_save_white", "file_save_white.svg"),
        },
        "search": {
            "normal": app.ui_icon_photos.get("workspace_file_search") or _load_workspace_icon(app, "file_search_green", "file_search_green.svg"),
            "active": app.ui_icon_photos.get("file_search_white") or _load_workspace_icon(app, "file_search_white", "file_search_white.svg"),
        },
        "exit": {
            "normal": app.ui_icon_photos.get("workspace_exit") or _load_workspace_icon(app, "exit_red", "exit_red.svg"),
            "active": app.ui_icon_photos.get("exit_white") or _load_workspace_icon(app, "exit_white", "exit_white.svg"),
        },
    }

def _get_nas_storage_usage_bytes(app):
    if state.is_demo_mode:
        demo_root = app._get_demo_workspace_base_path()
        active_workspace_root = app.get_workspace_root_path()

        used_bytes = _directory_size_bytes(active_workspace_root) if active_workspace_root else 0
        total_bytes = _directory_size_bytes(demo_root)

        if total_bytes <= 0:
            total_bytes = max(1, used_bytes)

        return used_bytes, total_bytes

    candidates = []
    workspace_root = app.get_workspace_root_path()
    if workspace_root:
        candidates.append(Path(workspace_root))

    drive_root = app.build_destination_drive_path()
    if drive_root:
        candidates.append(Path(drive_root))

    candidates.append(Path(config.default_server_name))

    seen = set()
    for raw_path in candidates:
        try:
            normalized = str(raw_path)
        except Exception:
            continue
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        try:
            usage = shutil.disk_usage(normalized)
            used_bytes = max(0, int(usage.used))
            total_bytes = max(0, int(usage.total))
            return used_bytes, total_bytes
        except Exception:
            continue

    return 0, 0

def _format_nas_usage_display(used_bytes, total_bytes):
    used = max(0, int(used_bytes or 0))
    total = max(0, int(total_bytes or 0))
    gb = 1024 ** 3
    tb = 1024 ** 4
    mb = 1024 ** 2

    if total >= tb:
        unit = "TB"
        divisor = float(tb)
    elif total >= gb:
        unit = "GB"
        divisor = float(gb)
    else:
        unit = "MB"
        divisor = float(mb)

    used_value = used / divisor if divisor else 0.0
    total_value = total / divisor if divisor else 0.0
    ratio = min(1.0, (used / total) if total > 0 else 0.0)
    percent = ratio * 100.0

    return {
        "used_text": f"{used_value:.2f} {unit}",
        "total_text": f"{total_value:.2f} {unit}",
        "percent_text": f"{percent:.2f}%",
        "ratio": ratio,
    }

def build_sidebar_nav(app, parent, active_key, items, icon_photos=None):
    rows = []
    nav_icons = _get_workspace_nav_icon_map(app)
    nav_section = tk.Frame(parent, bg=parent.cget("bg"))
    nav_section.pack(fill="both", expand=True)

    card_pad_x = 1
    card_height = 100
    card_gap_y = card_pad_x

    nav_section.grid_columnconfigure(0, weight=1)
    nav_section.grid_rowconfigure(1, weight=1)

    nav_top = tk.Frame(nav_section, bg=parent.cget("bg"))
    nav_top.grid(row=0, column=0, sticky="new", padx=card_pad_x, pady=(card_pad_x, 0))

    def build_row(key, icon, title, desc, command, icon_fg, active_bg, is_last):
        is_active = key == active_key
        base_bg = parent.cget("bg")
        hover_bg = MENU_NAV_HOVER_BG
        card_bg = active_bg if is_active else MENU_NAV_CARD_BG

        outer = tk.Frame(nav_top, bg=base_bg)
        outer.pack(fill="x", pady=(0, 0 if is_last else card_gap_y))

        card = tk.Canvas(
            outer,
            bg=base_bg,
            highlightthickness=0,
            bd=0,
            relief="flat",
            cursor="hand2",
            height=card_height,
        )
        card.pack(fill="x")

        def activate(_event=None):
            command()

        def apply_style(mode="normal"):
            nonlocal is_active
            if mode == "active":
                bg_color = active_bg
                border = active_bg
                icon_color = MENU_NAV_ACTIVE_TEXT
                title_color = MENU_NAV_ACTIVE_TEXT
                desc_color = MENU_NAV_ACTIVE_SUBTEXT
            elif mode == "hover":
                bg_color = hover_bg
                border = MENU_BORDER
                icon_color = MENU_TEXT_INVERSE
                title_color = MENU_TEXT_INVERSE
                desc_color = MENU_TEXT_INVERSE
            else:
                bg_color = card_bg
                border = MENU_BORDER
                icon_color = icon_fg
                title_color = MENU_NAV_DEFAULT_TEXT
                desc_color = MENU_TEXT_PRIMARY

            card.delete("nav")
            width = max(180, card.winfo_width())
            app._smooth_rounded_rect(card, 1, 1, width - 1, 95, 20, fill=bg_color, outline=border, width=1, tags="nav")
            icon_photo_item = (icon_photos or {}).get(key)
            use_active_icon = mode in ("hover", "active")
            if isinstance(icon_photo_item, dict):
                normal_icon = icon_photo_item.get("normal")
                active_icon = icon_photo_item.get("active") or normal_icon
                icon_photo = active_icon if use_active_icon else normal_icon
            else:
                mapped = nav_icons.get(key, {})
                normal_icon = icon_photo_item or mapped.get("normal")
                active_icon = mapped.get("active") or normal_icon
                icon_photo = active_icon if use_active_icon else normal_icon

            if icon_photo is not None:
                card.create_image(26, 30, image=icon_photo, anchor="center", tags="nav")
            else:
                card.create_text(26, 30, text=icon, font=("Segoe UI Emoji", 18), fill=icon_color, anchor="center", tags="nav")
            card.create_text(46, 30, text=title, font=app._font(11, "bold"), fill=title_color, anchor="w", tags="nav")
            card.create_text(
                46,
                62,
                text=desc,
                font=app._font(8),
                fill=desc_color,
                anchor="w",
                justify="left",
                width=max(110, width - 64),
                tags="nav",
            )

        card.bind("<Configure>", lambda _event: apply_style("active" if is_active else "normal"), add="+")
        card.bind("<Button-1>", activate, add="+")
        outer.bind("<Button-1>", activate, add="+")
        card.bind("<Enter>", lambda _event: apply_style("hover"), add="+")
        card.bind("<Leave>", lambda _event: apply_style("active" if is_active else "normal"), add="+")
        outer.bind("<Enter>", lambda _event: apply_style("hover"), add="+")
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
            active_bg=MENU_NAV_ACTIVE_BG,
            is_last=(idx == total - 1),
        )

    storage_outer = tk.Frame(nav_section, bg=parent.cget("bg"))
    storage_outer.grid(row=2, column=0, sticky="sew", padx=card_pad_x, pady=(0, card_pad_x))
    storage_card = tk.Canvas(
        storage_outer,
        bg=parent.cget("bg"),
        highlightthickness=0,
        bd=0,
        relief="flat",
        height=card_height,
    )
    storage_card.pack(fill="x")

    usage_data = _format_nas_usage_display(*_get_nas_storage_usage_bytes(app))

    def draw_storage_card(_event=None):
        storage_card.delete("usage")
        width = max(180, storage_card.winfo_width())
        height = max(90, storage_card.winfo_height())

        app._smooth_rounded_rect(
            storage_card,
            1,
            1,
            width - 1,
            height - 1,
            20,
            fill=MENU_SURFACE_ALT,
            outline=MENU_BORDER,
            width=1,
            tags="usage",
        )

        storage_icon = app.ui_icon_photos.get("workspace_storage")
        if storage_icon is not None:
            storage_card.create_image(26, 30, image=storage_icon, anchor="center", tags="usage")
            title_x = 46
        else:
            storage_card.create_text(26, 30, text="💽", font=("Segoe UI Emoji", 12), fill=MENU_NAV_DEFAULT_TEXT, anchor="center", tags="usage")
            title_x = 46

        storage_card.create_text(
            title_x,
            30,
            text="저장소 사용 현황",
            font=app._font(11, "bold"),
            fill=MENU_NAV_DEFAULT_TEXT,
            anchor="w",
            tags="usage",
        )

        bar_x1, bar_x2 = 15, width - 15
        bar_y1, bar_y2 = 55, 65
        bar_radius = max(2, (bar_y2 - bar_y1) // 2)
        app._smooth_rounded_rect(
            storage_card,
            bar_x1,
            bar_y1,
            bar_x2,
            bar_y2,
            bar_radius,
            fill=MENU_STORAGE_BAR_BG,
            outline="",
            width=0,
            tags="usage",
        )

        ratio = max(0.0, min(1.0, usage_data["ratio"]))
        if ratio > 0:
            fill_x2 = bar_x1 + int((bar_x2 - bar_x1) * ratio)
            fill_x2 = min(bar_x2, fill_x2)
            if fill_x2 <= bar_x1:
                fill_x2 = bar_x1 + 1
            app._smooth_rounded_rect(
                storage_card,
                bar_x1,
                bar_y1,
                fill_x2,
                bar_y2,
                bar_radius,
                fill=MENU_STORAGE_USAGE_FILL,
                outline="",
                width=0,
                tags="usage",
            )

        metrics_y = 82
        used_text = usage_data["used_text"]
        used_item = storage_card.create_text(
            42,
            metrics_y,
            text=used_text,
            font=app._font(9, "bold"),
            fill=MENU_STORAGE_USAGE_FILL,
            tags="usage",
        )
        bbox = storage_card.bbox(used_item) or (12, metrics_y, 12, metrics_y)
        right_x = bbox[2]
        storage_card.create_text(
            right_x,
            metrics_y,
            text=f" / {usage_data['total_text']} ({usage_data['percent_text']})",
            font=app._font(9),
            fill=MENU_STORAGE_USAGE_FILL,
            anchor="w",
            tags="usage",
        )

    storage_card.bind("<Configure>", draw_storage_card, add="+")
    draw_storage_card()

    return rows

def show_main_workspace_menu(app):
    if not state.active_workspace:
        app.show_workspace_selection_screen()
        return

    app.show_save_files_screen()

def show_workspace_exit_screen(app):
    shell = app._create_workspace_shell()
    app.root.title("애플망고 DMS - 워크스페이스 나가기")

    build_sidebar_nav(
        app,
        shell["sidebar"],
        "exit",
        [
            ("save", "\U0001F4E4", "파일 저장", "새 파일을 업로드하거나\n기존 파일을 저장합니다.", app.show_save_files_screen, colors.PRIMARY),
            ("search", "\U0001F50D", "파일 검색", "저장한 파일을 검색하고\n열람합니다.", app.show_search_files_screen, MENU_TEXT_PRIMARY),
            ("exit", "\u21a9", "워크스페이스 나가기", "현재 워크스페이스를 나가고\n목록으로 돌아갑니다.", app.show_workspace_exit_screen, colors.FAILED),
        ],
        icon_photos={
            "save": app.ui_icon_photos.get("workspace_file_save") or app.ui_icon_photos.get("file_save_blue"),
            "search": app.ui_icon_photos.get("workspace_file_search") or app.ui_icon_photos.get("file_search_green"),
            "exit": app.ui_icon_photos.get("workspace_exit") or app.ui_icon_photos.get("exit_red"),
        },
    )

    outer = shell["content"]
    app._build_workspace_page_header(outer, "워크스페이스 나가기", "현재 작업을 마치고 워크스페이스 목록으로 돌아갑니다.")

    action_row = tk.Frame(outer, bg=outer.cget("bg"))
    action_row.pack(fill="x", padx=20, pady=(4, 0))
    tk.Button(
        action_row,
        text="나가기",
        width=14,
        bg=MENU_EXIT_BUTTON_BG,
        fg=MENU_TEXT_INVERSE,
        activebackground=MENU_EXIT_BUTTON_ACTIVE_BG,
        relief="flat",
        bd=0,
        cursor="hand2",
        command=app.show_workspace_selection_screen,
    ).pack(side="left")
