from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "images" / "prism-integration-architecture.png"

W, H = 1800, 1260
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
PURPLE = "#6d4aff"
PURPLE_LIGHT = "#f1edff"
BORDER = "#c9d7e8"
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


def arrow(draw, start, end, color=BLUE, width=3):
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
    yy = y + (60 if h >= 90 else 48)
    max_lines = 2 if h >= 84 else 1
    for line in wrap(draw, body, F_SMALL, w - 34)[:max_lines]:
        text_left(draw, (x + 18, yy), line, F_SMALL, MUTED)
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

    text_center(draw, (W / 2, 62), "FinOps Explain AI + PRISM", F_TITLE)
    text_center(
        draw,
        (W / 2, 105),
        "Financial agent observability, evaluation, guardrails, and reliability architecture",
        F_SUB,
        MUTED,
    )

    summary = (
        "PRISM sits beside the financial-analysis runtime: it receives redacted run telemetry, connects outcomes to agent execution, "
        "evaluates evidence and guardrails, and turns repeat failures into validated regression scenarios."
    )
    rr(draw, (110, 146, W - 110, 218), BLUE_LIGHT, BLUE, 2, 8)
    yy = 166
    for line in wrap(draw, summary, F_BODY, W - 260):
        text_left(draw, (132, yy), line, F_BODY, INK)
        yy += 24

    # Primary product execution path.
    y = 260
    top = [
        (105, y, 235, 96, "User / CFO", "Uploads summaries and transaction CSVs", BLUE_LIGHT, BLUE),
        (405, y, 245, 96, "React Dashboard", "Upload, run progress, insights, drilldown", BLUE_LIGHT, BLUE),
        (715, y, 245, 96, "FastAPI Orchestrator", "Run IDs, job state, APIs, trace context", BLUE_LIGHT, BLUE),
        (1025, y, 275, 96, "Agent + Finance Runtime", "Agents, RAG, guardrails, deterministic math", GREEN_LIGHT, GREEN),
        (1365, y, 330, 96, "CFO-ready Explanation", "Narrative, drivers, citations, confidence", GREEN_LIGHT, GREEN),
    ]
    for x, by, bw, bh, title, body, fill, outline in top:
        node(draw, x, by, bw, bh, title, body, fill, outline, outline)
    for a, b in zip(top, top[1:]):
        arrow(draw, (a[0] + a[2] + 8, a[1] + 48), (b[0] - 8, b[1] + 48), BLUE)

    # PRISM integration layer.
    lane(
        draw,
        (105, 395, 1695, 594),
        "PRISM - Observability and Reliability Layer",
        "Asynchronous telemetry stays off the user request path; evidence and outcome signals remain connected to each analysis session",
        PURPLE_LIGHT,
        PURPLE,
    )
    prism = [
        (145, 492, 260, 72, "Trace Adapter", "redacted inputs, outputs, latency, model metadata"),
        (465, 492, 260, 72, "Session + Agent Run", "spans for agents, tools, retrieval, retries"),
        (785, 492, 260, 72, "Evaluators", "reconciliation, grounding, safety, quality checks"),
        (1105, 492, 260, 72, "Outcome Signals", "user goal, evidence, guardrail events, confidence"),
        (1425, 492, 230, 72, "Findings", "patterns, review queue, remediation"),
    ]
    for b in prism:
        node(draw, *b, WHITE, PURPLE, PURPLE)
    for a, b in zip(prism, prism[1:]):
        arrow(draw, (a[0] + a[2] + 8, a[1] + 36), (b[0] - 8, b[1] + 36), PURPLE)

    # Telemetry and feedback connections.
    arrow(draw, (837, 364), (837, 482), PURPLE, 3)
    arrow(draw, (1162, 364), (1162, 482), PURPLE, 3)
    arrow(draw, (1540, 364), (1540, 482), PURPLE, 3)
    text_center(draw, (880, 431), "async telemetry", F_TINY, MUTED)
    arrow(draw, (1540, 575), (1540, 654), PURPLE, 3)
    arrow(draw, (1540, 654), (1080, 654), PURPLE, 3)
    arrow(draw, (1080, 654), (1080, 614), PURPLE, 3)
    text_center(draw, (1310, 637), "validated regressions and remediation feedback", F_TINY, MUTED)

    # Core product tiers.
    lane(
        draw,
        (105, 675, 1695, 830),
        "Tier 1 - Data and Evidence",
        "Create reliable business facts before any financial explanation is generated",
        "#eef7ff",
        BLUE,
    )
    tier1 = [
        (175, 755, 255, 52, "CSV Parser", "schema, mapping, validation"),
        (500, 755, 255, 52, "Fetch Tester / QA", "quality warnings and completeness"),
        (825, 755, 255, 52, "Profile Builder", "normalized period and account JSON"),
        (1150, 755, 255, 52, "Evidence Store", "transactions, citations, source IDs"),
    ]
    for b in tier1:
        node(draw, *b, WHITE, BLUE, BLUE)
    for a, b in zip(tier1, tier1[1:]):
        arrow(draw, (a[0] + a[2] + 8, a[1] + 26), (b[0] - 8, b[1] + 26), BLUE)

    lane(
        draw,
        (105, 865, 1695, 1035),
        "Tier 2 - Agent Intelligence and Safety",
        "Retrieve relevant context, attribute financial movement, and verify the answer before delivery",
        GREEN_LIGHT,
        GREEN,
    )
    tier2 = [
        (145, 960, 230, 52, "Memory + RAG", "history, evidence, comparable periods"),
        (445, 960, 230, 52, "Analyzer / Researcher", "drivers, concentration, explanation"),
        (745, 960, 230, 52, "Finance Engine", "deterministic reconciliation and math"),
        (1045, 960, 230, 52, "Safety Guardrail", "grounding and claim checks"),
        (1345, 960, 230, 52, "Report Writer", "final concise, cited narrative"),
    ]
    for idx, b in enumerate(tier2):
        outline = RED if idx == 3 else GREEN
        accent = RED if idx == 3 else GREEN
        node(draw, *b, WHITE, outline, accent)
    for a, b in zip(tier2, tier2[1:]):
        arrow(draw, (a[0] + a[2] + 8, a[1] + 26), (b[0] - 8, b[1] + 26), GREEN)

    # Footer panels.
    footer_y = 1100
    footer = [
        (365, "Explainable AI", "claim to evidence, calculation, and agent path", BLUE_LIGHT, BLUE),
        (900, "Safety and Privacy", "redaction, policy checks, human review", RED_LIGHT, RED),
        (1435, "Scalable Operations", "async ingest, trace sampling, retention tiers", ORANGE_LIGHT, ORANGE),
    ]
    for cx, title, body, fill, outline in footer:
        rr(draw, (cx - 220, footer_y, cx + 220, footer_y + 68), fill, outline, 2, 16)
        text_center(draw, (cx, footer_y + 23), title, F_H3, INK)
        text_center(draw, (cx, footer_y + 47), body, F_SMALL, MUTED)

    text_center(draw, (W / 2, H - 26), "FinOps Explain AI - PRISM Integration Architecture", F_SMALL, MUTED)
    img.save(OUT, quality=95)
    print(OUT.resolve())


if __name__ == "__main__":
    main()
