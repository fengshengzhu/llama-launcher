"""生成打包用图标：python assets/make_icon.py（需要 Pillow）"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SIZE = 256
BG = (29, 39, 63, 255)
ACCENT = (109, 141, 255, 255)
WHITE = (240, 244, 255, 255)


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def main() -> None:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((8, 8, SIZE - 8, SIZE - 8), radius=52, fill=BG)
    draw.rounded_rectangle((28, 28, SIZE - 28, SIZE - 28), radius=36, outline=ACCENT, width=8)

    font = load_font(150)
    text = "L"
    box = draw.textbbox((0, 0), text, font=font)
    x = (SIZE - (box[2] - box[0])) / 2 - box[0]
    y = (SIZE - (box[3] - box[1])) / 2 - box[1] - 6
    draw.text((x, y), text, font=font, fill=WHITE)

    image.save(os.path.join(HERE, "app_icon.png"))
    image.save(
        os.path.join(HERE, "app_icon.ico"),
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print("icon generated")


if __name__ == "__main__":
    main()
