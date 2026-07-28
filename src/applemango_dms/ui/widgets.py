import time
import tkinter as tk

try:
    from PIL import Image, ImageDraw, ImageTk
    _PIL_AVAILABLE = True
except Exception:
    Image = None
    ImageDraw = None
    ImageTk = None
    _PIL_AVAILABLE = False

from applemango_dms.ui import colors

W_CARD_SURFACE = colors.SURFACE
W_CARD_SURFACE_HOVER = colors.SURFACE_ALT2
W_CARD_BORDER = colors.BORDER
W_CARD_BORDER_HOVER = colors.BORDER_SOFT
W_CARD_SHADOW_A = colors.SECONDARY_SOFT
W_CARD_SHADOW_B = colors.BORDER_SOFT

W_ICON_COLOR = colors.SECONDARY
W_TITLE_COLOR = colors.TEXT_TINT
W_TITLE_COLOR_ACTIVE = colors.TEXT_PRIMARY
W_CHEVRON_COLOR = colors.TEXT_PRIMARY
W_META_COLOR = colors.TEXT_PRIMARY

class WorkspaceCard(tk.Canvas):
    def __init__(self, parent, workspace_name, on_select=None, on_open=None, surface_bg=W_CARD_SURFACE, surface_hover_bg=W_CARD_SURFACE_HOVER, meta_icon_photos=None, folder_icon_photo=None, font_family="Segoe UI"):
        self._card_height = 216
        super().__init__(
            parent,
            bg=surface_bg,
            highlightthickness=0,
            bd=0,
            relief="flat",
            cursor="hand2",
            height=self._card_height,
        )

        self.workspace_name = workspace_name
        self.on_select = on_select
        self.on_open = on_open
        self.surface_bg = surface_bg
        self.surface_hover_bg = surface_hover_bg
        self.card_fill_bg = surface_bg
        self.meta_icon_photos = meta_icon_photos or {}
        self.folder_icon_photo = folder_icon_photo
        self.font_family = font_family

        self._select_progress = 0.0
        self._hover_progress = 0.0
        self._select_anim = None
        self._hover_anim = None
        self._tick_job = None
        self._press_y_root = None
        self._press_x_root = None
        self._dragged = False

        self.content = tk.Frame(self, bg=self.surface_bg)
        self.content_id = self.create_window(16, 10, window=self.content, anchor="nw")

        self.folder_icon = tk.Label(
            self.content,
            bg=self.surface_bg,
            fg=W_ICON_COLOR,
            anchor="w",
        )
        if self.folder_icon_photo is not None:
            self.folder_icon.configure(image=self.folder_icon_photo)
            self.folder_icon.image = self.folder_icon_photo
        else:
            self.folder_icon.configure(text="\U0001F4C1", font=("Segoe UI Emoji", 13))
        self.folder_icon.place(x=12, y=13, width=24, height=24)

        self.title_label = tk.Label(
            self.content,
            text=workspace_name,
            font=(self.font_family, 15, "bold"),
            bg=self.surface_bg,
            fg=W_TITLE_COLOR,
            anchor="w",
        )
        self.title_label.place(x=44, y=12, relwidth=1.0, height=28)

        self.chevron_label = tk.Label(
            self.content,
            text="\u203A",
            font=("Segoe UI Symbol", 16, "bold"),
            bg=self.surface_bg,
            fg=W_CHEVRON_COLOR,
            anchor="e",
        )
        self.chevron_label.place(relx=1.0, x=-18, y=14, width=18, height=22)

        self.meta_icon_labels = []
        for key, fallback in (("clock", "\U0001F551"), ("database", "\U0001F5C0"), ("file_stack", "\U0001F5CE")):
            photo = self.meta_icon_photos.get(key)
            label = tk.Label(self.content, bg=self.surface_bg, fg=W_META_COLOR, anchor="w")
            if photo is not None:
                label.configure(image=photo)
                label.image = photo
            else:
                label.configure(text=fallback, font=("Segoe UI Emoji", 10))
            self.meta_icon_labels.append(label)

        self.meta_labels = [
            tk.Label(self.content, text="", font=(self.font_family, 11), bg=self.surface_bg, fg=W_META_COLOR, anchor="w")
            for _ in range(3)
        ]
        meta_positions = (74, 106, 138)
        for icon_label, y in zip(self.meta_icon_labels, meta_positions):
            icon_label.place(x=12, y=y, width=20, height=20)
        self.meta_labels[0].place(x=44, y=74, relwidth=1.0, height=20)
        self.meta_labels[1].place(x=44, y=106, relwidth=1.0, height=20)
        self.meta_labels[2].place(x=44, y=138, relwidth=1.0, height=20)

        self.set_loading()
        self._bind_events()
        self.bind("<Configure>", self._on_configure, add="+")
        self._render()

    def _bind_events(self):
        widgets = [self, self.content, self.folder_icon, self.title_label, self.chevron_label] + self.meta_icon_labels + self.meta_labels
        for widget in widgets:
            widget.bind("<Enter>", self._on_enter, add="+")
            widget.bind("<Leave>", self._on_leave, add="+")
            widget.bind("<Button-1>", self._on_press, add="+")
            widget.bind("<B1-Motion>", self._on_drag, add="+")
            widget.bind("<ButtonRelease-1>", self._on_release, add="+")
            widget.bind("<Double-Button-1>", self._on_double_click, add="+")

    def _on_configure(self, _event):
        self._render()

    def _on_enter(self, _event):
        self._animate_to("hover", 1.0, 0.18)

    def _on_leave(self, _event):
        self._animate_to("hover", 0.0, 0.18)

    def _on_press(self, event):
        self._press_y_root = event.y_root
        self._press_x_root = event.x_root
        self._dragged = False

    def _on_drag(self, event):
        if self._press_y_root is None:
            return
        if abs(event.y_root - self._press_y_root) > 4 or abs(event.x_root - self._press_x_root) > 4:
            self._dragged = True

    def _on_release(self, _event):
        if not self._dragged and callable(self.on_select):
            self.on_select(self.workspace_name)
        self._press_y_root = None
        self._press_x_root = None
        self._dragged = False

    def _on_double_click(self, _event):
        if callable(self.on_open):
            self.on_open(self.workspace_name)

    def _animate_to(self, kind, target, duration):
        current = self._select_progress if kind == "select" else self._hover_progress
        anim = {
            "start": current,
            "target": float(target),
            "started": time.perf_counter(),
            "duration": max(0.001, float(duration)),
        }
        if kind == "select":
            self._select_anim = anim
        else:
            self._hover_anim = anim
        self._ensure_tick()

    def _ensure_tick(self):
        if self._tick_job is None:
            self._tick_job = self.after(16, self._tick)

    @staticmethod
    def _ease(progress):
        progress = max(0.0, min(1.0, progress))
        return progress * progress * (3.0 - 2.0 * progress)

    def _tick(self):
        self._tick_job = None
        now = time.perf_counter()
        active = False

        for kind, attr_name in (("select", "_select_progress"), ("hover", "_hover_progress")):
            anim = self._select_anim if kind == "select" else self._hover_anim
            if not anim:
                continue

            elapsed = (now - anim["started"]) / anim["duration"]
            if elapsed >= 1.0:
                setattr(self, attr_name, anim["target"])
                if kind == "select":
                    self._select_anim = None
                else:
                    self._hover_anim = None
            else:
                eased = self._ease(elapsed)
                value = anim["start"] + (anim["target"] - anim["start"]) * eased
                setattr(self, attr_name, value)
                active = True

        self._render()
        if active or self._select_anim or self._hover_anim:
            self._ensure_tick()

    @staticmethod
    def _hex_to_rgb(hex_color):
        value = hex_color.lstrip("#")
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)

    @staticmethod
    def _rgb_to_hex(rgb):
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

    def _blend(self, c1, c2, progress):
        r1, g1, b1 = self._hex_to_rgb(c1)
        r2, g2, b2 = self._hex_to_rgb(c2)
        rgb = (
            int(r1 + (r2 - r1) * progress),
            int(g1 + (g2 - g1) * progress),
            int(b1 + (b2 - b1) * progress),
        )
        return self._rgb_to_hex(rgb)

    def _smooth_rounded_rect(self, x1, y1, x2, y2, radius, fill="", outline="", width=1, tags=""):
        r = max(2, min(radius, int((x2 - x1) / 2), int((y2 - y1) / 2)))
        pts = [
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1,
        ]
        return self.create_polygon(pts, smooth=True, splinesteps=48, fill=fill, outline=outline, width=width, tags=tags)

    def _render(self):
        height = self._card_height
        self.configure(height=height)
        self.delete("card")

        width = max(260, self.winfo_width())
        hover_mix = min(1.0, self._hover_progress * 0.50 + self._select_progress * 0.35)
        fill = self._blend(self.surface_bg, self.surface_hover_bg, hover_mix)
        border = self._blend(W_CARD_BORDER, W_CARD_BORDER_HOVER, hover_mix)
        shadow_a = self._blend(W_CARD_SHADOW_A, W_CARD_SHADOW_A, hover_mix)
        shadow_b = self._blend(W_CARD_SHADOW_B, W_CARD_SHADOW_B, hover_mix)
        title_color = self._blend(W_TITLE_COLOR, W_TITLE_COLOR_ACTIVE, self._select_progress * 0.45)
        meta_color = self._blend(W_META_COLOR, W_META_COLOR, self._select_progress * 0.35)

        self._smooth_rounded_rect(6, 8, width - 2, height - 2, 24, fill=shadow_b, outline="", tags="card")
        self._smooth_rounded_rect(3, 5, width - 5, height - 5, 24, fill=shadow_a, outline="", tags="card")
        self._smooth_rounded_rect(0, 0, width - 8, height - 8, 24, fill=fill, outline="", tags="card")
        self._smooth_rounded_rect(0, 0, width - 8, height - 8, 24, fill="", outline=border, width=1, tags="card")

        content_width = max(220, width - 36)
        self.itemconfigure(self.content_id, width=content_width, height=self._card_height - 20)
        self.coords(self.content_id, 18, 10)
        self.tag_raise(self.content_id)

        self.content.configure(bg=fill)
        self.folder_icon.configure(bg=fill, fg=W_ICON_COLOR)
        self.title_label.configure(bg=fill, fg=title_color)
        self.chevron_label.configure(bg=fill, fg=W_CHEVRON_COLOR)
        for label in self.meta_icon_labels:
            label.configure(bg=fill, fg=W_META_COLOR)
        for label in self.meta_labels:
            label.configure(bg=fill, fg=meta_color)

    def is_height_animating(self):
        return self._select_anim is not None

    def get_render_height(self):
        return self._card_height

    def set_selected(self, selected):
        self._animate_to("select", 1.0 if selected else 0.0, 0.30)

    def set_loading(self):
        self.meta_labels[0].configure(text="마지막 수정 날짜: 로딩 중...")
        self.meta_labels[1].configure(text="워크스페이스 크기: 로딩 중...")
        self.meta_labels[2].configure(text="워크스페이스 파일 수: 로딩 중...")

    def set_metadata(self, meta):
        self.meta_labels[0].configure(text=f"마지막 수정 날짜: {meta['last_modified']}")
        self.meta_labels[1].configure(text=f"워크스페이스 크기: {meta['size_text']}")
        self.meta_labels[2].configure(text=f"워크스페이스 파일 수: {meta['file_count']:,}개")
        
