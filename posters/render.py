"""Draws a talk poster.

The layout copies the poster the team used to make by hand for every weekly
meeting, so a generated one looks like the ones people already know: the mark
and the name across the top, the title down the left with the speaker under
it, the speaker's photo on the right, the date, time and place below the
photo, and the Discord footer with its QR code.

It is drawn with Pillow rather than by a headless browser, so the server needs
nothing new installed. It is drawn at twice the final size and then scaled
down, because Pillow does not smooth the edges of the shapes it draws.

Every position below is in the units of the hand-made poster, which was 920
wide. Measuring against that poster is how the layout was checked, so the
numbers are kept in its units and scaled once, in `u()`.

Text that does not fit gets smaller, down to a floor, rather than running into
the photo or off the page. The presenter form limits the lengths too, so the
floor is only reached by text an admin edits in.
"""

import io
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import qrcode
from django.utils import timezone
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

FONTS = Path(__file__).resolve().parent / "fonts"
LOGO = Path(__file__).resolve().parent.parent / "static" / "assets" / "images" / "logo-mark-large.png"

# A4 at 150 dpi: it prints cleanly, and it is small enough to share in a chat.
WIDTH, HEIGHT = 1240, 1754
REF_WIDTH = 920
SUPERSAMPLE = 2
SCALE = WIDTH / REF_WIDTH * SUPERSAMPLE

INK = "#071033"
BLUE = "#0a4fab"
TEXT = "#3e3d43"
TILE = "#e3e7f2"
BOX_LINE = "#dce3ea"
DIVIDER = "#dedee0"
DISCORD = "#1954ae"
CODE_GREEN = "#2c7155"
LINK_BLUE = "#1f4f8f"
DOTS = ("#2c60c5", "#f5a300", "#2e8b57")
CIRCLES = (("#ff9e02", (848, -20), 125), ("#019052", (903, 76), 31), ("#f9311a", (854, 112), 43))
BAR = (("#3567b5", 0, 212), ("#b93e37", 212, 427), ("#dcb349", 427, 652), ("#257955", 652, 920))

REGULAR = "Poppins-Regular.ttf"
MEDIUM = "Poppins-Medium.ttf"
SEMIBOLD = "Poppins-SemiBold.ttf"
BOLD = "Poppins-Bold.ttf"
EXTRABOLD = "Poppins-ExtraBold.ttf"
MONO = "SpaceMono-Regular.ttf"
MONO_BOLD = "SpaceMono-Bold.ttf"
TITLE = "Oswald-Variable.ttf"
HAND = "Caveat-Variable.ttf"


@dataclass
class PosterContent:
    label: str
    title: str
    summary: str
    speaker_name: str
    speaker_tag: str
    about: str
    starts_at: datetime
    ends_at: datetime
    place: str
    place_detail: str
    icon: str  # "video", "discord" or "pin"
    link: str


def u(value):
    """A length in the hand-made poster's units, in pixels of the canvas being drawn."""
    return round(value * SCALE)


@lru_cache(maxsize=512)
def font(name, size, weight=None):
    loaded = ImageFont.truetype(str(FONTS / name), size)
    if weight:
        loaded.set_variation_by_axes([weight])
    return loaded


@lru_cache(maxsize=512)
def cap_height(fnt):
    return -fnt.getbbox("H", anchor="ls")[1]


def wrap(text, fnt, width):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if not line or fnt.getlength(trial) <= width:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def shorten(text, fnt, width):
    """Cut a line that is still too wide at the smallest size, and say so with an ellipsis."""
    if fnt.getlength(text) <= width:
        return text
    while text and fnt.getlength(text + "…") > width:
        text = text[:-1]
    return text.rstrip() + "…"


