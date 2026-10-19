import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from securetube.extensions import ExtensionManager

S = 2                                   
W, H, GAP, COLS = 212, 158, 14, 6


def rgb(h): return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def card(d, ox, oy, t, font):
    c = t.colors; rad = (min(t.radius, 14) * .85 + 2)
    px = lambda v: v * S
    X, Y, PW, PH = ox + 3, oy + 3, W - 6, 110
    d.rounded_rectangle((px(X), px(Y), px(X + PW), px(Y + PH)), px(rad), fill=rgb(c["bg"]), outline=rgb(c["line2"]), width=S)
    d.rectangle((px(X + 1), px(Y + 1), px(X + 28), px(Y + PH - 1)), fill=rgb(c["panel"]))
    for i in range(4):
        d.rounded_rectangle((px(X + 8), px(Y + 16 + i * 15), px(X + 20), px(Y + 22 + i * 15)), px(3), fill=rgb(c["accent"] if i == 0 else c["line2"]))
    d.rounded_rectangle((px(X + 38), px(Y + 8), px(X + PW - 66), px(Y + 19)), px(5), fill=rgb(c["raised"]))
    d.rounded_rectangle((px(X + PW - 58), px(Y + 7), px(X + PW - 8), px(Y + 20)), px(6), fill=rgb(c["accent"]))
    cw = (PW - 48 - 12) / 3; th = cw * 9 / 16
    for row in range(2):
        y = Y + 30 + row * (th + 19)
        if y + th > Y + PH: break
        for i in range(3):
            x = X + 38 + i * (cw + 6)
            fill = rgb(c["accent"]) if (row == 0 and i == 0) else rgb(c["hover"] if (i + row) % 2 else c["raised"])
            d.rounded_rectangle((px(x), px(y), px(x + cw), px(y + th)), px(min(5, rad)), fill=fill)
            d.rounded_rectangle((px(x), px(y + th + 4), px(x + cw * .82), px(y + th + 7.5)), px(1.7), fill=rgb(c["text"]))
            d.rounded_rectangle((px(x), px(y + th + 10), px(x + cw * .5), px(y + th + 13)), px(1.5), fill=rgb(c["muted"]))
    d.text((px(X + 2), px(Y + PH + 8)), t.name, fill=(235, 237, 244), font=font)
    d.text((px(X + 2), px(Y + PH + 26)), "Тёмная" if t.dark else "Светлая", fill=(140, 148, 166), font=font)


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    m = ExtensionManager(Path("/tmp/_x"), [root / "extensions"]); m.scan()
    themes = m.ordered_themes(); rows = (len(themes) + COLS - 1) // COLS
    img = Image.new("RGB", ((COLS * (W + GAP) + GAP) * S, (rows * (H + GAP) + GAP) * S), (18, 19, 24))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12 * S)
    except OSError:
        font = ImageFont.load_default()
    for i, t in enumerate(themes):
        r, c = divmod(i, COLS)
        card(d, GAP + c * (W + GAP), GAP + r * (H + GAP), t, font)
    out = root / "docs" / "themes_preview.png"
    img.resize((img.width // S, img.height // S), Image.LANCZOS).save(out)
    print("OK", out, len(themes), "тем")
