#!/usr/bin/env python3
"""CryptoKMS - independent verification and extended evaluation.

Re-implements the validate-before-dispatch checks from the method
specification (thresholds fixed a priori), then:
  E1  baseline statistics: AES-256, ECC P-256, RSA-2048
  E2  encoding artefact: raw material vs PEM / DER exports
  E3  fault injection: five generator classes, 2,000 keys each
  E4  detection delay: sequential binomial alarm vs healthy baseline
  E5  bias sweep: detection power as a function of P(1)
  E6  overhead and throughput

Run:  python3 verify_cryptokms.py [output_dir]
Writes results_v2.json, fig_entropy.png, fig_bias_sweep.png
Rule A = original entropy rule, Rule B = corrected rule (see entropy_threshold).
"""
import hashlib
import json
import math
import os
import platform
import random
import secrets
import statistics
import sys
import time

import numpy as np
from scipy import stats
from scipy.special import erfc
from Crypto.PublicKey import ECC, RSA

OUT = sys.argv[1] if len(sys.argv) > 1 else "."
os.makedirs(OUT, exist_ok=True)

# ---------------- thresholds (fixed a priori) ----------------
ALPHA = 0.01        # Monobit significance level
ENT_FRAC = 0.90     # entropy acceptance fraction of attainable ceiling
Z_TRANS = 2.576     # 99% two-sided normal band for transition ratio
ALARM_ALPHA = 1e-3  # significance of the aggregate (stream-level) alarm
RNG = np.random.default_rng(2027)


# ---------------- vectorised checks over an (N, L) uint8 array ----------------
def shannon_rows(a):
    """Byte-level Shannon entropy per row."""
    s = np.sort(a, axis=1)
    n = a.shape[1]
    out = np.empty(a.shape[0])
    for i, row in enumerate(s):
        _, c = np.unique(row, return_counts=True)
        p = c / n
        out[i] = -(p * np.log2(p)).sum()
    return out


def monobit_rows(a):
    bits = np.unpackbits(a, axis=1)
    n = bits.shape[1]
    s = 2 * bits.sum(axis=1).astype(np.int64) - n
    return erfc(np.abs(s) / math.sqrt(2 * n))


def transition_rows(a):
    bits = np.unpackbits(a, axis=1)
    return (bits[:, 1:] != bits[:, :-1]).sum(axis=1) / (bits.shape[1] - 1)


_REF = {}


def entropy_reference(L, n=200000, seed=90210):
    """Distribution of byte-level Shannon entropy for L uniform bytes
    (design constant derived from a uniform source, not from evaluation data)."""
    if L in _REF:
        return _REF[L]
    rng = np.random.default_rng(seed + L)
    H = np.empty(n)
    step = 20000
    for s0 in range(0, n, step):
        a = rng.integers(0, 256, size=(step, L), dtype=np.int64)
        c = np.zeros((step, 256), dtype=np.int64)
        np.add.at(c, (np.arange(step)[:, None], a), 1)
        p = c / L
        with np.errstate(divide="ignore", invalid="ignore"):
            H[s0:s0 + step] = -np.where(p > 0, p * np.log2(p), 0).sum(axis=1)
    _REF[L] = {"mean": float(H.mean()), "sd": float(H.std()),
               "q001": float(np.quantile(H, 0.001)),
               "ceiling": math.log2(min(256, L))}
    return _REF[L]


def entropy_threshold(L, rule):
    """Rule A: 0.9 * log2(min(256, L))  (original a-priori rule).
    Rule B: 0.1% quantile of H_L under a uniform source (corrected rule)."""
    if rule == "A":
        return ENT_FRAC * math.log2(min(256, L))
    return entropy_reference(L)["q001"]