def fit(text, name, largest, smallest, width, height, pitch, weight=None, squeeze=1):
    """The biggest size at which `text` wraps into lines that fit the box.

    Sizes and the box are in poster units; `pitch` is the line spacing as a
    multiple of the size. `squeeze` narrows the letters, as `Canvas.lines`
    will draw them. Returns the font, the lines and the pitch in pixels.
    """
    width_px, height_px = round(u(width) / squeeze), u(height)
    size = u(largest)
    while True:
        fnt = font(name, size, weight)
        step = round(size * pitch)
        lines = wrap(text, fnt, width_px)
        used = cap_height(fnt) + step * (len(lines) - 1)
        fits = used <= height_px and all(fnt.getlength(line) <= width_px for line in lines)
        if fits or size <= u(smallest):
            break
        size -= 2
    if not fits:
        room = max(1, (height_px - cap_height(fnt)) // step + 1)
        if len(lines) > room:
            lines = lines[:room]
            lines[-1] += "…"
        lines = [shorten(line, fnt, width_px) for line in lines]
    return fnt, lines, step


class Canvas:
    def __init__(self):
        self.image = Image.new("RGB", (u(REF_WIDTH), u(REF_WIDTH * HEIGHT / WIDTH)), "white")
        self.draw = ImageDraw.Draw(self.image)

    def text(self, x, top, value, fnt, fill, squeeze=1, stroke=0):
        """Draw one line so the top of its capital letters sits at `top`. Returns its width in units.

        `squeeze` narrows the letters, for faces a little wider than the
        original's; `stroke` thickens them a touch, for the thin monospace.
        """
        baseline = u(top) + cap_height(fnt)
        if squeeze == 1:
            self.draw.text((u(x), baseline), value, font=fnt, fill=fill, anchor="ls",
                           stroke_width=u(stroke), stroke_fill=fill)
            return fnt.getlength(value) / SCALE
        left, high, right, low = fnt.getbbox(value, anchor="ls", stroke_width=u(stroke))
        layer = Image.new("L", (right - left + 2, low - high + 2), 0)
        ImageDraw.Draw(layer).text((-left + 1, -high + 1), value, font=fnt, fill=255, anchor="ls",
                                   stroke_width=u(stroke), stroke_fill=255)
        layer = layer.resize((round(layer.width * squeeze), layer.height), Image.LANCZOS)
        self.image.paste(Image.new("RGB", layer.size, fill),
                         (u(x) + round(left * squeeze) - 1, baseline + high - 1), layer)
        return fnt.getlength(value) * squeeze / SCALE

    def lines(self, x, top, lines, fnt, step, fill, squeeze=1):
        """Draw wrapped lines from `top`. Returns the baseline of the last one, in units."""
        for number, line in enumerate(lines):
            self.text(x, top + number * step / SCALE, line, fnt, fill, squeeze)
        return top + (cap_height(fnt) + step * (len(lines) - 1)) / SCALE

    def single(self, x, top, value, name, largest, smallest, width, fill, weight=None,
               squeeze=1, stroke=0):
        """One line, as big as `largest` if it fits in `width`, never smaller than `smallest`."""
        size = u(largest)
        while size > u(smallest) and font(name, size, weight).getlength(value) * squeeze > u(width):
            size -= 1
        fnt = font(name, size, weight)
        return self.text(x, top, shorten(value, fnt, round(u(width) / squeeze)), fnt, fill,
                         squeeze, stroke)

    def box(self, x0, y0, x1, y1, radius, fill=None, outline=None, stroke=0):
        self.draw.rounded_rectangle(
            (u(x0), u(y0), u(x1), u(y1)), radius=u(radius), fill=fill, outline=outline,
            width=u(stroke) if stroke else 0)

    def circle(self, cx, cy, r, fill=None, outline=None, stroke=0):
        self.draw.ellipse((u(cx - r), u(cy - r), u(cx + r), u(cy + r)), fill=fill,
                          outline=outline, width=u(stroke) if stroke else 0)

    def line(self, points, fill, stroke):
        self.draw.line([(u(x), u(y)) for x, y in points], fill=fill, width=u(stroke),
                       joint="curve")

    def paste(self, picture, x, y, mask=None):
        self.image.paste(picture, (u(x), u(y)), mask)


# --- icons, drawn in a box of `size` units whose top left is (x, y) ----------

def icon_calendar(c, x, y, size, color, stroke):
    s = size
    c.box(x + s * .08, y + s * .16, x + s * .92, y + s * .94, s * .14, outline=color, stroke=stroke)
    c.line([(x + s * .08, y + s * .40), (x + s * .92, y + s * .40)], color, stroke)
    for px in (.3, .7):
        c.line([(x + s * px, y + s * .04), (x + s * px, y + s * .26)], color, stroke)
    for row in (.56, .76):
        for col in (.3, .5, .7):
            c.circle(x + s * col, y + s * row, s * .055, fill=color)


def icon_clock(c, x, y, size, color, stroke):
    s = size
    c.circle(x + s / 2, y + s / 2, s * .44, outline=color, stroke=stroke)
    c.line([(x + s * .5, y + s * .24), (x + s * .5, y + s * .52), (x + s * .68, y + s * .62)],
           color, stroke)


def icon_video(c, x, y, size, color, stroke):
    s = size
    c.box(x + s * .04, y + s * .24, x + s * .66, y + s * .76, s * .1, outline=color, stroke=stroke)
    c.line([(x + s * .66, y + s * .44), (x + s * .96, y + s * .28), (x + s * .96, y + s * .72),
            (x + s * .66, y + s * .56)], color, stroke)


def icon_pin(c, x, y, size, color, stroke):
    s = size
    cx = x + s / 2
    c.draw.arc((u(cx - s * .3), u(y + s * .06), u(cx + s * .3), u(y + s * .66)), 150, 390,
               fill=color, width=u(stroke))
    c.line([(cx - s * .26, y + s * .5), (cx, y + s * .94), (cx + s * .26, y + s * .5)], color, stroke)
    c.circle(cx, y + s * .36, s * .1, outline=color, stroke=stroke)


def icon_person(c, cx, cy, r, color, stroke):
    c.circle(cx, cy, r, outline=color, stroke=stroke)
    c.circle(cx, cy - r * .26, r * .24, outline=color, stroke=stroke)
    c.draw.arc((u(cx - r * .48), u(cy + r * .1), u(cx + r * .48), u(cy + r * .78)), 180, 360,
               fill=color, width=u(stroke))


def icon_folder_pen(c, x, y, size, color, stroke):
    s = size
    c.line([(x + s * .04, y + s * .24), (x + s * .04, y + s * .1), (x + s * .36, y + s * .1),
            (x + s * .44, y + s * .2), (x + s * .96, y + s * .2), (x + s * .96, y + s * .9),
            (x + s * .04, y + s * .9), (x + s * .04, y + s * .24), (x + s * .96, y + s * .24)],
           color, stroke)
    # A fountain-pen nib, point down.
    cx = x + s * .5
    c.line([(cx - s * .17, y + s * .38), (cx + s * .17, y + s * .38)], color, stroke)
    c.line([(cx - s * .17, y + s * .38), (cx - s * .2, y + s * .56), (cx, y + s * .82),
            (cx + s * .2, y + s * .56), (cx + s * .17, y + s * .38)], color, stroke)
    c.circle(cx, y + s * .58, s * .045, outline=color, stroke=stroke * .8)
    c.line([(cx, y + s * .63), (cx, y + s * .8)], color, stroke * .8)


def icon_discord(c, cx, cy, width, color, ground):
    """The Discord mark, approximated from simple shapes: a rounded head, two
    flared feet, a dipped chin and forehead, and two eyes."""
    w = width
    x, y = cx - w / 2, cy - w * .38
    c.box(x + w * .08, y + w * .06, x + w * .92, y + w * .68, w * .26, fill=color)
    for side in (.17, .83):
        c.draw.ellipse((u(x + w * (side - .16)), u(y + w * .5), u(x + w * (side + .16)),
                        u(y + w * .78)), fill=color)
    c.draw.ellipse((u(x + w * .26), u(y + w * .66), u(x + w * .74), u(y + w * .9)), fill=ground)
    c.draw.ellipse((u(x + w * .32), u(y - w * .06), u(x + w * .68), u(y + w * .12)), fill=ground)
    for side in (.36, .64):
        c.draw.ellipse((u(x + w * (side - .075)), u(y + w * .34), u(x + w * (side + .075)),
                        u(y + w * .52)), fill=ground)


def arrow(c, start, control, end, color, stroke):
    points = []
    for i in range(25):
        t = i / 24
        points.append(((1 - t) ** 2 * start[0] + 2 * (1 - t) * t * control[0] + t * t * end[0],
                       (1 - t) ** 2 * start[1] + 2 * (1 - t) * t * control[1] + t * t * end[1]))
    c.line(points, color, stroke)
    ex, ey = end
    c.line([(ex - 9, ey - 7), (ex, ey), (ex - 9, ey + 6)], color, stroke)


# --- pictures ---------------------------------------------------------------

@lru_cache(maxsize=4)
def logo(size_px):
    """The mark, with its cream disc turned white so it sits on the white page like the original."""
    mark = Image.open(LOGO).convert("RGBA")
    mark = mark.resize((size_px, round(size_px * mark.height / mark.width)), Image.LANCZOS)
    r, g, b, a = mark.split()
    cream = ImageChops.multiply(
        ImageChops.multiply(r.point(lambda v: 255 if v > 215 else 0),
                            g.point(lambda v: 255 if v > 205 else 0)),
        b.point(lambda v: 255 if v > 180 else 0))
    white = Image.new("RGBA", mark.size, (255, 255, 255, 255))
    mark.paste(white, (0, 0), ImageChops.multiply(cream, a))
    return mark


def rounded(picture, radius_px):
    mask = Image.new("L", picture.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *picture.size), radius=radius_px, fill=255)
    return mask


