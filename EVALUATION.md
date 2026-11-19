# CryptoKMS evaluation (ICCCT 2027 paper)

Every number and figure in Sections 4–5 of the ICCCT 2027 paper comes from `verify_cryptokms.py`.

## Reproduce

```bash
pip install pycryptodome scipy numpy matplotlib
python verify_cryptokms.py out          # about 2.5 minutes, single thread
python fig_sweep.py out/results_v2.json out/fig_bias_sweep.png
python fig_pipeline.py out/fig_pipeline.png
```

Outputs: `out/results_v2.json`, `out/fig_entropy.png`, `out/fig_bias_sweep.png`, `out/entropy_samples.npz`.

## What is exactly reproducible

- **Seeded, so identical on every run:** the biased-source, Mersenne Twister and Debian-pool fault classes; the bias sweep; the entropy reference table (Table 2).
- **Drawn from the OS CSPRNG, so they vary slightly per run:** the AES, ECC and RSA baselines and the healthy control. Expect differences in the first decimal of the percentages.
- **Environment-specific:** all timings and throughput.

## Experiments

| ID | What | Paper |
|---|---|---|
| E1 | Baseline: 10,000 AES-256, 1,000 ECC P-256, 200 RSA-2048 | Table 3 |
| E2 | Raw material vs PEM/DER encodings | Table 4 |
| E3 | Fault injection: 5 generator classes x 2,000 keys | Table 5 |
| E4 | Sequential binomial alarm (alpha = 1e-3) | Table 5, Sect. 5.4 |
| E5 | Bias sweep, P(1) = 0.50 to 0.65 | Fig. 3 |
| E6 | Overhead and throughput | Sect. 5.6 |

## Entropy rules

- **Rule A (original):** `H >= 0.9 * log2(min(256, L))`. This rejects about 68% of uniformly random 256-byte inputs, so about 69% of genuine RSA-2048 moduli fail it.
- **Rule B (corrected):** `H >= tau_L`, where `tau_L` is the 0.1% quantile of the entropy of L uniform bytes. `backend/agents/math_model_agent.py` implements Rule B.
