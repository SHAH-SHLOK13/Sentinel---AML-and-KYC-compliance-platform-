from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Body, Form
from typing import List, Dict, Any, Optional
from app.services.liveness_service import LivenessService
from app.config import get_settings
from uuid import uuid4
import json
import time

router = APIRouter(
    prefix="/api/kyc/liveness",
    tags=["liveness"]
)

liveness_service = LivenessService()
settings = get_settings()

# In-memory session store (simple dict with TTL)
# In production, use Redis
_active_sessions: Dict[str, Dict[str, Any]] = {}

def get_session(session_id: str) -> Dict[str, Any]:
    session = _active_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    # Check expiry (5 mins)
    if time.time() > session["expires_at"]:
        del _active_sessions[session_id]
        raise HTTPException(status_code=400, detail="Session expired")
        
    return session

def cleanup_sessions():
    """Helper to clean expired sessions. Call periodically or before new set."""
    now = time.time()
    expired = [sid for sid, s in _active_sessions.items() if now > s["expires_at"]]
    for sid in expired:
        del _active_sessions[sid]

@router.get("/session")
async def start_liveness_session(
    # user_id: str = Depends(get_current_user_id) # Requires Auth
):
    """
    Generate liveness session config for frontend.
    """
    cleanup_sessions() # Lazy cleanup
    
    config = liveness_service.generate_liveness_session()
    session_id = config["session_id"]
    
    # Store needed validation data
    _active_sessions[session_id] = {
        "flash_sequence": config["flash_sequence"],
        "active_challenges": config["active_challenges"],
        "created_at": time.time(),
        "expires_at": time.time() + 300 # 5 mins
    }
    
    return config

@router.post("/analyze")
async def analyze_liveness(
    session_id: str = Form(...),
    frame_BLACK: UploadFile = File(...),
    frame_RED: Optional[UploadFile] = File(None),
    frame_BLUE: Optional[UploadFile] = File(None),
    frame_GREEN: Optional[UploadFile] = File(None),
    frame_WHITE: Optional[UploadFile] = File(None),
    challenge_blink_frames: List[UploadFile] = File(None),
    challenge_turn_left_frames: List[UploadFile] = File(None),
    challenge_turn_right_frames: List[UploadFile] = File(None),
    challenge_smile_frames: List[UploadFile] = File(None),
    challenge_nod_frames: List[UploadFile] = File(None),
    frame_timestamps: str = Form(...) # JSON string
):
    """
    Analyze captured frames for liveness.
    """
    session = get_session(session_id)
    
    # Parse timestamps
    try:
        timestamps = json.loads(frame_timestamps)
    except:
        raise HTTPException(status_code=400, detail="Invalid timestamps format")

    # Collect Flash Frames
    flash_frames = {}
    
    async def read_file(f: UploadFile):
        return await f.read()

    if frame_BLACK: flash_frames["BLACK"] = await read_file(frame_BLACK)
    
    # Map colors from sequence. Frontend sends generic frame_COLOR or we map by order?
    # Directive says: "frame_RED: file (or whatever the first color was)"
    # But usually frontend sends key matching the color name.
    # Let's assume frontend sends keys: frame_RED, frame_BLUE etc. matches standard names.
    
    if frame_RED: flash_frames["RED"] = await read_file(frame_RED)
    if frame_BLUE: flash_frames["BLUE"] = await read_file(frame_BLUE)
    if frame_GREEN: flash_frames["GREEN"] = await read_file(frame_GREEN)
    if frame_WHITE: flash_frames["WHITE"] = await read_file(frame_WHITE)
    
    # Collect Challenge Frames
    challenge_frames = {}
    
    async def read_list(files: List[UploadFile]):
        return [await f.read() for f in files] if files else []

    if challenge_blink_frames: 
        challenge_frames["blink"] = await read_list(challenge_blink_frames)
    if challenge_turn_left_frames:
        challenge_frames["turn_left"] = await read_list(challenge_turn_left_frames)
    if challenge_turn_right_frames:
        challenge_frames["turn_right"] = await read_list(challenge_turn_right_frames)
    if challenge_smile_frames:
        challenge_frames["smile"] = await read_list(challenge_smile_frames)
    if challenge_nod_frames:
        challenge_frames["nod"] = await read_list(challenge_nod_frames)

    # Analyze
    result = await liveness_service.analyze_full_liveness(
        session_id=session_id,
        flash_frames=flash_frames,
        challenge_frames=challenge_frames,
        all_frame_timestamps=timestamps,
        expected_sequence=session["flash_sequence"],
        expected_challenges=session["active_challenges"]
    )
    
    # Audit Log (Placeholder)
    # log_audit(user_id, "LIVENESS_CHECK", result)
    
    return result

@router.post("/skip")
async def skip_liveness(
    session_id: str = Body(..., embed=True)
):
    """
    Mark session for manual review (accessibility skip).
    """
    # Verify session exists (optional) or just log the intent for the user
    # In real app, update KYC state in DB to 'MANUAL_REVIEW'
    
    return {"status": "skipped", "recommendation": "manual_review"}
