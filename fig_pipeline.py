#!/usr/bin/env python3
"""Fig. 1 - CryptoKMS validate-before-dispatch pipeline (matches backend/app.py)."""
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = sys.argv[1] if len(sys.argv) > 1 else "fig_pipeline.png"
plt.rcParams.update({"font.family": "serif", "font.size": 7})
fig, ax = plt.subplots(figsize=(4.8, 3.15), dpi=300)
ax.set_xlim(0, 100)
ax.set_ylim(0, 67.5)
ax.axis("off")

AGENT = "#e8eef6"
CHECK = "#f3f3f3"
GATE = "#fff4dc"
OK = "#e3f1e3"
BAD = "#f6e0e0"


def box(x, y, w, h, text, fc, bold=False, fs=6.6):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=1.2",
                                fc=fc, ec="#333333", lw=0.7))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            fontweight=("bold" if bold else "normal"), linespacing=1.25)


def arrow(x0, y0, x1, y1, text=None, tx=0, ty=0, style="-|>"):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle=style, lw=0.8, color="#222222", shrinkA=0, shrinkB=0))
    if text:
        ax.text((x0 + x1) / 2 + tx, (y0 + y1) / 2 + ty, text, fontsize=6, ha="center",
                va="center", style="italic")


# row 1: request -> generator -> raw extraction
box(1, 55, 16, 9, "Key request\n(algorithm,\nkey length)", "#ffffff", fs=6.2)
box(21, 55, 25, 9, "KeyGeneratorAgent\nOS CSPRNG /\nPyCryptodome", AGENT, fs=6.2)
box(50, 55, 38, 9, "Raw-material extraction\nAES key bytes | ECC scalar $d$\n| RSA modulus $n$", CHECK, fs=6.2)
arrow(17.6, 59.5, 20.4, 59.5)
arrow(46.6, 59.5, 49.4, 59.5)

# row 2: parallel validators (leave a corridor on the right for the retry path)
ys, h = 36, 12
xs = [1, 23, 45, 67]
labels = ["MathModelAgent\nentropy $H \\geq \\tau_L$\nMonobit $p \\geq 0.01$",
          "AIEntropyAgent\ntransition ratio\n$|t-0.5| \\leq 2.576\\,\\sigma_t$",
          "Duplicate screen\nSHA-256 index\nof issued material",
          "CryptoStrength-\nAgent\nSP 800-57 strength"]
for x, lab in zip(xs, labels):
    box(x, ys, 20, h, lab, AGENT, fs=6.2)
for x in xs:
    arrow(69, 54.4, x + 10, ys + h + 0.6)

# gate and retry decision
box(14, 20, 40, 9, "Unanimous acceptance gate\n(all checks pass, no duplicate)", GATE, bold=True, fs=6.4)
for x in xs:
    arrow(x + 10, ys - 0.6, 34 + (x + 10 - 34) * 0.30, 29.6)
box(62, 20, 26, 9, "Rejected:\nattempt < N = 10 ?", "#ffffff", fs=6.4)
arrow(54.6, 24.5, 61.4, 24.5, "reject", ty=1.6)

# retry path: right corridor, over the top row, back into the generator
ax.plot([88.6, 95, 95, 33.5], [24.5, 24.5, 66, 66], ls=(0, (3, 2)), lw=0.8, c="#555555")
ax.annotate("", xy=(33.5, 64.4), xytext=(33.5, 66.02),
            arrowprops=dict(arrowstyle="-|>", lw=0.8, color="#555555", shrinkA=0, shrinkB=0))
ax.text(96.2, 45, "yes: regenerate", rotation=90, fontsize=6, style="italic", va="center", color="#333333")

# outcomes
box(1, 2, 38, 10, "Dispatch key with per-agent\nverdict trail; register in vault", OK, fs=6.4)
box(62, 2, 26, 10, "no: fail closed\nEntropyFault,\nnothing dispatched", BAD, fs=6.4)
arrow(25, 19.4, 20, 12.6, "pass", tx=-3.5, ty=0.6)
arrow(75, 19.4, 75, 12.6)
ax.text(50.5, 7, "PerformanceAgent\nlogs latency and\nretry count", fontsize=5.8,
        ha="center", va="center", color="#333333", style="italic")
fig.tight_layout(pad=0.2)
fig.savefig(OUT)
print("written", OUT)
