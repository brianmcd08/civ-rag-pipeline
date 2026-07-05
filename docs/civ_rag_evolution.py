"""Generates docs/civ_rag_evolution.png (the architecture evolution diagram).

Regenerate after any phase/stage change:

    uv run --with matplotlib python docs/civ_rag_evolution.py

Gray = stage carried over unchanged; blue = deliberate architecture decision.
"""

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# --- style ---------------------------------------------------------------
GRAY_FILL = "#C4BEB2"
GRAY_EDGE = "#8A8478"
GRAY_TITLE = "#2B2B2B"
GRAY_SUB = "#6E6A60"

BLUE_FILL = "#93BCE5"
BLUE_EDGE = "#3E6FA3"
BLUE_TITLE = "#16355E"
BLUE_SUB = "#2F5486"

HEADER_COLOR = "#3A3A3A"
FOOT_COLOR = "#6E6A60"

# --- content ---------------------------------------------------------------
COLUMNS = ["Parse & route", "Retrieve", "Generate", "Eval", "Memory & deploy"]

ROWS = [
    ("Foundation", "Apr"),
    ("Hardening", "Jun 1–5"),
    ("Agentic", "Jun 6–13"),
    ("Ops", "Jun 25 – Jul 4"),
]

# (title, subtitle, changed?)
CELLS = [
    [
        ("Extractor", "1 LLM call", False),
        ("1 section", "Dense only", False),
        ("Persona", "Montezuma", False),
        ("Reference", "vs ideal ans", False),
        ("—", "No memory", False),
    ],
    [
        ("2 chains", "Parse+route", True),
        ("Multi-sec", "Hybrid α=0.5", True),
        ("No persona", "G 2.65 → 2.88", True),
        ("RAG triad", "CR 3.0 G 2.80", True),
        ("—", "No memory", False),
    ],
    [
        ("Parser only", "Router gone", True),
        ("ReAct agent", "6 tools", True),
        ("No persona", "Same as Hardening", False),
        ("Eval rewired", "ToolMsg pull", True),
        ("MemorySaver", "In-process", True),
    ],
    [
        ("Parser only", "Same as Agentic", False),
        ("ReAct agent", "Same as Agentic", False),
        ("Sonnet 4.6", "Measured swap", True),
        ("Eval rewired", "G 2.93 re-run", False),
        ("PostgresSaver", "Docker Compose", True),
    ],
]

FOOTNOTE = (
    "Dates are commit dates.  Foundation is the April baseline.  "
    "Hardening and Agentic shipped in a Jun 1–13 sprint.  "
    "Ops: Jun 25 infra upgrade, then the Jul 4 measured model swap."
)

# --- layout (in pixels; figure is 2064 x 778 at dpi=100) -------------------
W, H = 2064, 778
LEFT = 225          # x where the first column of cells starts
COL_W, COL_GAP = 332, 15
ROW_TOP = 124       # y (from top) where the first row of cells starts
ROW_H, ROW_GAP = 105, 19
HEADER_Y = 83       # y (from top) of the column header baseline

fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.invert_yaxis()
ax.axis("off")


def draw_cell(x, y, w, h, title, sub, changed):
    fill, edge = (BLUE_FILL, BLUE_EDGE) if changed else (GRAY_FILL, GRAY_EDGE)
    t_col, s_col = (BLUE_TITLE, BLUE_SUB) if changed else (GRAY_TITLE, GRAY_SUB)
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0,rounding_size=10",
            facecolor=fill, edgecolor=edge, linewidth=2,
        )
    )
    ax.text(x + w / 2, y + h * 0.38, title, ha="center", va="center",
            fontsize=17, fontweight="bold", color=t_col)
    ax.text(x + w / 2, y + h * 0.72, sub, ha="center", va="center",
            fontsize=13.5, color=s_col)


# column headers
for c, name in enumerate(COLUMNS):
    ax.text(LEFT + c * (COL_W + COL_GAP) + COL_W / 2, HEADER_Y, name,
            ha="center", va="center", fontsize=17, color=HEADER_COLOR)

# row labels + cells
for r, ((phase, date), row_cells) in enumerate(zip(ROWS, CELLS)):
    y = ROW_TOP + r * (ROW_H + ROW_GAP)
    ax.text(LEFT - 18, y + ROW_H * 0.40, phase, ha="right", va="center",
            fontsize=21, fontweight="bold", color="#111111")
    ax.text(LEFT - 18, y + ROW_H * 0.72, date, ha="right", va="center",
            fontsize=13.5, color=GRAY_SUB)
    for c, (title, sub, changed) in enumerate(row_cells):
        draw_cell(LEFT + c * (COL_W + COL_GAP), y, COL_W, ROW_H, title, sub, changed)

# legend
ly = ROW_TOP + 4 * (ROW_H + ROW_GAP) + 20
for x, fill, edge, label in [
    (LEFT, GRAY_FILL, GRAY_EDGE, "Unchanged"),
    (LEFT + 190, BLUE_FILL, BLUE_EDGE, "Changed"),
]:
    ax.add_patch(
        FancyBboxPatch((x, ly), 34, 24, boxstyle="round,pad=0,rounding_size=5",
                       facecolor=fill, edgecolor=edge, linewidth=2)
    )
    ax.text(x + 44, ly + 12, label, ha="left", va="center", fontsize=15,
            color="#222222")

# footnote
ax.text(LEFT, ly + 52, FOOTNOTE, ha="left", va="center", fontsize=13.5,
        color=FOOT_COLOR, style="italic")

fig.savefig("docs/civ_rag_evolution.png", dpi=100)
print("wrote docs/civ_rag_evolution.png")
