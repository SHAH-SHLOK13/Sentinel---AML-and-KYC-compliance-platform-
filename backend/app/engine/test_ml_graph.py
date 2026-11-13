"""
Sentinel AML Engine — ML & Graph Test Suite
Run with: python -m app.engine.test_ml_graph  (from backend/)
"""

import random
import statistics
from datetime import datetime, timedelta

# ──────────────────────────────────────────────
# Synthetic Data Generators
# ──────────────────────────────────────────────

BASE_TIME = datetime(2026, 2, 15, 10, 0, 0)

def make_txn(user_id, counterparty_id, amount, hours_offset, txn_type="UPI_TRANSFER", flagged=False):
    """Helper to build a transaction dict."""
    ts = BASE_TIME + timedelta(hours=hours_offset)
    return {
        "user_id": user_id,
        "counterparty_id": counterparty_id,
        "amount": amount,
        "timestamp": ts.isoformat(),
        "type": txn_type,
        "transaction_id": f"txn_{user_id}_{counterparty_id}_{abs(hash((user_id, hours_offset))) % 100000}",
        "flagged": flagged,
    }

def generate_normal_transactions(n=100):
    """Generate n normal-looking transactions with varied users."""
    txns = []
    random.seed(42)
    users = [f"user_{i:03d}" for i in range(20)]
    counterparties = [f"cp_{i:03d}" for i in range(30)]
    
    for i in range(n):
        u = random.choice(users)
        cp = random.choice(counterparties)
        amount = round(random.gauss(5000, 2000), 2)
        amount = max(100.0, amount)  # floor at 100
        hours = random.uniform(0, 168)  # spread over 7 days
        txns.append(make_txn(u, cp, amount, hours))
    return txns

def generate_structuring_transactions():
    """5 deposits just below 50k threshold — classic smurfing."""
    txns = []
    amounts = [48_500, 49_200, 47_800, 49_900, 48_000]
    for i, amt in enumerate(amounts):
        txns.append(make_txn("smurf_user", f"smurf_cp_{i}", float(amt), 72 + i * 4, "CASH_DEPOSIT", flagged=True))
    return txns

def generate_cycle_transactions():
    """A→B→C→A circular flow."""
    return [
        make_txn("cycle_A", "cycle_B", 200_000.0, 80, flagged=True),
        make_txn("cycle_B", "cycle_C", 195_000.0, 82, flagged=True),
        make_txn("cycle_C", "cycle_A", 190_000.0, 84, flagged=True),
    ]

def generate_fan_in_transactions():
    """8 different accounts sending to 1 mule account."""
    txns = []
    for i in range(8):
        txns.append(make_txn(f"fan_src_{i}", "mule_account", 25_000.0 + i * 1000, 90 + i, flagged=True))
    return txns

def build_user_profiles(normal_txns):
    """Build per-user profiles from normal transactions for the anomaly detector."""
    user_amounts = {}
    user_txn_counts = {}
    
    for txn in normal_txns:
        uid = txn["user_id"]
        amt = txn["amount"]
        user_amounts.setdefault(uid, []).append(amt)
        user_txn_counts.setdefault(uid, 0)
        user_txn_counts[uid] += 1

    profiles = {}
    for uid, amounts in user_amounts.items():
        mean_amt = statistics.mean(amounts)
        std_amt = statistics.stdev(amounts) if len(amounts) > 1 else 0.0
        profiles[uid] = {
            "mean_transaction_amount": mean_amt,
            "std_transaction_amount": std_amt,
            "avg_daily_txn_count": user_txn_counts[uid] / 7.0,  # 7-day window
        }
    
    # Add profiles for injected users (with low baselines to make them anomalous)
    for special_user in ["smurf_user", "cycle_A", "cycle_B", "cycle_C", "mule_account"] + [f"fan_src_{i}" for i in range(8)]:
        profiles[special_user] = {
            "mean_transaction_amount": 3000.0,
            "std_transaction_amount": 1500.0,
            "avg_daily_txn_count": 0.5,
        }
    return profiles

def build_user_histories(normal_txns):
    """Group normal transactions as history keyed by user_id."""
    histories = {}
    for txn in normal_txns:
        uid = txn["user_id"]
        histories.setdefault(uid, []).append(txn)
    return histories


