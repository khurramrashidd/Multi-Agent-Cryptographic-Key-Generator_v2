#!/usr/bin/env python3
"""Format every number the manuscript uses, straight from results_v2.json."""
import json
import sys

r = json.load(open(sys.argv[1]))
out = sys.argv[2]


def pct(x, d=1):
    return f"{100 * x:.{d}f}%"


def num(x, d=3):
    return f"{x:.{d}f}"


def ci(a):
    lo, hi = a["monobit_ci95"]
    return f"[{100 * lo:.1f}, {100 * hi:.1f}]"


def ms(x):
    if x < 0.01:
        return f"{x:.4f}"
    if x < 1:
        return f"{x:.3f}"
    return f"{x:,.0f}"


v = {}
a, e, s = r["aes"], r["ecc"], r["rsa"]
v["baseline_rows"] = [
    ["Samples", "10,000", "1,000", "200"],
    ["Bytes tested, L", str(a["bytes"]), str(e["bytes"]), str(s["bytes"])],
    ["E[H_L], uniform source", num(a["H_expected_uniform"]), num(e["H_expected_uniform"]),
     num(s["H_expected_uniform"])],
    ["Mean H ± sd (bits/byte)", f"{num(a['H_mean'])} ± {num(a['H_sd'])}",
     f"{num(e['H_mean'])} ± {num(e['H_sd'])}", f"{num(s['H_mean'])} ± {num(s['H_sd'])}"],
    ["Entropy pass, Rule A / Rule B", f"{pct(a['entropy_pass_ruleA'], 2)} / {pct(a['entropy_pass_ruleB'], 2)}",
     f"{pct(e['entropy_pass_ruleA'])} / {pct(e['entropy_pass_ruleB'])}",
     f"{pct(s['entropy_pass_ruleA'])} / {pct(s['entropy_pass_ruleB'])}"],
    ["Monobit pass", pct(a["monobit_pass"]), pct(e["monobit_pass"]), pct(s["monobit_pass"])],
    ["95% Wilson CI", ci(a), ci(e), ci(s)],
    ["Binomial p vs. 0.99", f"{a['monobit_vs_nominal_p']:.2f}", f"{e['monobit_vs_nominal_p']:.2f}",
     f"{s['monobit_vs_nominal_p']:.2f}"],
    ["Transition pass", pct(a["transition_pass"]), pct(e["transition_pass"]), pct(s["transition_pass"])],
    ["Mean transition ratio", f"{a['trans_mean']:.4f}", f"{e['trans_mean']:.4f}", f"{s['trans_mean']:.4f}"],
    ["Joint acceptance, Rule A / Rule B", f"{pct(a['joint_accept_ruleA'])} / {pct(a['joint_accept_ruleB'])}",
     f"{pct(e['joint_accept_ruleA'])} / {pct(e['joint_accept_ruleB'])}",
     f"{pct(s['joint_accept_ruleA'])} / {pct(s['joint_accept_ruleB'])}"],
    ["Generation per key (ms)", ms(a["gen_ms"]), ms(e["gen_ms"]), ms(s["gen_ms"])],
    ["Validation per key (ms)", ms(a["val_ms"]), ms(e["val_ms"]), ms(s["val_ms"])],
]

names = {"16": "AES-128 key", "24": "AES-192 key", "32": "AES-256, P-256 d",
         "128": "RSA-1024 modulus", "256": "RSA-2048 modulus", "512": "RSA-4096 modulus"}
v["entropy_ref_rows"] = []
for L in ("16", "24", "32", "128", "256", "512"):
    x = r["entropy_reference"][L]
    v["entropy_ref_rows"].append([
        L, names[L], num(x["ceiling"]), f"{num(x['mean'])} ± {num(x['sd'])}",
        f"{num(x['thr_ruleA'])} ({pct(x['ruleA_false_reject'], 2)})",
        f"{num(x['q001'])} ({pct(x['ruleB_false_reject'], 2)})"])

