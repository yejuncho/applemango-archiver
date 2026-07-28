import tkinter as tk
from datetime import date, timedelta
import applemango_dms.config as config
from applemango_dms.ui.workplace_menu import build_sidebar_nav
from applemango_dms.ui.widgets import RoundedInput

try:
    from PIL import Image, ImageDraw, ImageTk
    _PIL_AVAILABLE = True
except Exception:
    Image = None
    ImageDraw = None
    ImageTk = None
    _PIL_AVAILABLE = False

from applemango_dms.ui import colors
from applemango_dms.utils.images import load_svg_photo

SF_SURFACE = colors.SURFACE_ALT
SF_BORDER = colors.BORDER_LIGHT
SF_SEARCH_BOX_BORDER = "#5C667F"
SF_SURFACE_HOVER_SOFT = colors.SURFACE_HOVER_SOFT
SF_STATUS_PROCESSING = colors.PROCESSING
SF_TEXT_DARK = colors.TEXT_NEUTRAL_DARK
SF_TEXT_MAIN = colors.TEXT_EMPHASIS
SF_STATUS_FAILED = colors.FAILED_STRONG
SF_TEXT_PLACEHOLDER = colors.TEXT_PLACEHOLDER
SF_PRIMARY = colors.PRIMARY
SF_INPUT_IDLE_BORDER = colors.BORDER
SF_INPUT_FOCUS_BORDER = colors.PRIMARY_PRESSED

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
    split.grid_columnconfigure(0, weight=39, uniform="search_cols")
    split.grid_columnconfigure(1, weight=11, uniform="search_cols")
    split.grid_rowconfigure(0, weight=1)

    left_col = tk.Frame(split, bg=SF_SURFACE, highlightthickness=0, bd=0)
    left_col.grid(row=0, column=0, sticky="nsew", padx=(0, gap))

    left_top_card = tk.Canvas(left_col, bg=SF_SURFACE, highlightthickness=0, bd=0)

    left_bottom_card = tk.Canvas(left_col, bg=SF_SURFACE, highlightthickness=0, bd=0)

    right_card = tk.Canvas(split, bg=SF_SURFACE, highlightthickness=0, bd=0)
    right_card.grid(row=0, column=1, sticky="nsew")

    search_placeholder_text = "파일명, 문서 유형, 태그, 업로더 등으로 검색할 수 있어요."
    search_result_count_var = tk.StringVar(value="검색 결과 (#건)")
    search_var = tk.StringVar(value="")
    search_box_inset = 15
    search_box_height = 48
    filter_row_top_gap = 10
    filter_row_height = 30
    filter_content_top_gap = 8
    filter_content_height = 228
    filter_content_bottom_padding = 14

    search_box_holder = tk.Frame(left_top_card, bg=colors.SURFACE_ALT, highlightthickness=0, bd=0)

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
    to_icon_photo = load_svg_photo(
        config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "search_files" / "to.svg",
        max_width=14,
        max_height=14,
    )
    calendar_icon_photo = load_svg_photo(
        config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "search_files" / "calendar.svg",
        max_width=14,
        max_height=14,
    )

    filter_row = tk.Frame(left_top_card, bg=colors.SURFACE_ALT, highlightthickness=0, bd=0)
    filter_label = tk.Label(
        filter_row,
        text="상세 필터",
        bg=colors.SURFACE_ALT,
        fg=SF_TEXT_DARK,
        font=app._font(11, "bold"),
        anchor="w",
    )
    filter_content_clip = tk.Frame(left_top_card, bg=colors.SURFACE_ALT, highlightthickness=0, bd=0)
    filter_content_inner = tk.Frame(filter_content_clip, bg=colors.SURFACE_ALT, highlightthickness=0, bd=0)

    filter_column_specs = [
        ("문서 날짜", 18),
        ("문서 유형", 9),
        ("파일 종류", 9),
        ("업로드한 사람", 9),
    ]

    filter_content_inner.grid_rowconfigure(0, weight=1)
    for idx, (_title, weight) in enumerate(filter_column_specs):
        filter_content_inner.grid_columnconfigure(idx, weight=weight, uniform="filter_cols")

    filter_col_frames = []
    for idx, (title, _weight) in enumerate(filter_column_specs):
        col_frame = tk.Frame(filter_content_inner, bg=colors.SURFACE_ALT, highlightthickness=0, bd=0)
        col_frame.grid(row=0, column=idx, sticky="nsew", padx=(0 if idx == 0 else 8, 0), pady=(0, 0))
        col_frame.grid_columnconfigure(0, weight=1)

        header_label = tk.Label(
            col_frame,
            text=title,
            bg=colors.SURFACE_ALT,
            fg=SF_TEXT_DARK,
            font=app._font(10, "bold"),
            anchor="w",
            justify="left",
        )
        header_label.grid(row=0, column=0, sticky="w", padx=(2, 0), pady=(0, 8))
        filter_col_frames.append(col_frame)

    date_from_var = tk.StringVar(value="")
    date_to_var = tk.StringVar(value="")
    doc_type_var = tk.StringVar(value="")
    file_type_var = tk.StringVar(value="")
    uploader_var = tk.StringVar(value="")

    doc_type_options = list(config.DEFAULT_DOCUMENT_TYPES)
    file_type_options = [
        ".doc", ".docx", ".txt", ".pdf", ".xls", ".xlsx", ".xlsm", ".csv", ".ppt", ".pptx", ".pptm",
        ".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".webp", ".svg",
        ".zip", ".7z", ".rar", ".tar", ".gz",
        ".mp4", ".mov", ".avi", ".wmv", ".mkv",
        ".mp3", ".wma", ".m4a",
        ".exe", ".msi", ".bat", ".cmd",
        ".psd", ".ai", ".indd", ".xd",
        ".db", ".sqlite", ".mdb", ".accdb",
        ".html", ".htm",
    ]

    dropdown_state = {
        "doc_type_expanded": False,
        "file_type_expanded": False,
        "doc_type_popup": None,
        "file_type_popup": None,
    }

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

    result_table_state = {
        "select_all_checked": False,
    }

    result_table_icons = {
        "unchecked": load_svg_photo(
            config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "search_files" / "unchecked.svg",
            max_width=14,
            max_height=14,
        ),
        "checked": load_svg_photo(
            config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "search_files" / "checked.svg",
            max_width=14,
            max_height=14,
        ),
    }

    def _is_descendant_of(widget, ancestor):
        current = widget
        while current is not None:
            if current is ancestor:
                return True
            current = getattr(current, "master", None)
        return False

    def _on_click_outside_search_box(event):
        for popup_key in ("doc_type_popup", "file_type_popup"):
            popup = dropdown_state.get(popup_key)
            if popup is not None and popup.winfo_exists() and _is_descendant_of(event.widget, popup):
                return

        input_ancestors = [
            search_box_holder,
            date_from_field["canvas"],
            date_to_field["canvas"],
            doc_type_field["canvas"],
            file_type_field["canvas"],
            uploader_field["canvas"],
            date_quick_row,
        ]
        for ancestor in input_ancestors:
            if _is_descendant_of(event.widget, ancestor):
                return

        focused = app.root.focus_get()
        editable_widgets = {
            search_text_entry,
            date_from_field["entry"],
            date_to_field["entry"],
            doc_type_field["entry"],
            file_type_field["entry"],
            uploader_field["entry"],
        }
        if focused in editable_widgets:
            board.focus_set()

        _close_dropdown_popup("doc_type")
        _close_dropdown_popup("file_type")

    def _start_search_placeholder():
        search_text_entry.focus_set()

    def _clear_search_text():
        search_var.set("")
        search_text_entry.focus_set()

    def is_leap_year(year_value):
        return (year_value % 4 == 0 and year_value % 100 != 0) or (year_value % 400 == 0)

    def max_day_for_month(year_value, month_value):
        if month_value in (1, 3, 5, 7, 8, 10, 12):
            return 31
        if month_value in (4, 6, 9, 11):
            return 30
        if month_value == 2:
            return 29 if is_leap_year(year_value) else 28
        return 31

    def normalize_date_input(raw_value):
        current_year = 9999
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

    def _draw_plain_rounded_rect(canvas, x1, y1, x2, y2, radius, *, fill, outline, border_width=1):
        r = max(2, min(int(radius), int((x2 - x1) / 2), int((y2 - y1) / 2)))

        # Fill (no shadow): center strips + corner pies.
        canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline="")
        canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline="")
        canvas.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90, style="pieslice", fill=fill, outline="")
        canvas.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90, style="pieslice", fill=fill, outline="")
        canvas.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90, style="pieslice", fill=fill, outline="")
        canvas.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90, style="pieslice", fill=fill, outline="")

        # Outline.
        canvas.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90, style="arc", outline=outline, width=border_width)
        canvas.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90, style="arc", outline=outline, width=border_width)
        canvas.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90, style="arc", outline=outline, width=border_width)
        canvas.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90, style="arc", outline=outline, width=border_width)
        canvas.create_line(x1 + r, y1, x2 - r, y1, fill=outline, width=border_width)
        canvas.create_line(x2, y1 + r, x2, y2 - r, fill=outline, width=border_width)
        canvas.create_line(x1 + r, y2, x2 - r, y2, fill=outline, width=border_width)
        canvas.create_line(x1, y1 + r, x1, y2 - r, fill=outline, width=border_width)

    def _color_to_rgb(color_value):
        r16, g16, b16 = app.root.winfo_rgb(color_value)
        return (r16 // 256, g16 // 256, b16 // 256)

    def _draw_dropdown_shell(canvas, width, height, *, radius=10, border_width=1):
        canvas.delete("dropdown_shell")
        width = max(2, int(width))
        height = max(2, int(height))

        if _PIL_AVAILABLE:
            scale = 4
            sw = width * scale
            sh = height * scale
            sr = max(0, int(round(radius * scale)))
            sbw = max(1, int(round(border_width * scale)))

            bg_rgb = _color_to_rgb(colors.SURFACE_ALT)
            fill_rgb = _color_to_rgb(colors.SURFACE_ALT)
            border_rgb = _color_to_rgb(SF_INPUT_IDLE_BORDER)

            image = Image.new("RGBA", (sw, sh), (bg_rgb[0], bg_rgb[1], bg_rgb[2], 255))
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle([0, 0, sw - 1, sh - 1], radius=sr, fill=(border_rgb[0], border_rgb[1], border_rgb[2], 255))
            draw.rounded_rectangle(
                [sbw, sbw, sw - 1 - sbw, sh - 1 - sbw],
                radius=max(0, sr - sbw),
                fill=(fill_rgb[0], fill_rgb[1], fill_rgb[2], 255),
            )

            try:
                resample_mode = Image.Resampling.LANCZOS
            except Exception:
                resample_mode = Image.LANCZOS

            downsampled = image.resize((width, height), resample=resample_mode)
            photo = ImageTk.PhotoImage(downsampled, master=canvas)
            canvas._dropdown_shell_photo = photo
            canvas.create_image(0, 0, anchor="nw", image=photo, tags=("dropdown_shell",))
            return

        # Fallback: smooth rounded rect from app helper.
        app._smooth_rounded_rect(
            canvas,
            1,
            1,
            width - 1,
            height - 1,
            radius,
            fill=colors.SURFACE_ALT,
            outline=SF_INPUT_IDLE_BORDER,
            width=1,
            tags="dropdown_shell",
        )

    def _create_rounded_input(
        parent,
        text_var,
        *,
        placeholder="",
        with_toggle_icon=False,
        toggle_command=None,
        trailing_icon_photo=None,
        trailing_icon_command=None,
    ):
        field_holder = tk.Frame(parent, bg=colors.SURFACE_ALT, highlightthickness=0, bd=0)

        rounded_input = RoundedInput(
            field_holder,
            textvariable=text_var,
            placeholder=placeholder,
            width=120,
            height=34,
            corner_radius=10,
            font=app._font(10),
            foreground=SF_TEXT_DARK,
            placeholder_color=SF_TEXT_PLACEHOLDER,
            fill=colors.SURFACE_ALT,
            border_color=SF_INPUT_IDLE_BORDER,
            focus_fill=colors.SURFACE_ALT,
            focus_border_color=SF_INPUT_FOCUS_BORDER,
            disabled_fill=colors.SURFACE_ALT,
            disabled_foreground=SF_TEXT_PLACEHOLDER,
            state="normal",
        )
        rounded_input.pack(fill="both", expand=True)

        entry = rounded_input.entry
        entry.configure(justify="left", insertbackground=SF_TEXT_DARK)
        entry.grid_configure(padx=(6, 8))

        toggle_widget = None
        trailing_widget = None
        has_right_icon = False

        if with_toggle_icon and callable(toggle_command):
            toggle_widget = _create_icon_action(
                rounded_input,
                expand_icon_photo,
                "▾",
                toggle_command,
                icon_pad=(1, 1),
            )
            toggle_widget.place(relx=1.0, rely=0.5, x=-6, y=0, anchor="e")
            has_right_icon = True

        if trailing_icon_photo is not None:
            trailing_widget = _create_icon_action(
                rounded_input,
                trailing_icon_photo,
                "📅",
                trailing_icon_command if callable(trailing_icon_command) else (lambda: None),
                icon_pad=(1, 1),
            )
            trailing_widget.place(relx=1.0, rely=0.5, x=-6, y=0, anchor="e")
            has_right_icon = True

        if has_right_icon:
            entry.grid_configure(padx=(6, 30))

        return {
            "canvas": field_holder,
            "entry": entry,
            "toggle": toggle_widget,
            "trailing": trailing_widget,
            "rounded": rounded_input,
        }

    def _align_rounded_placeholder(field, left_pad, right_pad):
        rounded = field["rounded"]
        rounded._placeholder_left_pad_override = int(left_pad)
        rounded._placeholder_right_pad_override = int(right_pad)
        rounded._reposition_placeholder()

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

    def _set_dropdown_icon(toggle_widget, expanded):
        icon = collapse_icon_photo if expanded else expand_icon_photo
        fallback = "▴" if expanded else "▾"
        toggle_widget.icon_label.configure(image=icon, text=fallback if icon is None else "")
        toggle_widget.image = icon

    def _close_dropdown_popup(kind):
        popup_key = f"{kind}_popup"
        expanded_key = f"{kind}_expanded"
        popup = dropdown_state.get(popup_key)
        if popup is not None and popup.winfo_exists():
            popup.destroy()
        dropdown_state[popup_key] = None
        dropdown_state[expanded_key] = False

    def _open_dropdown_popup(kind, field, options, value_var):
        popup_key = f"{kind}_popup"
        expanded_key = f"{kind}_expanded"

        _close_dropdown_popup(kind)

        popup_width = max(120, int(field["canvas"].winfo_width()))
        popup_rows = max(1, min(5, len(options)))
        popup_height = (popup_rows * 28) + 12
        popup_x = field["canvas"].winfo_rootx()
        popup_y = field["canvas"].winfo_rooty() + field["canvas"].winfo_height() + 2

        popup = tk.Toplevel(app.root)
        popup.overrideredirect(True)
        popup.transient(app.root)
        popup.configure(bg=colors.SURFACE_ALT)
        popup.geometry(f"{popup_width}x{popup_height}+{popup_x}+{popup_y}")
        popup.lift()
        popup.focus_force()

        shell_canvas = tk.Canvas(popup, bg=colors.SURFACE_ALT, highlightthickness=0, bd=0)
        shell_canvas.pack(fill="both", expand=True)

        inner_pad = 2
        _draw_dropdown_shell(shell_canvas, popup_width, popup_height, radius=10, border_width=1)

        def _on_shell_resize(event):
            _draw_dropdown_shell(shell_canvas, event.width, event.height, radius=10, border_width=1)

        shell_canvas.bind("<Configure>", _on_shell_resize, add="+")

        body = tk.Frame(
            shell_canvas,
            bg=colors.SURFACE_ALT,
            bd=0,
            highlightthickness=0,
        )
        shell_canvas.create_window(
            inner_pad,
            inner_pad,
            anchor="nw",
            window=body,
            width=max(1, popup_width - (inner_pad * 2)),
            height=max(1, popup_height - (inner_pad * 2)),
        )

        listbox = tk.Listbox(
            body,
            height=popup_rows,
            activestyle="none",
            selectmode="browse",
            bd=0,
            highlightthickness=0,
            relief="flat",
            bg=colors.SURFACE_ALT,
            fg=SF_TEXT_DARK,
            font=app._font(11),
            selectbackground=SF_PRIMARY,
            selectforeground=colors.TEXT_INVERSE,
            exportselection=False,
        )
        listbox.pack(fill="both", expand=True)

        for option in options:
            listbox.insert(tk.END, option)

        current_value = (value_var.get() or "").strip()
        if current_value in options:
            current_index = options.index(current_value)
            listbox.selection_set(current_index)
            listbox.see(current_index)

        def _commit_selection(_event=None):
            selection = listbox.curselection()
            if not selection:
                return "break"
            chosen = listbox.get(selection[0])
            value_var.set(chosen)
            _close_dropdown_popup(kind)
            return "break"

        listbox.bind("<ButtonRelease-1>", _commit_selection)
        listbox.bind("<Double-Button-1>", _commit_selection)
        listbox.bind("<Return>", _commit_selection)
        popup.bind("<Escape>", lambda _event: _close_dropdown_popup(kind))
        popup.after(0, lambda: listbox.focus_set())

        dropdown_state[popup_key] = popup
        dropdown_state[expanded_key] = True

    def _layout_filter_row():
        row_width = max(140, left_top_card.winfo_width() - (search_box_inset * 2))
        row_height = filter_row_height
        row_y = search_box_inset + search_box_height + filter_row_top_gap
        filter_row.place(x=search_box_inset, y=row_y, width=row_width, height=row_height)

    def _layout_filter_content():
        content_x = search_box_inset
        content_y = search_box_inset + search_box_height + filter_row_top_gap + filter_row_height + filter_content_top_gap
        content_width = max(140, left_top_card.winfo_width() - (search_box_inset * 2))
        max_visible_height = max(0, left_top_card.winfo_height() - content_y - filter_content_bottom_padding)
        visible_height = min(filter_content_height, max_visible_height)

        if visible_height <= 0:
            filter_content_clip.place_forget()
            return

        filter_content_clip.place(x=content_x, y=content_y, width=content_width, height=visible_height)
        filter_content_inner.place(x=0, y=0, width=content_width, height=filter_content_height)

    def _toggle_doc_type_dropdown():
        if dropdown_state["doc_type_expanded"]:
            _close_dropdown_popup("doc_type")
        else:
            _close_dropdown_popup("file_type")
            _open_dropdown_popup("doc_type", doc_type_field, doc_type_options, doc_type_var)
        _set_dropdown_icon(doc_type_field["toggle"], dropdown_state["doc_type_expanded"])
        _set_dropdown_icon(file_type_field["toggle"], dropdown_state["file_type_expanded"])

    def _toggle_file_type_dropdown():
        if dropdown_state["file_type_expanded"]:
            _close_dropdown_popup("file_type")
        else:
            _close_dropdown_popup("doc_type")
            _open_dropdown_popup("file_type", file_type_field, file_type_options, file_type_var)
        _set_dropdown_icon(doc_type_field["toggle"], dropdown_state["doc_type_expanded"])
        _set_dropdown_icon(file_type_field["toggle"], dropdown_state["file_type_expanded"])

    def _refresh_layout_drawings():
        _draw_card(left_top_card, bottom_shrink=0)
        _draw_card(left_bottom_card, bottom_shrink=12)
        _draw_card(right_card, bottom_shrink=12)
        _draw_results_table()
        _draw_search_box()
        _layout_filter_row()
        _layout_filter_content()

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

    search_input = RoundedInput(
        search_box_holder,
        textvariable=search_var,
        placeholder=search_placeholder_text,
        width=260,
        height=search_box_height,
        corner_radius=12,
        font=app._font(11),
        foreground=SF_TEXT_DARK,
        placeholder_color=SF_TEXT_PLACEHOLDER,
        fill=colors.SURFACE_ALT,
        border_color=SF_INPUT_IDLE_BORDER,
        focus_fill=colors.SURFACE_ALT,
        focus_border_color=SF_INPUT_FOCUS_BORDER,
        disabled_fill=colors.SURFACE_ALT,
        disabled_foreground=SF_TEXT_PLACEHOLDER,
        leading_icon=search_icon_photo,
        state="normal",
    )
    search_text_entry = search_input.entry
    search_text_entry.configure(insertbackground=SF_TEXT_DARK)
    search_text_entry.grid_configure(padx=(6, 30))

    clear_icon_button = _create_icon_action(search_box_holder, clear_icon_photo, "✕", _clear_search_text)
    filter_toggle_icon = _create_icon_action(
        filter_row,
        expand_icon_photo,
        "▾",
        _toggle_filter_panel,
        icon_pad=(1, 1),
    )

    # Filter inputs: date range (2) + document type + file type + uploader.
    date_col = filter_col_frames[0]
    doc_type_col = filter_col_frames[1]
    file_type_col = filter_col_frames[2]
    uploader_col = filter_col_frames[3]

    date_range_row = tk.Frame(date_col, bg=colors.SURFACE_ALT, highlightthickness=0, bd=0)
    date_range_row.grid(row=1, column=0, sticky="ew", padx=(2, 6))
    date_range_row.grid_columnconfigure(0, weight=1)
    date_range_row.grid_columnconfigure(1, weight=0)
    date_range_row.grid_columnconfigure(2, weight=1)

    date_from_field = _create_rounded_input(
        date_range_row,
        date_from_var,
        placeholder="시작일",
        trailing_icon_photo=calendar_icon_photo,
        trailing_icon_command=lambda: None,
    )
    date_from_field["canvas"].grid(row=0, column=0, sticky="ew")
    _align_rounded_placeholder(date_from_field, left_pad=6, right_pad=30)

    to_label = tk.Label(
        date_range_row,
        image=to_icon_photo,
        text="~" if to_icon_photo is None else "",
        compound="center",
        bg=colors.SURFACE_ALT,
        fg=SF_TEXT_DARK,
        font=app._font(9, "bold"),
    )
    to_label.grid(row=0, column=1, padx=(6, 6))
    to_label.image = to_icon_photo

    date_to_field = _create_rounded_input(
        date_range_row,
        date_to_var,
        placeholder="종료일",
        trailing_icon_photo=calendar_icon_photo,
        trailing_icon_command=lambda: None,
    )
    date_to_field["canvas"].grid(row=0, column=2, sticky="ew")
    _align_rounded_placeholder(date_to_field, left_pad=6, right_pad=30)

    date_quick_row = tk.Frame(date_col, bg=colors.SURFACE_ALT, highlightthickness=0, bd=0)
    date_quick_row.grid(row=2, column=0, sticky="ew", padx=(2, 6), pady=(6, 0))
    for quick_idx in range(5):
        date_quick_row.grid_columnconfigure(quick_idx, weight=1, uniform="date_quick")

    doc_type_field = _create_rounded_input(
        doc_type_col,
        doc_type_var,
        placeholder="모든 문서 유형",
        with_toggle_icon=True,
        toggle_command=_toggle_doc_type_dropdown,
    )
    doc_type_field["canvas"].grid(row=1, column=0, sticky="ew", padx=(2, 6))
    _align_rounded_placeholder(doc_type_field, left_pad=6, right_pad=30)

    file_type_field = _create_rounded_input(
        file_type_col,
        file_type_var,
        placeholder="모든 파일 종류",
        with_toggle_icon=True,
        toggle_command=_toggle_file_type_dropdown,
    )
    file_type_field["canvas"].grid(row=1, column=0, sticky="ew", padx=(2, 6))
    _align_rounded_placeholder(file_type_field, left_pad=6, right_pad=30)

    uploader_field = _create_rounded_input(
        uploader_col,
        uploader_var,
        placeholder="이름을 입력하세요",
    )
    uploader_field["canvas"].grid(row=1, column=0, sticky="ew", padx=(2, 6))
    _align_rounded_placeholder(uploader_field, left_pad=6, right_pad=8)

    def _bind_date_entry(entry_widget, value_var):
        def on_focus_in(_event):
            return None

        def on_key_release(_event):
            if str(value_var.get() or "").strip() == "-":
                return
            _digits, normalized_text = normalize_date_input(value_var.get())
            value_var.set(normalized_text)
            entry_widget.icursor(tk.END)

        entry_widget.bind("<FocusIn>", on_focus_in, add="+")
        entry_widget.bind("<KeyRelease>", on_key_release, add="+")

    _bind_date_entry(date_from_field["entry"], date_from_var)
    _bind_date_entry(date_to_field["entry"], date_to_var)

    quick_date_state = {"active": None}
    quick_date_buttons = {}

    def _set_quick_button_state(active_key):
        quick_date_state["active"] = active_key
        for key, button in quick_date_buttons.items():
            button["set_active"](key == active_key)

    def _set_date_range_by_quick_key(key):
        today = date.today()
        if key == "today":
            iso_today = today.isoformat()
            date_from_var.set(iso_today)
            date_to_var.set(iso_today)
        elif key == "7d":
            date_to_var.set(today.isoformat())
            date_from_var.set((today - timedelta(days=6)).isoformat())
        elif key == "30d":
            date_to_var.set(today.isoformat())
            date_from_var.set((today - timedelta(days=29)).isoformat())
        elif key == "1y":
            date_to_var.set(today.isoformat())
            date_from_var.set((today - timedelta(days=365)).isoformat())
        elif key == "all":
            date_from_var.set("-")
            date_to_var.set("-")
        _set_quick_button_state(key)

    def _create_quick_button(parent, text, key):
        canvas = tk.Canvas(
            parent,
            bg=colors.SURFACE_ALT,
            highlightthickness=0,
            bd=0,
            height=24,
            cursor="hand2",
        )
        state = {"active": False}

        def _redraw(_event=None):
            canvas.delete("all")
            width = max(20, canvas.winfo_width())
            height = max(20, canvas.winfo_height())
            is_active = state["active"]
            fill_color = SF_PRIMARY if is_active else colors.SURFACE_ALT
            border_color = SF_PRIMARY if is_active else SF_INPUT_IDLE_BORDER
            text_color = colors.TEXT_INVERSE if is_active else SF_TEXT_DARK

            _draw_plain_rounded_rect(
                canvas,
                1,
                1,
                width - 1,
                height - 1,
                8,
                fill=fill_color,
                outline=border_color,
                border_width=1,
            )
            canvas.create_text(
                width / 2.0,
                height / 2.0,
                text=text,
                fill=text_color,
                font=app._font(9, "bold"),
                anchor="center",
                tags=("quick_btn",),
            )
            canvas.create_rectangle(0, 0, width, height, fill="", outline="", tags=("quick_btn",))

        def _apply_quick(_event=None):
            _set_date_range_by_quick_key(key)

        def _set_active(enabled):
            state["active"] = bool(enabled)
            _redraw()

        canvas.bind("<Configure>", _redraw, add="+")
        canvas.bind("<Button-1>", _apply_quick, add="+")
        canvas.tag_bind("quick_btn", "<Button-1>", _apply_quick)
        _redraw()
        return {
            "canvas": canvas,
            "set_active": _set_active,
        }

    for idx, (label_text, key) in enumerate([
        ("오늘", "today"),
        ("7일", "7d"),
        ("30일", "30d"),
        ("1년", "1y"),
        ("전체", "all"),
    ]):
        btn = _create_quick_button(date_quick_row, label_text, key)
        btn["canvas"].grid(row=0, column=idx, sticky="ew", padx=(0 if idx == 0 else 4, 0))
        quick_date_buttons[key] = btn

    _set_dropdown_icon(doc_type_field["toggle"], False)
    _set_dropdown_icon(file_type_field["toggle"], False)

    search_input.pack(fill="both", expand=True)
    clear_icon_button.place(relx=1.0, rely=0.5, x=-6, y=0, anchor="e")

    filter_label.pack(side="left", padx=(2, 0))
    filter_toggle_icon.pack(side="left", padx=(1, 0))

    app.root.bind("<Button-1>", _on_click_outside_search_box, add="+")

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

    def _draw_results_table():
        card_canvas = left_bottom_card
        card_width = max(100, card_canvas.winfo_width())
        full_height = max(100, card_canvas.winfo_height())
        card_height = max(100, full_height - 12)

        row_weights = [10.0, 7.5, 72.5, 10.0]
        row_colors = [colors.SURFACE_ALT, colors.SURFACE_ACCENT_SOFT, colors.SURFACE_ALT, colors.SURFACE_ALT]

        inner_padding = 8
        inner_x1, inner_y1 = inner_padding, inner_padding
        inner_x2, inner_y2 = card_width - inner_padding, card_height - inner_padding
        inner_height = max(1, inner_y2 - inner_y1)

        collapsed_top_height, _expanded_top_height, available_height = _compute_left_top_targets()
        baseline_bottom_height = max(1, int(available_height - collapsed_top_height))
        baseline_card_height = max(1, baseline_bottom_height - 12)
        baseline_inner_height = max(1, baseline_card_height - (inner_padding * 2))

        fixed_row1 = max(1, int(baseline_inner_height * (row_weights[0] / 100.0)))
        fixed_row2 = max(1, int(baseline_inner_height * (row_weights[1] / 100.0)))
        fixed_row4 = max(1, int(baseline_inner_height * (row_weights[3] / 100.0)))
        fixed_total = fixed_row1 + fixed_row2 + fixed_row4
        row3_height = max(1, inner_height - fixed_total)

        row_heights = [fixed_row1, fixed_row2, row3_height, fixed_row4]

        y_cursor = inner_y1
        divider_y = []
        for idx, row_height in enumerate(row_heights):
            y_next = y_cursor + row_height
            card_canvas.create_rectangle(
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
            card_canvas.create_line(inner_x1, y, inner_x2, y, fill=SF_BORDER, width=1)

        row1_top = inner_y1
        row1_bottom = row1_top + row_heights[0]
        row1_center_y = (row1_top + row1_bottom) // 2
        card_canvas.create_text(
            inner_x1 + 10,
            row1_center_y,
            text=search_result_count_var.get(),
            fill=SF_TEXT_MAIN,
            font=app._font(14, "bold"),
            anchor="w",
        )

        table_col_widths_pct = [5.0, 25.0, 10.0, 15.0, 10.0, 15.0, 5.0, 10.0, 5.0]
        row2_headers = [
            "",
            "문서명",
            "문서 유형",
            "문서 날짜",
            "업로더",
            "업로드 날짜",
            "크기",
            "파일 종류",
            "",
        ]

        row2_top = row1_bottom
        row2_bottom = row2_top + row_heights[1]
        row2_center_y = (row2_top + row2_bottom) // 2
        row2_inner_x1 = inner_x1 + 2
        row2_inner_x2 = inner_x2 - 2
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

        select_tag = "sf_result_select_all"
        unchecked_icon = result_table_icons.get("unchecked")
        checked_icon = result_table_icons.get("checked")

        def _update_select_all_icon():
            icon_checked = bool(result_table_state.get("select_all_checked", False))
            if select_icon_id is not None:
                next_icon = checked_icon if icon_checked else unchecked_icon
                if next_icon is not None:
                    card_canvas.itemconfigure(select_icon_id, image=next_icon)
            elif select_text_id is not None:
                card_canvas.itemconfigure(select_text_id, text="☑" if icon_checked else "□")

        def _toggle_select_all(_event=None):
            result_table_state["select_all_checked"] = not bool(result_table_state.get("select_all_checked", False))
            _update_select_all_icon()
            return "break"

        select_icon_id = None
        select_text_id = None
        if unchecked_icon is not None:
            select_icon_id = card_canvas.create_image(
                col_centers[0],
                row2_center_y,
                image=unchecked_icon,
                anchor="center",
                tags=(select_tag,),
            )
        else:
            select_text_id = card_canvas.create_text(
                col_centers[0],
                row2_center_y,
                text="□",
                fill=SF_TEXT_DARK,
                font=app._font(12, "bold"),
                anchor="center",
                tags=(select_tag,),
            )

        col1_x1 = row2_inner_x1
        col1_x2 = row2_inner_x1 + col_width_px[0]
        card_canvas.create_rectangle(
            col1_x1,
            row2_top,
            col1_x2,
            row2_bottom,
            fill="",
            outline="",
            tags=(select_tag,),
        )

        card_canvas.tag_bind(select_tag, "<Button-1>", _toggle_select_all)
        _update_select_all_icon()

        for idx, header_text in enumerate(row2_headers):
            if idx == 0 or not header_text:
                continue
            card_canvas.create_text(
                col_centers[idx],
                row2_center_y,
                text=header_text,
                fill=SF_TEXT_DARK,
                font=app._font(10),
                anchor="center",
            )

        row3_top = row2_bottom
        row3_bottom = row3_top + row_heights[2]
        row3_center_y = (row3_top + row3_bottom) // 2
        card_canvas.create_text(
            (inner_x1 + inner_x2) / 2.0,
            row3_center_y,
            text="검색 결과 데이터가 여기에 표시돼요.",
            fill=SF_TEXT_PLACEHOLDER,
            font=app._font(11),
            anchor="center",
        )

        # Keep icon references alive on the canvas.
        card_canvas.result_table_icons_ref = result_table_icons

    def _draw_search_box():
        bar_width = max(220, left_top_card.winfo_width() - (search_box_inset * 2))
        search_box_holder.place(
            x=search_box_inset,
            y=search_box_inset,
            width=bar_width,
            height=search_box_height,
        )

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

    def _on_screen_destroy(_event=None):
        _close_dropdown_popup("doc_type")
        _close_dropdown_popup("file_type")

    left_top_card.bind("<Destroy>", _on_screen_destroy, add="+")

    _set_filter_toggle_visuals(False)
    app.root.after_idle(_on_layout_change)