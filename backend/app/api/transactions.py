from fastapi import APIRouter, Depends, HTTPException, Body, Query, status, Request
from typing import List, Dict, Optional, Any
from datetime import datetime
import uuid
from pydantic import BaseModel
from main import require_role, get_current_user
from app.engine.engine import AMLEngine
from app.engine.rules.base import RuleContext
from app.lib.supabase import supabase

router = APIRouter(prefix="/api/transactions", tags=["Transactions"])

class TransactionCheckRequest(BaseModel):
    user_id: str
    amount: float
    type: str
    timestamp: Optional[datetime] = None
    counterparty: Optional[str] = None
    location: Optional[List[float]] = None # [lat, lon]

@router.post("/check")
async def check_transaction(
    request: Request,
    body: TransactionCheckRequest,
    current_user: Dict[str, str] = Depends(require_role("officer", "system", "admin"))
):
    """
    Run a transaction through the AML Engine and ML Anomaly Detector.
    Returns risk score, triggered rules, and ML anomaly flag.
    """
    engine = AMLEngine()
    
    # 1. Fetch user profile for context (age, occupation, etc.)
    profile_res = supabase.table("profiles").select("*").eq("id", body.user_id).single().execute()
    profile = profile_res.data if profile_res.data else {"kyc_risk_tier": "LOW", "occupation": "Unknown", "age_days": 0}
        
    ctx = RuleContext(
        user_id=body.user_id,
        transaction_amount=body.amount,
        transaction_type=body.type,
        transaction_time=body.timestamp or datetime.utcnow(),
        user_risk_tier=profile.get("kyc_risk_tier", "LOW"),
        user_occupation=profile.get("occupation", "Unknown"),
    )
    
    # 2. Rules Engine
    results = engine.evaluate(ctx)
    rules_score = engine.compute_transaction_risk(results)
    
    # 3. ML Anomaly Detection (if loaded)
    anomaly_detector = getattr(request.app.state, "anomaly_detector", None)
    
    is_anomaly = False
    ml_score = 0.0
    ml_explanations = []
    
    if anomaly_detector:
        # Build synthetic transaction dict
        txn_dict = {
            "id": str(uuid.uuid4()),
            "user_id": body.user_id,
            "amount": body.amount,
            "transaction_type": body.type,
            "timestamp": (body.timestamp or datetime.utcnow()).isoformat(),
            "counterparty_id": body.counterparty
        }
        
        # Get historical context
        user_histories = getattr(request.app.state, "user_histories", {})
        user_profiles = getattr(request.app.state, "user_profiles", {})
        history = user_histories.get(body.user_id, [])
        user_stats = user_profiles.get(body.user_id, {})
        
        try:
            ml_pred = anomaly_detector.predict(txn_dict, history, user_stats)
            is_anomaly = ml_pred.get("score", 0.0) > 0.5
            ml_score = ml_pred.get("score", 0.0)
            ml_explanations = ml_pred.get("feature_contributions", [])
            
            # Create Alert if anomalous
            if is_anomaly:
                alert = {
                    "id": str(uuid.uuid4()),
                    "user_id": body.user_id,
                    "alert_type": "ML_ANOMALY",
                    "severity": "HIGH" if ml_score > 0.75 else "MEDIUM",
                    "status": "PENDING",
                    "details": {
                        "transaction_id": txn_dict["id"],
                        "anomaly_score": ml_score,
                        "amount": body.amount,
                        "counterparty": body.counterparty,
                        "feature_contributions": ml_explanations,
                        "explanation": f"Live transaction scored {ml_score:.3f} anomaly score."
                    },
                    "created_at": datetime.utcnow().isoformat()
                }
                supabase.table("alerts").insert(alert).execute()
                
        except Exception as e:
            print(f"ML Scoring failed: {e}")
            
    # If high risk from rules, create Alert?
    if rules_score > 70:
        # TODO: Create rules-based Alert in DB
        pass
        
    final_verdict = "BLOCK" if rules_score >= 90 else "REVIEW" if (rules_score >= 50 or is_anomaly) else "ALLOW"
        
    return {
        "risk_score": rules_score,
        "ml_anomaly_score": ml_score,
        "is_anomaly": is_anomaly,
        "verdict": final_verdict,
        "triggered_rules": [
            {
                "rule_id": r.rule_id, 
                "name": r.rule_name, 
                "severity": r.severity.value,
                "explanation": r.explanation
            } 
            for r in results
        ],
        "ml_explanations": ml_explanations
    }

@router.get("/{user_id}")
async def get_transaction_history(
    user_id: str,
    page: int = 1,
    per_page: int = 20,
    current_user: Dict[str, str] = Depends(get_current_user)
):
    """
    Get paginated transaction history.
    """
    if current_user["role"] not in ["officer", "admin"] and current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
        
    offset = (page - 1) * per_page
    
    # Mock response if table doesn't exist yet, or query real table
    # Assuming 'transactions' table exists or will exist
    try:
        res = supabase.table("transactions").select("*", count="exact").eq("user_id", user_id).range(offset, offset + per_page - 1).execute()
        return {
            "data": res.data,
            "count": res.count,
            "page": page
        }
    except Exception:
        # Table might not exist in early dev
        return {"data": [], "count": 0, "page": page, "note": "No transactions found or table missing"}


class CreateTransactionRequest(BaseModel):
    fromUserId: str
    toUserId: Optional[str] = None
    amount: float
    type: str = "UPI_TRANSFER"
    note: Optional[str] = None


class DepositRequest(BaseModel):
    userId: str
    amount: float


@router.post("/create")
async def create_transaction(body: CreateTransactionRequest):
    """Create a new transaction (demo endpoint)."""
    txn = {
        "id": str(uuid.uuid4()),
        "user_id": body.fromUserId,
        "counterparty_id": body.toUserId or "SYSTEM",
        "amount": body.amount,
        "currency": "INR",
        "type": body.type,
        "risk_score": 0,
        "status": "completed",
        "created_at": datetime.utcnow().isoformat(),
    }
    try:
        supabase.table("transactions").insert(txn).execute()
    except Exception:
        pass  # Silently fail for demo if table doesn't exist

    return txn


@router.post("/deposit")
async def deposit(body: DepositRequest):
    """Deposit money into a user's account (demo endpoint)."""
    txn = {
        "id": str(uuid.uuid4()),
        "user_id": body.userId,
        "counterparty_id": "BANK_DEPOSIT",
        "amount": body.amount,
        "currency": "INR",
        "type": "CASH_DEPOSIT",
        "risk_score": 0,
        "status": "completed",
        "created_at": datetime.utcnow().isoformat(),
    }
    try:
        supabase.table("transactions").insert(txn).execute()
    except Exception:
        pass

    return {
        "balance": body.amount + 50000,  # Demo balance
        "transaction": txn,
    }

