import re
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import messagebox, simpledialog

import applemango_dms.config as config
import applemango_dms.state as state

from applemango_dms.ui import colors
from applemango_dms.ui.widgets import RoundedInput
from applemango_dms.ui.workplace_menu import (
    render_workspace_sidebar_nav,
)
from applemango_dms.utils.images import (
    load_svg_photo,
)

DT_SURFACE = colors.SURFACE_ALT
DT_CARD_BG = colors.SURFACE_ALT
DT_CARD_BORDER = colors.BORDER_LIGHT

DT_TEXT_TITLE = colors.TEXT_EMPHASIS
DT_TEXT_BODY = colors.TEXT_SUBTLE
DT_TEXT_MUTED = colors.TEXT_SECONDARY
DT_TEXT_VALUE = colors.TEXT_TINT
DT_TEXT_PRIMARY = colors.TEXT_PRIMARY

DT_PRIMARY = colors.SECONDARY_STRONG
DT_PRIMARY_HOVER = colors.SECONDARY_STRONG_HOVER
DT_SELECTED_BG = colors.SURFACE_HOVER_SOFT
DT_SELECTED_SEPARATOR = colors.SURFACE_HOVER_SOFT

DT_SUCCESS = colors.SUCCESS_STRONG
DT_DANGER = colors.FAILED_STRONG
DT_DISABLED_BG = colors.SURFACE_HOVER
DT_DISABLED_TEXT = colors.TEXT_PLACEHOLDER
DT_TEXT_ON_ACCENT = getattr(
    colors,
    "TEXT_ON_ACCENT",
    colors.TEXT_INVERSE,
)
DT_NUMBER_DESIGNATION_BG = getattr(
    colors,
    "NUMBER_DESIGNATION_BG",
    colors.SURFACE_HOVER,
)
DT_SUCCESS_SOFT = getattr(
    colors,
    "SUCCESS_SOFT",
    colors.SURFACE_HOVER_SOFT,
)

DT_CARD_RADIUS = 18
DT_CARD_GAP = 12

DT_ACTIVE_ROW_HEIGHT = 54
DT_TABLE_HEADER_HEIGHT = 38
DT_ADD_BUTTON_HEIGHT = 46
DT_VISIBLE_ACTIVE_ROWS = 5
DT_ACTIVE_TABLE_ROWS_WITH_ADD_BUTTON = 4
DT_VISIBLE_INACTIVE_ROWS = 1
DT_INACTIVE_CARD_MIN_HEIGHT = 146

DT_TABLE_COLUMN_WIDTHS = {
    "grip": 38,
    "order": 56,
    "icon": 48,
    "status": 94,
    "arrow": 42,
}

SEARCH_PLACEHOLDER = "문서 유형 검색..."

DOCUMENT_TYPE_ICON_DIR = (
    config.PROJECT_ROOT
    / "assets"
    / "icons"
    / "workspace"
    / "document_type"
)

DOCUMENT_TYPE_ICON_CATEGORIES = (
    "서류",
    "양식",
    "공문",
    "회계",
    "명부",
    "사진",
    "영상",
    "녹음",
    "디자인",
    "교육",
    "일정",
    "프로젝트",
    "홍보",
    "자산",
    "인사",
    "기록",
    "지도",
    "기타",
)

DOCUMENT_TYPE_ICON_COLORS = {
    "서류": "#4B5563",
    "양식": "#34A853",
    "공문": "#D14343",
    "회계": "#F59E0B",
    "명부": "#8B5CF6",
    "사진": "#3B82F6",
    "영상": "#4F46E5",
    "녹음": "#06B6D4",
    "디자인": "#EAB308",
    "교육": "#2E8B57",
    "일정": "#3447AA",
    "프로젝트": "#F97316",
    "홍보": "#EC4899",
    "자산": "#8B5E3C",
    "인사": "#7C3AED",
    "기록": "#9F1239",
    "지도": "#0F766E",
    "기타": "#9CA3AF",
}

DOCUMENT_TYPE_ICON_KEYWORDS = (
    (
        "공문",
        (
            "공문",
            "공증",
            "정관",
            "규정",
            "규칙",
            "내규",
            "증명서",
            "인증서",
            "허가서",
            "인가서",
            "법인서류",
        ),
    ),
    (
        "회계",
        (
            "회계",
            "청구서",
            "영수증",
            "결제",
            "세금계산서",
            "계산서",
            "견적서",
            "거래명세서",
            "지출",
            "수입",
            "예산",
            "결산",
            "송금",
            "입금",
            "출금",
            "급여",
            "후원금",
            "헌금",
            "재정보고",
        ),
    ),
    (
        "명부",
        (
            "명단",
            "명부",
            "연락처",
            "주소록",
            "회원목록",
            "회원명부",
            "교인명부",
            "학생명부",
            "출석부",
            "출석명단",
            "수강생",
        ),
    ),
    (
        "사진",
        (
            "사진",
            "이미지",
            "앨범",
            "스캔",
            "스크린샷",
            "캡처",
            "촬영사진",
        ),
    ),
    (
        "영상",
        (
            "영상",
            "동영상",
            "비디오",
            "영화",
            "촬영영상",
            "방송영상",
            "설교영상",
        ),
    ),
    (
        "녹음",
        (
            "녹음",
            "음성",
            "오디오",
            "음원",
            "인터뷰",
            "설교음원",
            "회의녹음",
        ),
    ),
    (
        "교육",
        (
            "교육",
            "교재",
            "강의",
            "강의자료",
            "수업",
            "수업자료",
            "학습",
            "시험",
            "시험자료",
            "교안",
            "교육자료",
            "훈련자료",
            "성경공부",
            "설교자료",
            "ppt",
            "강의ppt",
            "교육ppt",
            "교육영상",
        ),
    ),
    (
        "일정",
        (
            "일정",
            "일정표",
            "달력",
            "캘린더",
            "시간표",
            "스케줄",
            "행사일정",
            "행사계획",
        ),
    ),
    (
        "프로젝트",
        (
            "프로젝트",
            "사업계획",
            "사업문서",
            "캠페인",
            "건축",
            "공사",
            "선교계획",
            "사역계획",
            "사업제안",
        ),
    ),
    (
        "홍보",
        (
            "홍보",
            "포스터",
            "전단",
            "전단지",
            "브로슈어",
            "소식지",
            "뉴스레터",
            "광고",
            "현수막",
            "보도자료",
            "홍보물",
            "sns",
            "인스타",
            "facebook",
            "youtube",
            "thumbnail",
            "썸네일",
        ),
    ),
    (
        "자산",
        (
            "자산",
            "재고",
            "비품",
            "장비",
            "차량",
            "시설",
            "창고",
            "물품",
            "재물",
            "자산대장",
            "비품대장",
        ),
    ),
    (
        "인사",
        (
            "인사",
            "이력서",
            "지원서",
            "채용",
            "직원",
            "교직원",
            "봉사자",
            "사역자",
            "선교사",
            "임명",
            "발령",
            "인사평가",
            "근로계약",
        ),
    ),
    (
        "기록",
        (
            "기록",
            "회의록",
            "의사록",
            "일지",
            "연혁",
            "역사",
            "활동기록",
            "사역일지",
            "선교일지",
            "업무일지",
            "방문기록",
        ),
    ),
    (
        "지도",
        (
            "지도",
            "노선",
            "경로",
            "위치",
            "지리",
            "gis",
            "약도",
            "배치도",
        ),
    ),
    (
        "디자인",
        (
            "디자인",
            "명함",
            "로고",
            "시안",
            "그래픽",
            "디자인원본",
            "편집원본",
            "브랜드",
            "템플릿디자인",
            "ai",
            "psd",
            "figma",
            "illustrator",
        ),
    ),
    (
        "양식",
        (
            "양식",
            "서식",
            "공통서식",
            "신청양식",
            "신청서식",
            "빈양식",
            "폼",
        ),
    ),
    (
        "서류",
        (
            "서류",
            "문서",
            "보고서",
            "결재",
            "결재서류",
            "선적서류",
            "품의서",
            "동의서",
            "계약서",
            "협약서",
            "확인서",
            "각서",
            "시말서",
            "포기서",
            "신청서",
            "요청서",
            "제안서",
            "계획서",
            "결과보고",
            "업무보고",
            "공문서",
            "보고",
            "보고자료",
            "보고문",
            "회의자료",
            "회의안건",
            "발표자료",
        ),
    ),
)


def _normalize_document_type_text(value):
    text = str(value or "").strip().casefold()

    if not text:
        return ""

    return re.sub(
        r"[\s_\-./·ㆍ()[\]{}]+",
        "",
        text,
    )


def resolve_document_type_icon_category(name):
    normalized_name = _normalize_document_type_text(
        name
    )

    if not normalized_name:
        return "기타"

    # Exact category names always win.
    for category in DOCUMENT_TYPE_ICON_CATEGORIES:
        if normalized_name == (
            _normalize_document_type_text(category)
        ):
            return category

    # Then check specific aliases in priority order.
    for category, keywords in (
        DOCUMENT_TYPE_ICON_KEYWORDS
    ):
        for keyword in keywords:
            normalized_keyword = (
                _normalize_document_type_text(
                    keyword
                )
            )

            if (
                normalized_keyword
                and normalized_keyword
                in normalized_name
            ):
                return category

    return "기타"


def _create_icon_label(
    parent,
    *,
    image,
    bg,
    width=None,
    height=None,
):
    label = tk.Label(
        parent,
        image=image if image is not None else "",
        bg=bg,
        bd=0,
        highlightthickness=0,
    )

    if image is not None:
        label.image = image

    if width is not None:
        label.configure(width=width)

    if height is not None:
        label.configure(height=height)

    return label


def _create_status_badge(
    parent,
    app,
    *,
    text,
    kind,
):
    palette = {
        "active": {
            "bg": DT_SUCCESS_SOFT,
            "fg": colors.SUCCESS_STRONG,
        },
        "system": {
            "bg": colors.SURFACE_HOVER,
            "fg": colors.TEXT_SECONDARY,
        },
        "inactive": {
            "bg": colors.SURFACE_HOVER,
            "fg": colors.TEXT_PLACEHOLDER,
        },
    }

    selected = palette.get(
        kind,
        palette["inactive"],
    )

    badge = tk.Label(
        parent,
        text=text,
        font=app._font(11, "bold"),
        fg=selected["fg"],
        bg=selected["bg"],
        width=8,
        anchor="center",
        justify="center",
        padx=10,
        pady=4,
        bd=0,
        highlightthickness=0,
    )

    return badge


def _create_count_badge(
    app,
    parent,
    *,
    textvariable,
):
    badge_height = 28
    badge_radius = 10
    font_value = app._font(12, "bold")

    canvas = tk.Canvas(
        parent,
        bg=DT_CARD_BG,
        highlightthickness=0,
        bd=0,
        height=badge_height,
    )

    def _render(*_args):
        if not canvas.winfo_exists():
            return

        text_value = str(textvariable.get() or "")
        text_width = tkfont.Font(font=font_value).measure(text_value)
        badge_width = max(44, text_width + 20)

        canvas.configure(
            width=badge_width,
            height=badge_height,
        )
        canvas.delete("count_badge")

        app._smooth_rounded_rect(
            canvas,
            1,
            1,
            badge_width - 2,
            badge_height - 2,
            badge_radius,
            fill=DT_NUMBER_DESIGNATION_BG,
            outline=DT_NUMBER_DESIGNATION_BG,
            width=1,
            tags="count_badge",
        )

        canvas.create_text(
            int(badge_width / 2),
            int(badge_height / 2),
            text=text_value,
            font=font_value,
            fill=DT_TEXT_MUTED,
            tags="count_badge",
        )

    trace_id = textvariable.trace_add(
        "write",
        _render,
    )

    def _on_destroy(event):
        if event.widget is not canvas:
            return

        try:
            textvariable.trace_remove(
                "write",
                trace_id,
            )
        except Exception:
            pass

    canvas.bind(
        "<Destroy>",
        _on_destroy,
        add="+",
    )
    canvas.bind(
        "<Configure>",
        _render,
        add="+",
    )

    _render()
    return canvas


