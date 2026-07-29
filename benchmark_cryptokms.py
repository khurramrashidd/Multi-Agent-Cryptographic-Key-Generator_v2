#!/usr/bin/env python3
"""CryptoKMS evaluation suite: baseline statistics, statistical significance,
fault-injection detection study, and latency/overhead measurement.

Reproduces every number in Section V of the ICICIS 2026 camera-ready.
Run: python3 benchmark_cryptokms.py  (writes results.json, fig_entropy.png)
"""
import secrets, math, time, json, hashlib, random, statistics, platform
from scipy.special import erfc
from scipy import stats
from Crypto.PublicKey import RSA, ECC

# ---------------- pipeline checks (pre-registered thresholds) ----------------
ALPHA = 0.01            # Monobit significance
ENT_FRAC = 0.90         # entropy acceptance fraction of attainable ceiling
Z_TRANS = 2.576         # 99% two-sided band for transition ratio

def shannon(b):
    n = len(b)
    return -sum((c/n)*math.log2(c/n) for c in {x: b.count(x) for x in set(b)}.values())

def monobit_p(b):
    bits = bin(int.from_bytes(b, 'big'))[2:].zfill(len(b)*8)
    n = len(bits); s = 2*bits.count('1') - n
    return erfc(abs(s)/math.sqrt(2*n))

def transition(b):
    bits = bin(int.from_bytes(b, 'big'))[2:].zfill(len(b)*8)
    return sum(bits[i] != bits[i+1] for i in range(len(bits)-1))/(len(bits)-1)

def checks(b):
    L = len(b); nbits = 8*L
    ceil = math.log2(min(256, L))
    e_ok = shannon(b) >= ENT_FRAC*ceil
    m_ok = monobit_p(b) >= ALPHA
    band = Z_TRANS*0.5/math.sqrt(nbits-1)
    t_ok = abs(transition(b)-0.5) <= band
    return e_ok, m_ok, t_ok, e_ok and m_ok and t_ok

# ---------------- generators for fault injection ----------------
def g_csprng(n): return [secrets.token_bytes(32) for _ in range(n)]
def g_stuck(n): return [b'\xaa'*32 for _ in range(n)]
def g_biased(n, p1=0.55):
    out = []
    for _ in range(n):
        bits = ''.join('1' if random.random() < p1 else '0' for _ in range(256))
        out.append(int(bits, 2).to_bytes(32, 'big'))
    return out
def g_mt(n):
    r = random.Random(1337)
    return [r.getrandbits(256).to_bytes(32, 'big') for _ in range(n)]
def g_debian(n, pool_bits=15):
    pool = [hashlib.sha256(i.to_bytes(2, 'big')).digest() for i in range(2**pool_bits)]
    r = random.Random(42)
    return [pool[r.randrange(len(pool))] for _ in range(n)]

def run_fault(name, keys):
    det = [not checks(k)[3] for k in keys]
    seen, dup = set(), 0
    for k in keys:
        if k in seen: dup += 1
        seen.add(k)
    d = sum(det)/len(det)
    m = None if d in (0, 1) else math.ceil(math.log(0.001)/math.log(1-d))
    return {'per_key_detection': d, 'duplicates': dup, 'n': len(keys),
            'keys_for_999_detection': (1 if d == 1 else m)}

# ---------------- main ----------------
res = {'env': {'python': platform.python_version(), 'machine': platform.machine(),
               'system': platform.platform()}}
try:
    import Crypto; res['env']['pycryptodome'] = Crypto.__version__
    import scipy; res['env']['scipy'] = scipy.__version__
except Exception: pass
try:
    cpu = [l.split(':')[1].strip() for l in open('/proc/cpuinfo') if 'model name' in l][0]
    res['env']['cpu'] = cpu
except Exception: pass

# ---- baseline: AES-256 (n=10000), ECC P-256 (n=1000), RSA-2048 (n=200)
def summarize(name, raws, gen_ms, val_ms):
    H = [shannon(b) for b in raws]; P = [monobit_p(b) for b in raws]
    T = [transition(b) for b in raws]
    n = len(raws); passed = sum(p >= ALPHA for p in P)
    lo, hi = stats.binomtest(passed, n, 0.99).proportion_ci(0.95, method='wilson')
    ks = stats.kstest(P, 'uniform')
    bt = stats.binomtest(passed, n, 0.99, alternative='two-sided')
    return {'n': n, 'bytes': len(raws[0]),
            'H_mean': statistics.mean(H), 'H_sd': statistics.pstdev(H),
            'H_min': min(H), 'H_ceiling': math.log2(min(256, len(raws[0]))),
            'monobit_pass': passed/n, 'monobit_ci95': [lo, hi],
            'monobit_vs_nominal_p': bt.pvalue, 'ks_uniform_p': ks.pvalue,
            'trans_mean': statistics.mean(T), 'gen_ms': gen_ms, 'val_ms': val_ms}

