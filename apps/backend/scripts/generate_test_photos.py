"""Generate synthetic bookshelf photos that exercise each failure mode.

These are deliberately synthetic so the failure modes are reproducible on any
machine. Real shelf photos live alongside them in test_photos/ and are what the
measured numbers in the README were taken from.
"""

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).resolve().parents[3] / "test_photos"

SPINE_COLORS = [
    (94, 60, 48),
    (46, 74, 61),
    (120, 44, 44),
    (37, 51, 84),
    (150, 122, 60),
    (72, 61, 96),
    (28, 76, 88),
    (140, 88, 46),
]

TITLES = [
    ("THE GREAT GATSBY", "FITZGERALD"),
    ("DUNE", "HERBERT"),
    ("1984", "ORWELL"),
    ("THE HOBBIT", "TOLKIEN"),
    ("THE ROAD", "MCCARTHY"),
    ("SAPIENS", "HARARI"),
    ("THE MARTIAN", "WEIR"),
    ("BELOVED", "MORRISON"),
]


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_vertical_text(canvas: Image.Image, text: str, size: int, color: tuple) -> Image.Image:
    strip = Image.new("RGBA", (canvas.height, canvas.width), (0, 0, 0, 0))
    draw = ImageDraw.Draw(strip)
    draw.text((18, (canvas.width - size) // 2), text, font=_font(size), fill=color)
    rotated = strip.rotate(90, expand=True)
    canvas.paste(rotated, (0, 0), rotated)
    return canvas


def build_shelf(path: Path, *, books: int, blur: bool = False, seed: int = 7) -> None:
    random.seed(seed)
    width, height = 1200, 620
    image = Image.new("RGB", (width, height), (222, 210, 192))
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, height - 60, width, height], fill=(120, 88, 58))

    x = 40
    shelf_height = height - 90
    for index in range(books):
        spine_width = random.randint(58, 96)
        if x + spine_width > width - 40:
            break
        top = 40 + random.randint(0, 20)
        spine = Image.new(
            "RGB",
            (spine_width, shelf_height - top + 40),
            SPINE_COLORS[index % len(SPINE_COLORS)],
        )
        title, author = TITLES[index % len(TITLES)]
        _draw_vertical_text(spine, title, 22, (240, 234, 222))
        _draw_vertical_text(spine, author, 14, (215, 205, 190))
        image.paste(spine, (x, top))
        x += spine_width + random.randint(4, 10)

    if blur:
        from PIL import ImageFilter

        image = image.filter(ImageFilter.GaussianBlur(radius=6))

    image.save(path, format="JPEG", quality=88)
    print(f"wrote {path.name}")


def build_empty_wall(path: Path) -> None:
    """No spines at all: exercises the zero-detections fallback."""
    image = Image.new("RGB", (900, 600), (228, 222, 210))
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 520, 900, 600], fill=(150, 140, 126))
    image.save(path, format="JPEG", quality=88)
    print(f"wrote {path.name}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    build_shelf(OUT_DIR / "shelf_readable.jpg", books=8, seed=7)
    build_shelf(OUT_DIR / "shelf_low_confidence.jpg", books=6, blur=True, seed=11)
    build_empty_wall(OUT_DIR / "shelf_zero_detections.jpg")


if __name__ == "__main__":
    main()
