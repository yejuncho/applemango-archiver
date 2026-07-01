import tkinter as tk
import shutil
import random
from pathlib import Path

import applemango_dms.state as state
import applemango_dms.config as config


def _get_nas_storage_usage_bytes(app):
    if state.is_demo_mode:
        return 0, 0

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
    nav_section = tk.Frame(parent, bg=parent.cget("bg"))
    nav_section.pack(fill="both", expand=True)

    card_pad_x = 6
    card_height = 100
    card_gap_y = 6

    nav_section.grid_columnconfigure(0, weight=1)
    nav_section.grid_rowconfigure(1, weight=1)

    nav_top = tk.Frame(nav_section, bg=parent.cget("bg"))
    nav_top.grid(row=0, column=0, sticky="new", padx=card_pad_x, pady=(card_pad_x, 0))

    def build_row(key, icon, title, desc, command, icon_fg, active_bg, is_last):
        is_active = key == active_key
        base_bg = parent.cget("bg")
        hover_bg = "#f2f5fb"
        card_bg = active_bg if is_active else "#fdfefe"

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
                border = "#d0d7e6"
                icon_color = icon_fg
                title_color = "#2b3348"
                desc_color = "#000000"
            elif mode == "hover":
                bg_color = hover_bg
                border = "#d5dbe9"
                icon_color = icon_fg
                title_color = "#2b3348"
                desc_color = "#000000"
            else:
                bg_color = card_bg
                border = "#d9deea"
                icon_color = icon_fg
                title_color = "#2d3448"
                desc_color = "#000000"

            card.delete("nav")
            width = max(180, card.winfo_width())
            app._smooth_rounded_rect(card, 1, 1, width - 1, 95, 20, fill=bg_color, outline=border, width=1, tags="nav")
            icon_photo = (icon_photos or {}).get(key)
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
    demo_ratio = random.random() if state.is_demo_mode else usage_data["ratio"]

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
            fill="#fdfefe",
            outline="#d9deea",
            width=1,
            tags="usage",
        )

        storage_icon = app.ui_icon_photos.get("workspace_storage")
        if storage_icon is not None:
            storage_card.create_image(26, 30, image=storage_icon, anchor="center", tags="usage")
            title_x = 46
        else:
            storage_card.create_text(26, 30, text="💽", font=("Segoe UI Emoji", 12), fill="#2d3448", anchor="center", tags="usage")
            title_x = 46

        storage_card.create_text(
            title_x,
            30,
            text="저장소 사용 현황",
            font=app._font(11, "bold"),
            fill="#2d3448",
            anchor="w",
            tags="usage",
        )

        bar_x1, bar_x2 = 12, width - 12
        bar_y1, bar_y2 = 58, 66
        bar_radius = max(2, (bar_y2 - bar_y1) // 2)
        app._smooth_rounded_rect(
            storage_card,
            bar_x1,
            bar_y1,
            bar_x2,
            bar_y2,
            bar_radius,
            fill="#d7deea",
            outline="",
            width=0,
            tags="usage",
        )

        ratio = max(0.0, min(1.0, demo_ratio if state.is_demo_mode else usage_data["ratio"]))
        if ratio > 0:
            fill_x2 = bar_x1 + max((bar_y2 - bar_y1), int((bar_x2 - bar_x1) * ratio))
            fill_x2 = min(bar_x2, fill_x2)
            app._smooth_rounded_rect(
                storage_card,
                bar_x1,
                bar_y1,
                fill_x2,
                bar_y2,
                bar_radius,
                fill="#2d6cdf",
                outline="",
                width=0,
                tags="usage",
            )

        metrics_y = 82
        used_text = usage_data["used_text"]
        used_item = storage_card.create_text(
            12,
            metrics_y,
            text=used_text,
            font=app._font(9, "bold"),
            fill="#2d6cdf",
            anchor="w",
            tags="usage",
        )
        bbox = storage_card.bbox(used_item) or (12, metrics_y, 12, metrics_y)
        right_x = bbox[2] + 4
        storage_card.create_text(
            right_x,
            metrics_y,
            text=f" / {usage_data['total_text']} ({usage_data['percent_text']})",
            font=app._font(9),
            fill="#2d3448",
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
    app._build_workspace_page_header(outer, "워크스페이스 나가기", "현재 작업을 마치고 워크스페이스 목록으로 돌아갑니다.")

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
        command=app.show_workspace_selection_screen,
    ).pack(side="left")
