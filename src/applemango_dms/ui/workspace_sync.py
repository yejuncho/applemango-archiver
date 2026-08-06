import tkinter as tk

from applemango_dms.ui import colors
from applemango_dms.ui.workplace_menu import render_workspace_sidebar_nav

SYNC_PAGE_BG = colors.SURFACE_ALT
SYNC_CARD_BG = colors.SURFACE_ALT
SYNC_CARD_BORDER = colors.BORDER_LIGHT

SYNC_TEXT_TITLE = colors.TEXT_EMPHASIS
SYNC_TEXT_BODY = colors.TEXT_SUBTLE
SYNC_TEXT_LABEL = colors.TEXT_SECONDARY
SYNC_TEXT_VALUE = colors.TEXT_TINT

SYNC_BADGE_BG = colors.SURFACE_HOVER
SYNC_BADGE_BORDER = colors.BORDER

SYNC_HOVER_BG = colors.SURFACE_HOVER_SOFT

SYNC_BUTTON_PRIMARY_BG = colors.PRIMARY
SYNC_BUTTON_PRIMARY_HOVER = colors.PRIMARY_HOVER
SYNC_BUTTON_PRIMARY_TEXT = colors.TEXT_INVERSE

SYNC_BUTTON_DISABLED_BG = colors.SURFACE_HOVER
SYNC_BUTTON_DISABLED_BORDER = colors.BORDER
SYNC_BUTTON_DISABLED_TEXT = colors.TEXT_PLACEHOLDER

SYNC_PROGRESS_TRACK_BG = colors.SURFACE_HOVER
SYNC_PROGRESS_FILL_BG = colors.PROCESSING

SYNC_STATUS_OK = colors.SUCCESS
SYNC_STATUS_INFO = colors.PROCESSING
# Reuse the warm orange already present in the app's status accents.
SYNC_STATUS_WARN = "#f97316"
SYNC_STATUS_ERROR = colors.FAILED


def _create_rounded_card(app, parent, *, radius=16, height=None):
    canvas = tk.Canvas(parent, bg=parent.cget("bg"), highlightthickness=0, bd=0)
    if height is not None:
        canvas.configure(height=height)

    body = tk.Frame(canvas, bg=SYNC_CARD_BG, highlightthickness=0, bd=0)
    body_id = canvas.create_window(0, 0, window=body, anchor="nw")

    def redraw(_event=None):
        canvas.delete("card")

        width = max(120, int(canvas.winfo_width()))
        full_height = max(80, int(canvas.winfo_height()))

        x1, y1 = 2, 2
        x2, y2 = width - 4, full_height - 4
        app._smooth_rounded_rect(
            canvas,
            x1,
            y1,
            x2,
            y2,
            radius,
            fill=SYNC_CARD_BG,
            outline=SYNC_CARD_BORDER,
            width=1,
            tags="card",
        )

        inset = 16
        canvas.coords(body_id, inset, inset)
        canvas.itemconfigure(body_id, width=max(10, width - (inset * 2)), height=max(10, full_height - (inset * 2)))
        canvas.tag_lower("card")

    canvas.bind("<Configure>", redraw, add="+")
    canvas.after_idle(redraw)
    return canvas, body


def _create_status_badge(app, parent, text):
    badge = tk.Canvas(parent, width=96, height=32, bg=parent.cget("bg"), highlightthickness=0, bd=0)

    def redraw(_event=None):
        badge.delete("all")
        width = max(80, badge.winfo_width())
        height = max(24, badge.winfo_height())
        app._smooth_rounded_rect(
            badge,
            1,
            1,
            width - 1,
            height - 1,
            14,
            fill=SYNC_BADGE_BG,
            outline=SYNC_BADGE_BORDER,
            width=1,
        )
        badge.create_text(
            width / 2.0,
            height / 2.0,
            text=text,
            fill=SYNC_TEXT_LABEL,
            font=app._font(10, "bold"),
            anchor="center",
        )

    badge.bind("<Configure>", redraw, add="+")
    badge.after_idle(redraw)
    return badge


