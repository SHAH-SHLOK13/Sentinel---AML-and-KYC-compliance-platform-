"""
Smart Mock Providers for Demo Fallback.

If a live API fails or does not exist for a document type, these smart mocks take over:
1. Validates document format with actual regex (catches true garbage)
2. Instead of a dummy database, it dynamically accepts ANY validly formatted document.
3. It assumes the name provided (from OCR) is the accurate name and returns it as a match.
4. Simulates realistic API latency (1.5-3.0 seconds).
5. Returns rich responses identical to real govt API payloads so KYCOrchestrator works flawlessly.
"""

import asyncio
import random
import re
import time
from typing import Dict, Any, List, Optional
from fuzzywuzzy import fuzz

from app.providers.base import (
    OCRProvider, FaceMatchProvider, LivenessProvider,
    GovVerificationProvider, SanctionsProvider, LLMProvider
)


# ============================================================================
# FORMAT VALIDATORS
# ============================================================================

PAN_REGEX      = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
PASSPORT_REGEX = re.compile(r"^[A-Z][0-9]{7}$")
DL_REGEX       = re.compile(r"^[A-Z]{2}\d{2,}")


def _fuzzy_name_score(name1: str, name2: str) -> int:
    """Raw fuzzywuzzy token_sort_ratio score."""
    if not name1 or not name2:
        return 0
    return fuzz.token_sort_ratio(name1.upper().strip(), name2.upper().strip())


# ============================================================================
# MOCK OCR PROVIDER
# ============================================================================

class MockOCRProvider(OCRProvider):
    async def extract_document(self, image_bytes: bytes, doc_type: str) -> Dict[str, Any]:
        """
        Since OCR requires actual models (e.g., Tesseract/Google Vision),
        this mock returns a generic placeholder string.
        """
        if doc_type == "PAN":
            return {
                "name": "TEST USER",
                "dob": "1990-01-01",
                "document_number": "ABCDE1234F",
                "confidence": round(0.97 + random.uniform(-0.03, 0.02), 4),
            }
        elif doc_type == "AADHAAR":
            return {
                "name": "Test User",
                "dob": "1990-01-01",
                "document_number": "XXXX-XXXX-1234",
                "confidence": round(0.95 + random.uniform(-0.03, 0.02), 4),
            }
        elif doc_type == "DL":
            return {
                "name": "TEST USER",
                "dob": "1990-01-01",
                "document_number": "MH1212345678901",
                "confidence": round(0.93 + random.uniform(-0.03, 0.02), 4),
            }
        elif doc_type == "PASSPORT":
            return {
                "name": "TEST USER",
                "dob": "1990-01-01",
                "document_number": "A1234567",
                "confidence": round(0.94 + random.uniform(-0.03, 0.02), 4),
            }
        return {"name": "UNKNOWN", "dob": "", "document_number": "", "confidence": 0.0}


# ============================================================================
# MOCK FACE MATCH PROVIDER (unchanged)
# ============================================================================

class MockFaceMatchProvider(FaceMatchProvider):
    async def compare_faces(self, face1_bytes: bytes, face2_bytes: bytes) -> Dict[str, Any]:
        score = random.uniform(0.78, 0.96)
        threshold = 0.60
        return {"match": score > threshold, "score": round(score, 4), "threshold": threshold}


# ============================================================================
# MOCK LIVENESS PROVIDER (unchanged)
# ============================================================================

class MockLivenessProvider(LivenessProvider):
    async def check_liveness(self, frames: List[bytes]) -> Dict[str, Any]:
        if random.random() < 0.05:
            return {"real": False, "score": random.uniform(20.0, 50.0), "method": "active_challenge_response+frame_jitter"}
        return {"real": True, "score": random.uniform(92.0, 99.5), "method": "active_challenge_response+frame_jitter"}


# ============================================================================
# DYNAMIC VALIDATION PROVIDER (Smart Mock without static DBs)
# ============================================================================

