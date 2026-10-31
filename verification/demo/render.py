"""tmux capture-pane -e 의 출력을 PNG · APNG 로 그린다. 셀 단위로 그리므로 표시 폭이 터미널과 같다."""
import re
import unicodedata
from dataclasses import dataclass, replace

from fontTools.ttLib import TTCollection, TTFont
from PIL import Image, ImageDraw, ImageFont

CELL_W = 12
CELL_H = 24
FONT_SIZE = 20
TITLE_H = 40
CAPTION_H = 60
PALETTE_COLORS = 128

BACKGROUND = (22, 24, 29)
FOREGROUND = (212, 212, 212)
CHROME = (40, 43, 51)
CAPTION_BACKGROUND = (13, 15, 19)
CAPTION_TEXT = (240, 240, 240)
ACCENT = (245, 166, 35)
WINDOW_DOTS = ((255, 95, 86), (255, 189, 46), (39, 201, 63))
ANSI_16 = (
    (0, 0, 0), (205, 49, 49), (13, 188, 121), (229, 229, 16),
    (36, 114, 200), (188, 63, 188), (17, 168, 205), (229, 229, 229),
    (102, 102, 102), (241, 76, 76), (35, 209, 139), (245, 245, 67),
    (59, 142, 234), (214, 112, 214), (41, 184, 219), (255, 255, 255),
)

# 공개 이미지에 남기지 않는 문구. 계정 요금제 · 사용량 경고 · Claude Code 의 안내문이고 플러그인 화면이 아니다.
MASKS = (
    re.compile(r' · Clau\w*(?: \w+)?'),
    re.compile(r'Get to finished work sooner[^│]*'),
    re.compile(r'^\s+/model\.\s'),
    re.compile(r'\d+ more notices? hidden'),
    re.compile(r"You've (?:used|hit|reached)[^│]*"),
    re.compile(r'▎[^│]*'),
    re.compile(r'[^│]*weekly limit[^│]*'),
    re.compile(r'[^│]*(?:Share Claude Code|usage credits)[^│]*'),
)

OSC = re.compile(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)')
SGR = re.compile(r'\x1b\[([0-9;:]*)m')
OTHER_CSI = re.compile(r'\x1b\[[0-9;?]*[A-Za-ln-z]')

FONT_DIR = '/System/Library/Fonts'
MENLO = f'{FONT_DIR}/Menlo.ttc'
FALLBACKS = (
    f'{FONT_DIR}/Apple Symbols.ttf',
    f'{FONT_DIR}/AppleSDGothicNeo.ttc',
    f'{FONT_DIR}/Supplemental/Arial Unicode.ttf',
)


@dataclass(frozen=True)
class Style:
    fg: object = None
    bg: object = None
    is_bold: bool = False
    is_dim: bool = False
    is_reversed: bool = False
    is_underlined: bool = False


@dataclass
class Cell:
    char: str
    style: Style
    width: int


