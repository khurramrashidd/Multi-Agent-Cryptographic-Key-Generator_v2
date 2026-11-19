#!/usr/bin/env python3
"""Fig. 3 - bias sweep, redrawn from results_v2.json (no re-measurement)."""
import json, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
res = json.load(open(sys.argv[1]))
out = sys.argv[2]
sweep, p0 = res["bias_sweep"], res["alarm"]["baseline_p0"]
plt.rcParams.update({"font.family": "serif", "font.size": 8})
xs = [s["p1"] for s in sweep]
fig, ax1 = plt.subplots(figsize=(4.8, 2.7), dpi=300)
ax1.plot(xs, [100 * s["per_key_detection"] for s in sweep], "o-", c="#222222", lw=1.2, ms=3.5,
         label="Per-key rejection (%)")
ax1.axhline(100 * p0, ls=":", c="#222222", lw=0.9, label="Healthy baseline (%.1f%%)" % (100 * p0))
ax1.set_xlabel("Source bias P(1)")
ax1.set_ylabel("Per-key rejection (%)")
ax1.set_ylim(-3, 103)
ax2 = ax1.twinx()
ok = [s for s in sweep if s["alarm_rate"] >= 0.95]
ax2.plot([s["p1"] for s in ok], [s["median_keys_to_alarm"] for s in ok], "s--", c="#777777",
         lw=1.2, ms=3.5, label="Median keys to alarm (where $\\geq$95% of streams alarm)")
ax2.set_yscale("log")
ax2.set_ylim(1, 2000)
ax2.set_ylabel("Median keys to alarm (log)")
h1, l1 = ax1.get_legend_handles_labels()
h2, l2 = ax2.get_legend_handles_labels()
fig.legend(h1 + h2, l1 + l2, fontsize=6.5, loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 1.0), columnspacing=1.2, handlelength=2.2)
fig.tight_layout(rect=(0, 0, 1, 0.84))
fig.savefig(out)
print("written", out)
