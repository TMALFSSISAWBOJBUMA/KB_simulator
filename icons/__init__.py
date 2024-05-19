from PIL.ImageTk import PhotoImage
from PIL import Image
import os

SIZE = (24, 24)


def load_resize_icon(file: str, size: tuple[int, int] = SIZE):
    with Image.open(os.path.join(__file__, os.pardir, file)) as img:
        resized_image = img.resize(size, Image.ANTIALIAS)
        return PhotoImage(resized_image)


BTS_ICON = load_resize_icon(file="1655866-200.png")
UE_ICON = load_resize_icon(file="2363272-200.png")