# ──────────────────────────────────────────────
# Printer Helpers
# ──────────────────────────────────────────────

def section(title):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


# ──────────────────────────────────────────────
# Main Test Runner
# ──────────────────────────────────────────────

def main():
    print("\n🔷 SENTINEL ML & GRAPH ENGINE — TEST SUITE 🔷\n")

    # ── Step 1: Generate Data ──────────────────
    section("Step 1: Generate 100 normal transactions")
    normal_txns = generate_normal_transactions(100)
    print(f"  Generated {len(normal_txns)} normal transactions across "
          f"{len(set(t['user_id'] for t in normal_txns))} users")

    section("Step 2: Inject 5 structuring (smurfing) transactions")
    structuring_txns = generate_structuring_transactions()
    for t in structuring_txns:
        print(f"  ₹{t['amount']:>10,.2f}  {t['user_id']} → {t['counterparty_id']}")

    section("Step 3: Inject 3-node cycle (A→B→C→A)")
    cycle_txns = generate_cycle_transactions()
    for t in cycle_txns:
        print(f"  ₹{t['amount']:>12,.2f}  {t['user_id']} → {t['counterparty_id']}")

    section("Step 4: Inject fan-in pattern (8 → mule_account)")
    fan_txns = generate_fan_in_transactions()
    for t in fan_txns:
        print(f"  ₹{t['amount']:>10,.2f}  {t['user_id']} → {t['counterparty_id']}")

    # ── Step 5: Train Isolation Forest ─────────
    section("Step 5: Train Isolation Forest on normal data")
    try:
        from app.engine.anomaly.isolation_forest import AnomalyDetector
    except ImportError as e:
        print(f"  ⚠️  Skipping ML tests — missing dependency: {e}")
        print("  Install with: pip install scikit-learn shap numpy")
        anomaly_detector = None
    else:
        user_profiles = build_user_profiles(normal_txns)
        user_histories = build_user_histories(normal_txns)
        anomaly_detector = AnomalyDetector()
        anomaly_detector.train(normal_txns, user_histories, user_profiles)
        print(f"  ✅ Model trained on {len(normal_txns)} transactions")
        print(f"     Score range: [{anomaly_detector.min_score:.4f}, {anomaly_detector.max_score:.4f}]")

    # ── Step 6: Anomaly Detection ──────────────
    section("Step 6: Run anomaly detection on injected transactions")
    if anomaly_detector:
        test_txns = structuring_txns + cycle_txns + fan_txns
        user_profiles = build_user_profiles(normal_txns)
        user_histories = build_user_histories(normal_txns)

        results = []
        for txn in test_txns:
            uid = txn["user_id"]
            history = user_histories.get(uid, [])
            profile = user_profiles.get(uid, {})
            result = anomaly_detector.predict(txn, history, profile)
            result["_txn"] = txn
            results.append(result)

        anomalous = [r for r in results if r["anomaly"]]
        print(f"  Tested {len(test_txns)} transactions")
        print(f"  🚨 Anomalies detected: {len(anomalous)} / {len(test_txns)}")
        print()
        for r in results:
            txn = r["_txn"]
            flag = "🚨" if r["anomaly"] else "  "
            print(f"  {flag} score={r['score']:.3f}  ₹{txn['amount']:>12,.2f}  "
                  f"{txn['user_id']} → {txn['counterparty_id']}")

        # ── Step 11: SHAP for most anomalous ──
        section("Step 11: SHAP explanations for most anomalous transaction")
        if anomalous:
            most_anomalous = max(results, key=lambda r: r["score"])
            txn = most_anomalous["_txn"]
            print(f"  Transaction: {txn['user_id']} → {txn['counterparty_id']}  ₹{txn['amount']:,.2f}")
            print(f"  Anomaly Score: {most_anomalous['score']:.4f}")
            print(f"  Top Feature Contributions:")
            for fc in most_anomalous.get("feature_contributions", []):
                direction = "↑" if fc["contribution"] > 0 else "↓"
                print(f"    {direction} {fc['feature']:30s}  contribution={fc['contribution']:+.4f}  value={fc['value']:.4f}")
        else:
            print("  No anomalies detected — cannot show SHAP explanations.")
    else:
        print("  ⚠️  Skipped (ML dependencies not available)")

    # ── Step 7: Build Transaction Graph ────────
    section("Step 7: Build transaction graph from ALL transactions")
    from app.engine.graph.graph_engine import TransactionGraphEngine
    
    all_txns = normal_txns + structuring_txns + cycle_txns + fan_txns
    graph_engine = TransactionGraphEngine()
    graph_engine.build_graph(all_txns)
    print(f"  Nodes: {graph_engine.graph.number_of_nodes()}")
    print(f"  Edges: {graph_engine.graph.number_of_edges()}")
    print(f"  Communities detected: {len(graph_engine.communities)}")

    # ── Step 8: Cycle Detection ────────────────
    section("Step 8: Cycle detection — expecting A→B→C→A")
    from app.engine.graph.graph_aml_rules import CircularFlowRule

    cycles = graph_engine.detect_cycles(max_length=5)
    print(f"  Total cycles found: {len(cycles)}")
    cycle_a_found = False
    for c in cycles:
        is_target = ("cycle_A" in c and "cycle_B" in c and "cycle_C" in c)
        marker = "  ✅ TARGET" if is_target else ""
        if is_target:
            cycle_a_found = True
        print(f"    {' → '.join(c)}{marker}")

    # Also run the CircularFlowRule
    cycle_rule = CircularFlowRule(graph_engine)
    cycle_result = cycle_rule.evaluate({"user_id": "cycle_A"})
    print(f"\n  CircularFlowRule for cycle_A:")
    print(f"    triggered={cycle_result['triggered']}, confidence={cycle_result.get('confidence', 0):.2f}")
    if cycle_result.get("evidence"):
        print(f"    {cycle_result['evidence'].get('message', '')}")

    assert cycle_a_found, "A→B→C→A cycle was NOT detected!"
    print(f"\n  ✅ Cycle assertion passed")

    # ── Step 9: Fan Detection ──────────────────
    section("Step 9: Fan detection — expecting mule_account as fan-in")
    from app.engine.graph.graph_aml_rules import FanPatternRule

    fans = graph_engine.detect_fan_patterns(threshold=5)
    print(f"  Fan-out hubs: {len(fans['fan_out'])}")
    for f in fans["fan_out"]:
        print(f"    {f['node']}: out_degree={f['out_degree']}, total=₹{f['total_amount']:,.2f}")
    
    print(f"  Fan-in hubs: {len(fans['fan_in'])}")
    mule_found = False
    for f in fans["fan_in"]:
        is_mule = f["node"] == "mule_account"
        marker = "  ✅ MULE" if is_mule else ""
        if is_mule:
            mule_found = True
        print(f"    {f['node']}: in_degree={f['in_degree']}, total=₹{f['total_amount']:,.2f}{marker}")

    # Also run the FanPatternRule
    fan_rule = FanPatternRule(graph_engine)
    fan_result = fan_rule.evaluate({"user_id": "mule_account"})
    print(f"\n  FanPatternRule for mule_account:")
    print(f"    triggered={fan_result['triggered']}, confidence={fan_result.get('confidence', 0):.2f}")
    if fan_result.get("evidence"):
        print(f"    pattern_type={fan_result['evidence'].get('pattern_type')}")

    assert mule_found, "mule_account was NOT detected as fan-in hub!"
    print(f"\n  ✅ Fan-in assertion passed")

    # ── Step 10: Serialize for Frontend ────────
    section("Step 10: Serialize graph for frontend")
    serialized = graph_engine.serialize_for_frontend()
    print(f"  Serialized nodes: {len(serialized['nodes'])}")
    print(f"  Serialized edges: {len(serialized['edges'])}")
    print(f"  Cycles in payload: {len(serialized['cycles'])}")

    # Sample node
    if serialized["nodes"]:
        sample = serialized["nodes"][0]
        print(f"  Sample node: {sample}")

    # ── Summary ────────────────────────────────
    section("SUMMARY")
    print("  ✅ All graph assertions passed")
    if anomaly_detector:
        print(f"  ✅ Anomaly detector trained and scored {len(test_txns)} transactions")
        print(f"     Anomalies flagged: {len(anomalous)}/{len(test_txns)}")
    else:
        print("  ⚠️  ML tests skipped (install scikit-learn, shap, numpy)")
    print()


if __name__ == "__main__":
    main()