class WorkspaceStack(tk.Frame):
    def __init__(self, parent, workspace_names, on_open=None, on_layout=None, bg=W_CARD_SURFACE, card_bg=W_CARD_SURFACE, card_hover_bg=W_CARD_SURFACE_HOVER, meta_icon_photos=None, folder_icon_photo=None, font_family="Segoe UI"):
        super().__init__(parent, bg=bg, bd=0, highlightthickness=0)
        self.configure(height=1)
        self.pack_propagate(False)

        self.on_open = on_open
        self.on_layout = on_layout
        self.card_bg = card_bg
        self.card_hover_bg = card_hover_bg
        self.meta_icon_photos = meta_icon_photos or {}
        self.folder_icon_photo = folder_icon_photo
        self.font_family = font_family
        self._top_pad = 8
        self._side_pad = 2
        self._stack_step = 73
        self._selected_reveal_gap = 10
        self._selected_name = None
        self._selected_index = None
        self._layout_job = None
        self._layout_anim = None
        self._current_y = {}

        self.cards = []
        self.cards_by_name = {}

        for workspace_name in workspace_names:
            card = WorkspaceCard(
                self,
                workspace_name,
                on_select=self.select_workspace,
                on_open=self._open_workspace,
                surface_bg=self.card_bg,
                surface_hover_bg=self.card_hover_bg,
                meta_icon_photos=self.meta_icon_photos,
                folder_icon_photo=self.folder_icon_photo,
                font_family=self.font_family,
            )
            self.cards.append(card)
            self.cards_by_name[workspace_name] = card

        self.bind("<Configure>", self._on_configure, add="+")
        self._relayout(animated=False)

    def _on_configure(self, _event):
        self._relayout(animated=False)

    def _open_workspace(self, workspace_name):
        if callable(self.on_open):
            self.on_open(workspace_name)

    def _schedule_layout(self):
        if self._layout_job is None:
            self._layout_job = self.after(16, self._layout_tick)

    @staticmethod
    def _ease(progress):
        progress = max(0.0, min(1.0, progress))
        return progress * progress * (3.0 - 2.0 * progress)

    def _compute_target_positions(self):
        target = {}
        reveal_extra = 0
        if self.cards:
            reveal_extra = max(0, (self.cards[0].get_render_height() - self._stack_step) + self._selected_reveal_gap)

        for index, card in enumerate(self.cards):
            y = self._top_pad + index * self._stack_step
            if self._selected_index is not None and index > self._selected_index:
                y += reveal_extra
            target[card.workspace_name] = int(y)
        return target

    def _start_layout_animation(self, duration=0.20):
        targets = self._compute_target_positions()
        starts = {}
        for card in self.cards:
            current = self._current_y.get(card.workspace_name)
            if current is None:
                current = card.winfo_y() if card.winfo_ismapped() else targets.get(card.workspace_name, self._top_pad)
            starts[card.workspace_name] = float(current)
        self._layout_anim = {
            "started": time.perf_counter(),
            "duration": max(0.001, float(duration)),
            "starts": starts,
            "targets": targets,
        }
        self._schedule_layout()

    def _layout_tick(self):
        self._layout_job = None
        self._relayout(animated=True)

        animating = any(card.is_height_animating() for card in self.cards) or (self._layout_anim is not None)
        if animating:
            self._schedule_layout()

    def _relayout(self, animated=False):
        width = max(260, self.winfo_width() - (self._side_pad * 2))
        max_bottom = float(self._top_pad)

        target_positions = self._compute_target_positions()
        if self._layout_anim:
            now = time.perf_counter()
            elapsed = (now - self._layout_anim["started"]) / self._layout_anim["duration"]
            progress = self._ease(elapsed)
            for card in self.cards:
                name = card.workspace_name
                start_y = self._layout_anim["starts"][name]
                end_y = self._layout_anim["targets"][name]
                y = start_y + (end_y - start_y) * progress
                self._current_y[name] = y
            if elapsed >= 1.0:
                self._layout_anim = None
                for name, y in target_positions.items():
                    self._current_y[name] = float(y)
        else:
            for name, y in target_positions.items():
                self._current_y[name] = float(y)

        for card in self.cards:
            y = self._current_y.get(card.workspace_name, float(self._top_pad))
            height = card.get_render_height()
            card.place(x=self._side_pad, y=int(y), width=width, height=height)
            max_bottom = max(max_bottom, y + height)

        total_height = int(max_bottom + self._top_pad + 6)
        self.configure(height=total_height)
        if callable(self.on_layout):
            self.on_layout(total_height)

    def select_workspace(self, workspace_name):
        if workspace_name == self._selected_name:
            return

        self._selected_name = workspace_name
        self._selected_index = None
        for index, card in enumerate(self.cards):
            if card.workspace_name == workspace_name:
                self._selected_index = index
                break

        for card in self.cards:
            card.set_selected(card.workspace_name == workspace_name)

        self._start_layout_animation(duration=0.20)

    def set_card_metadata(self, workspace_name, meta):
        card = self.cards_by_name.get(workspace_name)
        if card is not None:
            card.set_metadata(meta)
            self._relayout(animated=False)