def checks(a, rule="B"):
    L = a.shape[1]
    nbits = 8 * L
    H = shannon_rows(a)
    P = monobit_rows(a)
    T = transition_rows(a)
    band = Z_TRANS * 0.5 / math.sqrt(nbits - 1)
    e_ok = H >= entropy_threshold(L, rule)
    m_ok = P >= ALPHA
    t_ok = np.abs(T - 0.5) <= band
    return H, P, T, e_ok, m_ok, t_ok, (e_ok & m_ok & t_ok)


def to_arr(byte_list):
    return np.frombuffer(b"".join(byte_list), dtype=np.uint8).reshape(len(byte_list), -1)


# ---------------- generators ----------------
def g_csprng(n):
    return to_arr([secrets.token_bytes(32) for _ in range(n)])


def g_stuck(n):
    return np.full((n, 32), 0xAA, dtype=np.uint8)


def g_biased(n, p1=0.55, rng=RNG):
    bits = (rng.random((n, 256)) < p1).astype(np.uint8)
    return np.packbits(bits, axis=1)


def g_mt(n, seed=1337):
    r = random.Random(seed)
    return to_arr([r.getrandbits(256).to_bytes(32, "big") for _ in range(n)])


_POOL = None


def g_debian(n, pool_bits=15, seed=42):
    global _POOL
    if _POOL is None:
        _POOL = [hashlib.sha256(i.to_bytes(2, "big")).digest() for i in range(2 ** pool_bits)]
    r = random.Random(seed)
    return to_arr([_POOL[r.randrange(len(_POOL))] for _ in range(n)])


def duplicates(a):
    seen, dup = set(), 0
    for row in a:
        k = row.tobytes()
        if k in seen:
            dup += 1
        seen.add(k)
    return dup


# ---------------- sequential aggregate alarm ----------------
def alarm_curve(p0, max_m):
    """Smallest rejection count r_m that raises the alarm after m keys:
    P(X >= r_m | m, p0) < ALARM_ALPHA under a healthy generator."""
    crit = np.empty(max_m + 1, dtype=np.int64)
    for m in range(1, max_m + 1):
        r = int(stats.binom.isf(ALARM_ALPHA, m, p0)) + 1
        while stats.binom.sf(r - 1, m, p0) >= ALARM_ALPHA:
            r += 1
        crit[m] = r
    crit[0] = 10 ** 9
    return crit


def keys_to_alarm(reject_vec, crit):
    """First m at which cumulative rejections reach the critical count; None if never."""
    cum = np.cumsum(reject_vec)
    m = np.arange(1, len(reject_vec) + 1)
    hit = np.nonzero(cum >= crit[m])[0]
    return int(hit[0] + 1) if hit.size else None


def stream_study(gen, p0, crit, streams=300, length=2000):
    delays, missed = [], 0
    for _ in range(streams):
        rej = ~checks(gen(length))[6]
        d = keys_to_alarm(rej, crit)
        if d is None:
            missed += 1
        else:
            delays.append(d)
    rate = len(delays) / streams
    return {
        "alarm_rate_within_%d" % length: rate,
        "median_keys_to_alarm": (float(np.median(delays)) if delays else None),
        "p95_keys_to_alarm": (float(np.percentile(delays, 95)) if delays else None),
        "streams": streams,
    }


# ---------------- E1 baseline ----------------
def summarize(raw, gen_ms, val_ms):
    H, P, T, e_okA, m_ok, t_ok, okA = checks(raw, "A")
    e_okB = H >= entropy_threshold(raw.shape[1], "B")
    okB = e_okB & m_ok & t_ok
    n = raw.shape[0]
    passed = int(m_ok.sum())
    bt = stats.binomtest(passed, n, 0.99)
    lo, hi = bt.proportion_ci(0.95, method="wilson")
    L = raw.shape[1]
    ref = entropy_reference(L)
    return {
        "n": n, "bytes": int(L),
        "H_ceiling": ref["ceiling"], "H_expected_uniform": ref["mean"],
        "H_sd_uniform": ref["sd"],
        "thr_ruleA": entropy_threshold(L, "A"), "thr_ruleB": entropy_threshold(L, "B"),
        "H_mean": float(H.mean()), "H_sd": float(H.std()), "H_min": float(H.min()),
        "entropy_pass_ruleA": float(e_okA.mean()), "entropy_pass_ruleB": float(e_okB.mean()),
        "monobit_pass": passed / n, "monobit_ci95": [float(lo), float(hi)],
        "monobit_vs_nominal_p": float(bt.pvalue),
        "transition_pass": float(t_ok.mean()), "trans_mean": float(T.mean()),
        "joint_accept_ruleA": float(okA.mean()), "joint_accept_ruleB": float(okB.mean()),
        "gen_ms": gen_ms, "val_ms": val_ms,
    }