def _create_action_button(app, parent, text, command, *, enabled=True, primary=False, width=220, height=56):
    button = tk.Canvas(parent, width=width, height=height, bg=parent.cget("bg"), highlightthickness=0, bd=0, cursor="hand2" if enabled else "")
    state = {"enabled": bool(enabled), "hovered": False}

    def redraw():
        button.delete("all")
        btn_w = max(width, button.winfo_width())
        btn_h = max(height, button.winfo_height())

        if state["enabled"]:
            if primary:
                fill = SYNC_BUTTON_PRIMARY_HOVER if state["hovered"] else SYNC_BUTTON_PRIMARY_BG
                border = fill
                text_color = SYNC_BUTTON_PRIMARY_TEXT
            else:
                fill = SYNC_CARD_BG
                border = colors.BORDER
                text_color = SYNC_TEXT_VALUE
        else:
            fill = SYNC_BUTTON_DISABLED_BG
            border = SYNC_BUTTON_DISABLED_BORDER
            text_color = SYNC_BUTTON_DISABLED_TEXT

        app._smooth_rounded_rect(
            button,
            1,
            1,
            btn_w - 1,
            btn_h - 1,
            14,
            fill=fill,
            outline=border,
            width=1,
        )

        button.create_text(
            btn_w / 2.0,
            btn_h / 2.0,
            text=text,
            fill=text_color,
            font=app._font(12, "bold"),
            anchor="center",
        )

    def on_enter(_event=None):
        if not state["enabled"]:
            return
        state["hovered"] = True
        redraw()

    def on_leave(_event=None):
        if not state["enabled"]:
            return
        state["hovered"] = False
        redraw()

    def on_click(_event=None):
        if not state["enabled"]:
            return "break"
        command()
        return "break"

    button.bind("<Configure>", lambda _event: redraw(), add="+")
    button.bind("<Enter>", on_enter, add="+")
    button.bind("<Leave>", on_leave, add="+")
    button.bind("<Button-1>", on_click, add="+")

    button.after_idle(redraw)
    return button