def qr_image(link, size_px):
    code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, border=0)
    code.add_data(link)
    code.make(fit=True)
    matrix = code.get_matrix()
    count = len(matrix)
    picture = Image.new("RGB", (size_px, size_px), "white")
    draw = ImageDraw.Draw(picture)
    cell = size_px / count
    for row, cells in enumerate(matrix):
        for col, dark in enumerate(cells):
            if dark:
                draw.rectangle((round(col * cell), round(row * cell),
                                round((col + 1) * cell) - 1, round((row + 1) * cell) - 1),
                               fill=INK)
    # The mark in the middle, as on the hand-made poster. Level H correction
    # loses up to 30% of the code and still reads; this covers about 5%.
    hole = round(size_px * .22)
    centre = (size_px - hole) // 2
    draw.rounded_rectangle((centre - 4, centre - 4, centre + hole + 4, centre + hole + 4),
                           radius=6, fill="white")
    picture.paste(logo(hole), (centre, centre), logo(hole))
    return picture


# --- the poster -------------------------------------------------------------

def _clock(moment):
    return f"{moment:%I:%M %p}".lstrip("0")


def render(content, photo):
    """The poster as PNG bytes. `photo` is a Pillow image, already the right way up."""
    c = Canvas()
    start = timezone.localtime(content.starts_at)
    end = timezone.localtime(content.ends_at)

    # Header: the circles in the corner, the mark, the name, the motto.
    for color, (cx, cy), r in CIRCLES:
        c.circle(cx, cy, r, fill=color)
    mark = logo(u(196))
    c.paste(mark, 60, -2, mark)
    c.text(294, 34, "KDU", font(EXTRABOLD, u(86)), INK, squeeze=.94)
    c.text(296, 109, "Developer Community", font(MONO, u(35)), INK, squeeze=.86, stroke=.4)
    tag = font(MONO, u(17.4))
    gap = tag.getlength(" • ") / SCALE
    x = 296
    for part, dot in (("< learn", 0), ("build", 1), ("connect", 2), ("grow />", None)):
        x += c.text(x, 172, part, tag, INK, stroke=.25)
        if dot is not None:
            c.circle(x + gap / 2, 179, 3.4, fill=DOTS[dot])
            x += gap

    # The label in its pill.
    pill = font(SEMIBOLD, u(19.5))
    label = shorten(content.label.upper(), pill, u(230))
    right = 103 + pill.getlength(label) / SCALE + 22
    c.box(42, 235, max(right, 200), 280, 22.5, fill=BLUE)
    icon_calendar(c, 55, 246, 23, "white", 2.1)
    c.text(103, 251, label, pill, "white")

    # Title, the short rule under it, and the summary.
    fnt, lines, step = fit(content.title.upper(), TITLE, 73, 40, 355, 215, 1.048, weight=700,
                           squeeze=.91)
    bottom = c.lines(46, 317, lines, fnt, step, INK, squeeze=.91)
    c.box(47, bottom + 20, 150, bottom + 24, 0, fill=BLUE)
    fnt, lines, step = fit(content.summary, REGULAR, 21.2, 14, 362, 712 - (bottom + 52), 1.5)
    c.lines(47, bottom + 52, lines, fnt, step, TEXT)

    # The speaker.
    icon_person(c, 79, 760, 32, BLUE, 2.2)
    c.text(139, 739, "SPEAKER", font(SEMIBOLD, u(16.5)), BLUE)
    fnt, lines, step = fit(content.speaker_name.upper(), BOLD, 34, 18, 300, 62, 1.06)
    name_bottom = c.lines(139, 768, lines, fnt, step, INK)
    badge = font(SEMIBOLD, u(15.5))
    tag_text = shorten(content.speaker_tag.upper(), badge, u(280))
    width = badge.getlength(tag_text) / SCALE
    top = name_bottom + 14
    c.box(138, top, 138 + width + 28, top + 33, 6, fill=BLUE)
    c.text(152, top + 10.5, tag_text, badge, "white")

    # The photo.
    size = (u(386), u(704))
    framed = ImageOps.fit(photo.convert("RGB"), size, Image.LANCZOS, centering=(0.5, 0.35))
    c.paste(framed, 496, 253, rounded(framed, u(40)))

    # About the talk.
    c.box(37, 942, 461, 1087, 12, fill="white", outline=BOX_LINE, stroke=1.6)
    icon_folder_pen(c, 52, 966, 80, INK, 2.8)
    c.text(152, 959, "ABOUT THE TALK", font(BOLD, u(17.5)), BLUE)
    fnt, lines, step = fit(content.about, REGULAR, 14.6, 10.5, 296, 84, 1.58)
    c.lines(152, 990, lines, fnt, step, TEXT)

    # When and where.
    c.box(499, 980, 554, 1033, 9, fill=TILE)
    icon_calendar(c, 512.5, 993, 28, BLUE, 2.1)
    c.single(575, 989, f"{start:%A}".upper(), SEMIBOLD, 14, 10, 150, BLUE)
    c.single(575, 1012, f"{start.day} {start:%B %Y}".upper(), SEMIBOLD, 14, 10, 150, INK)
    c.line([(727, 978), (727, 1036)], DIVIDER, 1.4)
    c.box(740, 980, 795, 1033, 9, fill=TILE)
    icon_clock(c, 753.5, 993, 28, BLUE, 2.1)
    c.single(809, 989, f"{_clock(start)} -", SEMIBOLD, 14.5, 10, 104, INK)
    c.single(809, 1012, _clock(end), SEMIBOLD, 14.5, 10, 104, INK)
    c.line([(565, 1050), (565, 1110)], DIVIDER, 1.4)
    c.box(578, 1052, 633, 1108, 9, fill=TILE)
    if content.icon == "discord":
        icon_discord(c, 605.5, 1081, 31, BLUE, TILE)
    else:
        (icon_pin if content.icon == "pin" else icon_video)(c, 591.5, 1066, 28, BLUE, 2.1)
    c.single(650, 1065, content.place.upper(), BOLD, 17, 11, 258, INK)
    if content.place_detail:
        c.single(650, 1092, f"({content.place_detail})", SEMIBOLD, 17, 11, 258, INK)

    # The coloured rule and the footer.
    for color, x0, x1 in BAR:
        c.box(x0, 1170, x1, 1175, 0, fill=color)
    c.circle(77, 1230, 28, fill=DISCORD)
    icon_discord(c, 77, 1231, 33, "white", DISCORD)
    c.text(124, 1213, "JOIN THE COMMUNITY", font(BOLD, u(17)), BLUE)
    body = font(REGULAR, u(15.5))
    c.text(124, 1240, "Connect, learn and grow", body, INK)
    c.text(124, 1264, "with fellow developers!", body, INK)
    c.line([(359, 1205), (359, 1280)], DIVIDER, 1.5)
    c.text(405, 1219, "</>", font(MONO_BOLD, u(36)), CODE_GREEN)
    printed = content.link.removeprefix("https://").removeprefix("http://").rstrip("/")
    c.single(405, 1267, printed, MEDIUM, 17, 11, 190, LINK_BLUE)
    c.single(600, 1213, "Scan to join!", HAND, 25, 18, 112, INK, weight=600)
    arrow(c, (640, 1244), (642, 1272), (700, 1268), INK, 1.8)
    c.box(716, 1190, 812, 1286, 6, fill="white", outline=BOX_LINE, stroke=1.2)
    qr = qr_image(content.link, u(86))
    c.paste(qr, 721, 1195)

    final = c.image.resize((WIDTH, HEIGHT), Image.LANCZOS)
    out = io.BytesIO()
    final.save(out, "PNG", optimize=True)
    return out.getvalue()