def timed(fn, n):
    t0 = time.perf_counter()
    out = fn()
    return out, (time.perf_counter() - t0) / n * 1000


res = {"env": {"python": platform.python_version(), "machine": platform.machine(),
               "system": platform.platform(), "numpy": np.__version__}}
try:
    import Crypto
    import scipy
    res["env"]["pycryptodome"] = Crypto.__version__
    res["env"]["scipy"] = scipy.__version__
except Exception:
    pass
try:
    res["env"]["cpu"] = [l.split(":")[1].strip() for l in open("/proc/cpuinfo")
                         if "model name" in l][0]
except Exception:
    pass

print("E1 baseline ...", flush=True)
for _L in (16, 24, 32, 128, 256, 512):
    entropy_reference(_L)  # precompute so it never falls inside a timing window
aes_list, gen_aes = timed(lambda: [secrets.token_bytes(32) for _ in range(10000)], 10000)
aes = to_arr(aes_list)
_, val_aes = timed(lambda: [checks(aes[i:i + 1]) for i in range(2000)], 2000)
res["aes"] = summarize(aes, gen_aes, val_aes)

ecc_keys, gen_ecc = timed(lambda: [ECC.generate(curve="P-256") for _ in range(1000)], 1000)
ecc = to_arr([int(k.d).to_bytes(32, "big") for k in ecc_keys])
_, val_ecc = timed(lambda: [checks(ecc[i:i + 1]) for i in range(1000)], 1000)
res["ecc"] = summarize(ecc, gen_ecc, val_ecc)

rsa_keys, gen_rsa = timed(lambda: [RSA.generate(2048) for _ in range(200)], 200)
rsa = to_arr([k.n.to_bytes(256, "big") for k in rsa_keys])
_, val_rsa = timed(lambda: [checks(rsa[i:i + 1]) for i in range(200)], 200)
res["rsa"] = summarize(rsa, gen_rsa, val_rsa)

qA = 1 - res["rsa"]["joint_accept_ruleA"]
qB = 1 - res["rsa"]["joint_accept_ruleB"]
res["rsa_retry_impact"] = {
    "expected_attempts_ruleA": 1 / (1 - qA), "fail_closed_prob_ruleA": qA ** 10,
    "expected_attempts_ruleB": 1 / (1 - qB), "fail_closed_prob_ruleB": qB ** 10}
res["entropy_reference"] = {str(L): entropy_reference(L) for L in (16, 24, 32, 128, 256, 512)}
for L in (16, 24, 32, 128, 256, 512):
    ref = res["entropy_reference"][str(L)]
    ref["thr_ruleA"] = entropy_threshold(L, "A")
    rng_chk = np.random.default_rng(7 + L)
    samp = rng_chk.integers(0, 256, size=(20000, L), dtype=np.uint8)
    Hs = shannon_rows(samp)
    ref["ruleA_false_reject"] = float((Hs < ref["thr_ruleA"]).mean())
    ref["ruleB_false_reject"] = float((Hs < ref["q001"]).mean())

# ---------------- E2 encoding artefact ----------------
print("E2 encodings ...", flush=True)