def _draw_progress_bar(app, canvas, percent):
    canvas.delete("all")

    bar_width = max(120, canvas.winfo_width())
    bar_height = max(14, canvas.winfo_height())
    ratio = max(0.0, min(1.0, float(percent) / 100.0))

    app._smooth_rounded_rect(
        canvas,
        1,
        1,
        bar_width - 1,
        bar_height - 1,
        max(4, bar_height // 2),
        fill=SYNC_PROGRESS_TRACK_BG,
        outline=colors.BORDER,
        width=1,
    )

    if ratio > 0:
        fill_x2 = 1 + int((bar_width - 2) * ratio)
        fill_x2 = min(bar_width - 1, max(2, fill_x2))
        app._smooth_rounded_rect(
            canvas,
            1,
            1,
            fill_x2,
            bar_height - 1,
            max(4, bar_height // 2),
            fill=SYNC_PROGRESS_FILL_BG,
            outline="",
            width=0,
        )


def _create_result_row(app, parent, *, symbol, filename, description, color, is_last):
    row = tk.Frame(parent, bg=SYNC_CARD_BG, padx=10, pady=8, highlightthickness=0, bd=0)
    row.pack(fill="x")

    icon_canvas = tk.Canvas(row, width=22, height=22, bg=SYNC_CARD_BG, highlightthickness=0, bd=0)
    icon_canvas.pack(side="left", padx=(0, 10), pady=(2, 0))
    icon_canvas.create_oval(2, 2, 20, 20, fill=color, outline="")
    icon_canvas.create_text(11, 11, text=symbol, fill=colors.TEXT_INVERSE, font=app._font(10, "bold"), anchor="center")

    text_block = tk.Frame(row, bg=SYNC_CARD_BG)
    text_block.pack(side="left", fill="x", expand=True)

    filename_label = tk.Label(
        text_block,
        text=filename,
        font=app._font(11, "bold"),
        fg=SYNC_TEXT_VALUE,
        bg=SYNC_CARD_BG,
        anchor="w",
    )
    filename_label.pack(fill="x")

    desc_label = tk.Label(
        text_block,
        text=description,
        font=app._font(10),
        fg=SYNC_TEXT_LABEL,
        bg=SYNC_CARD_BG,
        anchor="w",
    )
    desc_label.pack(fill="x", pady=(3, 0))

    hover_widgets = [row, icon_canvas, text_block, filename_label, desc_label]

    def apply_bg(bg):
        row.configure(bg=bg)
        icon_canvas.configure(bg=bg)
        text_block.configure(bg=bg)
        filename_label.configure(bg=bg)
        desc_label.configure(bg=bg)

    def on_enter(_event=None):
        apply_bg(SYNC_HOVER_BG)

    def on_leave(_event=None):
        apply_bg(SYNC_CARD_BG)

    for widget in hover_widgets:
        widget.bind("<Enter>", on_enter, add="+")
        widget.bind("<Leave>", on_leave, add="+")

    if not is_last:
        divider = tk.Frame(parent, bg=colors.BORDER, height=1)
        divider.pack(fill="x", padx=10)


def _create_summary_box(app, parent, *, value, label):
    canvas = tk.Canvas(parent, bg=parent.cget("bg"), height=82, highlightthickness=0, bd=0)

    value_label = tk.Label(canvas, text=str(value), font=app._font(17, "bold"), fg=SYNC_TEXT_TITLE, bg=SYNC_CARD_BG)
    text_label = tk.Label(canvas, text=label, font=app._font(10), fg=SYNC_TEXT_LABEL, bg=SYNC_CARD_BG)

    value_window = canvas.create_window(0, 0, window=value_label, anchor="n")
    text_window = canvas.create_window(0, 0, window=text_label, anchor="n")

    def redraw(_event=None):
        canvas.delete("card")
        width = max(120, canvas.winfo_width())
        height = max(70, canvas.winfo_height())

        app._smooth_rounded_rect(
            canvas,
            1,
            1,
            width - 1,
            height - 1,
            12,
            fill=SYNC_CARD_BG,
            outline=colors.BORDER,
            width=1,
            tags="card",
        )

        canvas.coords(value_window, width / 2.0, 14)
        canvas.coords(text_window, width / 2.0, 48)
        canvas.tag_lower("card")

    canvas.bind("<Configure>", redraw, add="+")
    canvas.after_idle(redraw)
    return canvas, value_label


def show_sync_workspace_screen(app):
    shell = app._create_workspace_shell()
    app.root.title("애플망고 DMS - 워크스페이스 동기화")

    render_workspace_sidebar_nav(app, shell["sidebar"], "sync")

    outer = shell["content"]
    app._build_workspace_page_header(
        outer,
        "워크스페이스 동기화",
        "NAS 서버와 DMS 데이터베이스를 비교하여 누락되거나 불일치하는 파일 정보를 자동으로 연동할 수 있어요.",
    )

    board = tk.Frame(outer, bg=SYNC_PAGE_BG, highlightthickness=0, bd=0)
    board.pack(fill="both", expand=True, padx=0, pady=0)

    page = tk.Frame(board, bg=SYNC_PAGE_BG, highlightthickness=0, bd=0)
    page.pack(fill="both", expand=True, padx=15, pady=(12, 12))
    page.grid_columnconfigure(0, weight=1)
    page.grid_rowconfigure(1, weight=1)

    app.status_badge = None

    middle = tk.Frame(page, bg=SYNC_PAGE_BG)
    middle.grid(row=0, column=0, sticky="ew", pady=(0, 12))
    middle.grid_columnconfigure(0, weight=35)
    middle.grid_columnconfigure(1, weight=65)

    left_card_canvas, left_card = _create_rounded_card(app, middle, radius=16, height=320)
    left_card_canvas.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

    right_card_canvas, right_card = _create_rounded_card(app, middle, radius=16, height=320)
    right_card_canvas.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

    tk.Label(
        left_card,
        text="워크스페이스 상태",
        font=app._font(13, "bold"),
        fg=SYNC_TEXT_TITLE,
        bg=SYNC_CARD_BG,
        anchor="w",
    ).pack(fill="x")

    status_rows = tk.Frame(left_card, bg=SYNC_CARD_BG)
    status_rows.pack(fill="both", expand=True, pady=(12, 0))

    row_specs = [
        ("마지막 검사", "-", "last_scan_value"),
        ("마지막 동기화", "-", "last_sync_value"),
        ("인덱싱된 파일", "0", "indexed_count_value"),
        ("새로 발견된 파일", "0", "pending_count_value"),
        ("저장소에서 누락된 파일", "0", "missing_count_value"),
        ("오류", "0", "error_count_value"),
        ("상태", "대기 중", "state_value"),
    ]

    value_widgets = {}

    for index, (label_text, initial_value, attr_name) in enumerate(row_specs):
        row = tk.Frame(status_rows, bg=SYNC_CARD_BG)
        row.pack(fill="x", pady=(0, 9 if index < len(row_specs) - 1 else 0))

        tk.Label(
            row,
            text=label_text,
            font=app._font(10),
            fg=SYNC_TEXT_LABEL,
            bg=SYNC_CARD_BG,
            anchor="w",
        ).pack(fill="x")

        value_label = tk.Label(
            row,
            text=initial_value,
            font=app._font(12, "bold"),
            fg=SYNC_TEXT_VALUE,
            bg=SYNC_CARD_BG,
            anchor="w",
        )
        value_label.pack(fill="x", pady=(2, 0))
        value_widgets[attr_name] = value_label

    app.last_scan_value = value_widgets["last_scan_value"]
    app.last_sync_value = value_widgets["last_sync_value"]
    app.indexed_count_value = value_widgets["indexed_count_value"]
    app.pending_count_value = value_widgets["pending_count_value"]
    app.missing_count_value = value_widgets["missing_count_value"]
    app.error_count_value = value_widgets["error_count_value"]
    app.state_value = value_widgets["state_value"]

    tk.Label(
        right_card,
        text="동기화 작업",
        font=app._font(13, "bold"),
        fg=SYNC_TEXT_TITLE,
        bg=SYNC_CARD_BG,
        anchor="w",
    ).pack(fill="x")

    button_block = tk.Frame(right_card, bg=SYNC_CARD_BG)
    button_block.pack(fill="x", pady=(12, 0))

    def on_scan_click():
        print("[Placeholder] 워크스페이스 검사 버튼 클릭")

    def on_sync_click():
        print("[Placeholder] 동기화 적용 버튼 클릭")

    app.scan_button = _create_action_button(
        app,
        button_block,
        "워크스페이스 검사",
        on_scan_click,
        enabled=True,
        primary=True,
        width=220,
        height=56,
    )
    app.scan_button.pack(anchor="w")

    app.sync_button = _create_action_button(
        app,
        button_block,
        "동기화 적용",
        on_sync_click,
        enabled=False,
        primary=False,
        width=220,
        height=56,
    )
    app.sync_button.pack(anchor="w", pady=(20, 0))

    progress_block = tk.Frame(right_card, bg=SYNC_CARD_BG)
    progress_block.pack(fill="x", pady=(22, 0))

    tk.Label(
        progress_block,
        text="진행 상태",
        font=app._font(10),
        fg=SYNC_TEXT_LABEL,
        bg=SYNC_CARD_BG,
        anchor="w",
    ).pack(fill="x")

    app.progress_status_value = tk.Label(
        progress_block,
        text="대기 중",
        font=app._font(12, "bold"),
        fg=SYNC_TEXT_VALUE,
        bg=SYNC_CARD_BG,
        anchor="w",
    )
    app.progress_status_value.pack(fill="x", pady=(2, 8))

    app.progress_bar = tk.Canvas(progress_block, height=18, bg=SYNC_CARD_BG, highlightthickness=0, bd=0)
    app.progress_bar.pack(fill="x")

    app.progress_percent_value = tk.Label(
        progress_block,
        text="0%",
        font=app._font(10, "bold"),
        fg=SYNC_TEXT_LABEL,
        bg=SYNC_CARD_BG,
        anchor="e",
    )
    app.progress_percent_value.pack(fill="x", pady=(4, 10))

    tk.Label(
        progress_block,
        text="현재 작업",
        font=app._font(10),
        fg=SYNC_TEXT_LABEL,
        bg=SYNC_CARD_BG,
        anchor="w",
    ).pack(fill="x")

    app.current_task_value = tk.Label(
        progress_block,
        text="-",
        font=app._font(11, "bold"),
        fg=SYNC_TEXT_VALUE,
        bg=SYNC_CARD_BG,
        anchor="w",
    )
    app.current_task_value.pack(fill="x", pady=(2, 0))

    def redraw_progress(_event=None):
        _draw_progress_bar(app, app.progress_bar, 0)

    app.progress_bar.bind("<Configure>", redraw_progress, add="+")
    app.progress_bar.after_idle(redraw_progress)

    result_card_canvas, result_card = _create_rounded_card(app, page, radius=16)
    result_card_canvas.grid(row=1, column=0, sticky="nsew")

    tk.Label(
        result_card,
        text="동기화 결과",
        font=app._font(13, "bold"),
        fg=SYNC_TEXT_TITLE,
        bg=SYNC_CARD_BG,
        anchor="w",
    ).pack(fill="x")

    tk.Label(
        result_card,
        text="검사 및 동기화 과정에서 발견된 파일과 상태를 표시합니다.",
        font=app._font(10),
        fg=SYNC_TEXT_LABEL,
        bg=SYNC_CARD_BG,
        anchor="w",
    ).pack(fill="x", pady=(4, 10))

    list_shell = tk.Frame(result_card, bg=SYNC_CARD_BG, highlightthickness=1, highlightbackground=colors.BORDER, bd=0)
    list_shell.pack(fill="both", expand=True)

    list_canvas = tk.Canvas(list_shell, bg=SYNC_CARD_BG, highlightthickness=0, bd=0)
    list_scroll = tk.Scrollbar(list_shell, orient="vertical", command=list_canvas.yview)
    list_canvas.configure(yscrollcommand=list_scroll.set)

    list_canvas.pack(side="left", fill="both", expand=True)
    list_scroll.pack(side="right", fill="y")

    app.results_container = tk.Frame(list_canvas, bg=SYNC_CARD_BG)
    list_window_id = list_canvas.create_window((0, 0), window=app.results_container, anchor="nw")

    def sync_list_region(_event=None):
        list_canvas.configure(scrollregion=list_canvas.bbox("all"))

    def resize_list_inner(event):
        list_canvas.itemconfigure(list_window_id, width=max(10, int(event.width)))

    app.results_container.bind("<Configure>", sync_list_region, add="+")
    list_canvas.bind("<Configure>", resize_list_inner, add="+")

    placeholder_rows = [
        ("✓", "report.pdf", "이미 등록된 파일", SYNC_STATUS_OK),
        ("+", "quotation.docx", "새로운 파일 발견", SYNC_STATUS_INFO),
        ("!", "invoice.xlsx", "저장소에는 존재하지만 DB에 없음", SYNC_STATUS_WARN),
        ("✕", "duplicate.pdf", "파일 이름 충돌", SYNC_STATUS_ERROR),
        ("✓", "asset_manifest.csv", "이미 등록된 파일", SYNC_STATUS_OK),
        ("+", "summary_note.txt", "새로운 파일 발견", SYNC_STATUS_INFO),
        ("!", "archive_legacy.zip", "저장소에는 존재하지만 DB에 없음", SYNC_STATUS_WARN),
    ]

    total_rows = len(placeholder_rows)
    for index, (symbol, filename, description, color) in enumerate(placeholder_rows):
        _create_result_row(
            app,
            app.results_container,
            symbol=symbol,
            filename=filename,
            description=description,
            color=color,
            is_last=(index == total_rows - 1),
        )

    summary_strip = tk.Frame(result_card, bg=SYNC_PAGE_BG, highlightthickness=1, highlightbackground=colors.BORDER, bd=0)
    summary_strip.pack(fill="x", pady=(12, 0), ipady=10)
    summary_strip.grid_columnconfigure(0, weight=1, uniform="sync_summary")
    summary_strip.grid_columnconfigure(1, weight=1, uniform="sync_summary")
    summary_strip.grid_columnconfigure(2, weight=1, uniform="sync_summary")
    summary_strip.grid_columnconfigure(3, weight=1, uniform="sync_summary")

    summary_indexed_box, app.summary_indexed = _create_summary_box(app, summary_strip, value="0", label="인덱싱됨")
    summary_indexed_box.grid(row=0, column=0, sticky="ew", padx=(10, 6), pady=8)

    summary_new_box, app.summary_new = _create_summary_box(app, summary_strip, value="0", label="새 파일")
    summary_new_box.grid(row=0, column=1, sticky="ew", padx=6, pady=8)

    summary_missing_box, app.summary_missing = _create_summary_box(app, summary_strip, value="0", label="누락")
    summary_missing_box.grid(row=0, column=2, sticky="ew", padx=6, pady=8)

    summary_error_box, app.summary_errors = _create_summary_box(app, summary_strip, value="0", label="오류")
    summary_error_box.grid(row=0, column=3, sticky="ew", padx=(6, 10), pady=8)