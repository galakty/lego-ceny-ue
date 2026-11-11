"""Renders a vertical (1080x1920) price-comparison reel: hook, set photo, shop prices,
saving and a klockownik.pl call to action. Frames are drawn with Pillow and piped to ffmpeg.
Needs Pillow and ffmpeg (on PATH, or the binary from the imageio-ffmpeg package). The Inter font is
bundled in lego_prices/fonts (SIL Open Font License); DejaVu Sans is the fallback."""
import os
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
YELLOW = (255, 207, 0)
INK = (29, 29, 27)
DARK = (20, 20, 19)
CARD = (31, 31, 29)
WHITE = (236, 236, 234)
MUTED = (163, 163, 157)
RED = (208, 16, 18)
GREEN = (74, 194, 107)

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
FALLBACK_FONTS = {"Medium": "DejaVuSans.ttf", "SemiBold": "DejaVuSans-Bold.ttf", "Bold": "DejaVuSans-Bold.ttf",
                  "ExtraBold": "DejaVuSans-Bold.ttf", "Black": "DejaVuSans-Bold.ttf"}
_fonts: dict = {}


def font(weight, size):
    key = (weight, size)
    if key not in _fonts:
        path = os.path.join(FONT_DIR, f"Inter-{weight}.otf")
        if not os.path.exists(path):
            path = "/usr/share/fonts/truetype/dejavu/" + FALLBACK_FONTS[weight]
        _fonts[key] = ImageFont.truetype(path, size)
    return _fonts[key]


def ffmpeg_exe() -> str:
    path = shutil.which("ffmpeg")
    if path:
        return path
    import imageio_ffmpeg  # pip package with a static ffmpeg build, so CI needs no apt
    return imageio_ffmpeg.get_ffmpeg_exe()


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def pln(value):
    whole, frac = f"{value:.2f}".split(".")
    groups = []
    while whole:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    return " ".join(groups) + "," + frac + " zł"


def center_text(d, y, text, f, fill, alpha=1.0, bg=None):
    w = d.textlength(text, font=f)
    if alpha < 1.0 and bg is not None:
        fill = tuple(int(bg[i] + (fill[i] - bg[i]) * alpha) for i in range(3))
    d.text(((W - w) / 2, y), text, font=f, fill=fill)


def brick_icon(logo):
    # The brick occupies roughly the middle of the 800x800 logo.
    return logo.crop((190, 190, 610, 560))


def scene_hook(t, deal):
    img = Image.new("RGB", (W, H), YELLOW)
    d = ImageDraw.Draw(img)
    a1 = ease(t / 0.4)
    center_text(d, 560 + 40 * (1 - a1), deal.get("hook", "Ten sam zestaw LEGO."), font("ExtraBold", 84), INK, a1, YELLOW)
    a2 = ease((t - 0.6) / 0.4)
    center_text(d, 700 + 40 * (1 - a2), "Różnica w cenie:", font("Bold", 72), INK, a2, YELLOW)
    a3 = ease((t - 1.2) / 0.5)
    if a3 > 0:
        size = int(150 + 60 * a3)
        center_text(d, 900 - (size - 150) / 2, f"{deal['diff']:.0f} zł", font("Black", size), RED, a3, YELLOW)
    return img


