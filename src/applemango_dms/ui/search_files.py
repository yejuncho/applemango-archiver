import tkinter as tk
import applemango_dms.config as config
from applemango_dms.ui.workplace_menu import build_sidebar_nav

from applemango_dms.ui import colors
from applemango_dms.utils.images import load_svg_photo

SF_SURFACE = colors.SURFACE_ALT
SF_BORDER = colors.BORDER_LIGHT
SF_SEARCH_BOX_BORDER = colors.BORDER_INPUT
SF_SURFACE_HOVER_SOFT = colors.SURFACE_HOVER_SOFT
SF_STATUS_PROCESSING = colors.PROCESSING
SF_TEXT_DARK = colors.TEXT_NEUTRAL_DARK
SF_STATUS_FAILED = colors.FAILED_STRONG
SF_TEXT_PLACEHOLDER = colors.TEXT_PLACEHOLDER
SF_PRIMARY = colors.PRIMARY

def show_search_files_screen(app):
    shell = app._create_workspace_shell()
    app.root.title("애플망고 DMS - 파일 검색")

    build_sidebar_nav(
        app,
        shell["sidebar"],
        "search",
        [
            ("save", "\U0001F4E4", "파일 저장", "새 파일을 업로드하거나\n기존 파일을 저장합니다.", app.show_save_files_screen, SF_STATUS_PROCESSING),
            ("search", "\U0001F50D", "파일 검색", "저장한 파일을 검색하고\n열람합니다.", app.show_search_files_screen, SF_TEXT_DARK),
            ("exit", "\u21a9", "워크스페이스 나가기", "현재 워크스페이스를 나가고\n목록으로 돌아갑니다.", app.show_workspace_exit_screen, SF_STATUS_FAILED),
        ],
        icon_photos={
            "save": app.ui_icon_photos.get("workspace_file_save"),
            "search": app.ui_icon_photos.get("workspace_file_search"),
            "exit": app.ui_icon_photos.get("workspace_exit"),
        },
    )

    outer = shell["content"]
    app._build_workspace_page_header(outer, "파일 검색", "다양한 조건으로 파일을 검색할 수 있어요.")

    board = tk.Frame(outer, bg=SF_SURFACE, highlightthickness=0, bd=0)
    board.pack(fill="both", expand=True, padx=0, pady=0)

    gap = 15

    split = tk.Frame(board, bg=SF_SURFACE)
    split.pack(fill="both", expand=True, padx=gap, pady=0)
    split.grid_columnconfigure(0, weight=4, uniform="search_cols")
    split.grid_columnconfigure(1, weight=1, uniform="search_cols")
    split.grid_rowconfigure(0, weight=1)

    left_col = tk.Frame(split, bg=SF_SURFACE, highlightthickness=0, bd=0)
    left_col.grid(row=0, column=0, sticky="nsew", padx=(0, gap))

    left_top_card = tk.Canvas(left_col, bg=SF_SURFACE, highlightthickness=0, bd=0)

    left_bottom_card = tk.Canvas(left_col, bg=SF_SURFACE, highlightthickness=0, bd=0)

    right_card = tk.Canvas(split, bg=SF_SURFACE, highlightthickness=0, bd=0)
    right_card.grid(row=0, column=1, sticky="nsew")

    search_placeholder_text = "파일명, 문서 유형, 태그, 업로더 등으로 검색할 수 있어요."
    search_var = tk.StringVar(value="")
    search_box_inset = 15
    search_box_height = 48
    filter_row_top_gap = 10
    filter_row_height = 30

    search_box_canvas = tk.Canvas(left_top_card, bg=SF_SURFACE, highlightthickness=0, bd=0)
    search_box_inner = tk.Frame(search_box_canvas, bg=colors.SURFACE_ALT, highlightthickness=0, bd=0)
    search_box_inner.place(relx=0, rely=0, relwidth=1, relheight=1)

    search_text_entry = tk.Entry(
        search_box_inner,
        textvariable=search_var,
        bd=0,
        relief="flat",
        highlightthickness=0,
        bg=colors.SURFACE_ALT,
        fg=SF_TEXT_DARK,
        insertbackground=SF_TEXT_DARK,
        font=app._font(11),
        cursor="xterm",
    )

    icon_size = 20
    icon_gap = 4
    icon_padding = (7, 7)
    search_icon_photo = load_svg_photo(
        config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "search_files" / "search.svg",
        max_width=icon_size,
        max_height=icon_size,
    )
    clear_icon_photo = load_svg_photo(
        config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "search_files" / "exit.svg",
        max_width=icon_size,
        max_height=icon_size,
    )
    expand_icon_photo = load_svg_photo(
        config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "search_files" / "expand.svg",
        max_width=18,
        max_height=18,
    )
    collapse_icon_photo = load_svg_photo(
        config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "search_files" / "collapse.svg",
        max_width=18,
        max_height=18,
    )

    icon_row = tk.Frame(search_box_inner, bg=colors.SURFACE_ALT, highlightthickness=0, bd=0)
    filter_row = tk.Frame(left_top_card, bg=colors.SURFACE_ALT, highlightthickness=0, bd=0)
    filter_label = tk.Label(
        filter_row,
        text="상세 필터",
        bg=colors.SURFACE_ALT,
        fg=SF_TEXT_DARK,
        font=app._font(11, "bold"),
        anchor="w",
    )

    placeholder_state = {"active": False}
    filter_panel_state = {
        "expanded": False,
        "target_expanded": False,
        "current_top_height": 0.0,
        "anim_job": None,
        "anim_start_height": 0.0,
        "anim_target_height": 0.0,
        "anim_start_time": 0.0,
        "anim_duration_ms": 220,
    }
    layout_state = {
        "retry_job": None,
    }

    def _set_placeholder_text():
        placeholder_state["active"] = True
        search_var.set(search_placeholder_text)
        search_text_entry.config(fg=SF_TEXT_PLACEHOLDER)

    def _clear_placeholder_if_needed():
        if not placeholder_state["active"]:
            return
        placeholder_state["active"] = False
        search_var.set("")
        search_text_entry.config(fg=SF_TEXT_DARK)

    def _on_entry_focus_in(_event):
        _clear_placeholder_if_needed()

    def _on_entry_focus_out(_event):
        if search_var.get().strip():
            return
        _set_placeholder_text()

    def _is_descendant_of(widget, ancestor):
        current = widget
        while current is not None:
            if current is ancestor:
                return True
            current = getattr(current, "master", None)
        return False

    def _on_click_outside_search_box(event):
        if _is_descendant_of(event.widget, search_box_canvas):
            return
        if app.root.focus_get() is search_text_entry:
            board.focus_set()
        if not search_var.get().strip():
            _set_placeholder_text()

    def _start_search_placeholder():
        if placeholder_state["active"]:
            return

    def _clear_search_text():
        placeholder_state["active"] = False
        search_var.set("")
        search_text_entry.config(fg=SF_TEXT_DARK)
        search_text_entry.focus_set()

    def _create_icon_action(parent, icon_photo, fallback_text, command, *, icon_pad=None):
        local_icon_pad = icon_padding if icon_pad is None else icon_pad
        wrapper = tk.Frame(parent, bg=colors.SURFACE_ALT, highlightthickness=0, bd=0, cursor="hand2")
        label = tk.Label(
            wrapper,
            image=icon_photo,
            text=fallback_text if icon_photo is None else "",
            compound="center",
            bg=colors.SURFACE_ALT,
            fg=SF_TEXT_DARK,
            font=("Segoe UI Emoji", 11),
            cursor="hand2",
        )
        label.pack(padx=local_icon_pad[0], pady=local_icon_pad[1])

        def set_state(bg_color):
            wrapper.configure(bg=bg_color)
            label.configure(bg=bg_color)

        def on_enter(_event):
            set_state(SF_SURFACE_HOVER_SOFT)

        def on_leave(_event):
            set_state(colors.SURFACE_ALT)

        def on_click(_event):
            command()

        for widget in (wrapper, label):
            widget.bind("<Enter>", on_enter, add="+")
            widget.bind("<Leave>", on_leave, add="+")
            widget.bind("<Button-1>", on_click, add="+")

        wrapper.image = icon_photo
        wrapper.icon_label = label
        return wrapper

    def _compute_left_top_targets():
        total_height = max(1, left_col.winfo_height())
        available_height = max(1, total_height - gap)

        # Baseline expanded size keeps the previous visual target.
        expanded_height = max(120, int(available_height * 0.40))

        # Default collapsed size is one-third of the baseline expanded size.
        collapsed_min_height = search_box_inset + search_box_height + filter_row_top_gap + filter_row_height + 16
        collapsed_height = max(collapsed_min_height, int(expanded_height / 3.0))

        min_bottom_height = 120
        expanded_height = min(expanded_height, max(collapsed_height, available_height - min_bottom_height))
        collapsed_height = min(collapsed_height, expanded_height)
        return collapsed_height, expanded_height, available_height

    def _has_valid_left_layout_space():
        min_height = search_box_inset + search_box_height + filter_row_top_gap + filter_row_height + 20
        return left_col.winfo_width() > 160 and left_col.winfo_height() >= min_height

    def _schedule_layout_retry():
        if layout_state["retry_job"] is not None:
            return
        layout_state["retry_job"] = app.root.after(24, _retry_layout)

    def _retry_layout():
        layout_state["retry_job"] = None
        _on_layout_change()

    def _place_left_cards(top_height):
        _collapsed, _expanded, available_height = _compute_left_top_targets()
        min_bottom_height = 1
        clamped_top = max(1, min(int(top_height), max(1, available_height - min_bottom_height)))
        bottom_height = max(1, available_height - clamped_top)

        left_top_card.place(x=0, y=0, relwidth=1.0, width=0, height=clamped_top)
        left_bottom_card.place(x=0, y=clamped_top + gap, relwidth=1.0, width=0, height=bottom_height)
        return clamped_top

    def _apply_left_top_height(top_height):
        clamped_top = _place_left_cards(top_height)
        filter_panel_state["current_top_height"] = float(clamped_top)

    def _set_filter_toggle_visuals(expanded):
        filter_label.configure(fg=SF_PRIMARY if expanded else SF_TEXT_DARK)
        icon = collapse_icon_photo if expanded else expand_icon_photo
        fallback = "▴" if expanded else "▾"
        filter_toggle_icon.icon_label.configure(image=icon, text=fallback if icon is None else "")
        filter_toggle_icon.image = icon

    def _layout_filter_row():
        row_width = max(140, left_top_card.winfo_width() - (search_box_inset * 2))
        row_height = filter_row_height
        row_y = search_box_inset + search_box_height + filter_row_top_gap
        filter_row.place(x=search_box_inset, y=row_y, width=row_width, height=row_height)

    def _refresh_layout_drawings():
        _draw_card(left_top_card, bottom_shrink=0)
        _draw_card(left_bottom_card, bottom_shrink=12)
        _draw_card(right_card, bottom_shrink=12)
        _draw_search_box()
        _layout_filter_row()

    def _finish_filter_animation(expanded):
        filter_panel_state["expanded"] = expanded
        filter_panel_state["target_expanded"] = expanded
        filter_panel_state["anim_job"] = None
        _set_filter_toggle_visuals(expanded)
        _refresh_layout_drawings()

    def _animate_filter_height_step():
        filter_panel_state["anim_job"] = None
        now_ms = int(app.root.tk.call("clock", "milliseconds"))
        elapsed = now_ms - int(filter_panel_state["anim_start_time"])
        duration = max(1, int(filter_panel_state["anim_duration_ms"]))
        progress = min(1.0, max(0.0, elapsed / float(duration)))
        eased = progress * progress * (3.0 - 2.0 * progress)

        start_h = float(filter_panel_state["anim_start_height"])
        target_h = float(filter_panel_state["anim_target_height"])
        next_h = start_h + ((target_h - start_h) * eased)
        _apply_left_top_height(next_h)
        _refresh_layout_drawings()

        if progress >= 1.0:
            _finish_filter_animation(filter_panel_state["target_expanded"])
            return

        filter_panel_state["anim_job"] = app.root.after(16, _animate_filter_height_step)

    def _toggle_filter_panel():
        if filter_panel_state["anim_job"] is not None:
            app.root.after_cancel(filter_panel_state["anim_job"])
            filter_panel_state["anim_job"] = None

        target_expanded = not bool(filter_panel_state["target_expanded"])
        filter_panel_state["target_expanded"] = target_expanded
        _set_filter_toggle_visuals(target_expanded)

        collapsed_height, expanded_height, _available = _compute_left_top_targets()
        target_height = expanded_height if target_expanded else collapsed_height
        current_height = float(filter_panel_state["current_top_height"] or collapsed_height)

        filter_panel_state["anim_start_height"] = current_height
        filter_panel_state["anim_target_height"] = float(target_height)
        filter_panel_state["anim_start_time"] = int(app.root.tk.call("clock", "milliseconds"))
        filter_panel_state["anim_job"] = app.root.after(16, _animate_filter_height_step)

    search_icon_button = _create_icon_action(icon_row, search_icon_photo, "🔍", _start_search_placeholder)
    clear_icon_button = _create_icon_action(icon_row, clear_icon_photo, "✕", _clear_search_text)
    filter_toggle_icon = _create_icon_action(
        filter_row,
        expand_icon_photo,
        "▾",
        _toggle_filter_panel,
        icon_pad=(1, 1),
    )

    clear_icon_button.pack(side="right")
    search_icon_button.pack(side="right", padx=(0, icon_gap))

    icon_row.pack(side="right", padx=(4, 8), pady=0)
    search_text_entry.pack(side="left", fill="x", expand=True, padx=(14, 6), pady=(0, 1))
    filter_label.pack(side="left", padx=(2, 0))
    filter_toggle_icon.pack(side="left", padx=(1, 0))

    search_text_entry.bind("<FocusIn>", _on_entry_focus_in, add="+")
    search_text_entry.bind("<FocusOut>", _on_entry_focus_out, add="+")
    app.root.bind("<Button-1>", _on_click_outside_search_box, add="+")
    _set_placeholder_text()

    def _draw_card(card_canvas, bottom_shrink=12):
        card_canvas.delete("all")
        card_width = max(100, card_canvas.winfo_width())
        full_height = max(100, card_canvas.winfo_height())
        card_height = max(100, full_height - bottom_shrink)
        app._smooth_rounded_rect(
            card_canvas,
            1,
            1,
            card_width - 1,
            card_height - 1,
            24,
            fill=colors.SURFACE_ALT,
            outline=SF_BORDER,
            width=1,
        )

    def _draw_search_box():
        bar_width = max(220, left_top_card.winfo_width() - (search_box_inset * 2))
        search_box_canvas.place(
            x=search_box_inset,
            y=search_box_inset,
            width=bar_width,
            height=search_box_height,
        )
        search_box_canvas.delete("all")
        app._smooth_rounded_rect(
            search_box_canvas,
            1,
            1,
            bar_width - 1,
            search_box_height - 1,
            16,
            fill=colors.SURFACE_ALT,
            outline=SF_SEARCH_BOX_BORDER,
            width=1,
        )
        search_box_canvas.tag_lower("all")

    def _on_layout_change(_event=None):
        if not _has_valid_left_layout_space():
            _schedule_layout_retry()
            return

        if filter_panel_state["anim_job"] is None:
            collapsed_height, expanded_height, _available = _compute_left_top_targets()
            target_height = expanded_height if filter_panel_state["expanded"] else collapsed_height
            _apply_left_top_height(target_height)

        _refresh_layout_drawings()

    left_top_card.bind("<Configure>", _on_layout_change)
    left_bottom_card.bind("<Configure>", _on_layout_change)
    split.bind("<Configure>", _on_layout_change)
    right_card.bind("<Configure>", _on_layout_change)
    left_col.bind("<Configure>", _on_layout_change)

    _set_filter_toggle_visuals(False)
    app.root.after_idle(_on_layout_change)