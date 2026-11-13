from typing import Dict, Any, List
import random
import asyncio

class MockCornealReflectionAnalyzer:
    """
    Returns realistic-looking results without actually analyzing frames.
    Used during development and demo when we can't do real camera capture.
    
    Produces results that LOOK like real analysis was done, including
    plausible per-channel deltas and iris quality scores.
    """

    FLASH_SEQUENCE = [
        {"color": "RED",   "rgb": (255, 0, 0),   "hex": "#FF0000", "duration_ms": 400},
        {"color": "BLUE",  "rgb": (0, 0, 255),   "hex": "#0000FF", "duration_ms": 400},
        {"color": "GREEN", "rgb": (0, 255, 0),   "hex": "#00FF00", "duration_ms": 400},
        {"color": "WHITE", "rgb": (255, 255, 255), "hex": "#FFFFFF", "duration_ms": 400},
    ]

    def generate_session_sequence(self) -> List[Dict[str, Any]]:
        """
        Generate a randomized flash sequence (same as real).
        """
        sequence = self.FLASH_SEQUENCE.copy()
        random.shuffle(sequence)
        sequence.insert(0, {
            "color": "BLACK", 
            "rgb": (0, 0, 0),
            "hex": "#000000", 
            "duration_ms": 300
        })
        return sequence

    async def analyze_reflection(self, frames: Dict[str, bytes], expected_sequence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate realistic mock results.
        """
        # Simulate processing delay
        await asyncio.sleep(1.0)
        
        # Check for "SPOOF" trigger mechanism
        # For simplicity, if any frame byte size is very small (dummy) we might default to HAPPY_PATH for now
        # unless we have specific trigger. 
        # Directive says: "If frames contain a special marker or env var".
        # Let's check for a specific env var for testing 'SPOOF_MODE'.
        import os
        is_spoof = os.environ.get("MOCK_LIVENESS_SPOOF", "false").lower() == "true"
        
        if not is_spoof:
            # HAPPY_PATH
            per_flash_results = [
                {
                    "color": "RED", 
                    "passed": True, 
                    "left_delta": [32.4, -1.8, -2.1], 
                    "right_delta": [31.5, -2.0, -1.9],
                    "reflection_intensity": 32.4,
                    "details": {"expected": "R", "detected_dominant": "R"}
                },
                {
                    "color": "BLUE", 
                    "passed": True, 
                    "left_delta": [-1.2, -0.9, 28.7], 
                    "right_delta": [-1.5, -0.8, 29.1],
                    "reflection_intensity": 28.7,
                    "details": {"expected": "B", "detected_dominant": "B"}
                },
                {
                    "color": "GREEN", 
                    "passed": True, 
                    "left_delta": [-2.3, 26.1, -1.5], 
                    "right_delta": [-2.1, 25.8, -1.4],
                    "reflection_intensity": 26.1,
                    "details": {"expected": "G", "detected_dominant": "G"}
                },
                {
                    "color": "WHITE", 
                    "passed": True, 
                    "left_delta": [24.8, 22.1, 25.3], 
                    "right_delta": [25.1, 22.5, 25.6],
                    "reflection_intensity": 24.8,
                    "details": {"expected": "ALL", "detected_dominant": "Balanced"}
                }
            ]
            
            # Filter to match expected sequence order roughly if needed, 
            # but usually we just return results for what was in the sequence.
            # The real analyzer iterates expected_sequence.
            
            # Let's map our static results to the expected colors
            final_results = []
            for item in expected_sequence:
                if item["color"] == "BLACK": continue
                # Find matching mock result
                res = next((r for r in per_flash_results if r["color"] == item["color"]), None)
                if res:
                    final_results.append(res)
            
            return {
                "real": True,
                "score": 87.3,
                "method": "corneal_reflection",
                "per_flash_results": final_results,
                "eyes_detected": True,
                "iris_quality": 0.82,
                "failure_reason": None
            }
            
        else:
            # SPOOF PATH
            per_flash_results = [
                {
                    "color": "RED", 
                    "passed": False, 
                    "left_delta": [4.2, 3.8, 5.1], 
                    "right_delta": [4.5, 3.9, 5.0],
                    "details": {"expected": "R", "detected_dominant": "Other"}
                },
                # ... add others if needed, typically one fail is enough to tank score
            ]
            
            # Fill rest with fails
            colors = ["BLUE", "GREEN", "WHITE"] 
            for c in colors:
                 per_flash_results.append({
                    "color": c, 
                    "passed": False, 
                    "left_delta": [2.0, 2.0, 2.0], 
                    "right_delta": [2.0, 2.0, 2.0],
                    "details": {"expected": "X", "detected_dominant": "None"}
                 })

            final_results = []
            for item in expected_sequence:
                 if item["color"] == "BLACK": continue
                 res = next((r for r in per_flash_results if r["color"] == item["color"]), None)
                 if res: final_results.append(res)

            return {
                "real": False,
                "score": 23.1,
                "method": "corneal_reflection",
                "per_flash_results": final_results,
                "eyes_detected": True,
                "iris_quality": 0.34,
                "failure_reason": "Corneal reflections do not match expected color sequence"
            }