def enc_stats(blobs):
    P = np.array([monobit_rows(np.frombuffer(b, dtype=np.uint8)[None, :])[0] for b in blobs])
    H = np.array([shannon_rows(np.frombuffer(b, dtype=np.uint8)[None, :])[0] for b in blobs])
    return {"monobit_pass": float((P >= ALPHA).mean()), "H_mean": float(H.mean())}


res["encodings"] = {
    "ecc_raw": {"monobit_pass": res["ecc"]["monobit_pass"], "H_mean": res["ecc"]["H_mean"]},
    "ecc_der": enc_stats([k.export_key(format="DER") for k in ecc_keys]),
    "ecc_pem": enc_stats([k.export_key(format="PEM").encode() for k in ecc_keys]),
    "rsa_raw": {"monobit_pass": res["rsa"]["monobit_pass"], "H_mean": res["rsa"]["H_mean"]},
    "rsa_pem": enc_stats([k.export_key() for k in rsa_keys]),
}

# ---------------- E3 fault injection ----------------
print("E3 fault injection ...", flush=True)
classes = {
    "control_csprng": g_csprng,
    "stuck_at": g_stuck,
    "biased_0.55": lambda n: g_biased(n, 0.55),
    "mersenne_twister": g_mt,
    "debian_15bit_pool": g_debian,
}
faults = {}
for name, gen in classes.items():
    a = gen(2000)
    H, P, T, e_ok, m_ok, t_ok, ok = checks(a)
    faults[name] = {
        "n": 2000,
        "per_key_detection": float((~ok).mean()),
        "reject_entropy": float((~e_ok).mean()),
        "reject_monobit": float((~m_ok).mean()),
        "reject_transition": float((~t_ok).mean()),
        "per_key_detection_ruleA": float((~checks(a, "A")[6]).mean()),
        "duplicates": duplicates(a),
    }
res["faults"] = faults
# healthy per-key rejection rate, calibrated on the 10,000-key AES baseline
p0 = 1 - res["aes"]["joint_accept_ruleB"]
pool_n = 2 ** 15
res["debian_expected_duplicates"] = 2000 - pool_n * (1 - (1 - 1 / pool_n) ** 2000)

# ---------------- E4 detection delay (sequential alarm) ----------------
print("E4 detection delay ...", flush=True)
crit = alarm_curve(p0, 2000)
res["alarm"] = {"baseline_p0": p0, "alpha": ALARM_ALPHA}
res["alarm"]["control_csprng"] = stream_study(g_csprng, p0, crit)
res["alarm"]["biased_0.55"] = stream_study(lambda n: g_biased(n, 0.55), p0, crit)
res["alarm"]["mersenne_twister"] = stream_study(
    lambda n: g_mt(n, seed=int(RNG.integers(1 << 31))), p0, crit, streams=100)
stuck_rej = ~checks(g_stuck(50))[6]
res["alarm"]["stuck_at"] = {"keys_to_alarm": keys_to_alarm(stuck_rej, crit)}

# ---------------- E5 bias sweep ----------------
print("E5 bias sweep ...", flush=True)
sweep = []
for p1 in [0.50, 0.51, 0.52, 0.53, 0.54, 0.55, 0.57, 0.60, 0.65]:
    a = g_biased(5000, p1)
    det = float((~checks(a)[6]).mean())
    s = stream_study(lambda n, p=p1: g_biased(n, p), p0, crit, streams=200)
    sweep.append({"p1": p1, "per_key_detection": det,
                  "alarm_rate": s["alarm_rate_within_2000"],
                  "median_keys_to_alarm": s["median_keys_to_alarm"],
                  "p95_keys_to_alarm": s["p95_keys_to_alarm"]})
res["bias_sweep"] = sweep

# ---------------- E6 throughput ----------------
print("E6 throughput ...", flush=True)
t0 = time.perf_counter()
for _ in range(5000):
    checks(np.frombuffer(secrets.token_bytes(32), dtype=np.uint8)[None, :])