def fit_lines(d, text, weight, size, max_w, max_lines=2):
    """Split text into up to max_lines lines and shrink the font until every line fits."""
    words = text.split()
    while size > 30:
        f = font(weight, size)
        lines, cur = [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            if d.textlength(trial, font=f) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        if len(lines) <= max_lines and all(d.textlength(l, font=f) <= max_w for l in lines):
            return f, lines
        size -= 6
    return font(weight, size), [text]


def photo_card(photo, box_w, box_h, full=False):
    """Fit the set photo on a white rounded card, or full-bleed (e.g. box art on a dark background)."""
    if full:
        p = photo.convert("RGB")
        p.thumbnail((box_w, box_h))
        mask = Image.new("L", p.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, p.width, p.height), radius=60, fill=255)
        return p, mask
    card = Image.new("RGB", (box_w, box_h), (255, 255, 255))
    p = photo.copy()
    p.thumbnail((box_w - 80, box_h - 80))
    card.paste(p, ((box_w - p.width) // 2, (box_h - p.height) // 2), p if p.mode == "RGBA" else None)
    mask = Image.new("L", (box_w, box_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, box_w, box_h), radius=60, fill=255)
    return card, mask


def scene_set(t, deal, brick, photo=None):
    img = Image.new("RGB", (W, H), DARK)
    d = ImageDraw.Draw(img)
    a = ease(t / 0.5)
    if photo is not None:
        card, mask = photo
        bx, by = (W - card.width) // 2, int(260 + 60 * (1 - a))
        img.paste(card, (bx, by), mask)
        text_top = by + card.height + 70
    else:
        b = brick.resize((int(brick.width * 1.4), int(brick.height * 1.4)))
        bx, by = int((W - b.width) / 2), int(400 + 60 * (1 - a))
        d.rounded_rectangle((bx - 60, by - 60, bx + b.width + 60, by + b.height + 60), radius=60, fill=YELLOW)
        img.paste(b, (bx, by))
        text_top = 1110
    d = ImageDraw.Draw(img)
    a2 = ease((t - 0.4) / 0.5)
    center_text(d, text_top + 30 * (1 - a2), deal["theme"], font("SemiBold", 64), YELLOW, a2, DARK)
    f, lines = fit_lines(d, deal["name"], "Black", 100, W - 140, 3)
    y = text_top + 90
    for line in lines:
        center_text(d, y + 30 * (1 - a2), line, f, WHITE, a2, DARK)
        y += int(f.size * 1.15)
    a3 = ease((t - 0.9) / 0.5)
    center_text(d, y + 30, f"nr zestawu {deal['set_num']}", font("Medium", 52), MUTED, a3, DARK)
    return img


def scene_prices(t, deal):
    img = Image.new("RGB", (W, H), DARK)
    d = ImageDraw.Draw(img)
    center_text(d, 330, "Ten sam zestaw,", font("Bold", 70), WHITE)
    center_text(d, 420, "różne sklepy:", font("Bold", 70), WHITE)
    offers = deal["offers"]  # sorted most expensive first
    row_h, top = 230, 640
    for i, (shop, price) in enumerate(offers):
        a = ease((t - 0.3 - i * 1.1) / 0.45)
        if a <= 0:
            continue
        cheapest = i == len(offers) - 1
        priciest = i == 0
        y = top + i * (row_h + 40)
        x = 80 + int((1 - a) * 300)
        fill = (24, 64, 36) if cheapest and t > 0.3 + i * 1.1 + 0.6 else CARD
        d.rounded_rectangle((x, y, x + W - 160, y + row_h), radius=36, fill=fill,
                            outline=GREEN if cheapest else None, width=6)
        d.text((x + 50, y + 40), shop, font=font("SemiBold", 54), fill=WHITE)
        color = GREEN if cheapest else (RED if priciest else WHITE)
        d.text((x + 50, y + 110), pln(price), font=font("Black", 84), fill=color)
        if cheapest and a >= 1:
            badge = "NAJTANIEJ"
            bf = font("ExtraBold", 40)
            bw = d.textlength(badge, font=bf)
            bx = x + W - 160 - bw - 90
            d.rounded_rectangle((bx, y + 40, bx + bw + 50, y + 105), radius=20, fill=GREEN)
            d.text((bx + 25, y + 48), badge, font=bf, fill=DARK)
    return img


def scene_saving(t, deal):
    img = Image.new("RGB", (W, H), YELLOW)
    d = ImageDraw.Draw(img)
    center_text(d, 640, "Oszczędzasz", font("Bold", 90), INK)
    shown = deal["diff"] * ease(t / 1.2)
    center_text(d, 780, f"{shown:.0f} zł", font("Black", 230), INK)
    a = ease((t - 1.2) / 0.4)
    center_text(d, 1070, f"to {deal['pct']:.0f}% mniej", font("Bold", 80), RED, a, YELLOW)
    return img


def scene_cta(t, deal, logo):
    img = Image.new("RGB", (W, H), YELLOW)
    a = ease(t / 0.5)
    lg = logo.resize((620, 620))
    img.paste(lg, (int((W - 620) / 2), int(380 + 40 * (1 - a))))
    d = ImageDraw.Draw(img)
    a2 = ease((t - 0.4) / 0.5)
    center_text(d, 1100, "Sprawdź cenę, zanim kupisz:", font("Bold", 64), INK, a2, YELLOW)
    center_text(d, 1200, "klockownik.pl", font("Black", 120), INK, a2, YELLOW)
    center_text(d, 1700, deal["note"], font("Medium", 36), (90, 75, 0), a2, YELLOW)
    return img


def render(deal: dict, logo_path: str, out_path: str, photo_path: str | None = None) -> float:
    """deal: set_num, theme, name, offers [(shop, price)] most expensive first, diff, pct, note, optional hook
    and photo_full (photo is box art on a dark background). Returns the length in seconds."""
    logo = Image.open(logo_path).convert("RGB")
    brick = brick_icon(logo)
    photo = photo_card(Image.open(photo_path).convert("RGBA"), 920, 900, deal.get("photo_full", False)) if photo_path else None
    n_offers = len(deal["offers"])
    scenes = [
        (3.2, lambda t: scene_hook(t, deal)),
        (3.0, lambda t: scene_set(t, deal, brick, photo)),
        (0.8 + n_offers * 1.1 + 1.6, lambda t: scene_prices(t, deal)),
        (2.8, lambda t: scene_saving(t, deal)),
        (3.5, lambda t: scene_cta(t, deal, logo)),
    ]
    total = sum(s[0] for s in scenes)
    cmd = [ffmpeg_exe(), "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-f", "lavfi", "-t", f"{total}", "-i", "anullsrc=r=44100:cl=stereo",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "20",
           "-c:a", "aac", "-shortest", "-movflags", "+faststart", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for dur, fn in scenes:
        for i in range(int(round(dur * FPS))):
            proc.stdin.write(fn(i / FPS).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg failed for {out_path}")
    return total
