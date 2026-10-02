"""Render documentation figures from committed reports; no experiment is rerun.

Python 3.11+ and matplotlib==3.10.8. Run from any directory:
    python docs/visuals/generate.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
INK = "#172B4D"
MUTED = "#526580"
TEAL = "#087F8C"
ORANGE = "#B85516"
PAPER = "#FAFCFF"
GRID = "#DDE5EF"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 11,
    "text.color": INK, "axes.labelcolor": MUTED,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.edgecolor": GRID, "axes.spines.top": False,
    "axes.spines.right": False, "axes.facecolor": PAPER,
    "figure.facecolor": PAPER, "savefig.facecolor": PAPER,
    "svg.hashsalt": "hash-avalanche-documentation-v1",
})


def read_report(name: str) -> dict:
    report = json.loads((ROOT / "results" / "replayable" / f"{name}-100k-seed20261002.json").read_text())
    histogram = {int(k): v for k, v in report["distribution"].items()}
    assert sum(histogram.values()) == report["trials"] == 100_000
    assert sum(k * v for k, v in histogram.items()) == report["distance_sum"]
    assert sum(k * k * v for k, v in histogram.items()) == report["distance_square_sum"]
    assert report["payload_bytes"] == 32 and report["seed"] == 20261002
    assert math.isclose(report["normalized_mean"], report["distance_sum"] / (report["trials"] * report["digest_bits"]))
    return report


def save(fig, name: str, title: str) -> None:
    fig.savefig(HERE / f"{name}.png", dpi=160, metadata={"Title": title})
    svg = HERE / f"{name}.svg"
    fig.savefig(svg, metadata={"Date": None, "Title": title})
    # Matplotlib emits trailing spaces in multiline SVG paths. Newlines already
    # separate coordinates, so normalise whitespace without changing geometry.
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text(encoding="utf-8").splitlines()) + "\n",
                   encoding="utf-8", newline="\n")
    plt.close(fig)


def heading(fig, title: str, subtitle: str) -> None:
    fig.text(.075, .945, title, weight="bold", fontsize=21, va="top")
    fig.text(.075, .885, subtitle, fontsize=11, color=MUTED, va="top")


def distributions() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 6.4), sharex=True, sharey=True)
    fig.subplots_adjust(left=.075, right=.965, bottom=.20, top=.72, wspace=.10)
    heading(fig, "One changed input bit. About half the digest changes.",
            "Observed MD5 and SHA-256 distributions | 100,000 trials each | 32-byte payload | seed 20261002")
    for ax, name, color in zip(axes, ("md5", "sha256"), (ORANGE, TEAL)):
        r = read_report(name)
        bits, n = r["digest_bits"], r["trials"]
        counts = {int(k): v for k, v in r["distribution"].items()}
        x = [k / bits for k in range(bits + 1)]
        density = [counts.get(k, 0) / n * bits for k in range(bits + 1)]
        # Exact Binomial(B, 0.5) reference, scaled by the same 1/B bin width.
        ideal = [math.comb(bits, k) / 2**bits * bits for k in range(bits + 1)]
        ax.fill_between(x, density, step="mid", color=color, alpha=.17)
        ax.step(x, density, where="mid", color=color, linewidth=2, label="Recorded observations")
        ax.plot(x, ideal, color=INK, linestyle=(0, (4, 3)), linewidth=1.5,
                label="Independent-bit reference")
        ax.axvline(.5, color=MUTED, linestyle=":", linewidth=1, zorder=0)
        ax.set_xlim(.25, .75)
        ax.set_ylim(0, 14.6)
        ax.set_xticks([.3, .4, .5, .6, .7])
        ax.set_xlabel("Fraction of digest bits changed (X / B)", labelpad=10)
        ax.set_title(f"{'MD5' if name == 'md5' else 'SHA-256'}  /  {bits} digest bits", loc="left", fontsize=14, weight="bold", pad=31)
        ax.text(0, 1.035, f"Mean {r['normalized_mean']:.6f}  ·  Standard deviation {r['normalized_standard_deviation']:.6f}",
                transform=ax.transAxes, fontsize=10, color=MUTED)
        ax.grid(axis="y", color=GRID, linewidth=.7)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("Probability density", labelpad=10)
    axes[0].legend(loc="upper left", fontsize=9, frameon=False)
    fig.text(.075, .09, "Density = observed fraction / bin width (1/B). The full nonzero range of each recorded histogram is shown.", fontsize=10, color=MUTED)
    fig.text(.075, .047, "A narrower SHA-256 curve is expected from its longer digest; this comparison does not establish cryptographic security.", fontsize=10, color=MUTED)
    save(fig, "normalized-distributions", "Normalized avalanche distributions from committed 100,000-trial reports")


def memory() -> None:
    report = json.loads((ROOT / "benchmarks" / "windows-python-2026-10-02.json").read_text())
    rows = {(r["algorithm"], r["trials"], r["mode"]): r for r in report["records"]}
    fig, axes = plt.subplots(1, 2, figsize=(12, 6.5), sharex=True, sharey=True)
    fig.subplots_adjust(left=.085, right=.965, bottom=.24, top=.73, wspace=.10)
    heading(fig, "Fixed bins replace a growing observation list.",
            "Peak traced Python allocation | controlled retained-distance reference versus streaming aggregation")
    for ax, name in zip(axes, ("md5", "sha256")):
        sizes = [1_000, 10_000, 100_000]
        for n in sizes:
            assert rows[name, n, "retained"]["result_sha256"] == rows[name, n, "streaming"]["result_sha256"]
        for mode, color, marker, label in (("retained", ORANGE, "s", "Retained distances"),
                                           ("streaming", TEAL, "o", "Streaming histogram")):
            peaks = [rows[name, n, mode]["traced_peak_bytes"] / 1024 for n in sizes]
            ax.plot(sizes, peaks, marker=marker, color=color, linewidth=2.2, markersize=7, label=label)
            # Labels describe the final observation; they are not a fitted asymptote.
            ax.annotate(f"{peaks[-1]:,.1f} KiB", (sizes[-1], peaks[-1]), xytext=(-5, 10),
                        textcoords="offset points", ha="right", color=color, weight="bold", fontsize=10)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlim(800, 150_000)
        ax.set_ylim(8, 4000)
        ax.set_xticks(sizes, ["1,000", "10,000", "100,000"])
        ax.set_yticks([10, 100, 1000], ["10", "100", "1,000"])
        ax.minorticks_off()
        ax.set_xlabel("Number of trials (log scale)", labelpad=10)
        ax.set_title("MD5" if name == "md5" else "SHA-256", loc="left", fontsize=14, weight="bold", pad=12)
        ax.grid(which="major", axis="both", color=GRID, linewidth=.7)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("Peak Python allocation (KiB, log scale)", labelpad=10)
    axes[0].legend(loc="upper left", fontsize=10, frameon=False)
    fig.text(.085, .13, "Python 3.12.14 on Windows 11 · 32-byte payload · seed 20261002 · one separate tracemalloc pass per configuration", fontsize=10, color=MUTED)
    fig.text(.085, .083, "Same histogram and integer moments in every paired run. Memory excludes native OpenSSL allocations and total process RSS.", fontsize=10, color=MUTED)
    fig.text(.085, .037, "The baseline stores a list then tuple of trial distances; it is a controlled reference, not a rerun of the historical investigation.", fontsize=10, color=MUTED)
    save(fig, "streaming-memory", "Measured retained versus streaming Python allocation from committed benchmark JSON")


def flow() -> None:
    fig = plt.figure(figsize=(12, 6.2))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 6.2)
    ax.axis("off")
    ax.text(.6, 5.7, "A small experiment with an auditable path to the result.", fontsize=20, weight="bold")
    ax.text(.6, 5.26, "Each trial changes exactly one bit in the bytes passed to the hash function.", fontsize=12, color=MUTED)

    def box(x, y, w, h, title, body, color=INK, tint="#EEF3F9"):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                   linewidth=1, edgecolor=GRID, facecolor=tint))
        ax.text(x+.17, y+h-.31, title, fontsize=12, weight="bold", color=color, va="top")
        ax.text(x+.17, y+h-.71, body, fontsize=10.5, linespacing=1.55, va="top", color=MUTED)

    def arrow(start, end, bend=0):
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=14,
                                    linewidth=1.7, color=MUTED, connectionstyle=f"arc3,rad={bend}"))

    for x, title, body in [
        (.6, "01  Sample bytes", "Local seeded PRNG\nFixed payload length"),
        (3.4, "02  Flip one bit", "Choose bit position\nXOR one bit mask"),
        (6.2, "03  Hash both", "Original + modified\nMD5 or SHA-256"),
        (9.0, "04  Compare", "XOR each digest byte\nCount changed bits: X"),
    ]:
        box(x, 3.30, 2.4, 1.52, title, body)
    for x in (3.0, 5.8, 8.6):
        arrow((x+.025, 4.03), (x+.36, 4.03))
    box(6.2, 1.12, 5.2, 1.51, "05  Keep the distribution, not the trial list",
        "B + 1 histogram bins  ·  count  ·  ΣX  ·  ΣX²\nExact integer aggregation; trial order is discarded.", TEAL, "#EAF7F7")
    box(.6, 1.12, 4.7, 1.51, "06  Report and replay",
        "JSON: configuration + versions + histogram + moments\nReplay regenerates and checks integer observations.")
    arrow((10.2, 3.27), (10.2, 2.68))
    arrow((6.16, 1.87), (5.34, 1.87))
    ax.text(.6, .52, "N trials · P payload bytes · B digest bits", fontsize=11, weight="bold")
    ax.text(5.2, .52, "Work O(N(P + B))  |  O(P + B) stored values", fontsize=11, color=TEAL, weight="bold")
    ax.text(.6, .18, "Counter bit widths still grow with N. Seeded sampling supports replay; it is not cryptographic randomness.", fontsize=10, color=MUTED)
    save(fig, "experiment-flow", "One-bit avalanche experiment and bounded aggregation data flow")


if __name__ == "__main__":
    distributions()
    memory()
    flow()
    print("Generated three SVG/PNG pairs from committed evidence; input consistency checks passed.")
