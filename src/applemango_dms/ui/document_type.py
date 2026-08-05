import tkinter as tk

import applemango_dms.state as state
from applemango_dms.ui import colors
from applemango_dms.ui.workplace_menu import render_workspace_sidebar_nav

DT_SURFACE = colors.SURFACE_ALT
DT_CARD_BG = colors.SURFACE_ALT
DT_CARD_BORDER = colors.BORDER_LIGHT
DT_TEXT_TITLE = colors.TEXT_EMPHASIS
DT_TEXT_BODY = colors.TEXT_SUBTLE
DT_TEXT_MUTED = colors.TEXT_SECONDARY
DT_TEXT_VALUE = colors.TEXT_TINT
DT_DISABLED_BG = colors.SURFACE_HOVER
DT_DISABLED_BORDER = colors.BORDER
DT_DISABLED_TEXT = colors.TEXT_PLACEHOLDER


def _create_rounded_card(app, parent, *, radius=16):
    canvas = tk.Canvas(parent, bg=parent.cget("bg"), highlightthickness=0, bd=0)
    body = tk.Frame(canvas, bg=DT_CARD_BG, highlightthickness=0, bd=0)
    body_id = canvas.create_window(0, 0, window=body, anchor="nw")

    def redraw(_event=None):
        canvas.delete("card")

        width = max(180, int(canvas.winfo_width()))
        height = max(120, int(canvas.winfo_height()))

        app._smooth_rounded_rect(
            canvas,
            2,
            2,
            width - 3,
            height - 3,
            radius,
            fill=DT_CARD_BG,
            outline=DT_CARD_BORDER,
            width=1,
            tags="card",
        )

        inset = 16
        canvas.coords(body_id, inset, inset)
        canvas.itemconfigure(body_id, width=max(10, width - (inset * 2)), height=max(10, height - (inset * 2)))
        canvas.tag_lower("card")

    canvas.bind("<Configure>", redraw, add="+")
    canvas.after_idle(redraw)
    return canvas, body


def _load_document_type_names(app):
    workspace_id = getattr(state, "active_workspace_id", None)
    if workspace_id is None:
        return [], "활성 워크스페이스 정보를 찾지 못했습니다."

    try:
        records = app.db.get_document_types(workspace_id)
    except Exception:
        return [], "문서 유형 목록을 불러오지 못했습니다."

    names = [str(row.get("name", "")).strip() for row in records]
    names = [name for name in names if name]
    return names, None


def show_document_type_management_screen(app):
    shell = app._create_workspace_shell()
    app.root.title("애플망고 DMS - 문서 유형 관리")

    render_workspace_sidebar_nav(app, shell["sidebar"], "doc_type")

    outer = shell["content"]
    app._build_workspace_page_header(
        outer,
        "문서 유형 관리",
        "문서 유형 관리 기능 안내 문구를 여기에 작성해 주세요.",
    )

    board = tk.Frame(outer, bg=DT_SURFACE, highlightthickness=0, bd=0)
    board.pack(fill="both", expand=True, padx=0, pady=0)

    split = tk.Frame(board, bg=DT_SURFACE)
    split.pack(fill="both", expand=True, padx=10, pady=0)
    split.grid_columnconfigure(0, weight=3, uniform="doc_type_cols")
    split.grid_columnconfigure(1, weight=2, uniform="doc_type_cols")
    split.grid_rowconfigure(0, weight=1)

    left_card, left_body = _create_rounded_card(app, split)
    left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=0)

    right_card, right_body = _create_rounded_card(app, split)
    right_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=0)

    tk.Label(
        left_body,
        text="등록된 문서 유형",
        font=app._font(13, "bold"),
        fg=DT_TEXT_TITLE,
        bg=DT_CARD_BG,
        anchor="w",
    ).pack(fill="x")

    names, load_error = _load_document_type_names(app)
    count_text = f"총 {len(names)}개"
    if load_error:
        count_text = "데이터 불러오기 실패"

    tk.Label(
        left_body,
        text=count_text,
        font=app._font(10),
        fg=DT_TEXT_MUTED,
        bg=DT_CARD_BG,
        anchor="w",
    ).pack(fill="x", pady=(4, 10))

    list_shell = tk.Frame(left_body, bg=DT_CARD_BG)
    list_shell.pack(fill="both", expand=True)

    if load_error:
        tk.Label(
            list_shell,
            text=load_error,
            font=app._font(10),
            fg=colors.FAILED_STRONG,
            bg=DT_CARD_BG,
            anchor="w",
            justify="left",
        ).pack(fill="x", pady=(8, 0))
    elif not names:
        tk.Label(
            list_shell,
            text="이 워크스페이스에 등록된 문서 유형이 없습니다.",
            font=app._font(10),
            fg=DT_TEXT_BODY,
            bg=DT_CARD_BG,
            anchor="w",
            justify="left",
        ).pack(fill="x", pady=(8, 0))
    else:
        listbox = tk.Listbox(
            list_shell,
            activestyle="none",
            font=app._font(11),
            fg=DT_TEXT_VALUE,
            bg="#ffffff",
            selectbackground=colors.SURFACE_HOVER_SOFT,
            selectforeground=DT_TEXT_TITLE,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=colors.BORDER,
            highlightcolor=colors.BORDER,
            exportselection=False,
        )
        scrollbar = tk.Scrollbar(list_shell, orient="vertical", command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)

        for name in names:
            listbox.insert("end", name)

        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        if names:
            listbox.selection_set(0)

    tk.Label(
        right_body,
        text="관리 작업",
        font=app._font(13, "bold"),
        fg=DT_TEXT_TITLE,
        bg=DT_CARD_BG,
        anchor="w",
    ).pack(fill="x")

    tk.Label(
        right_body,
        text="문서 유형 추가/수정/비활성화 동작은 다음 단계에서 연결됩니다.",
        font=app._font(10),
        fg=DT_TEXT_BODY,
        bg=DT_CARD_BG,
        anchor="w",
        justify="left",
        wraplength=360,
    ).pack(fill="x", pady=(6, 14))

    for button_text in ("유형 추가", "이름 변경", "유형 비활성화"):
        tk.Button(
            right_body,
            text=button_text,
            state="disabled",
            bg=DT_DISABLED_BG,
            fg=DT_DISABLED_TEXT,
            activebackground=DT_DISABLED_BG,
            activeforeground=DT_DISABLED_TEXT,
            disabledforeground=DT_DISABLED_TEXT,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=DT_DISABLED_BORDER,
            highlightcolor=DT_DISABLED_BORDER,
            padx=14,
            pady=8,
            cursor="arrow",
        ).pack(fill="x", pady=(0, 8))

    tk.Label(
        right_body,
        text="추가 안내 문구 자리표시자",
        font=app._font(10),
        fg=DT_TEXT_MUTED,
        bg=DT_CARD_BG,
        anchor="w",
    ).pack(fill="x", pady=(8, 0))
