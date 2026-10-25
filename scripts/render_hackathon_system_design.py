from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "images" / "hackathon-system-design.png"

W, H = 1800, 1160
BG = "#f7fafc"
INK = "#102a43"
MUTED = "#62748a"
BLUE = "#2563eb"
BLUE_LIGHT = "#e8f1ff"
GREEN = "#0f9f7a"
GREEN_LIGHT = "#e7f8f1"
ORANGE = "#f08a24"
ORANGE_LIGHT = "#fff2df"
RED = "#d94841"
RED_LIGHT = "#ffeceb"
BORDER = "#c9d7e8"
LINE = "#8aa2bf"
WHITE = "#ffffff"


def font(size, weight="regular"):
    names = {
        "regular": ["segoeui.ttf", "arial.ttf"],
        "bold": ["segoeuib.ttf", "arialbd.ttf"],
        "semibold": ["seguisb.ttf", "arialbd.ttf"],
    }
    for name in names[weight]:
        path = Path("C:/Windows/Fonts") / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


F_TITLE = font(44, "bold")
F_SUB = font(21)
F_H2 = font(25, "bold")
F_H3 = font(18, "bold")
F_BODY = font(16)
F_SMALL = font(13)
F_TINY = font(11)


def rr(draw, box, fill, outline=BORDER, width=2, radius=14):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text_center(draw, xy, text, fnt, fill=INK):
    draw.text(xy, text, font=fnt, fill=fill, anchor="mm")


def text_left(draw, xy, text, fnt, fill=INK):
    draw.text(xy, text, font=fnt, fill=fill, anchor="la")


