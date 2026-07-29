# backend/agents/key_generator.py
from Crypto.PublicKey import RSA, ECC
from Crypto.Random import get_random_bytes
import binascii

# backend/agents/key_generator.py
import secrets
from Crypto.PublicKey import RSA, ECC

class KeyGeneratorAgent:
    def __init__(self):
        self.name = "KeyGeneratorAgent"

    def generate_key(self, algorithm: str, length: int) -> dict:
        algorithm = algorithm.upper()
        
        if algorithm == "AES":
            return self._generate_aes(length)
        elif algorithm == "RSA":
            return self._generate_rsa(length)
        elif algorithm == "ECC":
            # ECC length generally dictates the curve, but we'll default to standard P-256 for simplicity in this demo
            return self._generate_ecc()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

    def _generate_aes(self, length: int) -> dict:
        # Length comes in bits (e.g., 128, 256), get_random_bytes needs bytes
        byte_length = length // 8
        key = get_random_bytes(byte_length)
        key_hex = binascii.hexlify(key).decode('utf-8')
        return {
            "algorithm": "AES",
            "length": length,
            "key_hex": key_hex,
            # Raw key material analysed by the validation agents (paper Sec. V-C):
            # for AES the key bytes themselves.
            "raw_hex": key_hex
        }

    def _generate_rsa(self, length: int) -> dict:
        if length not in [1024, 2048, 4096]:
            length = 2048 # Default to secure length

        key = RSA.generate(length)
        private_key = key.export_key().decode('utf-8')
        public_key = key.publickey().export_key().decode('utf-8')
        
        return {
            "algorithm": "RSA",
            "length": length,
            "private_key": private_key,
            "public_key": public_key,
            # Raw key material = the modulus n, NOT the PEM/DER export.
            # Testing encoded exports produces near-total false rejection
            # (paper Sec. V-C, Table III).
            "raw_hex": key.n.to_bytes(length // 8, "big").hex()
        }

    def _generate_ecc(self) -> dict:
        # Using the standard NIST P-256 curve
        key = ECC.generate(curve='P-256')
        private_key = key.export_key(format='PEM')
        public_key = key.public_key().export_key(format='PEM')
        
        return {
            "algorithm": "ECC",
            "curve": "P-256",
            "private_key": private_key,
            "public_key": public_key,
            # Raw key material = the 32-byte private scalar d (paper Sec. V-C).
            "raw_hex": int(key.d).to_bytes(32, "big").hex()
        }