import os
import sys
import warnings
import tkinter as tk

# Make src importable when run from repository root.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from applemango_dms.ui.widgets import RoundedInput  # noqa: E402


def run_matrix():
    warnings.simplefilter("always", ResourceWarning)

    heights = [28, 32, 36, 40, 44, 48]
    widths = [100, 180, 360]
    states = ["normal", "hover", "focused", "error", "disabled"]
    variants = ["standard", "search", "clear", "password"]

    root = tk.Tk()
    root.title("RoundedInput Smoke Matrix")
    root.withdraw()

    host = tk.Frame(root, bg="#F4F4F4")
    host.pack(fill="both", expand=True)

    # Tiny icon substitute so no asset dependency is needed.
    icon = tk.PhotoImage(width=12, height=12)
    icon.put("#2F5BFF", to=(0, 0, 11, 11))

    failures = []
    total = 0

    for height in heights:
        for width in widths:
            for variant in variants:
                for state in states:
                    total += 1
                    var = tk.StringVar(value="Sample text")
                    kwargs = {
                        "textvariable": var,
                        "width": width,
                        "height": height,
                        "corner_radius": 13,
                        "fill": "#FFFFFF",
                        "border_color": "#9AA3B5",
                        "focus_border_color": "#2F5BFF",
                        "placeholder": "Placeholder",
                    }

                    if variant == "search":
                        kwargs["leading_icon"] = icon
                    if variant == "clear":
                        kwargs["show_clear_button"] = True
                    if variant == "password":
                        kwargs["show"] = "*"

                    widget = RoundedInput(host, **kwargs)
                    widget.place(x=0, y=0, width=width, height=height)
                    root.update_idletasks()

                    if state == "hover":
                        widget._hover = True
                        widget._focused = False
                        widget._error = False
                        widget.set_enabled(True)
                    elif state == "focused":
                        widget._hover = False
                        widget._focused = True
                        widget._error = False
                        widget.set_enabled(True)
                    elif state == "error":
                        widget._hover = False
                        widget._focused = False
                        widget._error = True
                        widget.set_enabled(True)
                    elif state == "disabled":
                        widget._hover = False
                        widget._focused = False
                        widget._error = False
                        widget.set_enabled(False)
                    else:
                        widget._hover = False
                        widget._focused = False
                        widget._error = False
                        widget.set_enabled(True)

                    widget._refresh_visual_state(redraw=True)
                    root.update_idletasks()

                    # Resize churn: verify no surface image accumulation.
                    for delta in (0, 2, -1, 1, 0):
                        w = max(80, width + delta)
                        widget.place_configure(width=w, height=height)
                        root.update_idletasks()

                    surface_count = len(widget._canvas.find_withtag("ri_surface"))
                    if surface_count > 1:
                        failures.append(
                            f"Surface image leak: h={height}, w={width}, state={state}, variant={variant}, count={surface_count}"
                        )

                    if widget.winfo_height() != height:
                        failures.append(
                            f"Geometry mismatch: expected h={height}, got {widget.winfo_height()} for w={width}, state={state}, variant={variant}"
                        )

                    widget.destroy()
                    root.update_idletasks()

    root.destroy()

    print(f"RoundedInput smoke matrix cases: {total}")
    if failures:
        print("FAILURES:")
        for item in failures:
            print(item)
        return 1

    print("RoundedInput smoke matrix completed without structural failures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_matrix())