def wrap(draw, text, fnt, max_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=fnt)[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def arrow(draw, start, end, color=LINE, width=3):
    draw.line([start, end], fill=color, width=width)
    x1, y1 = start
    x2, y2 = end
    if abs(x2 - x1) >= abs(y2 - y1):
        direction = 1 if x2 >= x1 else -1
        head = [(x2, y2), (x2 - 16 * direction, y2 - 8), (x2 - 16 * direction, y2 + 8)]
    else:
        direction = 1 if y2 >= y1 else -1
        head = [(x2, y2), (x2 - 8, y2 - 16 * direction), (x2 + 8, y2 - 16 * direction)]
    draw.polygon(head, fill=color)


def node(draw, x, y, w, h, title, body, fill=WHITE, outline=BLUE, accent=None):
    rr(draw, (x, y, x + w, y + h), fill, outline, 2, 12)
    if accent:
        draw.rounded_rectangle((x, y, x + w, y + 9), radius=8, fill=accent)
    text_left(draw, (x + 18, y + 28), title, F_H3, INK)
    body_font = F_SMALL if h >= 90 else F_TINY
    yy = y + (60 if h >= 90 else 50 if h >= 70 else 43)
    max_lines = 0 if h <= 76 else 2
    for line in wrap(draw, body, body_font, w - 34)[:max_lines]:
        text_left(draw, (x + 18, yy), line, body_font, MUTED)
        yy += 18


def lane(draw, box, title, subtitle, fill, outline):
    rr(draw, box, fill, outline, 2, 16)
    x1, y1, _, _ = box
    text_left(draw, (x1 + 20, y1 + 28), title, F_H2, INK)
    text_left(draw, (x1 + 20, y1 + 62), subtitle, F_SMALL, MUTED)


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    text_center(draw, (W / 2, 62), "FinOps Explain AI - Hackathon System Design", F_TITLE)
    text_center(
        draw,
        (W / 2, 105),
        "MAXIMOR Money Operations Track | Multi-agent financial variance intelligence platform",
        F_SUB,
        MUTED,
    )

    summary = (
        "Project summary: FinOps Explain AI turns monthly summaries and transaction CSVs into a concise, "
        "evidence-backed explanation of what changed, why it changed, and which transactions drove the movement."
    )
    rr(draw, (110, 146, W - 110, 218), BLUE_LIGHT, BLUE, 2, 8)
    yy = 166
    for line in wrap(draw, summary, F_BODY, W - 260):
        text_left(draw, (132, yy), line, F_BODY, INK)
        yy += 24

    # Top runtime flow.
    y = 270
    boxes = [
        (105, y, 210, 96, "User / CFO", "Uploads CSVs and asks what changed", BLUE_LIGHT, BLUE),
        (365, y, 220, 96, "React Dashboard", "Upload, loading, charts, reports", BLUE_LIGHT, BLUE),
        (640, y, 220, 96, "FastAPI Backend", "Run orchestration and APIs", BLUE_LIGHT, BLUE),
        (915, y, 230, 96, "Agent Graph", "Specialized agents with traces", GREEN_LIGHT, GREEN),
        (1205, y, 230, 96, "Finance Engine", "Deterministic variance math", GREEN_LIGHT, GREEN),
        (1490, y, 205, 96, "Final Payload", "Dashboard-ready JSON", BLUE_LIGHT, BLUE),
    ]
    for x, by, bw, bh, title, body, fill, outline in boxes:
        node(draw, x, by, bw, bh, title, body, fill, outline, outline)
    for i in range(len(boxes) - 1):
        x, by, bw, bh = boxes[i][:4]
        nx, ny, _, _ = boxes[i + 1][:4]
        arrow(draw, (x + bw + 8, by + bh // 2), (nx - 8, ny + bh // 2), BLUE)

    rr(draw, (255, 395, 1545, 442), "#f3f8ff", BORDER, 2, 10)
    text_center(
        draw,
        (900, 419),
        "Design principle: LLMs explain and synthesize. Deterministic services calculate, reconcile, test, and ground every claim.",
        F_BODY,
        INK,
    )

    lane(
        draw,
        (105, 475, 1695, 642),
        "Tier 1 - Data Intelligence",
        "Normalize uploads into reliable business facts before reasoning begins",
        "#eef7ff",
        BLUE,
    )
    tier1 = [
        (170, 558, 260, 64, "CSV Parser", "schema detection, coercion, preview"),
        (510, 558, 260, 64, "Fetch Tester / QA", "missing fields, quality score, warnings"),
        (850, 558, 260, 64, "Profile Builder", "business JSON and period context"),
        (1190, 558, 260, 64, "Canonical Store", "transactions, summaries, facts"),
    ]
    for b in tier1:
        node(draw, *b, WHITE, BLUE, BLUE)
    for a, b in zip(tier1, tier1[1:]):
        arrow(draw, (a[0] + a[2] + 8, a[1] + 32), (b[0] - 8, b[1] + 32), BLUE)

    lane(
        draw,
        (105, 670, 1695, 832),
        "Tier 2 - Memory + RAG",
        "Bring prior runs, comparable patterns, and evidence into the current analysis",
        GREEN_LIGHT,
        GREEN,
    )
    tier2 = [
        (220, 752, 300, 64, "Memory Agent", "learns business context across runs"),
        (625, 752, 300, 64, "RAG Agent", "retrieves history, docs, evidence"),
        (1030, 752, 300, 64, "Evidence Store", "facts, citations, prior explanations"),
    ]
    for b in tier2:
        node(draw, *b, WHITE, GREEN, GREEN)
    for a, b in zip(tier2, tier2[1:]):
        arrow(draw, (a[0] + a[2] + 8, a[1] + 32), (b[0] - 8, b[1] + 32), GREEN)

    lane(
        draw,
        (105, 860, 1695, 1048),
        "Tier 3 - Analysis, Safety, and Delivery",
        "Explain financial movement, verify grounding, stress test, and produce the final CFO-ready answer",
        ORANGE_LIGHT,
        ORANGE,
    )
    tier3 = [
        (160, 942, 230, 72, "Analyzer / Researcher", "what changed, why, key drivers"),
        (450, 942, 230, 72, "Variance Engine", "bridges, attribution, concentration"),
        (740, 942, 230, 72, "Safety Guardrail", "grounding and claim checks"),
        (1030, 942, 230, 72, "Stress Tester", "edge cases and scenario checks"),
        (1320, 942, 230, 72, "Report Writer", "summary, charts, exportable report"),
    ]
    for idx, b in enumerate(tier3):
        outline = RED if idx == 2 else ORANGE
        accent = RED if idx == 2 else ORANGE
        node(draw, *b, WHITE, outline, accent)
    for a, b in zip(tier3, tier3[1:]):
        arrow(draw, (a[0] + a[2] + 8, a[1] + 36), (b[0] - 8, b[1] + 36), ORANGE)

    # Provider badges.
    badge_y = 1082
    badges = [
        ("Groq: QA, guardrails, stress tests", 325, BLUE_LIGHT, BLUE),
        ("NVIDIA NIM: analyzer and financial reasoning", 770, GREEN_LIGHT, GREEN),
        ("OpenRouter: memory, RAG, report writing", 1245, ORANGE_LIGHT, ORANGE),
    ]
    for text, cx, fill, outline in badges:
        bw = 380
        rr(draw, (cx - bw // 2, badge_y - 22, cx + bw // 2, badge_y + 24), fill, outline, 2, 20)
        text_center(draw, (cx, badge_y + 2), text, F_SMALL, INK)

    text_center(draw, (W / 2, H - 28), "FinOps Explain AI - Money Operations Track System Design", F_SMALL, MUTED)
    img.save(OUT, quality=95)
    print(OUT.resolve())


if __name__ == "__main__":
    main()
