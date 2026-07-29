# backend/agents/duplicate_screen.py
#
# Vault-level exact-duplicate screen (paper Sec. III, Sec. V-D, Sec. VI).
#
# Per-key statistical tests cannot detect Debian-style seed-space collapse,
# because every key drawn from a small pool is individually well-formed.
# The only issuance-time signal is an exact repeat. This screen keeps a
# SHA-256 index of all raw key material ever dispatched and refuses to
# dispatch a key whose raw bytes were issued before. O(1) per lookup.
#
# SECURITY NOTE: only the *hash* of the raw material is stored, never the
# key itself, so the index cannot become a plaintext-key registry.

import hashlib
import threading


class DuplicateScreen:
    def __init__(self):
        self.name = "DuplicateScreen"
        self._issued = set()          # in-process index of SHA-256 hex digests
        self._lock = threading.Lock()

    @staticmethod
    def _digest(raw_hex: str) -> str:
        return hashlib.sha256(bytes.fromhex(raw_hex)).hexdigest()

    def is_duplicate(self, raw_hex: str) -> bool:
        """True if this exact raw key material was already dispatched."""
        h = self._digest(raw_hex)
        with self._lock:
            return h in self._issued
        # For a multi-instance deployment, back this with the vault instead:
        # replace the set membership test with a Firestore lookup on an
        # indexed collection, e.g.
        #   db.collection("issued_hashes").document(h).get().exists

    def register(self, raw_hex: str) -> None:
        """Record raw key material as dispatched. Call only on acceptance."""
        h = self._digest(raw_hex)
        with self._lock:
            self._issued.add(h)
        # Firestore variant:
        #   db.collection("issued_hashes").document(h).set({"t": time.time()})
