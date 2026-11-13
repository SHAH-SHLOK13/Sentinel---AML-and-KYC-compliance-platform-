from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Dict, Optional, Any
from main import require_role
from app.lib.supabase import supabase
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

@router.get("/metrics")
async def get_dashboard_metrics(
    current_user: Dict[str, str] = Depends(require_role("analyst", "officer", "admin"))
):
    """
    Get key performance indicators for the dashboard.
    """
    # 1. Alert Velocity (Last 24h)
    start_24h = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    alerts_24h = supabase.table("alerts").select("created_at", count="exact").gte("created_at", start_24h).execute()
    alert_count_24h = alerts_24h.count
    
    # Calculate alerts per hour (simple avg)
    alerts_per_hour = round(alert_count_24h / 24, 2)
    
    # 2. Active Users (Last 24h logins or transactions)
    # Assuming 'profiles' has last_login or check transactions
    # For now, let's use recent transactions count as proxy for activity
    tx_24h = supabase.table("transactions").select("user_id", count="exact").gte("created_at", start_24h).execute()
    active_users_24h = tx_24h.count # This is tx count, distinct user count requires RPC or raw query
    
    # 3. Pending KYC
    pending_kyc = supabase.table("profiles").select("id", count="exact").eq("kyc_status", "PENDING_REVIEW").execute()
    
    # 4. Recent Audit Activity
    recent_audit = supabase.table("audit_logs").select("*").order("timestamp", desc=True).limit(10).execute()
    
    return {
        "alert_velocity": {
            "total_24h": alert_count_24h,
            "avg_per_hour": alerts_per_hour
        },
        "active_users_24h": active_users_24h,
        "pending_kyc_reviews": pending_kyc.count,
        "recent_activity": recent_audit.data
    }

@router.get("/money-map")
async def get_money_map(
    days: int = 30,
    current_user: Dict[str, str] = Depends(require_role("officer", "admin"))
):
    """
    Build transaction graph for visualization.
    Nodes: Users/Entities. Edges: Transactions.
    """
    try:
        # 1. Try to read from cache first
        cache_res = supabase.table("graph_cache").select("*").eq("id", "latest").execute()
        
        if cache_res.data:
            cache_entry = cache_res.data[0]
            computed_at_str = cache_entry.get("computed_at")
            if computed_at_str:
                computed_at = datetime.fromisoformat(computed_at_str.replace('Z', '+00:00'))
                # Check if cache is fresh (less than 15 mins old)
                # Ensure both are offset-aware or offset-naive, assuming datetime.utcnow() is naive
                if datetime.utcnow() - computed_at.replace(tzinfo=None) < timedelta(minutes=15):
                    return cache_entry.get("graph_data", {"nodes": [], "edges": [], "cycles": []})

        # 2. If no cache or stale cache, compute it
        start_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
        
        # Fetch transactions
        tx_res = supabase.table("transactions").select("*").gte("created_at", start_date).limit(5000).execute()
        transactions = tx_res.data
        
        if not transactions:
            return {"nodes": [], "edges": [], "cycles": []}

        # Build Graph
        from app.engine.graph.graph_engine import TransactionGraphEngine
        engine = TransactionGraphEngine()
        engine.build_graph(transactions)
        
        # Serialize
        graph_data = engine.serialize_for_frontend()
        
        # Store to cache
        try:
            nodes_count = len(graph_data.get("nodes", []))
            edges_count = len(graph_data.get("edges", []))
            cycles_count = len(graph_data.get("cycles", []))
            
            supabase.table("graph_cache").upsert({
                "id": "latest",
                "graph_data": graph_data,
                "computed_at": datetime.utcnow().isoformat(),
                "node_count": nodes_count,
                "edge_count": edges_count,
                "cycles_found": cycles_count
            }).execute()
        except Exception as e:
            print(f"Failed to cache graph: {e}")
            
        return graph_data
        
    except Exception as e:
        print(f"Graph engine failed: {e}")
        # Return empty structure gracefully rather than 500
        return {"nodes": [], "edges": [], "cycles": []}

@router.post("/money-map/refresh")
async def refresh_money_map(
    days: int = 30,
    current_user: Dict[str, str] = Depends(require_role("admin"))
):
    """
    Force a fresh graph computation and cache update.
    """
    try:
        start_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
        tx_res = supabase.table("transactions").select("*").gte("created_at", start_date).limit(5000).execute()
        transactions = tx_res.data
        
        from app.engine.graph.graph_engine import TransactionGraphEngine
        engine = TransactionGraphEngine()
        engine.build_graph(transactions)
        
        graph_data = engine.serialize_for_frontend()
        
        supabase.table("graph_cache").upsert({
            "id": "latest",
            "graph_data": graph_data,
            "computed_at": datetime.utcnow().isoformat(),
            "node_count": len(graph_data.get("nodes", [])),
            "edge_count": len(graph_data.get("edges", [])),
            "cycles_found": len(graph_data.get("cycles", []))
        }).execute()
        
        return {"status": "success", "message": "Graph refreshed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