def color_256(index):
    if index < 16:
        return ANSI_16[index]
    if index >= 232:
        level = 8 + (index - 232) * 10
        return (level, level, level)
    steps = (0, 95, 135, 175, 215, 255)
    index -= 16
    return (steps[index // 36], steps[index // 6 % 6], steps[index % 6])


def apply_sgr(style, codes):
    position = 0
    while position < len(codes):
        code = codes[position]
        position += 1
        if code == 0:
            style = Style()
        elif code == 1:
            style = replace(style, is_bold=True)
        elif code == 2:
            style = replace(style, is_dim=True)
        elif code == 4:
            style = replace(style, is_underlined=True)
        elif code == 7:
            style = replace(style, is_reversed=True)
        elif code == 22:
            style = replace(style, is_bold=False, is_dim=False)
        elif code == 24:
            style = replace(style, is_underlined=False)
        elif code == 27:
            style = replace(style, is_reversed=False)
        elif 30 <= code <= 37:
            style = replace(style, fg=ANSI_16[code - 30])
        elif code == 39:
            style = replace(style, fg=None)
        elif 40 <= code <= 47:
            style = replace(style, bg=ANSI_16[code - 40])
        elif code == 49:
            style = replace(style, bg=None)
        elif 90 <= code <= 97:
            style = replace(style, fg=ANSI_16[code - 90 + 8])
        elif 100 <= code <= 107:
            style = replace(style, bg=ANSI_16[code - 100 + 8])
        elif code in (38, 48) and position < len(codes):
            mode = codes[position]
            size = 2 if mode == 5 else 4
            values = codes[position + 1:position + size]
            position += size
            color = color_256(values[0]) if mode == 5 else tuple(values)
            style = replace(style, **({'fg': color} if code == 38 else {'bg': color}))
    return style


def parse_screen(ansi, width, height):
    """화면을 행 목록으로 바꾼다. 넓은 글자는 Cell 하나가 두 칸을 차지하고 뒤 칸은 빈 글자로 둔다."""
    rows = []
    style = Style()
    for line in OSC.sub('', ansi).split('\n')[:height]:
        cells = []
        position = 0
        while position < len(line):
            matched = SGR.match(line, position)
            if matched:
                codes = [int(part or 0) for part in re.split('[;:]', matched.group(1))]
                style = apply_sgr(style, codes)
                position = matched.end()
                continue
            other = OTHER_CSI.match(line, position)
            if other:
                position = other.end()
                continue
            char = line[position]
            position += 1
            if unicodedata.combining(char) and cells:
                continue
            char_width = 2 if unicodedata.east_asian_width(char) in 'WF' else 1
            cells.append(Cell(char, style, char_width))
            if char_width == 2:
                cells.append(Cell('', style, 0))
        cells.extend(Cell(' ', Style(), 1) for _ in range(width - len(cells)))
        rows.append(cells[:width])
    while len(rows) < height:
        rows.append([Cell(' ', Style(), 1) for _ in range(width)])
    return rows


def row_text(row):
    return ''.join(cell.char or ' ' for cell in row)


# 마스크가 놓친 문구를 저장 전에 찾는다. 재로드 줄은 녹화 중에 plugin.json 을 고쳤다는 뜻이므로 다시 찍는다.
FORBIDDEN = re.compile(r'reloaded \(modules|weekly limit|/passes|focus-events|Clau\b|Ultra\b|Max\b|credits|Tip:|free reviews')


def forbidden_text(rows):
    return sorted({matched.group() for row in rows for matched in FORBIDDEN.finditer(row_text(row))})


def mask_tips(rows):
    """스피너 아래의 Tip 줄과 이어지는 줄을 지운다. 줄 수가 tip 마다 달라 한 줄 정규식으로 지울 수 없다."""
    is_in_tip = False
    for row in rows:
        text = row_text(row)
        is_in_tip = bool(re.match(r'\s*⎿\s+Tip:', text)) or (is_in_tip and text.startswith('     '))
        if not is_in_tip:
            continue
        end = text.find('│')
        for column in range(end if end >= 0 else len(row)):
            row[column] = Cell(' ', Style(), 1)


def mask_private(rows):
    mask_tips(rows)
    for row in rows:
        for mask in MASKS:
            for matched in mask.finditer(row_text(row)):
                for column in range(matched.start(), matched.end()):
                    row[column] = Cell(' ', Style(), 1)
    return rows


def reversed_text(rows):
    """반전으로 그려진 글자. pane 의 포커스는 반전으로 표시된다."""
    return ''.join(cell.char for row in rows for cell in row if cell.style.is_reversed)


class Fonts:
    def __init__(self):
        self.regular = ImageFont.truetype(MENLO, FONT_SIZE, index=0)
        self.bold = ImageFont.truetype(MENLO, FONT_SIZE, index=1)
        self.chrome = ImageFont.truetype(MENLO, 16, index=0)
        self.caption = ImageFont.truetype(MENLO, 22, index=1)
        self.key = ImageFont.truetype(MENLO, 18, index=1)
        self.menlo_map = TTCollection(MENLO).fonts[0].getBestCmap()
        self.fallbacks = []
        for path in FALLBACKS:
            is_collection = path.endswith('.ttc')
            parsed = TTCollection(path).fonts[0] if is_collection else TTFont(path)
            self.fallbacks.append((ImageFont.truetype(path, FONT_SIZE), parsed.getBestCmap()))

    def font_for(self, char, is_bold):
        if ord(char) in self.menlo_map:
            return self.bold if is_bold else self.regular
        for font, cmap in self.fallbacks:
            if ord(char) in cmap:
                return font
        return self.regular


def blend(front, back, amount):
    return tuple(round(a * amount + b * (1 - amount)) for a, b in zip(front, back))


def cell_colors(style):
    fg = style.fg or FOREGROUND
    bg = style.bg or BACKGROUND
    if style.is_dim:
        fg = blend(fg, bg, 0.6)
    return (bg, fg) if style.is_reversed else (fg, bg)


BOX_ARMS = {
    '─': 'lr', '│': 'ud', '┌': 'rd', '┐': 'ld', '└': 'ru', '┘': 'lu',
    '├': 'udr', '┤': 'udl', '┬': 'lrd', '┴': 'lru', '┼': 'udlr',
}
ROUND_CORNERS = {'╭': (0, 0), '╮': (1, 0), '╯': (1, 1), '╰': (0, 1)}
QUADRANTS = {
    '▘': 'a', '▝': 'b', '▖': 'c', '▗': 'd', '▀': 'ab', '▄': 'cd', '▌': 'ac', '▐': 'bd',
    '▚': 'ad', '▞': 'bc', '▛': 'abc', '▜': 'abd', '▙': 'acd', '▟': 'bcd', '█': 'abcd',
}


def draw_shape(draw, char, left, top, color):
    """선과 블록은 글꼴 대신 칸에 맞춰 그린다. 글꼴로 그리면 줄 사이가 벌어진다."""
    right = left + CELL_W
    bottom = top + CELL_H
    middle_x = left + CELL_W // 2
    middle_y = top + CELL_H // 2
    if char in BOX_ARMS:
        arms = BOX_ARMS[char]
        if 'l' in arms:
            draw.line((left, middle_y, middle_x, middle_y), fill=color, width=2)
        if 'r' in arms:
            draw.line((middle_x, middle_y, right - 1, middle_y), fill=color, width=2)
        if 'u' in arms:
            draw.line((middle_x, top, middle_x, middle_y), fill=color, width=2)
        if 'd' in arms:
            draw.line((middle_x, middle_y, middle_x, bottom - 1), fill=color, width=2)
        return True
    if char in ROUND_CORNERS:
        side_x, side_y = ROUND_CORNERS[char]
        target_x = left if side_x else right - 1
        target_y = top if side_y else bottom - 1
        draw.line((middle_x, middle_y, target_x, middle_y), fill=color, width=2)
        draw.line((middle_x, middle_y, middle_x, target_y), fill=color, width=2)
        return True
    if char == '⏺':
        draw.ellipse((left + 2, middle_y - 4, left + 10, middle_y + 4), fill=color)
        return True
    if char == '⏵':
        draw.polygon(((left + 3, middle_y - 6), (left + 3, middle_y + 6), (left + 10, middle_y)), fill=color)
        return True
    if char == '⏸':
        draw.rectangle((left + 3, middle_y - 6, left + 4, middle_y + 6), fill=color)
        draw.rectangle((left + 8, middle_y - 6, left + 9, middle_y + 6), fill=color)
        return True
    if char in QUADRANTS:
        parts = {
            'a': (left, top, middle_x, middle_y), 'b': (middle_x, top, right, middle_y),
            'c': (left, middle_y, middle_x, bottom), 'd': (middle_x, middle_y, right, bottom),
        }
        for part in QUADRANTS[char]:
            x0, y0, x1, y1 = parts[part]
            draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=color)
        return True
    return False


def locate_mark(rows, mark):
    """(첫 행 정규식, 마지막 행 정규식 또는 None) 을 칸 범위로 바꾼다. 여러 행이고 pane 안이면 pane 너비 전체를 잡는다."""
    first_pattern, last_pattern = mark
    for top, row in enumerate(rows):
        first = re.search(first_pattern, row_text(row))
        if first is None:
            continue
        is_in_pane = '│' in row_text(row)[:first.start()]
        if last_pattern is None:
            return (first.start(), top, first.end(), top + 1)
        right = len(row) - 1 if is_in_pane else first.end()
        left = row_text(row).rindex('│', 0, first.start()) + 1 if is_in_pane else first.start()
        for bottom in range(top, len(rows)):
            last = re.search(last_pattern, row_text(rows[bottom]))
            if last is not None:
                return (left, top, max(right, last.end()), bottom + 1)
    return None


def draw_frame(rows, width, height, fonts, title, caption='', key_label='', mark=None, mark_width=3):
    image = Image.new(
        'RGB',
        (width * CELL_W, TITLE_H + height * CELL_H + CAPTION_H),
        BACKGROUND,
    )
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, image.width, TITLE_H - 1), fill=CHROME)
    for index, dot in enumerate(WINDOW_DOTS):
        center = 22 + index * 22
        draw.ellipse((center - 7, TITLE_H // 2 - 7, center + 7, TITLE_H // 2 + 7), fill=dot)
    draw.text((image.width / 2, TITLE_H / 2), title, font=fonts.chrome, fill=(190, 190, 190), anchor='mm')

    for row_index, row in enumerate(rows):
        top = TITLE_H + row_index * CELL_H
        for column, cell in enumerate(row):
            if cell.width == 0:
                continue
            left = column * CELL_W
            fg, bg = cell_colors(cell.style)
            if bg != BACKGROUND:
                draw.rectangle((left, top, left + CELL_W * cell.width - 1, top + CELL_H - 1), fill=bg)
            if cell.char == ' ' or draw_shape(draw, cell.char, left, top, fg):
                continue
            font = fonts.font_for(cell.char, cell.style.is_bold)
            draw.text((left, top + CELL_H / 2), cell.char, font=font, fill=fg, anchor='lm')
            if cell.style.is_underlined:
                draw.line((left, top + CELL_H - 2, left + CELL_W * cell.width, top + CELL_H - 2), fill=fg)

    if mark is not None:
        located = locate_mark(rows, mark)
        if located is None:
            print(f'  mark not located: {mark}')
        else:
            x0, y0, x1, y1 = located
            draw.rounded_rectangle(
                (x0 * CELL_W - 5, TITLE_H + y0 * CELL_H - 3, x1 * CELL_W + 5, TITLE_H + y1 * CELL_H + 3),
                radius=8, outline=ACCENT, width=mark_width,
            )

    caption_top = TITLE_H + height * CELL_H
    draw.rectangle((0, caption_top, image.width, image.height), fill=CAPTION_BACKGROUND)
    draw.rectangle((0, caption_top, image.width, caption_top + 2), fill=ACCENT)
    middle = caption_top + CAPTION_H // 2 + 1
    draw.text((20, middle), caption, font=fonts.caption, fill=CAPTION_TEXT, anchor='lm')
    if key_label != '':
        text_width = draw.textlength(key_label, font=fonts.key)
        right = image.width - 20
        draw.rounded_rectangle((right - text_width - 24, middle - 17, right, middle + 17), radius=7, fill=ACCENT)
        draw.text((right - 12, middle), key_label, font=fonts.key, fill=(20, 20, 20), anchor='rm')
    return image


def social_preview(screen_path, title, subtitle):
    """GitHub Settings 의 Social preview 에 올리는 1280x640 이미지를 만든다."""
    image = Image.new('RGB', (1280, 640), CAPTION_BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.text((60, 58), title, font=ImageFont.truetype(MENLO, 58, index=1), fill=CAPTION_TEXT)
    draw.text((60, 136), subtitle, font=ImageFont.truetype(MENLO, 26, index=0), fill=ACCENT)
    screen = Image.open(screen_path).convert('RGB')
    width = 1160
    resized = screen.resize((width, round(screen.height * width / screen.width)), Image.Resampling.LANCZOS)
    image.paste(resized.crop((0, 0, width, 640 - 200)), (60, 200))
    return image


def shared_palette(images):
    """여러 프레임을 이어 붙여 팔레트 하나를 만든다. 프레임마다 팔레트가 다르면 색이 깜빡인다."""
    samples = images[:: max(len(images) // 12, 1)]
    sheet = Image.new('RGB', (samples[0].width, samples[0].height * len(samples)))
    for index, image in enumerate(samples):
        sheet.paste(image, (0, index * image.height))
    return sheet.quantize(colors=PALETTE_COLORS, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)


def save_apng(path, frames):
    """frames 는 (Image, 밀리초) 목록이다. 앞 프레임과 달라진 영역만 저장되어 파일이 작다."""
    images = [image for image, _ in frames]
    palette = shared_palette(images)
    indexed = [image.quantize(palette=palette, dither=Image.Dither.NONE) for image in images]
    indexed[0].save(
        path,
        format='PNG',
        save_all=True,
        append_images=indexed[1:],
        duration=[duration for _, duration in frames],
        loop=0,
        disposal=0,
        blend=0,
        compress_level=9,
    )