res["aes_throughput_keys_per_s_single"] = 5000 / (time.perf_counter() - t0)
batch = g_csprng(100000)
t0 = time.perf_counter()
checks(batch)
res["aes_throughput_keys_per_s_batched"] = 100000 / (time.perf_counter() - t0)

with open(os.path.join(OUT, "results_v2.json"), "w") as f:
    json.dump(res, f, indent=1, default=float)
print(json.dumps(res, indent=1, default=float))

# ---------------- figures ----------------
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({"font.family": "serif", "font.size": 8})
H_aes = checks(aes)[0]
H_rsa = checks(rsa)[0]
np.savez(os.path.join(OUT, "entropy_samples.npz"), aes=H_aes, rsa=H_rsa, ecc=checks(ecc)[0])

fig, axes = plt.subplots(1, 2, figsize=(4.8, 2.3), dpi=300)
panels = [(axes[0], H_aes, 32, "(a) AES-256 key, L = 32 bytes", (4.40, 5.04)),
          (axes[1], H_rsa, 256, "(b) RSA-2048 modulus, L = 256 bytes", (6.94, 7.33))]
for ax, H, L, title, xl in panels:
    lo, hi = xl
    ax.hist(H, bins=np.linspace(lo, hi, 36), color="#9a9a9a", edgecolor="#5a5a5a", lw=0.3)
    ax.axvline(entropy_threshold(L, "A"), ls=":", lw=1.2, c="#b03030", label="Rule A: 0.9 log2(min(256,L))")
    ax.axvline(entropy_threshold(L, "B"), ls="-.", lw=1.2, c="#1f5fa0", label="Rule B: 0.1% quantile of $H_L$")
    ax.axvline(entropy_reference(L)["mean"], ls="-", lw=0.8, c="k", label="$E[H_L]$, uniform source")
    if L == 32:
        ax.axvline(5.0, ls="--", lw=0.9, c="k", label="log2(L) ceiling")
    ax.set_xlim(lo, hi)
    ax.set_title(title, fontsize=7.5)
    ax.set_xlabel("Shannon entropy (bits/byte)", fontsize=7.5)
    ax.tick_params(labelsize=6.5)
axes[0].set_ylabel("Keys", fontsize=7.5)
h, l = axes[0].get_legend_handles_labels()
fig.legend(h, l, loc="upper center", ncol=2, fontsize=6.5, frameon=False, bbox_to_anchor=(0.5, 1.02))
fig.tight_layout(rect=(0, 0, 1, 0.84))
fig.savefig(os.path.join(OUT, "fig_entropy.png"))

xs = [s["p1"] for s in sweep]
fig, ax1 = plt.subplots(figsize=(4.8, 2.4), dpi=300)
ax1.plot(xs, [100 * s["per_key_detection"] for s in sweep], "o-", c="#222222", lw=1.2,
         ms=3.5, label="Per-key rejection (%)")
ax1.axhline(100 * p0, ls=":", c="#222222", lw=0.9)
ax1.text(0.6505, 100 * p0 + 2.5, "healthy baseline", fontsize=6.5, ha="right")
ax1.set_xlabel("Source bias P(1)")
ax1.set_ylabel("Per-key rejection (%)")
ax2 = ax1.twinx()
ok = [s for s in sweep if s["alarm_rate"] >= 0.95]
ax2.plot([s["p1"] for s in ok], [s["median_keys_to_alarm"] for s in ok], "s--", c="#777777",
         lw=1.2, ms=3.5, label="Median keys to alarm (alarm rate $\\geq$ 95%)")
ax2.set_yscale("log")
ax2.set_ylabel("Median keys to alarm (log)")
h1, l1 = ax1.get_legend_handles_labels()
h2, l2 = ax2.get_legend_handles_labels()
ax1.legend(h1 + h2, l1 + l2, fontsize=6.5, loc="center right", frameon=False)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_bias_sweep.png"))
print("figures written")