# AES
t0 = time.perf_counter(); aes = [secrets.token_bytes(32) for _ in range(10000)]
gen_aes = (time.perf_counter()-t0)/10000*1000
t0 = time.perf_counter(); _ = [checks(k) for k in aes]
val_aes = (time.perf_counter()-t0)/10000*1000
res['aes'] = summarize('aes', aes, gen_aes, val_aes)

# ECC
t0 = time.perf_counter(); ecc = [ECC.generate(curve='P-256') for _ in range(1000)]
gen_ecc = (time.perf_counter()-t0)/1000*1000
raw_ecc = [int(k.d).to_bytes(32, 'big') for k in ecc]
t0 = time.perf_counter(); _ = [checks(k) for k in raw_ecc]
val_ecc = (time.perf_counter()-t0)/1000*1000
res['ecc'] = summarize('ecc', raw_ecc, gen_ecc, val_ecc)
pem_ecc = [k.export_key(format='PEM').encode() for k in ecc]
der_ecc = [k.export_key(format='DER') for k in ecc]
res['ecc_pem_pass'] = sum(monobit_p(b) >= ALPHA for b in pem_ecc)/1000
res['ecc_der_pass'] = sum(monobit_p(b) >= ALPHA for b in der_ecc)/1000
res['ecc_pem_H'] = statistics.mean(shannon(b) for b in pem_ecc)
res['ecc_der_H'] = statistics.mean(shannon(b) for b in der_ecc)

# RSA
t0 = time.perf_counter(); rsa = [RSA.generate(2048) for _ in range(200)]
gen_rsa = (time.perf_counter()-t0)/200*1000
raw_rsa = [k.n.to_bytes(256, 'big') for k in rsa]
t0 = time.perf_counter(); _ = [checks(k) for k in raw_rsa]
val_rsa = (time.perf_counter()-t0)/200*1000
res['rsa'] = summarize('rsa', raw_rsa, gen_rsa, val_rsa)
pem_rsa = [k.export_key() for k in rsa]
res['rsa_pem_pass'] = sum(monobit_p(b) >= ALPHA for b in pem_rsa)/200
res['rsa_pem_H'] = statistics.mean(shannon(b) for b in pem_rsa)

# throughput
t0 = time.perf_counter()
for _ in range(5000):
    k = secrets.token_bytes(32); checks(k)
res['aes_throughput_keys_per_s'] = 5000/(time.perf_counter()-t0)

# ---- fault injection (2000 keys per class)
res['faults'] = {
    'control_csprng': run_fault('control', g_csprng(2000)),
    'stuck_at': run_fault('stuck', g_stuck(2000)),
    'biased_0.55': run_fault('biased', g_biased(2000)),
    'mersenne_twister': run_fault('mt', g_mt(2000)),
    'debian_15bit_pool': run_fault('debian', g_debian(2000)),
}

json.dump(res, open('results.json', 'w'), indent=1, default=float)
print(json.dumps(res, indent=1, default=float))

# ---- figure: entropy distributions
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(3.45, 2.1), dpi=300)
ax.hist([shannon(b) for b in aes], bins=40, alpha=0.75, label='AES-256 raw (max 5.0)', color='#444444')
ax.hist([shannon(b) for b in raw_rsa], bins=40, alpha=0.75, label='RSA-2048 modulus (max 8.0)', color='#999999')
ax.axvline(5.0, ls='--', lw=0.8, c='k'); ax.axvline(8.0, ls='--', lw=0.8, c='k')
ax.set_xlabel('Shannon entropy (bits/byte)', fontsize=7)
ax.set_ylabel('Keys', fontsize=7)
ax.tick_params(labelsize=6); ax.legend(fontsize=6, loc='upper center')
fig.tight_layout(); fig.savefig('fig_entropy.png')
print('figure written')
