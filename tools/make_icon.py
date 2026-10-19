from pathlib import Path
from PIL import Image, ImageDraw

SIZE = 512
A, B = (255, 77, 109), (123, 97, 255)


def build() -> Image.Image:
    grad = Image.new("RGB", (SIZE, SIZE))
    px = grad.load()
    for y in range(SIZE):
        for x in range(SIZE):
            t = (x + y) / (2 * (SIZE - 1))
            px[x, y] = tuple(int(A[i] + (B[i] - A[i]) * t) for i in range(3))
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, SIZE - 1, SIZE - 1), radius=int(SIZE * 0.27), fill=255)
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    tri = [(SIZE * 0.39, SIZE * 0.29), (SIZE * 0.39, SIZE * 0.71), (SIZE * 0.73, SIZE * 0.50)]
    d.polygon(tri, fill="white")
    d.line(tri + [tri[0]], fill="white", width=int(SIZE * 0.05), joint="curve")
    for x, y in tri:
        r = SIZE * 0.025
        d.ellipse((x - r, y - r, x + r, y + r), fill="white")
    return img


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "assets" / "securetube.ico"
    out.parent.mkdir(exist_ok=True)
    build().save(out, format="ICO", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    print("OK", out)
