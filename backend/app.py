# backend/app.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import base64
import re

# Import all 5 Core Agents
from agents.key_generator import KeyGeneratorAgent
from agents.math_model_agent import MathModelAgent 
from agents.ai_entropy_agent import AIEntropyAgent
from agents.crypto_strength_agent import CryptoStrengthAgent
from agents.performance_agent import PerformanceAgent
from agents.duplicate_screen import DuplicateScreen

app = FastAPI(title="CryptoKMS Engine", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate Agents
key_gen_agent = KeyGeneratorAgent()
math_model_agent = MathModelAgent() 
ai_agent = AIEntropyAgent()
strength_agent = CryptoStrengthAgent()
perf_agent = PerformanceAgent()
dup_screen = DuplicateScreen()

class KeyRequest(BaseModel):
    purpose: str = Field(..., description="E.g., SBI Net Banking")
    algorithm: str = Field(..., description="AES, RSA, or ECC")
    length: int = Field(256, description="Key length in bits")
@app.get("/")
def health_check():
    return {
        "status": "Online",
        "message": "CryptoKMS Engine API is running perfectly.",
        "version": "2.0"
    }
@app.post("/api/generate-key")
def generate_cryptographic_key(request: KeyRequest):
    try:
        perf_agent.start_timer()
        # Bumping to 10 attempts to give asymmetric keys more chances
        max_retries = 10 
        attempt = 0
        is_secure = False
        
        generated_data = {}
        math_analysis = {}
        ai_analysis = {}
        strength_analysis = strength_agent.evaluate_strength(request.algorithm, request.length)

        while not is_secure and attempt < max_retries:
            attempt += 1
            
            # Agent 1: Generate
            generated_data = key_gen_agent.generate_key(request.algorithm, request.length)
            
            # Validate RAW key material for every algorithm (paper Sec. V-C):
            # AES key bytes, the ECC private scalar d, or the RSA modulus n.
            # Testing PEM/DER exports instead drives Monobit pass rates to ~0%
            # on perfectly good keys (Table III), so no encoded form is tested.
            target_data = generated_data["raw_hex"]

            # Agent 3 & 2: Validate
            math_analysis = math_model_agent.analyze_key(target_data)
            ai_analysis = ai_agent.analyze_patterns(target_data)

            math_pass = math_analysis["overall_math_grade"] == "Strong"
            ai_pass = ai_analysis["recommendation"] == "Pass"
            strength_pass = strength_analysis["verdict"] == "Pass"

            # Vault-level exact-duplicate screen (paper Sec. V-D): the only
            # issuance-time defence against Debian-style pool collapse.
            is_dup = dup_screen.is_duplicate(target_data)
            if is_dup:
                print(f"[DuplicateScreen] repeated raw key material on attempt {attempt} - possible generator fault")

            # ONE strict unanimous policy for all algorithms. The former
            # relaxed OR-rule for RSA/ECC only compensated for the encoding
            # artefact and would mask a genuinely defective generator.
            if math_pass and ai_pass and strength_pass and not is_dup:
                is_secure = True
                
        perf_analysis = perf_agent.stop_timer(retries=attempt)
        
        if not is_secure:
            # Fail closed: never dispatch unvalidated material (paper Sec. IV).
            raise ValueError(f"Pipeline failed to generate a secure {request.algorithm} key after {max_retries} attempts.")

        # Register accepted raw material in the duplicate index (hash only).
        dup_screen.register(generated_data["raw_hex"])

        return {
            "status": "success",
            "pipeline_result": "Approved & Certified",
            "metadata": {
                "purpose": request.purpose,
                "algorithm": request.algorithm,
                "bits": request.length
            },
            "key_data": generated_data,
            "pipeline_agents": {
                "Agent_3_Math": math_analysis,
                "Agent_2_AI": ai_analysis,
                "Agent_4_Strength": strength_analysis,
                "Agent_5_Performance": perf_analysis
            }
        }

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
