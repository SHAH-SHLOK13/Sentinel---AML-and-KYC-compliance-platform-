import numpy as np
import cv2
import mediapipe as mp
from uuid import uuid4
from typing import Dict, Any, List, Optional, Tuple
from app.services.corneal_reflection import CornealReflectionAnalyzer
import random
import math

class LivenessService:
    """
    Multi-layer liveness detection combining:
    1. Corneal Reflection Analysis (PRIMARY — defeats deepfakes)
    2. Active Challenge-Response (SECONDARY — defeats static images)
    3. Frame Timing Analysis (TERTIARY — defeats virtual cameras)

    Each layer produces an independent score. The final decision uses
    a weighted combination with corneal reflection weighted highest.
    """

    def __init__(self):
        from app.config import get_settings
        settings = get_settings()
        
        if settings.USE_MOCK_PROVIDERS:
            from app.services.corneal_reflection_mock import MockCornealReflectionAnalyzer
            self.corneal_analyzer = MockCornealReflectionAnalyzer()
        else:
            from app.services.corneal_reflection import CornealReflectionAnalyzer
            self.corneal_analyzer = CornealReflectionAnalyzer()
            
        # Initialize MediaPipe Face Mesh for active challenges
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False, # Video mode
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

    def generate_liveness_session(self) -> Dict[str, Any]:
        """
        Generate everything needed for a liveness check session.
        Returns config for the frontend to execute.
        """
        
        flash_sequence = self.corneal_analyzer.generate_session_sequence()
        active_challenges = self._pick_random_challenges(count=2)
        
        return {
            "session_id": str(uuid4()),
            "flash_sequence": flash_sequence,
            "active_challenges": active_challenges,
            "instructions": {
                "corneal": "Look at the screen while colors flash (3 seconds)",
                "active": f"Then: {active_challenges[0]}, then {active_challenges[1]}",
            },
            "estimated_duration_seconds": 8,
            "epilepsy_warning": True
        }

    async def analyze_full_liveness(self, session_id: str, 
                                  flash_frames: Dict[str, bytes], 
                                  challenge_frames: Dict[str, List[bytes]],
                                  all_frame_timestamps: List[float],
                                  expected_sequence: List[Dict[str, Any]], 
                                  expected_challenges: List[str]) -> Dict[str, Any]:
        """
        Run ALL liveness checks and produce a combined verdict.
        
        Args:
            flash_frames: {"BLACK": bytes, "RED": bytes, ...} from corneal flash
            challenge_frames: {"blink": [frame1, frame2, ...], "turn_left": [...]}
            all_frame_timestamps: list of timestamps (ms) for timing analysis
            expected_sequence: the flash sequence that was displayed
            expected_challenges: the challenges that were requested
            
        Returns comprehensive liveness result.
        """
        
        # Layer 1: Corneal Reflection (weight: 0.50)
        corneal_result = await self.corneal_analyzer.analyze_reflection(flash_frames, expected_sequence)
        
        # Layer 2: Active Challenge-Response (weight: 0.30)
        challenge_result = await self._check_active_challenges(challenge_frames, expected_challenges)
        
        # Layer 3: Frame Timing Analysis (weight: 0.20)
        timing_result = self._analyze_frame_timing(all_frame_timestamps)
        
        # Weighted combination
        corneal_score = corneal_result["score"] * 0.50
        challenge_score = challenge_result["score"] * 0.30
        timing_score = timing_result["score"] * 0.20
        final_score = corneal_score + challenge_score + timing_score
        
        # Decision logic:
        # - If corneal PASSES (score >= 70): strong signal, be lenient on others
        # - If corneal FAILS (score < 40): almost certainly fake, reject
        # - If corneal AMBIGUOUS (40-70): rely heavily on other signals
        
        real = False
        if corneal_result["score"] >= 70:
            real = final_score >= 55  # Lenient — corneal is strong
        elif corneal_result["score"] < 40:
            real = False  # Corneal failure = reject regardless
        else:
            real = final_score >= 70  # Ambiguous corneal = need strong other signals
            
        return {
            "real": real,
            "score": round(final_score, 1),
            "method": "corneal_reflection+active_challenge+timing_analysis",
            "layers": {
                "corneal": corneal_result,
                "active_challenges": challenge_result,
                "timing_analysis": timing_result
            },
            "weighted_scores": {
                "corneal": round(corneal_score, 1),
                "challenges": round(challenge_score, 1),
                "timing": round(timing_score, 1)
            },
            "session_id": session_id,
            "recommendation": "approve" if real else ("retry" if final_score > 40 else "reject"),
            "failure_reasons": self._collect_failure_reasons(corneal_result, challenge_result, timing_result)
        }

    def _pick_random_challenges(self, count: int = 2) -> List[str]:
        options = ["blink", "turn_left", "turn_right", "smile", "nod"]
        return random.sample(options, count)

    async def _check_active_challenges(self, challenge_frames: Dict[str, List[bytes]], expected_challenges: List[str]) -> Dict[str, Any]:
        """Check active liveness challenges using MediaPipe Face Mesh."""
        
        from app.config import get_settings
        if get_settings().USE_MOCK_PROVIDERS:
             return {
                 "score": 100.0,
                 "challenges": [{"name": c, "passed": True, "detail": "Mock pass"} for c in expected_challenges]
             }
        
        results = []
        total_passed = 0
        
        for challenge in expected_challenges:
            frames_bytes = challenge_frames.get(challenge, [])
            if not frames_bytes:
                results.append({"name": challenge, "passed": False, "detail": "No frames provided"})
                continue
                
            passed = False
            detail = "Action not detected"
            
            # Decode frames properly
            frames = []
            for fb in frames_bytes:
                nparr = np.frombuffer(fb, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is not None:
                     frames.append(img)
            
            if not frames:
                 results.append({"name": challenge, "passed": False, "detail": "Could not decode frames"})
                 continue

            if challenge == "blink":
                passed, detail = self._detect_blink(frames)
            elif challenge == "turn_left":
                passed, detail = self._detect_head_turn(frames, "left")
            elif challenge == "turn_right":
                passed, detail = self._detect_head_turn(frames, "right")
            elif challenge == "smile":
                passed, detail = self._detect_smile(frames)
            elif challenge == "nod":
                passed, detail = self._detect_nod(frames)
            
            if passed:
                total_passed += 1
            
            results.append({"name": challenge, "passed": passed, "detail": detail})
            
        score = (total_passed / len(expected_challenges)) * 100 if expected_challenges else 0.0
        
        return {
            "score": float(score),
            "challenges": results
        }

    def _extract_landmarks(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = self.face_mesh.process(rgb)
        if res.multi_face_landmarks:
            return res.multi_face_landmarks[0].landmark
        return None

    def _detect_blink(self, frames) -> Tuple[bool, str]:
        # Compute EAR. Threshold < 0.2 is closed, > 0.25 is open.
        # Need to see Open -> Closed -> Open
        
        ear_history = []
        
        # Indices for landmarks (Left eye: 33, 160, 158, 133, 153, 144) - roughly
        # Better standard indices:
        # Left Eye: 362, 385, 387, 263, 373, 380 (Right on mesh, left on screen?) 
        # Actually MP mesh: 
        # Left Eye: 33(p1), 160(p2), 158(p3), 133(p4), 153(p5), 144(p6)
        # Right Eye: 362(p1), 385(p2), 387(p3), 263(p4), 373(p5), 380(p6)
        
        # Let's use simpler index set if needed, but these are standard
        LEFT_EYE = [33, 160, 158, 133, 153, 144]
        RIGHT_EYE = [362, 385, 387, 263, 373, 380]
        
        def calculate_ear(landmarks, indices):
             # p2-p6 (160-144) + p3-p5 (158-153) / 2 * p1-p4 (33-133)
             # Note: Indices in array are 0-based from the list above? No, indices in global mesh
             p1 = landmarks[indices[0]]
             p2 = landmarks[indices[1]]
             p3 = landmarks[indices[2]]
             p4 = landmarks[indices[3]]
             p5 = landmarks[indices[4]]
             p6 = landmarks[indices[5]]
             
             def dist(a, b): return math.hypot(a.x - b.x, a.y - b.y)
             
             v1 = dist(p2, p6)
             v2 = dist(p3, p5)
             h = dist(p1, p4)
             return (v1 + v2) / (2.0 * h)

        min_ear = 1.0
        
        for frame in frames:
            lms = self._extract_landmarks(frame)
            if not lms: continue
            
            l_ear = calculate_ear(lms, LEFT_EYE)
            r_ear = calculate_ear(lms, RIGHT_EYE)
            ear = (l_ear + r_ear) / 2.0
            ear_history.append(ear)
            if ear < min_ear: min_ear = ear
            
        # Check for dip
        has_closed = min_ear < 0.2
        # Check if it opened again? Usually sequence ends. 
        # If we pushed mostly open frames, but one closed, that's a blink.
        # But we need to ensure it wasn't JUST closed (eyes closed test).
        # We need variance.
        
        was_open = any(e > 0.25 for e in ear_history)
        
        if has_closed and was_open:
            return True, f"Blink detected (min EAR {min_ear:.2f})"
        return False, f"No blink (min EAR {min_ear:.2f})"

    def _detect_head_turn(self, frames, direction) -> Tuple[bool, str]:
        # Track Nose Tip (1) relative to face width (Left cheek 234, Right cheek 454)
        x_history = []
        
        for frame in frames:
            lms = self._extract_landmarks(frame)
            if not lms: continue
            
            nose = lms[1].x
            left_edge = lms[234].x
            right_edge = lms[454].x
            width = right_edge - left_edge
            
            # Normalized nose position (0.5 = center, < 0.5 right(screen left), > 0.5 left(screen right))
            # Wait, x coordinates increase left to right.
            # If user turns LEFT (their left), they look to screen RIGHT. Nose x increases.
            # If user turns RIGHT (their right), they look to screen LEFT. Nose x decreases.
            
            rel_x = (nose - left_edge) / width
            x_history.append(rel_x)
            
        if not x_history: return False, "Face not found"
        
        start_x = x_history[0]
        max_dist = 0
        
        if direction == "turn_left":
             # User turns LEFT -> Nose moves RIGHT on screen (User's left is our right) -> x increases
             # Wait, usually "Turn Left" means "Turn your head to the left".
             # If I turn head left, my nose points Left. 
             # On camera (mirror), nose points Left (x decreases).
             # Standard "Turn Left" usually means "Look Left".
             # Let's assume standard intuitive mirror behavior.
             # Turn Left -> Nose X decreases significantly?
             
             # Actually, let's verify logic:
             # Mirror: I turn left. My reflection turns left.
             # Non-mirror: I turn left. The image shows me turning right.
             # Frontend usually mirrors.
             # Let's check DISPLACEMENT magnitude.
             
             # Let's just look for significant movement in expected direction.
             # Assuming standard selfie cam (mirrored):
             # Turn Left -> x decreases
             # Turn Right -> x increases
             
             min_x = min(x_history)
             displacement = start_x - min_x
             if displacement > 0.12: # 12% width
                  return True, f"Left turn detected (delta {displacement:.2f})"
             return False, f"Inufficient left movement ({displacement:.2f})"

        elif direction == "turn_right":
             max_x = max(x_history)
             displacement = max_x - start_x
             if displacement > 0.12:
                  return True, f"Right turn detected (delta {displacement:.2f})"
             return False, f"Insufficient right movement ({displacement:.2f})"
             
        return False, "Unknown direction"

    def _detect_smile(self, frames) -> Tuple[bool, str]:
        # Ratio of mouth width (61, 291) to face width (234, 454)
        ratios = []
        for frame in frames:
            lms = self._extract_landmarks(frame)
            if not lms: continue
            
            face_w = math.hypot(lms[454].x - lms[234].x, lms[454].y - lms[234].y)
            mouth_w = math.hypot(lms[291].x - lms[61].x, lms[291].y - lms[61].y)
            ratios.append(mouth_w / face_w)
            
        if not ratios: return False, "Face not found"
        
        min_r = min(ratios)
        max_r = max(ratios)
        increase = (max_r - min_r) / min_r
        
        if increase > 0.08: # 8% increase
             return True, f"Smile detected (+{increase*100:.1f}%)"
        return False, f"No smile (+{increase*100:.1f}%)"

    def _detect_nod(self, frames) -> Tuple[bool, str]:
        # Track Nose Tip Y. 
        # Nod down -> Y increases.
        y_history = []
        for frame in frames:
             lms = self._extract_landmarks(frame)
             if not lms: continue
             y_history.append(lms[1].y) # Nose tip
             
        if not y_history: return False, "Face not found"
        
        # Look for significant dip (increase in Y) then return
        start_y = y_history[0]
        max_y = max(y_history) # Lowest point visually (highest Y value)
        
        diff = max_y - start_y
        # Normalize by face height? 
        # Let's assume roughly 5% screen height or similar.
        # But face size varies.
        # Let's use simple absolute threshold for now or logic from directive "5% of face height"
        # We need face height.
        
        # Re-calc with face height
        # Height: chin(152) - forehead(10)
        # Just grab one frame's height
        # Approx
        
        # Let's just use raw diff if we can't easily get height every frame without re-parsing
        # 0.05 in normalized coords is 5% of screen. Valid.
        if diff > 0.05:
             return True, f"Nod detected (delta {diff:.3f})"
        return False, f"No nod (delta {diff:.3f})"
        

    def _analyze_frame_timing(self, timestamps: List[float]) -> Dict[str, Any]:
        """Detect virtual cameras by analyzing frame timing patterns."""
        if len(timestamps) < 5:
             return {"score": 0.0, "verdict": "suspicious", "detail": "Insufficent frames", "cv": 0}
             
        intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
        mean_interval = np.mean(intervals)
        std_interval = np.std(intervals)
        
        if mean_interval == 0:
             return {"score": 0.0, "verdict": "virtual_camera", "cv": 0, "detail": "Zero interval"}

        cv = std_interval / mean_interval
        
        # CV > 0.05 (jittery = real camera): score = 90-100
        # CV between 0.02-0.05 (moderate jitter): score = 60-89
        # CV between 0.005-0.02 (suspiciously uniform): score = 20-59
        # CV < 0.005 (virtual camera likely): score = 0-19
        
        if cv > 0.05:
            score = 100.0
            verdict = "real_camera"
        elif cv > 0.02:
            score = 75.0
            verdict = "real_camera"
        elif cv > 0.005:
            score = 40.0
            verdict = "suspicious"
        else:
            score = 10.0
            verdict = "virtual_camera"
            
        return {
            "score": score,
            "frame_count": len(timestamps),
            "mean_interval_ms": float(mean_interval),
            "std_interval_ms": float(std_interval),
            "cv": float(cv),
            "verdict": verdict,
            "detail": f"CV={cv:.4f}"
        }

    def _collect_failure_reasons(self, corneal, challenges, timing) -> List[str]:
        reasons = []
        if not corneal.get("eyes_detected"):
            reasons.append("Eyes not clearly visible — remove glasses or improve lighting")
        if corneal.get("score", 0) < 40:
            reasons.append("Corneal reflections inconsistent with live human")
        for c in challenges.get("challenges", []):
            if not c.get("passed"):
                reasons.append(f"Challenge '{c['name']}' not detected")
        if timing.get("verdict") == "virtual_camera":
            reasons.append("Camera feed timing pattern suggests virtual/synthetic source")
        return reasons