def _is_system_document_type(record):
    name = str(
        record.get("name") or ""
    ).strip()

    return name in {
        "기타",
        "미분류",
    }


def _filter_document_type_records(
    records,
    search_text,
):
    normalized_query = (
        _normalize_document_type_text(
            search_text
        )
    )

    if not normalized_query:
        return list(records)

    matched = []

    for record in records:
        normalized_name = (
            _normalize_document_type_text(
                record.get("name")
            )
        )

        if normalized_query in normalized_name:
            matched.append(record)

    return matched


def _load_svg_if_present(
    path,
    *,
    max_width,
    max_height,
    tint=None,
):
    try:
        if not Path(path).is_file():
            return None

        return load_svg_photo(
            path,
            max_width=max_width,
            max_height=max_height,
            tint=tint,
        )
    except Exception:
        return None


def _load_document_type_icons():
    icons = {}
    fallback_tint = DOCUMENT_TYPE_ICON_COLORS[
        "기타"
    ]

    for category in (
        DOCUMENT_TYPE_ICON_CATEGORIES
    ):
        category_tint = (
            DOCUMENT_TYPE_ICON_COLORS.get(
                category,
                fallback_tint,
            )
        )
        category_icon = _load_svg_if_present(
            DOCUMENT_TYPE_ICON_DIR
            / f"{category}.svg",
            max_width=24,
            max_height=24,
            tint=category_tint,
        )

        if category_icon is None:
            category_icon = _load_svg_if_present(
                DOCUMENT_TYPE_ICON_DIR
                / "doc_type"
                / f"{category}.svg",
                max_width=24,
                max_height=24,
                tint=category_tint,
            )

        icons[category] = category_icon

    action_icon_names = (
        "search",
        "exit",
        "cancel",
        "add",
        "grip",
        "lock",
        "edit",
        "deactivate",
        "recover",
        "move_up",
        "move_down",
        "info",
    )

    for icon_name in action_icon_names:
        icon_max = 22 if icon_name == "grip" else 18
        icons[icon_name] = _load_svg_if_present(
            DOCUMENT_TYPE_ICON_DIR
            / f"{icon_name}.svg",
            max_width=icon_max,
            max_height=icon_max,
        )

    if icons.get("add") is None:
        icons["add"] = _load_svg_if_present(
            DOCUMENT_TYPE_ICON_DIR
            / "plus.svg",
            max_width=18,
            max_height=18,
        )

    row_arrow_candidates = (
        config.PROJECT_ROOT
        / "assets"
        / "icons"
        / "workspace_selection"
        / "chevron_right.svg",
        config.PROJECT_ROOT
        / "assets"
        / "icons"
        / "workspace_selection"
        / "after.svg",
        config.PROJECT_ROOT
        / "assets"
        / "icons"
        / "workspace"
        / "search_files"
        / "after.svg",
    )

    icons["row_arrow"] = None

    for row_arrow_path in row_arrow_candidates:
        row_arrow_icon = _load_svg_if_present(
            row_arrow_path,
            max_width=14,
            max_height=14,
            tint=colors.TEXT_PRIMARY,
        )

        if row_arrow_icon is not None:
            icons["row_arrow"] = row_arrow_icon
            break

    return icons


def _load_document_type_records(app):
    workspace_id = getattr(
        state,
        "active_workspace_id",
        None,
    )

    if workspace_id is None:
        return {
            "workspace_id": None,
            "active": [],
            "inactive": [],
            "error": (
                "활성 워크스페이스 정보를 "
                "찾지 못했습니다."
            ),
        }

    try:
        records = app.db.list_document_types(
            workspace_id,
            include_inactive=True,
        )
    except Exception as exc:
        return {
            "workspace_id": workspace_id,
            "active": [],
            "inactive": [],
            "error": (
                "문서 유형 목록을 불러오지 "
                f"못했습니다.\n오류: {exc}"
            ),
        }

    active = [
        record
        for record in records
        if record.get("is_active")
    ]

    inactive = [
        record
        for record in records
        if not record.get("is_active")
    ]

    return {
        "workspace_id": workspace_id,
        "active": active,
        "inactive": inactive,
        "error": None,
    }


def _create_rounded_card(
    app,
    parent,
    *,
    radius=DT_CARD_RADIUS,
    inset=16,
):
    canvas = tk.Canvas(
        parent,
        bg=parent.cget("bg"),
        highlightthickness=0,
        bd=0,
    )

    body = tk.Frame(
        canvas,
        bg=DT_CARD_BG,
        highlightthickness=0,
        bd=0,
    )

    body_id = canvas.create_window(
        0,
        0,
        window=body,
        anchor="nw",
    )

    def redraw(_event=None):
        canvas.delete("card_surface")

        width = max(
            40,
            int(canvas.winfo_width()),
        )
        height = max(
            40,
            int(canvas.winfo_height()),
        )

        app._smooth_rounded_rect(
            canvas,
            1,
            1,
            width - 2,
            height - 2,
            radius,
            fill=DT_CARD_BG,
            outline=DT_CARD_BORDER,
            width=1,
            tags="card_surface",
        )

        canvas.coords(
            body_id,
            inset,
            inset,
        )

        canvas.itemconfigure(
            body_id,
            width=max(
                10,
                width - (inset * 2),
            ),
            height=max(
                10,
                height - (inset * 2),
            ),
        )

        canvas.tag_lower("card_surface")

    canvas.bind(
        "<Configure>",
        redraw,
        add="+",
    )
    canvas.after_idle(redraw)

    return {
        "canvas": canvas,
        "body": body,
        "redraw": redraw,
    }


def _configure_document_type_row_columns(
    frame,
):
    frame.grid_columnconfigure(
        0,
        minsize=DT_TABLE_COLUMN_WIDTHS[
            "grip"
        ],
        weight=0,
    )
    frame.grid_columnconfigure(
        1,
        minsize=DT_TABLE_COLUMN_WIDTHS[
            "order"
        ],
        weight=0,
    )
    frame.grid_columnconfigure(
        2,
        minsize=DT_TABLE_COLUMN_WIDTHS[
            "icon"
        ],
        weight=0,
    )
    frame.grid_columnconfigure(
        3,
        weight=1,
    )
    frame.grid_columnconfigure(
        4,
        minsize=DT_TABLE_COLUMN_WIDTHS[
            "status"
        ],
        weight=0,
    )
    frame.grid_columnconfigure(
        5,
        minsize=DT_TABLE_COLUMN_WIDTHS[
            "arrow"
        ],
        weight=0,
    )


def _bind_mousewheel_to_canvas(
    widget,
    canvas,
):
    def on_mousewheel(event):
        delta = getattr(
            event,
            "delta",
            0,
        )

        if delta:
            canvas.yview_scroll(
                int(-delta / 120),
                "units",
            )

        return "break"

    def bind_all(_event=None):
        canvas.bind_all(
            "<MouseWheel>",
            on_mousewheel,
        )

    def unbind_all(_event=None):
        canvas.unbind_all(
            "<MouseWheel>",
        )

    widget.bind(
        "<Enter>",
        bind_all,
        add="+",
    )
    widget.bind(
        "<Leave>",
        unbind_all,
        add="+",
    )


def _blend_hex(c1, c2, ratio):
    c1 = str(c1).lstrip("#")
    c2 = str(c2).lstrip("#")
    r1, g1, b1 = int(c1[0:2], 16), int(c1[2:4], 16), int(c1[4:6], 16)
    r2, g2, b2 = int(c2[0:2], 16), int(c2[2:4], 16), int(c2[4:6], 16)
    r = int(r1 + (r2 - r1) * ratio)
    g = int(g1 + (g2 - g1) * ratio)
    b = int(b1 + (b2 - b1) * ratio)
    return f"#{r:02x}{g:02x}{b:02x}"


def _draw_rounded_rect(canvas, x1, y1, x2, y2, radius, *, fill, outline, width=1, tags=""):
    r = max(1, int(min(radius, (x2 - x1) / 2, (y2 - y1) / 2)))

    canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline="", tags=tags)
    canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline="", tags=tags)
    canvas.create_oval(x1, y1, x1 + 2 * r, y1 + 2 * r, fill=fill, outline="", tags=tags)
    canvas.create_oval(x2 - 2 * r, y1, x2, y1 + 2 * r, fill=fill, outline="", tags=tags)
    canvas.create_oval(x1, y2 - 2 * r, x1 + 2 * r, y2, fill=fill, outline="", tags=tags)
    canvas.create_oval(x2 - 2 * r, y2 - 2 * r, x2, y2, fill=fill, outline="", tags=tags)

    if width > 0:
        canvas.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90, style="arc", outline=outline, width=width, tags=tags)
        canvas.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90, style="arc", outline=outline, width=width, tags=tags)
        canvas.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90, style="arc", outline=outline, width=width, tags=tags)
        canvas.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90, style="arc", outline=outline, width=width, tags=tags)
        canvas.create_line(x1 + r, y1, x2 - r, y1, fill=outline, width=width, tags=tags)
        canvas.create_line(x1 + r, y2, x2 - r, y2, fill=outline, width=width, tags=tags)
        canvas.create_line(x1, y1 + r, x1, y2 - r, fill=outline, width=width, tags=tags)
        canvas.create_line(x2, y1 + r, x2, y2 - r, fill=outline, width=width, tags=tags)


def _draw_horizontal_gradient_rounded(canvas, x1, y1, x2, y2, radius, start_color, end_color, *, tags=""):
    r = max(1, int(min(radius, (x2 - x1) / 2, (y2 - y1) / 2)))
    width_px = max(1, int(x2 - x1))

    for i in range(width_px):
        ratio = i / max(1, width_px - 1)
        color = _blend_hex(start_color, end_color, ratio)
        x = x1 + i
        if i < r:
            dx = r - i
            dy = int(r - max(0.0, (r * r - dx * dx)) ** 0.5)
        elif i > width_px - r:
            dx = i - (width_px - r)
            dy = int(r - max(0.0, (r * r - dx * dx)) ** 0.5)
        else:
            dy = 0

        canvas.create_line(x, y1 + dy, x, y2 - dy, fill=color, tags=tags)


