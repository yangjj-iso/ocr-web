from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
    ]
    for path in candidates:
        p = Path(path)
        if p.exists():
            return ImageFont.truetype(str(p), size=size)
    return ImageFont.load_default()


def draw_centered_text(draw: ImageDraw.ImageDraw, box, text, font, fill=(31, 45, 61)):
    x1, y1, x2, y2 = box
    w, h = draw.textbbox((0, 0), text, font=font)[2:]
    tx = x1 + (x2 - x1 - w) / 2
    ty = y1 + (y2 - y1 - h) / 2
    draw.text((tx, ty), text, font=font, fill=fill)


def draw_actor(draw: ImageDraw.ImageDraw, x: int, y: int, label: str, font: ImageFont.FreeTypeFont):
    color = (44, 62, 80)
    # head
    draw.ellipse((x - 22, y, x + 22, y + 44), outline=color, width=3)
    # body
    draw.line((x, y + 44, x, y + 115), fill=color, width=3)
    # arms
    draw.line((x - 45, y + 70, x + 45, y + 70), fill=color, width=3)
    # legs
    draw.line((x, y + 115, x - 35, y + 165), fill=color, width=3)
    draw.line((x, y + 115, x + 35, y + 165), fill=color, width=3)
    # label
    tw = draw.textbbox((0, 0), label, font=font)[2]
    draw.text((x - tw / 2, y + 178), label, fill=color, font=font)


def draw_usecase(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    w: int = 290,
    h: int = 74,
):
    box = (cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2)
    fill = (242, 247, 255)
    outline = (68, 114, 196)
    draw.ellipse(box, fill=fill, outline=outline, width=3)
    draw_centered_text(draw, box, text, font=font, fill=(33, 52, 79))
    return box


def draw_line_to_box(draw: ImageDraw.ImageDraw, x: int, y: int, box, side: str):
    x1, y1, x2, y2 = box
    if side == "left":
        tx, ty = x1, (y1 + y2) // 2
    else:
        tx, ty = x2, (y1 + y2) // 2
    draw.line((x, y, tx, ty), fill=(102, 120, 148), width=2)


def main():
    width, height = 1920, 1080
    img = Image.new("RGB", (width, height), (248, 250, 253))
    draw = ImageDraw.Draw(img)

    title_font = load_font(52)
    subtitle_font = load_font(28)
    actor_font = load_font(30)
    uc_font = load_font(26)
    small_font = load_font(22)

    # Title
    title = "人社档案系统 功能用例图（第一阶段现状）"
    draw_centered_text(draw, (0, 28, width, 110), title, title_font, fill=(24, 54, 99))
    subtitle = "业务口径：导入 -> 识别 -> 校对 -> 归档 -> 质检"
    draw_centered_text(draw, (0, 110, width, 160), subtitle, subtitle_font, fill=(82, 102, 130))

    # System boundary
    boundary = (380, 190, 1540, 940)
    draw.rounded_rectangle(boundary, radius=18, outline=(93, 120, 173), width=3, fill=(255, 255, 255))
    draw.text((410, 210), "系统边界：档案智能整理平台", fill=(62, 83, 116), font=small_font)

    # Actors
    draw_actor(draw, 170, 320, "档案专员", actor_font)
    draw_actor(draw, 1740, 320, "审核管理员", actor_font)

    # Use cases
    usecases_left = [
        ("批量导入材料", 640, 320),
        ("选择识别模式", 640, 420),
        ("查看批次进度", 640, 520),
        ("人工编辑结果", 640, 620),
        ("保存归档并检索", 640, 720),
    ]
    usecases_right = [
        ("核对关键信息", 1240, 380),
        ("处理冲突与异常", 1240, 500),
        ("确认质量结果", 1240, 620),
    ]
    center_usecase = ("批次问答（证据可追溯）", 940, 820)

    left_boxes = []
    right_boxes = []
    for t, x, y in usecases_left:
        left_boxes.append(draw_usecase(draw, x, y, t, uc_font))
    for t, x, y in usecases_right:
        right_boxes.append(draw_usecase(draw, x, y, t, uc_font))
    center_box = draw_usecase(draw, center_usecase[1], center_usecase[2], center_usecase[0], uc_font, w=430, h=78)

    # actor links
    actor_left_anchor = (220, 390)
    for b in left_boxes:
        draw_line_to_box(draw, actor_left_anchor[0], actor_left_anchor[1], b, side="left")
    draw_line_to_box(draw, actor_left_anchor[0], actor_left_anchor[1], center_box, side="left")

    actor_right_anchor = (1690, 390)
    for b in right_boxes:
        draw_line_to_box(draw, actor_right_anchor[0], actor_right_anchor[1], b, side="right")
    draw_line_to_box(draw, actor_right_anchor[0], actor_right_anchor[1], center_box, side="right")

    # flow line
    flow_points = [(640, 320), (640, 420), (640, 520), (640, 620), (640, 720), (940, 820)]
    for i in range(len(flow_points) - 1):
        draw.line((flow_points[i][0], flow_points[i][1] + 40, flow_points[i + 1][0], flow_points[i + 1][1] - 40), fill=(170, 184, 210), width=2)

    # Footer
    footer = "说明：本图用于汇报展示，聚焦已落地功能与可核验能力，不涉及底层模型供应商信息。"
    draw_centered_text(draw, (300, 960, 1620, 1035), footer, small_font, fill=(98, 113, 138))

    out = Path(r"D:\OCR\docs\hr_usecase_diagram_phase1.png")
    img.save(out, format="PNG")
    print(str(out))


if __name__ == "__main__":
    main()
