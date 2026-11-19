import math
import random
from functools import lru_cache

import scipy.special as sp

# Rule B entropy thresholds (ICCCT 2027 paper, Sect. 3.3 and Table 2).
# tau_L is the 0.1% quantile of the byte-level Shannon entropy of L uniformly
# random bytes, so a healthy key of length L is falsely rejected about 0.1% of
# the time. Values come from verify_cryptokms.py (200,000 Monte Carlo samples
# per length). The old Rule A, 0.9 * log2(min(256, L)), rejected about 68% of
# genuine RSA-2048 moduli (L = 256) because 7.2 lies above E[H_256] = 7.175.
ENTROPY_THRESHOLD_RULE_B = {
    16: 3.5778,    # AES-128 key
    24: 4.1368,    # AES-192 key
    32: 4.5625,    # AES-256 key, ECC P-256 private scalar
    128: 6.3278,   # RSA-1024 modulus
    256: 7.0061,   # RSA-2048 modulus
    512: 7.4826,   # RSA-4096 modulus
}


def _shannon(data: bytes) -> float:
    n = len(data)
    counts = {}
    for b in data:
        counts[b] = counts.get(b, 0) + 1
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


@lru_cache(maxsize=None)
def entropy_threshold(length: int, samples: int = 20000, seed: int = 90210) -> float:
    """Rule B threshold for an L-byte sample; Monte Carlo fallback for unlisted L."""
    if length in ENTROPY_THRESHOLD_RULE_B:
        return ENTROPY_THRESHOLD_RULE_B[length]
    rng = random.Random(seed + length)
    vals = sorted(_shannon(bytes(rng.getrandbits(8) for _ in range(length)))
                  for _ in range(samples))
    return vals[max(0, int(0.001 * samples) - 1)]


class MathModelAgent:
    def __init__(self):
        self.name = "MathModelAgent"

    def calculate_shannon_entropy(self, byte_data: bytes) -> float:
        """Calculates the Shannon Entropy based on byte frequency."""
        if not byte_data:
            return 0.0
        return round(_shannon(byte_data), 4)

    def monobit_frequency_test(self, data: str) -> dict:
        """NIST SP 800-22 Monobit Test to check 0/1 balance."""
        try:
            bit_string = bin(int(data, 16))[2:].zfill(len(data) * 4)
        except ValueError:
            bit_string = ''.join(format(ord(c), '08b') for c in data)

        n = len(bit_string)
        if n == 0:
            return {"p_value": 0.0, "is_random": False, "score": "Fail"}

        sum_val = sum([1 if bit == '1' else -1 for bit in bit_string])
        s_obs = abs(sum_val) / math.sqrt(n)
        p_value = sp.erfc(s_obs / math.sqrt(2))
        is_random = p_value >= 0.01

        return {
            "p_value": float(round(p_value, 6)),
            "is_random": bool(is_random),
            "score": "Pass" if is_random else "Fail"
        }

    def analyze_key(self, data: str):
        # 1. Convert to bytes
        try:
            byte_data = bytes.fromhex(data)
        except ValueError:
            byte_data = data.encode('utf-8')

        data_length = len(byte_data)

        # 2. Calculate actual entropy
        entropy = self.calculate_shannon_entropy(byte_data)

        # 3. Theoretical ceiling (reported only) and the Rule B acceptance threshold
        max_possible_entropy = min(8.0, math.log(data_length, 2)) if data_length > 0 else 0
        threshold = entropy_threshold(data_length) if data_length > 1 else float("inf")

        # 4. Check NIST
        frequency = self.monobit_frequency_test(data)

        # 5. Grade it against the Rule B threshold (not 90% of the ceiling)
        is_strong_entropy = entropy >= threshold

        return {
            "agent": self.name,
            "shannon_entropy": entropy,
            "max_theoretical_entropy": round(max_possible_entropy, 4),
            "entropy_threshold": round(threshold, 4) if math.isfinite(threshold) else None,
            "entropy_rule": "B: 0.1% quantile of H_L for L uniform bytes",
            "entropy_health": f"{round((entropy/max_possible_entropy)*100, 2)}%" if max_possible_entropy else "0%",
            "nist_monobit": frequency,
            "overall_math_grade": "Strong" if (is_strong_entropy and frequency['is_random']) else "Weak"
        }