def _create_primary_add_button(
    app,
    parent,
    *,
    text,
    icon_photo,
    height,
    corner_radius=11,
    command,
):
    canvas = tk.Canvas(
        parent,
        height=height,
        bg=DT_CARD_BG,
        highlightthickness=0,
        bd=0,
        cursor="arrow",
    )

    state = {
        "enabled": True,
        "hover": False,
        "command": command,
    }

    def _render():
        try:
            canvas.delete("add_btn")
            width = max(140, int(canvas.winfo_width()))
            draw_height = max(int(height), int(canvas.winfo_height()))

            if state["enabled"]:
                start = colors.PRIMARY
                end = (
                    colors.PRIMARY_HOVER
                    if not state["hover"]
                    else colors.PRIMARY_PRESSED
                )
                border = colors.PRIMARY_HOVER
                text_color = DT_TEXT_ON_ACCENT
                cursor = "hand2"
            else:
                start = colors.BORDER
                end = colors.BORDER
                border = colors.BORDER
                text_color = DT_DISABLED_TEXT
                cursor = "arrow"

            canvas.configure(cursor=cursor)

            _draw_horizontal_gradient_rounded(
                canvas,
                1,
                1,
                width - 1,
                draw_height - 1,
                corner_radius,
                start,
                end,
                tags="add_btn",
            )

            _draw_rounded_rect(
                canvas,
                1,
                1,
                width - 1,
                draw_height - 1,
                corner_radius,
                fill="",
                outline=border,
                width=1,
                tags="add_btn",
            )

            font_value = app._font(11, "bold")
            text_width = tkfont.Font(font=font_value).measure(text)
            icon_width = 0

            if icon_photo is not None:
                try:
                    icon_width = int(icon_photo.width())
                except Exception:
                    icon_width = 0

            icon_gap = 8 if icon_width > 0 else 0
            content_width = icon_width + icon_gap + text_width
            content_left = int((width - content_width) / 2)
            center_y = int(draw_height / 2)

            if icon_width > 0 and icon_photo is not None:
                canvas.create_image(
                    content_left + int(icon_width / 2),
                    center_y,
                    image=icon_photo,
                    tags="add_btn",
                )

            canvas.create_text(
                content_left + icon_width + icon_gap,
                center_y,
                text=text,
                anchor="w",
                fill=text_color,
                font=font_value,
                tags="add_btn",
            )
        except Exception:
            canvas.delete("add_btn")
            canvas.configure(
                cursor=("hand2" if state["enabled"] else "arrow")
            )
            canvas.create_rectangle(
                1,
                1,
                max(2, int(canvas.winfo_width()) - 1),
                max(2, int(canvas.winfo_height()) - 1),
                fill=(
                    colors.PRIMARY
                    if state["enabled"]
                    else colors.BORDER
                ),
                outline=(
                    colors.PRIMARY_HOVER
                    if state["enabled"]
                    else colors.BORDER
                ),
                width=1,
                tags="add_btn",
            )
            canvas.create_text(
                int(max(2, canvas.winfo_width()) / 2),
                int(max(2, canvas.winfo_height()) / 2),
                text=text,
                fill=(
                    DT_TEXT_ON_ACCENT
                    if state["enabled"]
                    else DT_DISABLED_TEXT
                ),
                font=app._font(11, "bold"),
                tags="add_btn",
            )

    def _on_enter(_event):
        state["hover"] = True
        _render()

    def _on_leave(_event):
        state["hover"] = False
        _render()

    def _on_click(_event):
        if state["enabled"] and callable(state["command"]):
            state["command"]()

    def set_enabled(enabled):
        state["enabled"] = bool(enabled)
        if not state["enabled"]:
            state["hover"] = False
        _render()

    def set_command(new_command):
        state["command"] = new_command

    canvas.bind("<Configure>", lambda _event: _render())
    canvas.bind("<Enter>", _on_enter)
    canvas.bind("<Leave>", _on_leave)
    canvas.bind("<Button-1>", _on_click)

    canvas.set_enabled = set_enabled
    canvas.set_command = set_command
    _render()
    return canvas


def _format_document_type_created_at(created_at):
    text = str(created_at or "").strip()

    if not text:
        return "정보 없음"

    return text.replace("T", " ").split(".")[0]


def _format_document_type_creator(record):
    _ = record
    return "정보 없음"


def _format_document_type_updated_at(record):
    _ = record
    return "정보 없음"


def _count_document_type_files(
    app,
    workspace_id,
    document_type_id,
):
    if workspace_id is None:
        return None

    try:
        page = app.db.search_files_page(
            workspace_id,
            filters={
                "document_type_id": int(
                    document_type_id
                )
            },
            limit=1,
            offset=0,
        )
    except Exception:
        return None

    try:
        return int(
            page.get("total_count", 0)
        )
    except Exception:
        return None


