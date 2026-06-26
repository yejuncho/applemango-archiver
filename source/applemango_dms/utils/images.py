from pathlib import Path

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None


"""Image helpers used by the Tk UI layer."""


def resize_image_fit(image, max_width, max_height):
    if Image is None:
        return None

    src_w, src_h = image.size
    if src_w <= 0 or src_h <= 0:
        return image

    scale = min(max_width / src_w, max_height / src_h)
    scale = max(0.05, scale)
    new_size = (max(1, int(src_w * scale)), max(1, int(src_h * scale)))
    if new_size == image.size:
        return image

    return image.resize(new_size, Image.LANCZOS)


def load_logo_photo(logo_path, max_width, max_height):
    path = Path(logo_path)
    if Image is None or ImageTk is None or not path.exists():
        return None

    try:
        image = Image.open(path)
        resized = resize_image_fit(image, max_width=max_width, max_height=max_height)
        return ImageTk.PhotoImage(resized)
    except Exception:
        return None
