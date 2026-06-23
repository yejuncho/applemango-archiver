import tkinter as tk

class WorkspaceCard(tk.Frame):
    def __init__(self, parent, workspace_name, on_click=None):
        super().__init__(parent, bg='#cfcfcf', bd=0, highlightthickness=1, highlightbackground='#cfcfcf', height=62)
        self.pack_propagate(False)

        self.workspace_name = workspace_name
        self.on_click = on_click
        self._progress = 0.0
        self._target_progress = 0.0
        self._animating = False
        self._collapsed_height = 62
        self._expanded_height = 136
        self._bg_start = '#ffffff'
        self._bg_end = '#5bbf6a'
        self._title_fg_start = '#1f1f1f'
        self._title_fg_end = '#ffffff'
        self._meta_fg_start = '#7f8a80'
        self._meta_fg_end = '#ffffff'

        self.body = tk.Frame(self, bg=self._bg_start)
        self.body.pack(fill='both', expand=True)

        self.title_label = tk.Label(
            self.body,
            text=workspace_name,
            font=('Segoe UI', 12, 'bold'),
            bg=self._bg_start,
            fg=self._title_fg_start,
            anchor='w',
        )
        self.title_label.place(x=18, y=17, relwidth=0.9, height=24)

        self.meta_labels = [
            tk.Label(self.body, text='', font=('Segoe UI', 9), bg=self._bg_start, fg=self._meta_fg_start, anchor='w')
            for _ in range(3)
        ]
        self.meta_labels[0].place(x=18, y=56, relwidth=0.9, height=18)
        self.meta_labels[1].place(x=18, y=77, relwidth=0.9, height=18)
        self.meta_labels[2].place(x=18, y=98, relwidth=0.9, height=18)

        self.set_loading()
        self._bind_events()
        self._apply_style(0.0)

    def _bind_events(self):
        widgets = [self, self.body, self.title_label] + self.meta_labels
        for widget in widgets:
            widget.bind('<Enter>', self._on_enter, add='+')
            widget.bind('<Leave>', self._on_leave, add='+')
            widget.bind('<Button-1>', self._on_click, add='+')

    def _on_enter(self, _event):
        self._target_progress = 1.0
        self._start_animation()

    def _on_leave(self, _event):
        self._target_progress = 0.0
        self._start_animation()

    def _on_click(self, _event):
        if callable(self.on_click):
            self.on_click(self.workspace_name)

    def _start_animation(self):
        if self._animating:
            return
        self._animating = True
        self.after(16, self._animate_step)

    def _animate_step(self):
        if abs(self._target_progress - self._progress) < 0.01:
            self._progress = self._target_progress
            self._apply_style(self._progress)
            self._animating = False
            return

        step = 0.05
        if self._target_progress > self._progress:
            self._progress = min(self._target_progress, self._progress + step)
        else:
            self._progress = max(self._target_progress, self._progress - step)

        self._apply_style(self._progress)
        self.after(16, self._animate_step)

    @staticmethod
    def _hex_to_rgb(hex_color):
        value = hex_color.lstrip('#')
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

    def _apply_style(self, progress):
        bg_color = self._blend(self._bg_start, self._bg_end, progress)
        border_color = self._blend('#cfcfcf', '#52b55f', progress)
        title_color = self._blend(self._title_fg_start, self._title_fg_end, progress)

        metadata_progress = max(0.0, min(1.0, (progress - 0.2) / 0.8))
        meta_color = self._blend(self._meta_fg_start, self._meta_fg_end, metadata_progress)

        height = int(self._collapsed_height + (self._expanded_height - self._collapsed_height) * progress)
        title_y = int(17 - 8 * progress)

        self.configure(height=height, bg=border_color, highlightbackground=border_color)
        self.body.configure(bg=bg_color)
        self.title_label.configure(bg=bg_color, fg=title_color)
        self.title_label.place_configure(y=title_y)

        for label in self.meta_labels:
            label.configure(bg=bg_color, fg=meta_color)

    def set_loading(self):
        self.meta_labels[0].configure(text='마지막 수정 날짜: 로딩 중...')
        self.meta_labels[1].configure(text='워크스페이스 크기: 로딩 중...')
        self.meta_labels[2].configure(text='워크스페이스 파일 수: 로딩 중...')

    def set_metadata(self, meta):
        self.meta_labels[0].configure(text=f"마지막 수정 날짜: {meta['last_modified']}")
        self.meta_labels[1].configure(text=f"워크스페이스 크기: {meta['size_text']}")
        self.meta_labels[2].configure(text=f"워크스페이스 파일 수: {meta['file_count']:,}개")