en = r["encodings"]
v["enc_rows"] = [
    ["ECC P-256 raw scalar d", pct(en["ecc_raw"]["monobit_pass"]), num(en["ecc_raw"]["H_mean"], 2)],
    ["ECC P-256 DER export", pct(en["ecc_der"]["monobit_pass"]), num(en["ecc_der"]["H_mean"], 2)],
    ["ECC P-256 PEM export", pct(en["ecc_pem"]["monobit_pass"]), num(en["ecc_pem"]["H_mean"], 2)],
    ["RSA-2048 raw modulus n", pct(en["rsa_raw"]["monobit_pass"]), num(en["rsa_raw"]["H_mean"], 2)],
    ["RSA-2048 PEM export", pct(en["rsa_pem"]["monobit_pass"]), num(en["rsa_pem"]["H_mean"], 2)],
]

f, al = r["faults"], r["alarm"]


def brk(x):
    return f"{100 * x['reject_entropy']:.2f} / {100 * x['reject_monobit']:.2f} / {100 * x['reject_transition']:.2f}"


ctrl_alarms = round(al["control_csprng"]["alarm_rate_within_2000"] * al["control_csprng"]["streams"])
mt_alarms = round(al["mersenne_twister"]["alarm_rate_within_2000"] * al["mersenne_twister"]["streams"])
b = al["biased_0.55"]
v["fault_rows"] = [
    ["Healthy CSPRNG (control)", pct(f["control_csprng"]["per_key_detection"], 2), brk(f["control_csprng"]),
     f"{f['control_csprng']['duplicates']:,}", f"{ctrl_alarms} of {al['control_csprng']['streams']} streams"],
    ["Stuck-at (constant 0xAA)", pct(f["stuck_at"]["per_key_detection"], 0), brk(f["stuck_at"]),
     f"{f['stuck_at']['duplicates']:,}", f"after {al['stuck_at']['keys_to_alarm']} keys"],
    ["Biased source, P(1) = 0.55", pct(f["biased_0.55"]["per_key_detection"], 1), brk(f["biased_0.55"]),
     f"{f['biased_0.55']['duplicates']:,}",
     f"median {b['median_keys_to_alarm']:.0f} keys (p95 {b['p95_keys_to_alarm']:.0f})"],
    ["Seeded Mersenne Twister", pct(f["mersenne_twister"]["per_key_detection"], 2), brk(f["mersenne_twister"]),
     f"{f['mersenne_twister']['duplicates']:,}", f"{mt_alarms} of {al['mersenne_twister']['streams']} streams"],
    ["Debian-style 2^15 pool [3]", pct(f["debian_15bit_pool"]["per_key_detection"], 2), brk(f["debian_15bit_pool"]),
     f"{f['debian_15bit_pool']['duplicates']:,} ({r['debian_expected_duplicates']:.1f} expected)",
     "not per-key; duplicate flag"],
]

ri = r["rsa_retry_impact"]
v["p0"] = pct(al["baseline_p0"], 2)
v["rsa_attempts_A"] = f"{ri['expected_attempts_ruleA']:.1f}"
v["rsa_failclosed_A"] = pct(ri["fail_closed_prob_ruleA"], 1)
v["rsa_attempts_B"] = f"{ri['expected_attempts_ruleB']:.2f}"
v["rsa_failclosed_B"] = f"{ri['fail_closed_prob_ruleB']:.0e}"
v["thr_single"] = f"{r['aes_throughput_keys_per_s_single']:,.0f}"
v["thr_batched"] = f"{r['aes_throughput_keys_per_s_batched']:,.0f}"
v["sweep"] = {f"{x['p1']:.2f}": {"det": pct(x["per_key_detection"], 1),
                                 "rate": pct(x["alarm_rate"], 0),
                                 "med": (f"{x['median_keys_to_alarm']:.0f}" if x["median_keys_to_alarm"] else "-")}
              for x in r["bias_sweep"]}
v["env"] = r["env"]
json.dump(v, open(out, "w"), indent=1, ensure_ascii=False)
print(json.dumps(v, indent=1, ensure_ascii=False))
