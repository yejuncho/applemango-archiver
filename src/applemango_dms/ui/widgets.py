import time
import tkinter as tk

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