def show_document_type_management_screen(app):
    shell = app._create_workspace_shell()
    app.root.title(
        "애플망고 DMS - 문서 유형 관리"
    )

    render_workspace_sidebar_nav(
        app,
        shell["sidebar"],
        "doc_type",
    )

    outer = shell["content"]

    app._build_workspace_page_header(
        outer,
        "문서 유형 관리",
        (
            "해당 워크스페이스에서 사용하는 문서 유형을 "
            "추가, 수정, 정렬, 비활성화할 수 있어요."
        ),
    )

    board = tk.Frame(
        outer,
        bg=DT_SURFACE,
        highlightthickness=0,
        bd=0,
    )
    board.pack(
        fill="both",
        expand=True,
        padx=0,
        pady=0,
    )

    layout = tk.Frame(
        board,
        bg=DT_SURFACE,
        highlightthickness=0,
        bd=0,
    )
    layout.pack(
        fill="both",
        expand=True,
        padx=15,
        pady=(0, 8),
    )

    layout.grid_columnconfigure(
        0,
        weight=7,
        uniform="doc_type_columns",
    )
    layout.grid_columnconfigure(
        1,
        weight=3,
        uniform="doc_type_columns",
    )

    layout.grid_rowconfigure(
        0,
        weight=0,
        minsize=62,
    )
    layout.grid_rowconfigure(
        1,
        weight=5,
        minsize=342,
    )
    layout.grid_rowconfigure(
        2,
        weight=3,
        minsize=DT_INACTIVE_CARD_MIN_HEIGHT,
    )

    top_search_host = tk.Frame(
        layout,
        bg=DT_SURFACE,
        highlightthickness=0,
        bd=0,
    )

    middle_card = _create_rounded_card(
        app,
        layout,
        inset=16,
    )

    detail_card = _create_rounded_card(
        app,
        layout,
        inset=18,
    )

    bottom_card = _create_rounded_card(
        app,
        layout,
        inset=16,
    )

    top_search_host.grid(
        row=0,
        column=0,
        sticky="ew",
        padx=(6, DT_CARD_GAP // 2),
        pady=(0, DT_CARD_GAP // 2),
    )

    middle_card["canvas"].grid(
        row=1,
        column=0,
        sticky="nsew",
        padx=(6, DT_CARD_GAP // 2),
        pady=(0, DT_CARD_GAP // 2),
    )

    bottom_card["canvas"].grid(
        row=2,
        column=0,
        sticky="nsew",
        padx=(6, DT_CARD_GAP // 2),
        pady=(DT_CARD_GAP // 2, 0),
    )

    detail_card["canvas"].grid(
        row=0,
        column=1,
        rowspan=2,
        sticky="nsew",
        padx=(DT_CARD_GAP // 2, 0),
        pady=(0, DT_CARD_GAP // 2),
    )


    data_state = _load_document_type_records(
        app
    )

    icon_photos = _load_document_type_icons()

    layout._document_type_icon_photos = (
        icon_photos
    )
    layout._document_type_data_state = (
        data_state
    )

    screen_state = {
        "selected_document_type_id": None,
    }
    screen_state.update(
        {
            "dragging_document_type_id": None,
            "drag_section": None,
            "drag_section_state": None,
            "drag_indicator": None,
            "drop_index": None,
            "drag_pending_document_type_id": None,
            "drag_pending_section_state": None,
            "drag_start_x": None,
            "drag_start_y": None,
        }
    )
    layout._document_type_screen_state = (
        screen_state
    )

    reserved_name_values = getattr(
        app.db,
        "RESERVED_DOCUMENT_TYPE_NAMES",
        ("기타", "미분류"),
    )
    reserved_name_casefolds = {
        str(value).strip().casefold()
        for value in reserved_name_values
        if str(value or "").strip()
    }

    name_max_length = getattr(
        app.db,
        "DOCUMENT_TYPE_NAME_MAX_LENGTH",
        None,
    )

    if not isinstance(name_max_length, int):
        name_max_length = None

    def get_all_document_type_records():
        return [
            *data_state.get("active", []),
            *data_state.get("inactive", []),
        ]

    def get_document_type_record_by_id(document_type_id):
        for record in get_all_document_type_records():
            try:
                if int(record.get("id")) == int(
                    document_type_id
                ):
                    return record
            except Exception:
                continue

        return None

    search_body = top_search_host
    search_body.grid_columnconfigure(
        0,
        weight=1,
    )
    search_body.grid_rowconfigure(
        0,
        weight=1,
    )

    search_var = tk.StringVar(
        value=""
    )
    screen_state["search_var"] = search_var

    search_input_holder = tk.Frame(
        search_body,
        bg=DT_CARD_BG,
        highlightthickness=0,
        bd=0,
    )
    search_input_holder.grid(
        row=0,
        column=0,
        sticky="ew",
        padx=0,
        pady=0,
    )

    search_icon = icon_photos.get("search")

    search_input = RoundedInput(
        search_input_holder,
        textvariable=search_var,
        placeholder=SEARCH_PLACEHOLDER,
        width=260,
        height=48,
        corner_radius=12,
        font=app._font(11),
        foreground=colors.TEXT_NEUTRAL_DARK,
        placeholder_color=colors.TEXT_PLACEHOLDER,
        fill=DT_CARD_BG,
        border_color=colors.BORDER,
        focus_fill=DT_CARD_BG,
        focus_border_color=colors.PRIMARY_PRESSED,
        disabled_fill=DT_CARD_BG,
        disabled_foreground=colors.TEXT_PLACEHOLDER,
        leading_icon=search_icon,
        state="normal",
    )
    search_input.pack(
        fill="both",
        expand=True,
    )

    search_entry = search_input.entry
    search_entry.configure(
        insertbackground=colors.TEXT_NEUTRAL_DARK,
    )
    search_entry.grid_configure(
        padx=(6, 30),
    )

    clear_icon = _load_svg_if_present(
        DOCUMENT_TYPE_ICON_DIR / "exit.svg",
        max_width=16,
        max_height=16,
        tint=DT_TEXT_MUTED,
    )
    if clear_icon is None:
        clear_icon = icon_photos.get("exit")

    clear_button = tk.Button(
        search_input_holder,
        image=clear_icon if clear_icon is not None else "",
        text="" if clear_icon is not None else "×",
        font=app._font(11, "bold"),
        fg=DT_TEXT_MUTED,
        bg=DT_CARD_BG,
        activebackground=colors.SURFACE_HOVER_SOFT,
        activeforeground=DT_TEXT_TITLE,
        relief="flat",
        bd=0,
        highlightthickness=0,
        cursor="hand2",
        command=lambda: None,
    )

    if clear_icon is not None:
        clear_button.image = clear_icon

    clear_button.place(
        relx=1.0,
        rely=0.5,
        x=-15,
        y=0,
        anchor="e",
    )

    active_body = middle_card["body"]
    inactive_body = bottom_card["body"]

    table_states = {}
    screen_state["table_states"] = table_states
    screen_state["selected_document_type_record"] = None
    screen_state["document_count_by_type_id"] = {}

    screen_state[
        "search_placeholder_visible"
    ] = False
    screen_state[
        "suppress_search_trace"
    ] = False

    def build_document_type_table_section(
        parent,
        *,
        section_key,
        title_text,
        initial_count,
        include_add_button,
    ):
        header = tk.Frame(
            parent,
            bg=DT_CARD_BG,
        )
        header.pack(
            fill="x",
            pady=(0, (6 if include_add_button else 12)),
        )

        tk.Label(
            header,
            text=title_text,
            font=app._font(14, "bold"),
            fg=DT_TEXT_TITLE,
            bg=DT_CARD_BG,
        ).pack(side="left")

        count_var = tk.StringVar(
            value=f"{initial_count}개"
        )

        count_badge = _create_count_badge(
            app,
            header,
            textvariable=count_var,
        )
        count_badge.pack(
            side="left",
            padx=(8, 0),
        )

        table_shell = tk.Frame(
            parent,
            bg=DT_CARD_BG,
            highlightthickness=1,
            highlightbackground=DT_CARD_BORDER,
            bd=0,
        )

        visible_row_slots = (
            DT_ACTIVE_TABLE_ROWS_WITH_ADD_BUTTON
            if include_add_button
            else DT_VISIBLE_INACTIVE_ROWS
        )

        if include_add_button:
            table_shell.configure(
                height=(
                    DT_ACTIVE_ROW_HEIGHT
                    * visible_row_slots
                    + 2
                )
            )
            table_shell.pack(
                fill="x",
                expand=False,
                pady=(0, 2),
            )
            table_shell.pack_propagate(False)
        else:
            table_shell.configure(
                height=(
                    DT_ACTIVE_ROW_HEIGHT
                    * visible_row_slots
                    + 2
                )
            )
            table_shell.pack(
                fill="x",
                expand=False,
                pady=(0, 4),
            )
            table_shell.pack_propagate(False)

        viewport = tk.Frame(
            table_shell,
            bg=DT_CARD_BG,
            height=(
                DT_ACTIVE_ROW_HEIGHT
                * visible_row_slots
            ),
        )
        viewport.pack(
            fill="both",
            expand=True,
        )
        viewport.pack_propagate(False)

        canvas = tk.Canvas(
            viewport,
            bg=DT_CARD_BG,
            highlightthickness=0,
            bd=0,
        )
        canvas.pack(
            side="left",
            fill="both",
            expand=True,
        )

        rows_container = tk.Frame(
            canvas,
            bg=DT_CARD_BG,
        )

        rows_window = canvas.create_window(
            0,
            0,
            window=rows_container,
            anchor="nw",
        )

        def sync_scrollregion(_event=None):
            canvas.configure(
                scrollregion=canvas.bbox("all")
            )

        def sync_rows_width(event):
            canvas.itemconfigure(
                rows_window,
                width=event.width,
            )

        rows_container.bind(
            "<Configure>",
            sync_scrollregion,
        )
        canvas.bind(
            "<Configure>",
            sync_rows_width,
        )

        _bind_mousewheel_to_canvas(
            rows_container,
            canvas,
        )
        _bind_mousewheel_to_canvas(
            parent,
            canvas,
        )
        _bind_mousewheel_to_canvas(
            table_shell,
            canvas,
        )
        _bind_mousewheel_to_canvas(
            viewport,
            canvas,
        )

        section_state = {
            "section_key": section_key,
            "count_var": count_var,
            "rows_container": rows_container,
            "row_widgets": {},
            "ordered_ids": [],
            "source_count": 0,
            "canvas": canvas,
            "sync_scrollregion": sync_scrollregion,
            "table_shell": table_shell,
        }

        if include_add_button:
            add_button_height = int(round(32 * 1.25))

            add_button_slot = tk.Frame(
                parent,
                bg=DT_CARD_BG,
                highlightthickness=0,
                bd=0,
                height=add_button_height + 2,
            )
            add_button_slot.pack(
                side="bottom",
                fill="x",
                pady=(0, 0),
            )
            add_button_slot.pack_propagate(False)

            add_icon = _load_svg_if_present(
                config.PROJECT_ROOT
                / "assets"
                / "icons"
                / "workspace"
                / "document_type"
                / "plus.svg",
                max_width=18,
                max_height=18,
                tint=DT_TEXT_ON_ACCENT,
            )
            if add_icon is None:
                add_icon = icon_photos.get("add")

            add_button = _create_primary_add_button(
                app,
                add_button_slot,
                text="문서 유형 추가",
                icon_photo=add_icon,
                height=add_button_height,
                corner_radius=11,
                command=lambda: None,
            )
            add_button.pack(
                fill="x",
                padx=8,
                pady=(1, 0),
            )

            _bind_mousewheel_to_canvas(
                add_button_slot,
                canvas,
            )
            _bind_mousewheel_to_canvas(
                add_button,
                canvas,
            )

            section_state["add_button"] = add_button

        return section_state

    active_section = build_document_type_table_section(
        active_body,
        section_key="active",
        title_text="문서 유형 목록",
        initial_count=len(data_state["active"]),
        include_add_button=True,
    )
    table_states["active"] = active_section
    _bind_mousewheel_to_canvas(
        middle_card["canvas"],
        active_section["canvas"],
    )

    inactive_section = build_document_type_table_section(
        inactive_body,
        section_key="inactive",
        title_text="비활성 문서 유형",
        initial_count=len(data_state["inactive"]),
        include_add_button=False,
    )
    table_states["inactive"] = inactive_section

    add_button = active_section.get("add_button")

    detail_body = detail_card["body"]
    detail_widgets = {}
    screen_state["detail_widgets"] = detail_widgets

    tk.Label(
        detail_body,
        text="문서 유형 상세",
        font=app._font(13, "bold"),
        fg=DT_TEXT_TITLE,
        bg=DT_CARD_BG,
        anchor="w",
    ).pack(fill="x")

    detail_placeholder = tk.Label(
        detail_body,
        text="수정할 문서 유형을 선택해주세요.",
        font=app._font(10),
        fg=DT_TEXT_MUTED,
        bg=DT_CARD_BG,
        justify="center",
    )
    detail_placeholder.pack(
        fill="both",
        expand=True,
    )

    detail_content = tk.Frame(
        detail_body,
        bg=DT_CARD_BG,
    )

    detail_summary = tk.Frame(
        detail_content,
        bg=DT_CARD_BG,
    )
    detail_summary.pack(
        fill="x",
        pady=(0, 12),
    )

    summary_left = tk.Frame(
        detail_summary,
        bg=DT_CARD_BG,
    )
    summary_left.pack(
        side="left",
        fill="x",
        expand=True,
    )

    detail_icon = _create_icon_label(
        summary_left,
        image=None,
        bg=DT_CARD_BG,
    )
    detail_icon.pack(
        side="left",
        padx=(0, 10),
    )

    detail_title_row = tk.Frame(
        summary_left,
        bg=DT_CARD_BG,
    )
    detail_title_row.pack(
        side="left",
        fill="x",
        expand=True,
    )

    detail_title = tk.Label(
        detail_title_row,
        text="",
        font=app._font(14, "bold"),
        fg=DT_TEXT_TITLE,
        bg=DT_CARD_BG,
        anchor="w",
    )
    detail_title.pack(side="left")

    detail_lock_icon = icon_photos.get("lock")
    detail_lock = _create_icon_label(
        detail_title_row,
        image=detail_lock_icon,
        bg=DT_CARD_BG,
    )
    if detail_lock_icon is not None:
        detail_lock.image = detail_lock_icon
    detail_lock.pack(
        side="left",
        padx=(8, 0),
    )
    detail_lock.pack_forget()

    detail_status_holder = tk.Frame(
        detail_summary,
        bg=DT_CARD_BG,
    )
    detail_status_holder.pack(side="right")

    tk.Frame(
        detail_content,
        bg=DT_CARD_BORDER,
        height=1,
    ).pack(
        fill="x",
        pady=(0, 12),
    )

    metadata_grid = tk.Frame(
        detail_content,
        bg=DT_CARD_BG,
    )
    metadata_grid.pack(fill="x")

    metadata_rows = (
        ("order", "순서"),
        ("created", "생성일"),
        ("creator", "생성자"),
        ("count", "문서 수"),
        ("updated", "마지막 수정"),
    )

    metadata_values = {}

    for index, (meta_key, meta_title) in enumerate(
        metadata_rows
    ):
        tk.Label(
            metadata_grid,
            text=meta_title,
            font=app._font(10),
            fg=DT_TEXT_MUTED,
            bg=DT_CARD_BG,
            anchor="w",
        ).grid(
            row=index,
            column=0,
            sticky="w",
            pady=(0, 6),
        )

        value_label = tk.Label(
            metadata_grid,
            text="정보 없음",
            font=app._font(10, "bold"),
            fg=DT_TEXT_VALUE,
            bg=DT_CARD_BG,
            anchor="e",
        )
        value_label.grid(
            row=index,
            column=1,
            sticky="e",
            pady=(0, 6),
        )

        metadata_values[meta_key] = value_label

    metadata_grid.grid_columnconfigure(
        0,
        weight=0,
    )
    metadata_grid.grid_columnconfigure(
        1,
        weight=1,
    )

    tk.Frame(
        detail_content,
        bg=DT_CARD_BORDER,
        height=1,
    ).pack(
        fill="x",
        pady=(8, 12),
    )

    tk.Label(
        detail_content,
        text="작업",
        font=app._font(11, "bold"),
        fg=DT_TEXT_TITLE,
        bg=DT_CARD_BG,
        anchor="w",
    ).pack(
        fill="x",
        pady=(0, 10),
    )

    actions_box = tk.Frame(
        detail_content,
        bg=DT_CARD_BG,
    )
    actions_box.pack(fill="x")

    rename_button = tk.Button(
        actions_box,
        text="이름 수정",
        font=app._font(10, "bold"),
        relief="flat",
        bd=0,
        highlightthickness=0,
        cursor="hand2",
        pady=8,
        command=lambda: None,
    )
    rename_button.pack(
        fill="x",
        pady=(0, 8),
    )

    toggle_active_button = tk.Button(
        actions_box,
        text="비활성화",
        font=app._font(10, "bold"),
        relief="flat",
        bd=0,
        highlightthickness=1,
        cursor="hand2",
        pady=8,
        command=lambda: None,
    )
    toggle_active_button.pack(
        fill="x",
        pady=(0, 8),
    )

    move_up_button = tk.Button(
        actions_box,
        text="위로 이동",
        font=app._font(10, "bold"),
        relief="flat",
        bd=0,
        highlightthickness=1,
        cursor="hand2",
        pady=8,
        command=lambda: None,
    )
    move_up_button.pack(
        fill="x",
        pady=(0, 8),
    )

    move_down_button = tk.Button(
        actions_box,
        text="아래로 이동",
        font=app._font(10, "bold"),
        relief="flat",
        bd=0,
        highlightthickness=1,
        cursor="hand2",
        pady=8,
        command=lambda: None,
    )
    move_down_button.pack(fill="x")

    detail_widgets.update(
        {
            "placeholder": detail_placeholder,
            "content": detail_content,
            "icon": detail_icon,
            "title": detail_title,
            "lock": detail_lock,
            "status_holder": detail_status_holder,
            "meta_order": metadata_values["order"],
            "meta_created": metadata_values["created"],
            "meta_creator": metadata_values["creator"],
            "meta_count": metadata_values["count"],
            "meta_updated": metadata_values["updated"],
            "rename_button": rename_button,
            "toggle_active_button": toggle_active_button,
            "move_up_button": move_up_button,
            "move_down_button": move_down_button,
        }
    )

    def style_primary_action(button, text):
        button.configure(
            text=text,
            state="normal",
            cursor="hand2",
            fg=DT_TEXT_ON_ACCENT,
            bg=DT_PRIMARY,
            activeforeground=DT_TEXT_ON_ACCENT,
            activebackground=DT_PRIMARY_HOVER,
            highlightthickness=0,
        )

    def style_outline_action(
        button,
        *,
        text,
        fg,
        border,
        active_bg,
    ):
        button.configure(
            text=text,
            state="normal",
            cursor="hand2",
            fg=fg,
            bg=DT_CARD_BG,
            activeforeground=fg,
            activebackground=active_bg,
            highlightthickness=1,
            highlightbackground=border,
            highlightcolor=border,
            disabledforeground=DT_DISABLED_TEXT,
        )

    def style_disabled_action(button, text):
        button.configure(
            text=text,
            state="disabled",
            cursor="arrow",
            fg=DT_DISABLED_TEXT,
            bg=DT_DISABLED_BG,
            activeforeground=DT_DISABLED_TEXT,
            activebackground=DT_DISABLED_BG,
            disabledforeground=DT_DISABLED_TEXT,
            highlightthickness=1,
            highlightbackground=DT_CARD_BORDER,
            highlightcolor=DT_CARD_BORDER,
        )

    def set_detail_placeholder_visible(is_visible):
        if is_visible:
            detail_content.pack_forget()
            detail_placeholder.pack(
                fill="both",
                expand=True,
            )
            return

        detail_placeholder.pack_forget()
        detail_content.pack(
            fill="both",
            expand=True,
        )

    def refresh_document_type_detail(record):
        if record is None:
            set_detail_placeholder_visible(True)
            return

        set_detail_placeholder_visible(False)

        document_type_id = int(record["id"])
        name = str(
            record.get("name") or ""
        ).strip()
        is_system = _is_system_document_type(
            record
        )
        is_active = bool(record.get("is_active"))

        category = resolve_document_type_icon_category(
            name
        )
        category_icon = icon_photos.get(category)

        detail_widgets["icon"].configure(
            image=(
                category_icon
                if category_icon is not None
                else ""
            )
        )
        if category_icon is not None:
            detail_widgets["icon"].image = category_icon
        else:
            detail_widgets["icon"].image = None

        detail_widgets["title"].configure(
            text=name or "정보 없음"
        )

        if is_system:
            detail_widgets["lock"].pack(
                side="left",
                padx=(8, 0),
            )
        else:
            detail_widgets["lock"].pack_forget()

        for child in detail_widgets[
            "status_holder"
        ].winfo_children():
            child.destroy()

        if is_active:
            status_text = (
                "시스템 유형"
                if is_system
                else "사용 중"
            )
            status_kind = (
                "system"
                if is_system
                else "active"
            )
        else:
            status_text = "비활성"
            status_kind = "inactive"

        status_badge = _create_status_badge(
            detail_widgets["status_holder"],
            app,
            text=status_text,
            kind=status_kind,
        )
        status_badge.pack(side="right")

        if is_active:
            order_map = screen_state.get(
                "active_order_by_id",
                {},
            )
            row_last = len(data_state["active"])
        else:
            order_map = screen_state.get(
                "inactive_order_by_id",
                {},
            )
            row_last = len(data_state["inactive"])

        row_order = order_map.get(document_type_id)

        detail_widgets["meta_order"].configure(
            text=(
                str(row_order)
                if row_order is not None
                else "정보 없음"
            )
        )
        detail_widgets["meta_created"].configure(
            text=_format_document_type_created_at(
                record.get("created_at")
            )
        )
        detail_widgets["meta_creator"].configure(
            text=_format_document_type_creator(
                record
            )
        )

        count_cache = screen_state.get(
            "document_count_by_type_id",
            {},
        )
        if document_type_id not in count_cache:
            count_cache[document_type_id] = (
                _count_document_type_files(
                    app,
                    data_state.get("workspace_id"),
                    document_type_id,
                )
            )

        document_count = count_cache.get(
            document_type_id
        )

        detail_widgets["meta_count"].configure(
            text=(
                f"{document_count}개"
                if document_count is not None
                else "정보 없음"
            )
        )

        detail_widgets["meta_updated"].configure(
            text=_format_document_type_updated_at(
                record
            )
        )

        if (
            is_active
            and not is_system
            and not data_state["error"]
        ):
            style_primary_action(
                detail_widgets["rename_button"],
                "이름 수정",
            )
            detail_widgets[
                "rename_button"
            ].configure(
                command=on_rename_document_type,
            )
        else:
            style_disabled_action(
                detail_widgets["rename_button"],
                "이름 수정",
            )
            detail_widgets[
                "rename_button"
            ].configure(command=lambda: None)

        if is_active:
            if (
                is_system
                or len(data_state["active"]) <= 1
                or data_state["error"]
            ):
                style_disabled_action(
                    detail_widgets[
                        "toggle_active_button"
                    ],
                    "비활성화",
                )
                detail_widgets[
                    "toggle_active_button"
                ].configure(command=lambda: None)
            else:
                style_outline_action(
                    detail_widgets[
                        "toggle_active_button"
                    ],
                    text="비활성화",
                    fg=DT_DANGER,
                    border=DT_DANGER,
                    active_bg=colors.SURFACE_DANGER_HOVER,
                )
                detail_widgets[
                    "toggle_active_button"
                ].configure(
                    command=on_deactivate_document_type,
                )
        else:
            if is_system or data_state["error"]:
                style_disabled_action(
                    detail_widgets[
                        "toggle_active_button"
                    ],
                    "복원",
                )
                detail_widgets[
                    "toggle_active_button"
                ].configure(command=lambda: None)
            else:
                style_outline_action(
                    detail_widgets[
                        "toggle_active_button"
                    ],
                    text="복원",
                    fg=DT_SUCCESS,
                    border=DT_SUCCESS,
                    active_bg=DT_SUCCESS_SOFT,
                )
                detail_widgets[
                    "toggle_active_button"
                ].configure(
                    command=on_reactivate_document_type,
                )

        if (
            row_order is None
            or row_order <= 1
            or data_state["error"]
        ):
            style_disabled_action(
                detail_widgets["move_up_button"],
                "위로 이동",
            )
            detail_widgets[
                "move_up_button"
            ].configure(command=lambda: None)
        else:
            style_outline_action(
                detail_widgets["move_up_button"],
                text="위로 이동",
                fg=DT_TEXT_TITLE,
                border=DT_CARD_BORDER,
                active_bg=colors.SURFACE_HOVER,
            )
            detail_widgets[
                "move_up_button"
            ].configure(
                command=on_move_document_type_up,
            )

        if (
            row_order is None
            or row_order >= row_last
            or data_state["error"]
        ):
            style_disabled_action(
                detail_widgets["move_down_button"],
                "아래로 이동",
            )
            detail_widgets[
                "move_down_button"
            ].configure(command=lambda: None)
        else:
            style_outline_action(
                detail_widgets["move_down_button"],
                text="아래로 이동",
                fg=DT_TEXT_TITLE,
                border=DT_CARD_BORDER,
                active_bg=colors.SURFACE_HOVER,
            )
            detail_widgets[
                "move_down_button"
            ].configure(
                command=on_move_document_type_down,
            )

    screen_state[
        "refresh_document_type_detail"
    ] = refresh_document_type_detail

    def get_row_background(
        document_type_id,
    ):
        selected_id = screen_state.get(
            "selected_document_type_id"
        )

        if selected_id == document_type_id:
            return DT_SELECTED_BG

        return DT_CARD_BG

    def _apply_row_surface_state(
        row_data,
        *,
        background,
        separator_background,
    ):
        frame = row_data["frame"]
        frame.configure(
            bg=background,
            height=DT_ACTIVE_ROW_HEIGHT,
        )
        frame.pack_propagate(False)
        frame.grid_propagate(False)
        frame.grid_rowconfigure(
            0,
            minsize=DT_ACTIVE_ROW_HEIGHT,
            weight=1,
        )

        row_data["separator"].configure(
            bg=separator_background
        )

        for widget in row_data[
            "background_widgets"
        ]:
            try:
                widget.configure(
                    bg=background
                )
            except tk.TclError:
                pass

    def refresh_document_type_row_selection():
        selected_id = screen_state.get(
            "selected_document_type_id"
        )

        for section_state in table_states.values():
            for (
                document_type_id,
                row_data,
            ) in section_state[
                "row_widgets"
            ].items():
                is_selected = (
                    document_type_id == selected_id
                )

                background = (
                    DT_SELECTED_BG
                    if is_selected
                    else DT_CARD_BG
                )
                separator_background = (
                    DT_SELECTED_SEPARATOR
                    if is_selected
                    else DT_CARD_BORDER
                )
                _apply_row_surface_state(
                    row_data,
                    background=background,
                    separator_background=separator_background,
                )

    def _is_search_filter_active():
        if screen_state.get(
            "search_placeholder_visible"
        ):
            return False

        return bool(
            str(search_var.get() or "").strip()
        )

    def _show_reorder_filter_notice():
        messagebox.showinfo(
            "순서 변경 안내",
            (
                "검색 필터가 적용된 상태에서는 순서를 변경할 수 없어요.\n"
                "검색어를 지운 뒤 다시 시도해주세요."
            ),
            parent=app.root,
        )

    def _restore_document_type_row_background(
        section_state,
        document_type_id,
    ):
        if section_state is None:
            return

        row_data = section_state["row_widgets"].get(
            document_type_id
        )

        if row_data is None:
            return

        is_selected = (
            screen_state.get(
                "selected_document_type_id"
            )
            == document_type_id
        )

        background = (
            DT_SELECTED_BG
            if is_selected
            else DT_CARD_BG
        )
        separator_background = (
            DT_SELECTED_SEPARATOR
            if is_selected
            else DT_CARD_BORDER
        )
        _apply_row_surface_state(
            row_data,
            background=background,
            separator_background=separator_background,
        )

    def _is_widget_within_ancestor(
        widget,
        ancestor,
    ):
        current = widget

        while current is not None:
            if current == ancestor:
                return True

            try:
                parent_name = current.winfo_parent()
            except Exception:
                return False

            if not parent_name:
                return False

            try:
                current = current._nametowidget(
                    parent_name
                )
            except Exception:
                return False

        return False

    def _clear_drag_indicator():
        indicator = screen_state.get(
            "drag_indicator"
        )

        if indicator is not None:
            try:
                indicator.destroy()
            except tk.TclError:
                pass

        screen_state["drag_indicator"] = None
        screen_state["drop_index"] = None

    def _reset_drag_state(
        *,
        restore_selection=False,
    ):
        dragging_id = screen_state.get(
            "dragging_document_type_id"
        )
        drag_section_state = screen_state.get(
            "drag_section_state"
        )

        if (
            dragging_id is not None
            and drag_section_state is not None
        ):
            _restore_document_type_row_background(
                drag_section_state,
                dragging_id,
            )

        _clear_drag_indicator()

        screen_state[
            "dragging_document_type_id"
        ] = None
        screen_state["drag_section"] = None
        screen_state["drag_section_state"] = None
        screen_state[
            "drag_pending_document_type_id"
        ] = None
        screen_state[
            "drag_pending_section_state"
        ] = None
        screen_state["drag_start_x"] = None
        screen_state["drag_start_y"] = None
        screen_state["drop_index"] = None

        if restore_selection:
            refresh_document_type_row_selection()

    def _highlight_drag_row(
        section_state,
        document_type_id,
    ):
        row_data = section_state["row_widgets"].get(
            document_type_id
        )

        if row_data is None:
            return

        drag_bg = colors.SURFACE_HOVER
        _apply_row_surface_state(
            row_data,
            background=drag_bg,
            separator_background=DT_CARD_BORDER,
        )

    def _compute_drop_index_from_pointer(
        section_state,
        pointer_root_x,
        pointer_root_y,
    ):
        ordered_ids = list(
            section_state.get("ordered_ids")
            or []
        )

        if not ordered_ids:
            return None

        canvas = section_state["canvas"]
        rows_container = section_state[
            "rows_container"
        ]

        canvas.update_idletasks()
        rows_container.update_idletasks()

        canvas_left = int(canvas.winfo_rootx())
        canvas_right = (
            canvas_left + int(canvas.winfo_width())
        )

        if (
            pointer_root_x < canvas_left
            or pointer_root_x > canvas_right
        ):
            return None

        pointer_y_in_canvas = (
            pointer_root_y
            - int(canvas.winfo_rooty())
        )
        pointer_y = float(
            canvas.canvasy(pointer_y_in_canvas)
        )

        content_height = float(
            max(
                1,
                int(rows_container.winfo_height()),
            )
        )

        if pointer_y < 0 or pointer_y > content_height:
            return None

        for index, row_id in enumerate(
            ordered_ids
        ):
            row_data = section_state[
                "row_widgets"
            ].get(row_id)

            if row_data is None:
                continue

            row = row_data["frame"]
            row_mid = (
                float(row.winfo_y())
                + float(row.winfo_height()) / 2.0
            )

            if pointer_y < row_mid:
                return index

        return len(ordered_ids)

    def _show_drag_indicator(
        section_state,
        drop_index,
    ):
        ordered_ids = list(
            section_state.get("ordered_ids")
            or []
        )

        if not ordered_ids:
            _clear_drag_indicator()
            return

        rows_container = section_state[
            "rows_container"
        ]
        row_widgets = section_state[
            "row_widgets"
        ]

        indicator = screen_state.get(
            "drag_indicator"
        )

        if (
            indicator is None
            or not indicator.winfo_exists()
            or indicator.master != rows_container
        ):
            if indicator is not None:
                try:
                    indicator.destroy()
                except tk.TclError:
                    pass

            indicator = tk.Frame(
                rows_container,
                bg=DT_PRIMARY,
                height=2,
                bd=0,
                highlightthickness=0,
            )
            screen_state["drag_indicator"] = indicator

        clamped_index = max(
            0,
            min(int(drop_index), len(ordered_ids)),
        )

        if clamped_index <= 0:
            indicator_y = 0
        elif clamped_index >= len(ordered_ids):
            last_row = row_widgets.get(
                ordered_ids[-1]
            )

            if last_row is None:
                indicator_y = 0
            else:
                last_widget = last_row["frame"]
                indicator_y = int(
                    last_widget.winfo_y()
                    + last_widget.winfo_height()
                )
        else:
            before_row = row_widgets.get(
                ordered_ids[clamped_index]
            )

            if before_row is None:
                indicator_y = 0
            else:
                indicator_y = int(
                    before_row["frame"].winfo_y()
                )

        indicator.place(
            x=0,
            y=max(0, indicator_y - 1),
            relwidth=1.0,
            height=2,
        )

        screen_state["drop_index"] = clamped_index

    def _update_drag_indicator_from_pointer(
        section_state,
        pointer_root_x,
        pointer_root_y,
    ):
        drop_index = _compute_drop_index_from_pointer(
            section_state,
            pointer_root_x,
            pointer_root_y,
        )

        if drop_index is None:
            _clear_drag_indicator()
            return

        _show_drag_indicator(
            section_state,
            drop_index,
        )

    def _finish_document_type_drag(
        *,
        pointer_root_x,
        pointer_root_y,
    ):
        dragging_id = screen_state.get(
            "dragging_document_type_id"
        )
        drag_section = screen_state.get(
            "drag_section"
        )

        if dragging_id is None or drag_section is None:
            _reset_drag_state(
                restore_selection=True
            )
            return

        section_state = table_states.get(
            drag_section
        )
        drag_section_state = screen_state.get(
            "drag_section_state"
        )

        if drag_section_state is not None:
            section_state = drag_section_state

        if section_state is None:
            _reset_drag_state(
                restore_selection=True
            )
            return

        if _is_search_filter_active():
            _reset_drag_state(
                restore_selection=True
            )
            _show_reorder_filter_notice()
            return

        ordered_ids = list(
            section_state.get("ordered_ids")
            or []
        )
        source_count = int(
            section_state.get("source_count")
            or len(ordered_ids)
        )

        # Reordering requires all IDs in the section to be present.
        if (
            len(ordered_ids) <= 1
            or len(ordered_ids) != source_count
            or dragging_id not in ordered_ids
        ):
            _reset_drag_state(
                restore_selection=True
            )
            return

        _update_drag_indicator_from_pointer(
            section_state,
            pointer_root_x,
            pointer_root_y,
        )

        drop_index = screen_state.get("drop_index")
        if drop_index is None:
            _reset_drag_state(
                restore_selection=True
            )
            return

        current_index = ordered_ids.index(
            dragging_id
        )

        reordered_ids = list(ordered_ids)
        reordered_ids.pop(current_index)

        insertion_index = int(drop_index)
        if insertion_index > current_index:
            insertion_index -= 1

        insertion_index = max(
            0,
            min(
                insertion_index,
                len(reordered_ids),
            ),
        )

        reordered_ids.insert(
            insertion_index,
            dragging_id,
        )

        if reordered_ids == ordered_ids:
            _reset_drag_state(
                restore_selection=True
            )
            return

        workspace_id = data_state.get("workspace_id")
        if workspace_id is None:
            _reset_drag_state(
                restore_selection=True
            )
            return

        try:
            app.db.reorder_document_type_group(
                workspace_id,
                reordered_ids,
                is_active=(drag_section == "active"),
            )
        except Exception as exc:
            _reset_drag_state(
                restore_selection=True
            )
            messagebox.showerror(
                "문서 유형 순서 변경",
                format_document_type_action_error(exc),
                parent=app.root,
            )
            return

        _reset_drag_state(
            restore_selection=False
        )
        reload_document_type_screen(
            preferred_selected_id=dragging_id,
        )

    def ensure_selected_document_type_row_visible():
        selected_id = screen_state.get(
            "selected_document_type_id"
        )

        if selected_id is None:
            return

        for section_state in table_states.values():
            row_data = section_state[
                "row_widgets"
            ].get(selected_id)

            if row_data is None:
                continue

            canvas = section_state["canvas"]
            rows_container = section_state[
                "rows_container"
            ]
            row_widget = row_data["frame"]

            canvas.update_idletasks()
            rows_container.update_idletasks()
            row_widget.update_idletasks()

            content_height = max(
                1,
                int(rows_container.winfo_height()),
            )
            viewport_height = int(
                canvas.winfo_height()
            )

            if (
                viewport_height <= 0
                or content_height <= viewport_height
            ):
                return

            row_top = int(row_widget.winfo_y())
            row_bottom = row_top + int(
                row_widget.winfo_height()
            )

            viewport_top = int(canvas.canvasy(0))
            viewport_bottom = (
                viewport_top + viewport_height
            )

            if row_top < viewport_top:
                canvas.yview_moveto(
                    max(
                        0.0,
                        row_top / content_height,
                    )
                )
            elif row_bottom > viewport_bottom:
                target_top = (
                    row_bottom - viewport_height
                )
                canvas.yview_moveto(
                    min(
                        1.0,
                        max(
                            0.0,
                            target_top
                            / content_height,
                        ),
                    )
                )

            return

    def select_document_type(record):
        screen_state[
            "selected_document_type_id"
        ] = int(record["id"])

        screen_state[
            "selected_document_type_record"
        ] = record

        refresh_document_type_row_selection()
        refresh_document_type_detail(record)

    def create_document_type_row(
        section_key,
        record,
        display_order,
    ):
        section_state = table_states[section_key]
        rows_parent = section_state[
            "rows_container"
        ]

        document_type_id = int(record["id"])
        name = str(
            record.get("name") or ""
        ).strip()
        is_system = _is_system_document_type(
            record
        )

        row = tk.Frame(
            rows_parent,
            bg=get_row_background(document_type_id),
            height=DT_ACTIVE_ROW_HEIGHT,
            highlightthickness=0,
            bd=0,
        )
        row.pack(fill="x")
        row.pack_propagate(False)
        row.grid_propagate(False)
        row.grid_rowconfigure(
            0,
            minsize=DT_ACTIVE_ROW_HEIGHT,
            weight=1,
        )

        _configure_document_type_row_columns(row)

        separator = tk.Frame(
            rows_parent,
            bg=DT_CARD_BORDER,
            height=1,
        )
        separator.pack(fill="x")

        grip_icon = icon_photos.get("grip")
        grip_label = _create_icon_label(
            row,
            image=grip_icon,
            bg=get_row_background(document_type_id),
        )
        grip_label.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        order_label = tk.Label(
            row,
            text=str(display_order),
            font=app._font(11, "bold"),
            fg=DT_TEXT_MUTED,
            bg=get_row_background(document_type_id),
            padx=0,
            pady=0,
        )
        order_label.grid(
            row=0,
            column=1,
            padx=8,
        )

        category = resolve_document_type_icon_category(
            name
        )
        type_icon = icon_photos.get(category)
        type_icon_label = _create_icon_label(
            row,
            image=type_icon,
            bg=get_row_background(document_type_id),
        )
        type_icon_label.grid(
            row=0,
            column=2,
            padx=(4, 8),
        )

        name_cell = tk.Frame(
            row,
            bg=get_row_background(document_type_id),
        )
        name_cell.grid(
            row=0,
            column=3,
            sticky="nsew",
        )

        name_label = tk.Label(
            name_cell,
            text=name,
            font=app._font(11, "bold"),
            fg=DT_TEXT_TITLE,
            bg=get_row_background(document_type_id),
            anchor="w",
        )
        name_label.pack(side="left")

        lock_label = None
        if is_system:
            lock_icon = icon_photos.get("lock")
            lock_label = _create_icon_label(
                name_cell,
                image=lock_icon,
                bg=get_row_background(document_type_id),
            )
            lock_label.pack(
                side="left",
                padx=(8, 0),
            )

        if section_key == "inactive":
            status_text = "비활성"
            status_kind = "inactive"
        else:
            status_text = (
                "시스템 유형"
                if is_system
                else "사용 중"
            )
            status_kind = (
                "system"
                if is_system
                else "active"
            )

        status_badge = _create_status_badge(
            row,
            app,
            text=status_text,
            kind=status_kind,
        )
        status_badge.grid(
            row=0,
            column=4,
            padx=8,
        )

        arrow_icon = icon_photos.get("row_arrow")
        arrow_label = _create_icon_label(
            row,
            image=arrow_icon,
            bg=get_row_background(document_type_id),
        )
        if arrow_icon is None:
            arrow_label.configure(
                text="›",
                font=app._font(14, "bold"),
                fg=DT_TEXT_PRIMARY,
                anchor="e",
            )
        arrow_label.grid(
            row=0,
            column=5,
            sticky="nsew",
        )

        background_widgets = [
            row,
            grip_label,
            order_label,
            type_icon_label,
            name_cell,
            name_label,
            status_badge,
            arrow_label,
        ]
        if lock_label is not None:
            background_widgets.append(lock_label)

        hover_state = {
            "is_hovered": False,
        }

        def on_row_click(
            _event=None,
            selected_record=record,
        ):
            select_document_type(selected_record)
            return "break"

        def on_row_enter(_event=None):
            if screen_state.get(
                "dragging_document_type_id"
            ) == document_type_id:
                return

            if hover_state["is_hovered"]:
                return

            if (
                screen_state.get(
                    "selected_document_type_id"
                )
                == document_type_id
            ):
                return

            hover_bg = colors.SURFACE_HOVER
            _apply_row_surface_state(
                section_state["row_widgets"][document_type_id],
                background=hover_bg,
                separator_background=DT_CARD_BORDER,
            )

            hover_state["is_hovered"] = True

        def on_row_leave(_event=None):
            if screen_state.get(
                "dragging_document_type_id"
            ) == document_type_id:
                return

            if not hover_state["is_hovered"]:
                return

            def finalize_leave():
                hover_widget = app.root.winfo_containing(
                    app.root.winfo_pointerx(),
                    app.root.winfo_pointery(),
                )

                if _is_widget_within_ancestor(
                    hover_widget,
                    row,
                ):
                    return

                hover_state["is_hovered"] = False
                _restore_document_type_row_background(
                    section_state,
                    document_type_id,
                )

            app.root.after_idle(finalize_leave)

        def on_grip_press(
            event,
            selected_record=record,
        ):
            select_document_type(selected_record)

            if data_state.get("error"):
                return "break"

            if _is_search_filter_active():
                _show_reorder_filter_notice()
                return "break"

            ordered_ids = list(
                section_state.get("ordered_ids")
                or []
            )
            source_count = int(
                section_state.get("source_count")
                or len(ordered_ids)
            )

            if (
                len(ordered_ids) <= 1
                or len(ordered_ids) != source_count
                or document_type_id not in ordered_ids
            ):
                return "break"

            screen_state[
                "drag_pending_document_type_id"
            ] = document_type_id
            screen_state[
                "drag_pending_section_state"
            ] = section_state
            screen_state["drag_start_x"] = int(
                event.x_root
            )
            screen_state["drag_start_y"] = int(
                event.y_root
            )

            return "break"

        def on_grip_motion(event):
            dragging_id = screen_state.get(
                "dragging_document_type_id"
            )

            if dragging_id == document_type_id:
                if (
                    screen_state.get(
                        "drag_section_state"
                    )
                    is not section_state
                ):
                    return "break"

                canvas = section_state["canvas"]
                pointer_y_in_canvas = (
                    int(event.y_root)
                    - int(canvas.winfo_rooty())
                )

                if pointer_y_in_canvas < 20:
                    canvas.yview_scroll(-1, "units")
                elif pointer_y_in_canvas > (
                    int(canvas.winfo_height()) - 20
                ):
                    canvas.yview_scroll(1, "units")

                _update_drag_indicator_from_pointer(
                    section_state,
                    int(event.x_root),
                    int(event.y_root),
                )

                _highlight_drag_row(
                    section_state,
                    document_type_id,
                )

                return "break"

            if screen_state.get(
                "drag_pending_document_type_id"
            ) != document_type_id:
                return "break"

            if (
                screen_state.get(
                    "drag_pending_section_state"
                )
                is not section_state
            ):
                return "break"

            start_x = screen_state.get("drag_start_x")
            start_y = screen_state.get("drag_start_y")

            if start_x is None or start_y is None:
                return "break"

            if (
                abs(int(event.x_root) - int(start_x)) < 5
                and abs(int(event.y_root) - int(start_y))
                < 5
            ):
                return "break"

            if _is_search_filter_active():
                _reset_drag_state(
                    restore_selection=True
                )
                _show_reorder_filter_notice()
                return "break"

            ordered_ids = list(
                section_state.get("ordered_ids")
                or []
            )
            source_count = int(
                section_state.get("source_count")
                or len(ordered_ids)
            )

            if (
                len(ordered_ids) <= 1
                or len(ordered_ids) != source_count
                or document_type_id not in ordered_ids
            ):
                _reset_drag_state(
                    restore_selection=True
                )
                return "break"

            screen_state[
                "drag_pending_document_type_id"
            ] = None
            screen_state[
                "drag_pending_section_state"
            ] = None
            screen_state[
                "dragging_document_type_id"
            ] = document_type_id
            screen_state["drag_section"] = section_key
            screen_state["drag_section_state"] = (
                section_state
            )

            current_index = ordered_ids.index(
                document_type_id
            )
            _highlight_drag_row(
                section_state,
                document_type_id,
            )
            _show_drag_indicator(
                section_state,
                current_index,
            )

            canvas = section_state["canvas"]
            pointer_y_in_canvas = (
                int(event.y_root)
                - int(canvas.winfo_rooty())
            )

            if pointer_y_in_canvas < 20:
                canvas.yview_scroll(-1, "units")
            elif pointer_y_in_canvas > (
                int(canvas.winfo_height()) - 20
            ):
                canvas.yview_scroll(1, "units")

            _update_drag_indicator_from_pointer(
                section_state,
                int(event.x_root),
                int(event.y_root),
            )

            _highlight_drag_row(
                section_state,
                document_type_id,
            )

            return "break"

        def on_grip_release(event):
            if screen_state.get(
                "drag_pending_document_type_id"
            ) == document_type_id:
                _reset_drag_state(
                    restore_selection=True
                )
                return "break"

            if screen_state.get(
                "dragging_document_type_id"
            ) != document_type_id:
                return "break"

            _finish_document_type_drag(
                pointer_root_x=int(event.x_root),
                pointer_root_y=int(event.y_root),
            )
            return "break"

        interactive_widgets = [
            row,
            order_label,
            type_icon_label,
            name_cell,
            name_label,
            status_badge,
            arrow_label,
        ]
        if lock_label is not None:
            interactive_widgets.append(lock_label)

        for widget in interactive_widgets:
            widget.bind(
                "<Button-1>",
                on_row_click,
                add="+",
            )
            widget.configure(cursor="hand2")

        hover_widgets = [
            row,
            grip_label,
            order_label,
            type_icon_label,
            name_cell,
            name_label,
            status_badge,
            arrow_label,
        ]
        if lock_label is not None:
            hover_widgets.append(lock_label)

        for hover_widget in hover_widgets:
            hover_widget.bind(
                "<Enter>",
                on_row_enter,
                add="+",
            )
            hover_widget.bind(
                "<Leave>",
                on_row_leave,
                add="+",
            )

        grip_label.bind(
            "<ButtonPress-1>",
            on_grip_press,
            add="+",
        )
        grip_label.bind(
            "<B1-Motion>",
            on_grip_motion,
            add="+",
        )
        grip_label.bind(
            "<ButtonRelease-1>",
            on_grip_release,
            add="+",
        )
        grip_label.configure(cursor="fleur")

        section_state["row_widgets"][
            document_type_id
        ] = {
            "frame": row,
            "separator": separator,
            "record": record,
            "background_widgets": background_widgets,
            "order_label": order_label,
            "hover_state": hover_state,
        }

        _apply_row_surface_state(
            section_state["row_widgets"][document_type_id],
            background=get_row_background(document_type_id),
            separator_background=DT_CARD_BORDER,
        )

        _bind_mousewheel_to_canvas(
            row,
            section_state["canvas"],
        )

    def render_active_document_type_rows():
        section_state = table_states["active"]
        section_state["source_count"] = len(
            data_state.get("active", [])
        )

        for child in section_state[
            "rows_container"
        ].winfo_children():
            child.destroy()

        section_state["row_widgets"].clear()
        section_state["ordered_ids"] = []

        query = ""
        if not screen_state.get(
            "search_placeholder_visible"
        ):
            query = search_var.get()

        if data_state["error"]:
            section_state["count_var"].set("0개")
            tk.Label(
                section_state["rows_container"],
                text=data_state["error"],
                font=app._font(10),
                fg=DT_DANGER,
                bg=DT_CARD_BG,
                justify="left",
                anchor="w",
                pady=20,
            ).pack(
                fill="both",
                expand=True,
                padx=12,
            )
            section_state["sync_scrollregion"]()
            return

        filtered_records = _filter_document_type_records(
            data_state["active"],
            query,
        )

        section_state["count_var"].set(
            f"{len(filtered_records)}개"
        )
        section_state["ordered_ids"] = [
            int(record["id"])
            for record in filtered_records
        ]

        if not filtered_records:
            empty_text = (
                "검색 결과가 없습니다."
                if query.strip()
                else "사용 중인 문서 유형이 없습니다."
            )

            tk.Label(
                section_state["rows_container"],
                text=empty_text,
                font=app._font(10),
                fg=DT_TEXT_MUTED,
                bg=DT_CARD_BG,
                pady=28,
            ).pack(
                fill="both",
                expand=True,
            )

            section_state["sync_scrollregion"]()
            return

        active_order_by_id = {
            int(record["id"]): index
            for index, record in enumerate(
                data_state["active"],
                start=1,
            )
        }
        screen_state[
            "active_order_by_id"
        ] = active_order_by_id

        for record in filtered_records:
            create_document_type_row(
                "active",
                record,
                active_order_by_id[
                    int(record["id"])
                ],
            )

        refresh_document_type_row_selection()
        section_state["sync_scrollregion"]()

    def render_inactive_document_type_rows():
        section_state = table_states["inactive"]
        section_state["source_count"] = len(
            data_state.get("inactive", [])
        )

        for child in section_state[
            "rows_container"
        ].winfo_children():
            child.destroy()

        section_state["row_widgets"].clear()
        section_state["ordered_ids"] = []

        query = ""
        if not screen_state.get(
            "search_placeholder_visible"
        ):
            query = search_var.get()

        if data_state["error"]:
            section_state["count_var"].set("0개")
            tk.Label(
                section_state["rows_container"],
                text=data_state["error"],
                font=app._font(10),
                fg=DT_DANGER,
                bg=DT_CARD_BG,
                justify="left",
                anchor="w",
                pady=20,
            ).pack(
                fill="both",
                expand=True,
                padx=12,
            )
            section_state["sync_scrollregion"]()
            return

        inactive_order_by_id = {
            int(record["id"]): index
            for index, record in enumerate(
                data_state["inactive"],
                start=1,
            )
        }
        screen_state[
            "inactive_order_by_id"
        ] = inactive_order_by_id

        filtered_records = _filter_document_type_records(
            data_state["inactive"],
            query,
        )

        section_state["count_var"].set(
            f"{len(filtered_records)}개"
        )
        section_state["ordered_ids"] = [
            int(record["id"])
            for record in filtered_records
        ]

        if not filtered_records:
            tk.Label(
                section_state["rows_container"],
                text=(
                    "검색 결과가 없습니다."
                    if query.strip()
                    else "비활성 문서 유형이 없습니다."
                ),
                font=app._font(10),
                fg=DT_TEXT_MUTED,
                bg=DT_CARD_BG,
                pady=28,
            ).pack(
                fill="both",
                expand=True,
            )
            section_state["sync_scrollregion"]()
            return

        for record in filtered_records:
            create_document_type_row(
                "inactive",
                record,
                inactive_order_by_id[
                    int(record["id"])
                ],
            )

        refresh_document_type_row_selection()
        section_state["sync_scrollregion"]()

    def style_add_button_enabled(enabled):
        if add_button is None:
            return

        if hasattr(add_button, "set_enabled"):
            add_button.set_enabled(enabled)
            return

        if enabled:
            add_button.configure(
                state="normal",
                cursor="hand2",
                fg=DT_TEXT_ON_ACCENT,
                bg=DT_PRIMARY,
                activeforeground=DT_TEXT_ON_ACCENT,
                activebackground=DT_PRIMARY_HOVER,
                disabledforeground=DT_DISABLED_TEXT,
            )
            return

        add_button.configure(
            state="disabled",
            cursor="arrow",
            fg=DT_DISABLED_TEXT,
            bg=DT_DISABLED_BG,
            activeforeground=DT_DISABLED_TEXT,
            activebackground=DT_DISABLED_BG,
            disabledforeground=DT_DISABLED_TEXT,
        )

    def validate_document_type_name_input(
        raw_name,
        *,
        current_record=None,
    ):
        candidate_name = str(raw_name or "").strip()

        if not candidate_name:
            return None, "문서 유형 이름을 입력해주세요."

        if (
            name_max_length is not None
            and len(candidate_name) > name_max_length
        ):
            return (
                None,
                (
                    "문서 유형 이름은 "
                    f"최대 {name_max_length}자까지 입력할 수 있어요."
                ),
            )

        if (
            candidate_name.casefold()
            in reserved_name_casefolds
        ):
            return (
                None,
                (
                    "'기타'와 '미분류'는 시스템 예약 유형이라 "
                    "직접 생성하거나 이름을 바꿀 수 없어요."
                ),
            )

        current_id = None
        if current_record is not None:
            try:
                current_id = int(current_record["id"])
            except Exception:
                current_id = None

        candidate_key = candidate_name.casefold()

        for existing in get_all_document_type_records():
            existing_name = str(
                existing.get("name") or ""
            ).strip()

            if not existing_name:
                continue

            if existing_name.casefold() != candidate_key:
                continue

            try:
                existing_id = int(existing["id"])
            except Exception:
                existing_id = None

            if (
                current_id is not None
                and existing_id == current_id
            ):
                continue

            return (
                None,
                "같은 이름의 문서 유형이 이미 존재합니다.",
            )

        return candidate_name, None

    def format_document_type_action_error(exc):
        text = str(exc or "").strip()

        mapping = {
            "Reserved document type names are managed internally.": (
                "'기타'와 '미분류'는 시스템 예약 유형이라 "
                "직접 생성하거나 이름을 바꿀 수 없어요."
            ),
            "Document type name already exists.": (
                "같은 이름의 문서 유형이 이미 존재합니다."
            ),
            "Active document type not found.": (
                "선택한 문서 유형을 찾지 못했습니다. "
                "목록을 새로고침해 주세요."
            ),
            "Document type not found.": (
                "선택한 문서 유형을 찾지 못했습니다."
            ),
            "Reserved document type cannot be deactivated.": (
                "시스템 예약 문서 유형은 비활성화할 수 없습니다."
            ),
            "Document type is still used by active files.": (
                "활성 파일에서 사용 중인 문서 유형은 "
                "비활성화할 수 없습니다."
            ),
        }

        return mapping.get(text, text or "알 수 없는 오류")

    def reload_document_type_screen(
        *,
        preferred_selected_id=None,
    ):
        _reset_drag_state(
            restore_selection=False
        )

        refreshed_state = _load_document_type_records(app)

        data_state.clear()
        data_state.update(refreshed_state)

        layout._document_type_data_state = data_state

        screen_state[
            "document_count_by_type_id"
        ].clear()

        render_active_document_type_rows()
        render_inactive_document_type_rows()

        style_add_button_enabled(
            not bool(data_state.get("error"))
        )

        target_id = (
            preferred_selected_id
            if preferred_selected_id is not None
            else screen_state.get(
                "selected_document_type_id"
            )
        )

        target_record = None
        if target_id is not None:
            target_record = get_document_type_record_by_id(
                target_id
            )

        if target_record is None:
            screen_state[
                "selected_document_type_id"
            ] = None
            screen_state[
                "selected_document_type_record"
            ] = None
            refresh_document_type_row_selection()
            refresh_document_type_detail(None)
            return

        screen_state[
            "selected_document_type_id"
        ] = int(target_record["id"])
        screen_state[
            "selected_document_type_record"
        ] = target_record

        refresh_document_type_row_selection()
        refresh_document_type_detail(target_record)
        app.root.after_idle(
            ensure_selected_document_type_row_visible
        )

    def on_add_document_type():
        if data_state.get("error"):
            messagebox.showerror(
                "문서 유형 추가",
                (
                    "문서 유형 목록을 먼저 불러와야 합니다.\n"
                    "잠시 후 다시 시도해 주세요."
                ),
                parent=app.root,
            )
            return

        workspace_id = data_state.get("workspace_id")

        if workspace_id is None:
            messagebox.showerror(
                "문서 유형 추가",
                "활성 워크스페이스 정보를 찾을 수 없습니다.",
                parent=app.root,
            )
            return

        raw_name = simpledialog.askstring(
            "문서 유형 추가",
            "새 문서 유형 이름을 입력해주세요.",
            parent=app.root,
        )

        if raw_name is None:
            return

        normalized_name, error_message = (
            validate_document_type_name_input(
                raw_name,
            )
        )

        if error_message:
            messagebox.showerror(
                "문서 유형 추가",
                error_message,
                parent=app.root,
            )
            return

        try:
            created_record = app.db.create_document_type(
                workspace_id,
                normalized_name,
            )
        except Exception as exc:
            messagebox.showerror(
                "문서 유형 추가",
                format_document_type_action_error(exc),
                parent=app.root,
            )
            return

        created_id = None
        try:
            created_id = int(created_record["id"])
        except Exception:
            created_id = None

        reload_document_type_screen(
            preferred_selected_id=created_id,
        )

    def on_rename_document_type():
        selected_record = screen_state.get(
            "selected_document_type_record"
        )

        if not selected_record:
            return

        workspace_id = data_state.get("workspace_id")
        if workspace_id is None:
            return

        current_name = str(
            selected_record.get("name") or ""
        ).strip()

        raw_name = simpledialog.askstring(
            "문서 유형 이름 변경",
            "새 문서 유형 이름을 입력해주세요.",
            initialvalue=current_name,
            parent=app.root,
        )

        if raw_name is None:
            return

        normalized_name, error_message = (
            validate_document_type_name_input(
                raw_name,
                current_record=selected_record,
            )
        )

        if error_message:
            messagebox.showerror(
                "문서 유형 이름 변경",
                error_message,
                parent=app.root,
            )
            return

        if (
            normalized_name is not None
            and normalized_name.casefold()
            == current_name.casefold()
        ):
            return

        try:
            app.db.rename_document_type(
                workspace_id,
                int(selected_record["id"]),
                normalized_name,
            )
        except Exception as exc:
            messagebox.showerror(
                "문서 유형 이름 변경",
                format_document_type_action_error(exc),
                parent=app.root,
            )
            return

        reload_document_type_screen(
            preferred_selected_id=int(
                selected_record["id"]
            ),
        )

    def on_deactivate_document_type():
        selected_record = screen_state.get(
            "selected_document_type_record"
        )

        if not selected_record:
            return

        workspace_id = data_state.get("workspace_id")
        if workspace_id is None:
            return

        if _is_system_document_type(selected_record):
            return

        if len(data_state.get("active", [])) <= 1:
            messagebox.showerror(
                "문서 유형 비활성화",
                (
                    "최소 1개의 활성 문서 유형은 유지되어야 해서 "
                    "마지막 유형은 비활성화할 수 없어요."
                ),
                parent=app.root,
            )
            return

        selected_name = str(
            selected_record.get("name") or ""
        ).strip()

        confirmed = messagebox.askyesno(
            "문서 유형 비활성화",
            (
                f"'{selected_name}' 문서 유형을 비활성화하시겠습니까?\n\n"
                "기존 파일의 분류는 유지되며\n"
                "새 문서에서는 선택할 수 없게 됩니다."
            ),
            parent=app.root,
        )

        if not confirmed:
            return

        active_ids = [
            int(record["id"])
            for record in data_state.get("active", [])
        ]

        current_id = int(selected_record["id"])
        next_active_id = None

        if current_id in active_ids:
            current_index = active_ids.index(current_id)

            if current_index + 1 < len(active_ids):
                next_active_id = active_ids[
                    current_index + 1
                ]
            elif current_index - 1 >= 0:
                next_active_id = active_ids[
                    current_index - 1
                ]

        try:
            app.db.deactivate_document_type(
                workspace_id,
                current_id,
            )
        except Exception as exc:
            messagebox.showerror(
                "문서 유형 비활성화",
                format_document_type_action_error(exc),
                parent=app.root,
            )
            return

        reload_document_type_screen(
            preferred_selected_id=next_active_id,
        )

    def on_reactivate_document_type():
        selected_record = screen_state.get(
            "selected_document_type_record"
        )

        if not selected_record:
            return

        workspace_id = data_state.get("workspace_id")
        if workspace_id is None:
            return

        selected_name = str(
            selected_record.get("name") or ""
        ).strip()

        confirmed = messagebox.askyesno(
            "문서 유형 복원",
            (
                f"'{selected_name}' 문서 유형을 다시 활성화하시겠습니까?"
            ),
            parent=app.root,
        )

        if not confirmed:
            return

        selected_id = int(selected_record["id"])

        try:
            app.db.reactivate_document_type(
                workspace_id,
                selected_id,
            )
        except Exception as exc:
            messagebox.showerror(
                "문서 유형 복원",
                format_document_type_action_error(exc),
                parent=app.root,
            )
            return

        reload_document_type_screen(
            preferred_selected_id=selected_id,
        )

    def _move_selected_document_type(
        direction,
    ):
        selected_record = screen_state.get(
            "selected_document_type_record"
        )

        if not selected_record:
            return

        if data_state.get("error"):
            return

        workspace_id = data_state.get("workspace_id")
        if workspace_id is None:
            return

        selected_id = int(selected_record["id"])
        is_active = bool(
            selected_record.get("is_active")
        )

        if is_active:
            order_map = screen_state.get(
                "active_order_by_id",
                {},
            )
            row_last = len(data_state.get("active", []))
        else:
            order_map = screen_state.get(
                "inactive_order_by_id",
                {},
            )
            row_last = len(
                data_state.get("inactive", [])
            )

        row_order = order_map.get(selected_id)

        if row_order is None:
            return

        if direction == "up" and row_order <= 1:
            return

        if (
            direction == "down"
            and row_order >= row_last
        ):
            return

        try:
            if direction == "up":
                app.db.move_document_type_up(
                    workspace_id,
                    selected_id,
                )
            else:
                app.db.move_document_type_down(
                    workspace_id,
                    selected_id,
                )
        except Exception as exc:
            messagebox.showerror(
                "문서 유형 순서 변경",
                format_document_type_action_error(exc),
                parent=app.root,
            )
            return

        reload_document_type_screen(
            preferred_selected_id=selected_id,
        )

    def on_move_document_type_up():
        _move_selected_document_type("up")

    def on_move_document_type_down():
        _move_selected_document_type("down")

    if add_button is not None:
        if hasattr(add_button, "set_command"):
            add_button.set_command(
                on_add_document_type,
            )
        else:
            add_button.configure(
                command=on_add_document_type,
            )

    def _on_click_outside_search_box(event):
        if not board.winfo_exists():
            return

        if _is_widget_within_ancestor(
            event.widget,
            search_input_holder,
        ):
            return

        if app.root.focus_get() is search_entry:
            board.focus_set()

    def on_search_changed(*_args):
        if screen_state.get(
            "suppress_search_trace"
        ):
            return

        render_active_document_type_rows()
        render_inactive_document_type_rows()

    def clear_search():
        search_var.set("")
        search_entry.focus_set()

    clear_button.configure(
        command=clear_search
    )

    search_var.trace_add(
        "write",
        on_search_changed,
    )

    root_click_binding_id = app.root.bind(
        "<Button-1>",
        _on_click_outside_search_box,
        add="+",
    )

    def _on_screen_destroy(_event=None):
        if root_click_binding_id:
            try:
                app.root.unbind(
                    "<Button-1>",
                    root_click_binding_id,
                )
            except Exception:
                pass

    top_search_host.bind(
        "<Destroy>",
        _on_screen_destroy,
        add="+",
    )

    reload_document_type_screen()