class RoundedInput(tk.Frame):
    """Reusable rounded input field for Applemango DMS.

    Callback signatures:
    - on_submit(widget): called when submit is invoked (Enter key or invoke_submit).
    - on_change(widget): called when the underlying text value changes.
    - validate_callback(text) or validate_callback(widget): returns bool or (bool, message).

    Public methods:
    - get, set, clear, focus_input, set_enabled, set_error, clear_error,
      set_placeholder, validate, invoke_submit

    Generated virtual events:
    - <<RoundedInputChanged>>
    - <<RoundedInputSubmit>>

    Notes:
    - Uses native tk.Entry, preserving Korean IME composition and standard editing behavior.
    - Optional leading_icon is clickable and focuses the entry.
    """

    def __init__(
        self,
        parent,
        *,
        textvariable=None,
        placeholder="",
        width=360,
        height=44,
        corner_radius=13,
        font=None,
        foreground=None,
        placeholder_color=None,
        fill=None,
        border_color=None,
        focus_fill=None,
        focus_border_color=None,
        disabled_fill=None,
        disabled_foreground=None,
        error_border_color=None,
        leading_icon=None,
        show_clear_button=False,
        show=None,
        state="normal",
        on_submit=None,
        on_change=None,
        validate_callback=None,
        background=None,
    ):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=background if background is not None else parent.cget("bg"),
            highlightthickness=0,
            bd=0,
        )
        self.pack_propagate(False)
        self.grid_propagate(False)

        self.entry = None
        self.validation_message = ""

        self._height = int(max(28, height))
        self._corner_radius = int(max(8, corner_radius))
        self._on_submit = on_submit
        self._on_change = on_change
        self._validate_callback = validate_callback
        self._show_clear_button = bool(show_clear_button)
        self._leading_icon = leading_icon
        self._leading_icon_ref = leading_icon
        self._placeholder_text = str(placeholder or "")
        self._content_inset = 0
        self._border_width = 1
        self._entry_bottom_pad = 0
        self._pending_redraw_job = None
        self._surface_photo = None
        self._surface_image_id = None
        self._last_surface_key = None

        self._fill = fill if fill is not None else colors.SURFACE_ALT
        self._border_color = border_color if border_color is not None else colors.BORDER_INPUT
        self._focus_fill = focus_fill if focus_fill is not None else colors.SURFACE_HOVER_SOFT
        self._focus_border_color = focus_border_color if focus_border_color is not None else colors.PRIMARY
        self._disabled_fill = disabled_fill if disabled_fill is not None else colors.SURFACE_ALT2
        self._foreground = foreground if foreground is not None else colors.TEXT_NEUTRAL_DARK
        self._disabled_foreground = disabled_foreground if disabled_foreground is not None else colors.TEXT_SECONDARY
        self._placeholder_color = placeholder_color if placeholder_color is not None else colors.TEXT_PLACEHOLDER
        self._error_border_color = error_border_color if error_border_color is not None else colors.FAILED_STRONG

        self._enabled = str(state).lower() != "disabled"
        self._hover = False
        self._focused = False
        self._error = False
        self._suspend_trace_callback = False

        self._text_var = textvariable if textvariable is not None else tk.StringVar(value="")
        self._trace_id = self._text_var.trace_add("write", self._on_var_write)

        self._canvas = tk.Canvas(self, highlightthickness=0, bd=0, relief="flat", bg=self.cget("bg"))
        self._canvas.pack(fill="both", expand=True)

        self._inner = tk.Frame(self, bg=self._fill, bd=0, highlightthickness=0)
        self._update_content_inset()
        self._inner.place(
            x=self._content_inset,
            y=self._content_inset,
            relwidth=1.0,
            width=-(self._content_inset * 2),
            relheight=1.0,
            height=-(self._content_inset * 2),
        )
        self._inner.grid_rowconfigure(0, weight=1)

        self._leading_label = None
        self._clear_hit = None
        self._clear_label = None

        col = 0
        if self._leading_icon is not None:
            self._leading_label = tk.Label(
                self._inner,
                image=self._leading_icon,
                bg=self._fill,
                bd=0,
                highlightthickness=0,
                cursor="xterm" if self._enabled else "arrow",
            )
            self._leading_label.grid(row=0, column=col, sticky="w", padx=(10, 0))
            self._leading_label.bind("<Button-1>", self._focus_from_click, add="+")
            col += 1

        self._inner.grid_columnconfigure(col, weight=1)
        self.entry = tk.Entry(
            self._inner,
            textvariable=self._text_var,
            bd=0,
            relief="flat",
            highlightthickness=0,
            insertbackground=self._foreground,
            fg=self._foreground,
            bg=self._fill,
            disabledbackground=self._disabled_fill,
            disabledforeground=self._disabled_foreground,
            selectbackground=colors.PRIMARY,
            selectforeground=colors.TEXT_ON_PRIMARY_SOFT,
            show=show,
            font=font if font is not None else ("Segoe UI", 11),
            state="normal" if self._enabled else "disabled",
        )

        left_entry_pad = 13 if self._leading_label is None else 10
        self.entry.grid(row=0, column=col, sticky="ew", padx=(left_entry_pad, 8), pady=(0, 1))
        col += 1

        if self._show_clear_button:
            self._clear_hit = tk.Frame(self._inner, width=28, height=28, bg=self._fill, highlightthickness=0, bd=0, cursor="hand2")
            self._clear_hit.grid(row=0, column=col, sticky="e", padx=(0, 6))
            self._clear_hit.grid_propagate(False)

            self._clear_label = tk.Label(
                self._clear_hit,
                text="×",
                font=("Segoe UI", 11),
                fg=colors.TEXT_SECONDARY,
                bg=self._fill,
                bd=0,
                highlightthickness=0,
                cursor="hand2",
            )
            self._clear_label.place(relx=0.5, rely=0.5, anchor="center")

            for widget in (self._clear_hit, self._clear_label):
                widget.bind("<Button-1>", self._clear_and_refocus, add="+")
                widget.bind("<Enter>", self._on_clear_hover_enter, add="+")
                widget.bind("<Leave>", self._on_clear_hover_leave, add="+")

        self._placeholder_label = tk.Label(
            self._inner,
            text=self._placeholder_text,
            fg=self._placeholder_color,
            bg=self._fill,
            bd=0,
            highlightthickness=0,
            anchor="w",
            justify="left",
            font=font if font is not None else ("Segoe UI", 11),
            cursor="xterm" if self._enabled else "arrow",
        )
        self._placeholder_label.bind("<Button-1>", self._focus_from_click, add="+")

        self.entry.bind("<FocusIn>", self._on_focus_in, add="+")
        self.entry.bind("<FocusOut>", self._on_focus_out, add="+")
        self.entry.bind("<Return>", self._on_return, add="+")

        for widget in (self, self._canvas, self._inner):
            widget.bind("<Enter>", self._on_hover_enter, add="+")
            widget.bind("<Leave>", self._on_hover_leave, add="+")
            widget.bind("<Button-1>", self._focus_from_click, add="+")

        self.bind("<Configure>", self._on_configure, add="+")
        self.bind("<Destroy>", self._on_destroy, add="+")

        self._refresh_visual_state(redraw=True)
        self._update_placeholder_visibility()
        self._update_clear_visibility()

    # Example usage:
    # search_var = tk.StringVar()
    # search_input = RoundedInput(
    #     parent,
    #     textvariable=search_var,
    #     placeholder="파일명, 태그, 업로더 검색",
    #     show_clear_button=True,
    #     on_submit=lambda widget: run_search(widget.get()),
    # )
    # search_input.pack(fill="x")

    @staticmethod
    def _smooth_rounded_points(x1, y1, x2, y2, radius):
        r = max(0, min(int(radius), int((x2 - x1) / 2), int((y2 - y1) / 2)))
        return [
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1,
        ]

    def _color_to_rgb(self, color_value):
        r16, g16, b16 = self.winfo_rgb(color_value)
        return (r16 // 256, g16 // 256, b16 // 256)

    @staticmethod
    def _clamp_effective_radius(requested_radius, width, height, inset=0):
        usable_width = max(1.0, float(width) - (2.0 * float(inset)))
        usable_height = max(1.0, float(height) - (2.0 * float(inset)))
        maximum_radius = max(0.0, min(usable_width, usable_height) / 2.0)
        return max(0.0, min(float(requested_radius), maximum_radius))

    def _get_effective_radii(self, width, height, border_width):
        outer_radius = self._clamp_effective_radius(self._corner_radius, width, height, inset=1)
        inner_radius_request = max(0.0, outer_radius - float(border_width))
        inner_radius = self._clamp_effective_radius(inner_radius_request, width, height, inset=1 + border_width)
        return outer_radius, inner_radius

    def _get_render_scale(self):
        try:
            tk_scale = float(self.tk.call("tk", "scaling"))
        except Exception:
            tk_scale = 1.0

        if tk_scale >= 2.5:
            return 2
        if tk_scale >= 1.75:
            return 3
        return 4

    def _draw_canvas_rounded_fill(self, x1, y1, x2, y2, radius, fill, tags):
        if x2 <= x1 or y2 <= y1:
            return
        r = int(max(0, min(radius, (x2 - x1) // 2, (y2 - y1) // 2)))

        if r <= 0:
            self._canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline="", tags=tags)
            return

        self._canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline="", tags=tags)
        self._canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline="", tags=tags)
        self._canvas.create_arc(x1, y1, x1 + (2 * r), y1 + (2 * r), start=90, extent=90, style="pieslice", fill=fill, outline="", tags=tags)
        self._canvas.create_arc(x2 - (2 * r), y1, x2, y1 + (2 * r), start=0, extent=90, style="pieslice", fill=fill, outline="", tags=tags)
        self._canvas.create_arc(x2 - (2 * r), y2 - (2 * r), x2, y2, start=270, extent=90, style="pieslice", fill=fill, outline="", tags=tags)
        self._canvas.create_arc(x1, y2 - (2 * r), x1 + (2 * r), y2, start=180, extent=90, style="pieslice", fill=fill, outline="", tags=tags)

    def _draw_canvas_fallback(self, width, height, fill_color, border_color, border_width):
        self._canvas.delete("ri_surface")
        self._surface_image_id = None
        self._surface_photo = None

        self._canvas.delete("ri_fill")
        self._canvas.delete("ri_border")

        outer_x1, outer_y1 = 1, 1
        outer_x2 = max(outer_x1 + 1, int(width) - 1)
        outer_y2 = max(outer_y1 + 1, int(height) - 1)

        outer_radius, inner_radius = self._get_effective_radii(width, height, border_width)

        # Border first as a full rounded fill, then carve inner surface with an inset rounded fill.
        self._draw_canvas_rounded_fill(outer_x1, outer_y1, outer_x2, outer_y2, int(round(outer_radius)), border_color, "ri_border")

        inner_x1 = outer_x1 + int(border_width)
        inner_y1 = outer_y1 + int(border_width)
        inner_x2 = outer_x2 - int(border_width)
        inner_y2 = outer_y2 - int(border_width)
        if inner_x2 > inner_x1 and inner_y2 > inner_y1:
            self._draw_canvas_rounded_fill(inner_x1, inner_y1, inner_x2, inner_y2, int(round(inner_radius)), fill_color, "ri_fill")

    def _render_surface_image(self, width, height, fill_color, border_color, background_color, border_width):
        if not _PIL_AVAILABLE:
            return False

        scale = self._get_render_scale()
        sw = max(2, int(width) * scale)
        sh = max(2, int(height) * scale)
        sbw = max(1, int(round(border_width * scale)))

        outer_radius, inner_radius = self._get_effective_radii(width, height, border_width)
        so_radius = max(0, int(round(outer_radius * scale)))
        si_radius = max(0, int(round(inner_radius * scale)))

        bg_rgb = self._color_to_rgb(background_color)
        fill_rgb = self._color_to_rgb(fill_color)
        border_rgb = self._color_to_rgb(border_color)

        image = Image.new("RGBA", (sw, sh), (bg_rgb[0], bg_rgb[1], bg_rgb[2], 255))
        draw = ImageDraw.Draw(image)

        outer_box = [0, 0, sw - 1, sh - 1]
        draw.rounded_rectangle(outer_box, radius=so_radius, fill=(border_rgb[0], border_rgb[1], border_rgb[2], 255))

        inner_box = [sbw, sbw, sw - 1 - sbw, sh - 1 - sbw]
        if inner_box[2] > inner_box[0] and inner_box[3] > inner_box[1]:
            draw.rounded_rectangle(inner_box, radius=si_radius, fill=(fill_rgb[0], fill_rgb[1], fill_rgb[2], 255))

        try:
            resample_mode = Image.Resampling.LANCZOS
        except Exception:
            resample_mode = Image.LANCZOS
        downsampled = image.resize((int(width), int(height)), resample=resample_mode)

        photo = ImageTk.PhotoImage(downsampled, master=self._canvas)
        self._surface_photo = photo

        if self._surface_image_id is None:
            self._surface_image_id = self._canvas.create_image(0, 0, anchor="nw", image=photo, tags="ri_surface")
        else:
            self._canvas.itemconfigure(self._surface_image_id, image=photo)
            self._canvas.coords(self._surface_image_id, 0, 0)

        self._canvas.delete("ri_fill")
        self._canvas.delete("ri_border")
        return True

    def _update_content_inset(self):
        max_inset = max(2, self._corner_radius - 2)
        adaptive = max(2, int(max(1, self._height) * 0.12))
        self._content_inset = max(self._border_width + 1, min(max_inset, adaptive))
        self._entry_bottom_pad = 0 if self._height <= 32 else 1

    def _surface_key(self, width, height, fill_color, border_color):
        return (
            int(width),
            int(height),
            int(self._corner_radius),
            int(self._border_width),
            str(fill_color),
            str(border_color),
            str(self.cget("bg")),
            bool(self._enabled),
            bool(self._focused),
            bool(self._hover),
            bool(self._error),
            int(self._get_render_scale()),
        )

    def _schedule_surface_redraw(self, force=False):
        if not self.winfo_exists():
            return
        if force:
            self._last_surface_key = None
        if self._pending_redraw_job is not None:
            try:
                self.after_cancel(self._pending_redraw_job)
            except Exception:
                pass
            self._pending_redraw_job = None
        self._pending_redraw_job = self.after_idle(self._render_surface_if_needed)

    def _render_surface_if_needed(self):
        self._pending_redraw_job = None
        if not self.winfo_exists():
            return

        width = max(2, int(self.winfo_width()))
        height = max(2, int(self.winfo_height()))
        fill_color, border_color, _text_color = self._resolve_colors()

        key = self._surface_key(width, height, fill_color, border_color)
        if key == self._last_surface_key:
            return

        rendered = self._render_surface_image(width, height, fill_color, border_color, self.cget("bg"), self._border_width)
        if not rendered:
            self._draw_canvas_fallback(width, height, fill_color, border_color, self._border_width)

        self._last_surface_key = key

    def _resolve_colors(self):
        if not self._enabled:
            return self._disabled_fill, self._border_color, self._disabled_foreground
        if self._error:
            return self._fill, self._error_border_color, self._foreground
        if self._focused:
            return self._focus_fill, self._focus_border_color, self._foreground
        if self._hover:
            return self._fill, self._border_color, self._foreground
        return self._fill, self._border_color, self._foreground

    def _set_entry_state(self):
        self.entry.configure(state="normal" if self._enabled else "disabled")

    def _refresh_visual_state(self, redraw=False):
        fill_color, border_color, text_color = self._resolve_colors()
        if redraw:
            self._schedule_surface_redraw(force=True)

        self._inner.configure(bg=fill_color)
        if self._leading_label is not None:
            self._leading_label.configure(bg=fill_color, cursor="xterm" if self._enabled else "arrow")
        if self._clear_hit is not None:
            self._clear_hit.configure(bg=fill_color)
        if self._clear_label is not None:
            self._clear_label.configure(bg=fill_color)
        self._placeholder_label.configure(bg=fill_color)

        self.entry.configure(
            bg=fill_color,
            fg=text_color,
            insertbackground=text_color,
            disabledbackground=self._disabled_fill,
            disabledforeground=self._disabled_foreground,
        )
        self.entry.grid_configure(pady=(0, self._entry_bottom_pad))
        self._set_entry_state()
        self._update_placeholder_visibility()
        self._update_clear_visibility()

    def _on_configure(self, _event=None):
        self.configure(height=self._height)
        self._update_content_inset()
        self._inner.place_configure(
            x=self._content_inset,
            y=self._content_inset,
            width=-(self._content_inset * 2),
            height=-(self._content_inset * 2),
        )
        self._refresh_visual_state(redraw=False)
        self._schedule_surface_redraw(force=False)
        self._reposition_placeholder()

    def _reposition_placeholder(self):
        left_pad = getattr(self, "_placeholder_left_pad_override", None)
        right_pad = getattr(self, "_placeholder_right_pad_override", None)

        if left_pad is None:
            left_pad = 13
            if self._leading_label is not None:
                left_pad = 38

        if right_pad is None:
            right_pad = 38 if self._show_clear_button else 14

        width = max(10, self.winfo_width() - left_pad - right_pad)
        self._placeholder_label.place(x=left_pad, rely=0.5, anchor="w", width=width)

    def _on_hover_enter(self, _event=None):
        if self._enabled:
            self._hover = True
            self._refresh_visual_state(redraw=True)

    def _on_hover_leave(self, _event=None):
        if self._enabled:
            self._hover = False
            self._refresh_visual_state(redraw=True)

    def _on_focus_in(self, _event=None):
        self._focused = True
        self._refresh_visual_state(redraw=True)

    def _on_focus_out(self, _event=None):
        self._focused = False
        self._refresh_visual_state(redraw=True)

    def _focus_from_click(self, _event=None):
        if not self._enabled:
            return "break"
        self.focus_input()
        return "break"

    def _on_return(self, _event=None):
        self.invoke_submit()
        return "break"

    def _clear_and_refocus(self, _event=None):
        if not self._enabled:
            return "break"
        self.clear()
        self.focus_input()
        return "break"

    def _on_clear_hover_enter(self, _event=None):
        if self._clear_label is not None and self._enabled:
            self._clear_label.configure(fg=colors.TEXT_PRIMARY)

    def _on_clear_hover_leave(self, _event=None):
        if self._clear_label is not None:
            self._clear_label.configure(fg=colors.TEXT_SECONDARY)

    def _has_meaningful_text(self):
        return bool(self.get())

    def _update_placeholder_visibility(self):
        show_placeholder = (not self._has_meaningful_text()) and (not self._focused)
        if show_placeholder and self._placeholder_text:
            self._placeholder_label.configure(text=self._placeholder_text, fg=self._placeholder_color)
            self._placeholder_label.lift(self.entry)
            self._reposition_placeholder()
        else:
            self._placeholder_label.place_forget()

    def _update_clear_visibility(self):
        if not self._show_clear_button or self._clear_hit is None:
            return
        should_show = self._enabled and self._has_meaningful_text()
        if should_show:
            self._clear_hit.grid()
        else:
            self._clear_hit.grid_remove()

    def _on_var_write(self, *_args):
        if self._suspend_trace_callback:
            return
        if not self.winfo_exists():
            return
        self._update_placeholder_visibility()
        self._update_clear_visibility()
        self.event_generate("<<RoundedInputChanged>>", when="tail")
        if callable(self._on_change):
            self._on_change(self)

    def _on_destroy(self, event):
        if event.widget is not self:
            return
        if self._pending_redraw_job is not None:
            try:
                self.after_cancel(self._pending_redraw_job)
            except Exception:
                pass
            self._pending_redraw_job = None
        if self._trace_id is not None:
            try:
                self._text_var.trace_remove("write", self._trace_id)
            except Exception:
                pass
            self._trace_id = None
        self._surface_image_id = None
        self._surface_photo = None
        self._last_surface_key = None

    def _set_value_internal(self, value):
        self._suspend_trace_callback = True
        try:
            self._text_var.set("" if value is None else str(value))
        finally:
            self._suspend_trace_callback = False
        self._update_placeholder_visibility()
        self._update_clear_visibility()
        self.event_generate("<<RoundedInputChanged>>", when="tail")
        if callable(self._on_change):
            self._on_change(self)

    def get(self):
        return str(self._text_var.get() or "")

    def set(self, value):
        self._set_value_internal(value)

    def clear(self):
        self._set_value_internal("")

    def focus_input(self):
        if not self._enabled:
            return
        try:
            self.entry.focus_force()
        except Exception:
            self.entry.focus_set()
        self.entry.icursor(tk.END)

    def set_enabled(self, enabled):
        self._enabled = bool(enabled)
        if not self._enabled:
            self._focused = False
        self._refresh_visual_state(redraw=True)

    def set_error(self, enabled=True):
        self._error = bool(enabled)
        self._refresh_visual_state(redraw=True)

    def clear_error(self):
        self._error = False
        self.validation_message = ""
        self._refresh_visual_state(redraw=True)

    def set_placeholder(self, text):
        self._placeholder_text = str(text or "")
        self._update_placeholder_visibility()

    def validate(self):
        if not callable(self._validate_callback):
            self.clear_error()
            return True

        result = None
        value = self.get()
        try:
            result = self._validate_callback(value)
        except TypeError:
            result = self._validate_callback(self)

        is_valid = True
        message = ""
        if isinstance(result, tuple):
            is_valid = bool(result[0])
            if len(result) > 1 and result[1] is not None:
                message = str(result[1])
        else:
            is_valid = bool(result)

        self.validation_message = message
        if is_valid:
            self.clear_error()
            return True

        self.set_error(True)
        return False

    def invoke_submit(self):
        self.event_generate("<<RoundedInputSubmit>>", when="tail")
        if callable(self._on_submit):
            self._on_submit(self)