class MockGovVerificationProvider(GovVerificationProvider):
    """
    Dynamically accepts any validly formatted number instead of failing
    or checking against a hardcoded list. Designed to keep demos fluid while
    still enforcing layout correctness and generating realistic response traces.
    """

    # ── PAN VERIFICATION (PRIMARY DOCUMENT) ────────────────────────
    async def verify_pan(self, pan_number: str, name: str) -> Dict[str, Any]:
        start = time.monotonic()
        await asyncio.sleep(random.uniform(1.5, 2.5))
        pan = pan_number.strip().upper()

        if not PAN_REGEX.match(pan):
            return {
                "verified": False, "name_match": False, "name_on_record": "",
                "name_match_score": 0, "status": "INVALID_FORMAT", "category": "",
                "aadhaar_seeding_status": "",
                "error": f"Invalid PAN format: '{pan_number}'. Expected pattern: ABCDE1234A",
                "source": "SMART_VALIDATION_MOCK",
                "response_time_ms": int((time.monotonic() - start) * 1000),
            }

        # Dynamic success response
        clean_name = name.strip() or "VALIDATED USER"
        return {
            "verified": True,
            "name_match": True,
            "name_on_record": clean_name.upper(),
            "name_match_score": 100,
            "status": "ACTIVE",
            "category": "Individual",
            "aadhaar_seeding_status": "LINKED",
            "source": "SMART_VALIDATION_MOCK",
            "response_time_ms": int((time.monotonic() - start) * 1000),
        }

    # ── AADHAAR VERIFICATION (SECONDARY) ───────────────────────────
    async def verify_aadhaar_offline(self, digilocker_token: str) -> Dict[str, Any]:
        start = time.monotonic()
        await asyncio.sleep(random.uniform(2.0, 3.0))

        return {
            "verified": True,
            "masked_aadhaar": f"XXXX-XXXX-{random.randint(1000, 9999)}",
            "name": digilocker_token.split('_')[0].title() if "_" in digilocker_token else "Validated User",
            "dob": "1990-01-01",
            "address_available": True,
            "photo_available": True,
            "source": "DIGILOCKER_MOCK",
            "response_time_ms": int((time.monotonic() - start) * 1000),
        }

    # ── PASSPORT VERIFICATION (SECONDARY) ──────────────────────────
    async def verify_passport(self, passport_number: str, name: str, dob: str) -> Dict[str, Any]:
        start = time.monotonic()
        await asyncio.sleep(random.uniform(1.5, 2.5))
        pp = passport_number.strip().upper()

        if not PASSPORT_REGEX.match(pp):
            return {
                "verified": False, "name_match": False, "name_on_record": "",
                "name_match_score": 0, "dob_match": False, "nationality": "",
                "status": "INVALID_FORMAT",
                "error": f"Invalid passport format: '{passport_number}'. Expected: A1234567",
                "source": "SMART_VALIDATION_MOCK",
                "response_time_ms": int((time.monotonic() - start) * 1000),
            }

        clean_name = name.strip() or "VALIDATED USER"
        return {
            "verified": True,
            "name_match": True,
            "name_on_record": clean_name.upper(),
            "name_match_score": 100,
            "dob_match": True,
            "nationality": "INDIAN",
            "status": "ACTIVE",
            "source": "SMART_VALIDATION_MOCK",
            "response_time_ms": int((time.monotonic() - start) * 1000),
        }

    # ── DRIVING LICENSE VERIFICATION (SECONDARY) ───────────────────
    async def verify_driving_license(self, dl_number: str, name: str, dob: str) -> Dict[str, Any]:
        start = time.monotonic()
        await asyncio.sleep(random.uniform(1.5, 2.5))
        dl = dl_number.strip().upper().replace(" ", "").replace("-", "")

        if not DL_REGEX.match(dl):
            return {
                "verified": False, "name_match": False, "name_on_record": "",
                "name_match_score": 0, "dob_match": False, "dl_status": "INVALID_FORMAT",
                "issuing_authority": "",
                "error": f"Invalid DL format: '{dl_number}'. Expected: State code + numbers",
                "source": "SMART_VALIDATION_MOCK",
                "response_time_ms": int((time.monotonic() - start) * 1000),
            }

        clean_name = name.strip() or "VALIDATED USER"
        return {
            "verified": True,
            "name_match": True,
            "name_on_record": clean_name.upper(),
            "name_match_score": 100,
            "dob_match": True,
            "dl_status": "ACTIVE",
            "issuing_authority": "RTO Validated",
            "source": "SMART_VALIDATION_MOCK",
            "response_time_ms": int((time.monotonic() - start) * 1000),
        }

    # ── SECONDARY DOCUMENT (generic dispatcher) ────────────────────
    async def verify_secondary_document(self, doc_type: str, doc_number: str,
            name: str, dob: str = None) -> Dict[str, Any]:
        """Dispatches to the appropriate document-specific method."""
        if doc_type == "PASSPORT":
            return await self.verify_passport(doc_number, name, dob or "")
        elif doc_type == "DL":
            return await self.verify_driving_license(doc_number, name, dob or "")
        elif doc_type == "AADHAAR":
            return await self.verify_aadhaar_offline(f"{name.lower().split()[0]}_token")
        return {
            "verified": False,
            "error": f"Unsupported document type: {doc_type}",
            "verification_source": "UNSUPPORTED",
            "verification_id": "unsupported",
        }


# ============================================================================
# MOCK SANCTIONS PROVIDER (unchanged)
# ============================================================================

class MockSanctionsProvider(SanctionsProvider):
    async def screen_entity(self, name: str, dob: Optional[str] = None, nationality: Optional[str] = None) -> Dict[str, Any]:
        normalized_name = name.lower()
        suspicious_keywords = ["ahmed", "omar", "ibrahim", "sergei", "dawood"]
        for keyword in suspicious_keywords:
            if keyword in normalized_name:
                return {
                    "hit": True,
                    "matches": [{"name": f"{keyword.capitalize()} [REDACTED]", "score": 0.87, "list": "UN Security Council", "reason": "Associated with designated entity"}],
                    "highest_score": 0.87,
                }
        return {"hit": False, "matches": [], "highest_score": 0.0}


# ============================================================================
# MOCK LLM PROVIDER (unchanged)
# ============================================================================

class MockLLMProvider(LLMProvider):
    async def generate_alert_summary(self, alert_context: Dict[str, Any]) -> str:
        rule = alert_context.get("primary_rule", "anomaly")
        summaries = {
            "structuring": "The transaction pattern exhibits signs of structuring, with multiple deposits just below the reporting threshold.",
            "circular_flow": "A circular fund flow was detected between related accounts, potentially indicating round-tripping.",
            "dormant_wakeup": "Account dormant for >180 days suddenly received a large inflow followed by immediate outflow.",
            "geo_velocity": "Impossible travel detected: Transactions occurred in physically distant locations within a short timeframe.",
            "ctr_threshold": "Transaction exceeds mandatory CTR reporting threshold and requires filing.",
            "sanctions_match": "Name match found against designated sanctions list (UN/OFAC). Immediate freeze recommended.",
            "anomaly": "Unusual transaction pattern detected by ML model, deviating from customer's historical profile.",
        }
        return summaries.get(rule, summaries["anomaly"])
