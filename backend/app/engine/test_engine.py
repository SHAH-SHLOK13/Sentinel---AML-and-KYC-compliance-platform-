"""
Sentinel AML Engine — Comprehensive Test Suite
Run with: python -m app.engine.test_engine  (from backend/)
"""

from datetime import datetime, timedelta
from app.engine.rules.base import RuleContext, Severity
from app.engine.engine import AMLEngine

# ──────────────────────────────────────────────
# Helper: pretty-print a scenario result
# ──────────────────────────────────────────────

def print_scenario(title: str, results, score: int, max_severity: Severity):
    print(f"\n{'=' * 70}")
    print(f"  SCENARIO: {title}")
    print(f"{'=' * 70}")
    if not results:
        print("  ✅ No rules triggered.")
    else:
        for r in results:
            print(f"  🚨 [{r.rule_id}] {r.rule_name}")
            print(f"     Severity: {r.severity.value} | Confidence: {r.confidence:.2f}")
            print(f"     Explanation: {r.explanation}")
            if r.evidence:
                print(f"     Evidence: {r.evidence}")
    print(f"\n  📊 Risk Score: {score}/100 | Max Severity: {max_severity.value}")
    print(f"{'─' * 70}")


# ──────────────────────────────────────────────
# Mock provider for sanctions test
# ──────────────────────────────────────────────

class TestSanctionsProvider:
    """Returns a hard MATCH for any screened entity — used in test scenarios."""
    def screen_entity(self, name: str) -> dict:
        return {"score": 1.0, "status": "MATCH", "list": "TEST_WATCHLIST"}


NOW = datetime(2026, 2, 19, 14, 0, 0)


# ──────────────────────────────────────────────
# Scenario 1: Normal Transaction
# ──────────────────────────────────────────────

def scenario_normal():
    engine = AMLEngine()
    ctx = RuleContext(
        user_id="user_normal_001",
        transaction_amount=5_000.0,
        transaction_type="UPI_TRANSFER",
        transaction_time=NOW,
        user_age_days=365,
        user_occupation="Salaried",
        user_risk_tier="LOW",
        user_avg_transaction=4_500.0,
        user_last_activity_days=2,
    )
    results = engine.evaluate(ctx)
    score = engine.compute_transaction_risk(results)
    max_sev = engine.get_max_severity(results)
    print_scenario("Normal Transaction (₹5,000 UPI)", results, score, max_sev)
    assert score == 0, f"Expected score 0, got {score}"
    assert len(results) == 0, f"Expected 0 triggers, got {len(results)}"


# ──────────────────────────────────────────────
# Scenario 2: CTR Threshold (₹12,00,000)
# ──────────────────────────────────────────────

def scenario_ctr():
    engine = AMLEngine()
    ctx = RuleContext(
        user_id="user_ctr_002",
        transaction_amount=1_200_000.0,
        transaction_type="CASH_DEPOSIT",
        transaction_time=NOW,
        user_age_days=800,
        user_occupation="Business Owner",
        user_risk_tier="LOW",
        user_avg_transaction=50_000.0,
        user_last_activity_days=5,
    )
    results = engine.evaluate(ctx)
    score = engine.compute_transaction_risk(results)
    max_sev = engine.get_max_severity(results)
    print_scenario("CTR Threshold (₹12,00,000 Cash Deposit)", results, score, max_sev)
    ctr_ids = [r.rule_id for r in results]
    assert "R-101" in ctr_ids, "CTR rule (R-101) should have triggered"
    assert score == 100, f"Expected score 100, got {score}"


# ──────────────────────────────────────────────
# Scenario 3: Structuring / Smurfing
# ──────────────────────────────────────────────

def scenario_structuring():
    engine = AMLEngine()

    history = [
        {"amount": 42_000.0, "timestamp": NOW - timedelta(hours=26), "type": "CASH_DEPOSIT", "id": "tx_s1"},
        {"amount": 48_500.0, "timestamp": NOW - timedelta(hours=18), "type": "CASH_DEPOSIT", "id": "tx_s2"},
        {"amount": 47_200.0, "timestamp": NOW - timedelta(hours=8),  "type": "CASH_DEPOSIT", "id": "tx_s3"},
    ]

    ctx = RuleContext(
        user_id="user_smurf_003",
        transaction_amount=49_000.0,
        transaction_type="CASH_DEPOSIT",
        transaction_time=NOW,
        user_age_days=200,
        user_occupation="Salaried",
        user_risk_tier="LOW",
        user_avg_transaction=10_000.0,
        user_last_activity_days=3,
        recent_transactions=history,
    )
    results = engine.evaluate(ctx)
    score = engine.compute_transaction_risk(results)
    max_sev = engine.get_max_severity(results)
    print_scenario("Structuring (4 deposits ₹42k–₹49k in 28h)", results, score, max_sev)
    rule_ids = [r.rule_id for r in results]
    assert "R-205" in rule_ids, "Structuring rule (R-205) should have triggered"
    print(f"  ℹ️  Structuring score contribution: {score}")


# ──────────────────────────────────────────────
# Scenario 4: Sanctions Hit
# ──────────────────────────────────────────────

def scenario_sanctions():
    engine = AMLEngine()

    # Patch the sanctions rule's provider so "Ahmed Omar Testwal" returns a MATCH
    for rule in engine.rules:
        if rule.rule_id == "R-001":
            rule.provider = TestSanctionsProvider()
            break

    ctx = RuleContext(
        user_id="Ahmed Omar Testwal",
        transaction_amount=25_000.0,
        transaction_type="WIRE_TRANSFER",
        transaction_time=NOW,
        user_age_days=90,
        user_occupation="Salaried",
        user_risk_tier="HIGH",
        user_avg_transaction=20_000.0,
        user_last_activity_days=10,
    )
    results = engine.evaluate(ctx)
    score = engine.compute_transaction_risk(results)
    max_sev = engine.get_max_severity(results)
    print_scenario("Sanctions Hit (Ahmed Omar Testwal)", results, score, max_sev)
    rule_ids = [r.rule_id for r in results]
    assert "R-001" in rule_ids, "Sanctions rule (R-001) should have triggered"
    assert score == 100, f"Expected score 100, got {score}"


# ──────────────────────────────────────────────
# Scenario 5: Dormant Account Wake-up
# ──────────────────────────────────────────────

def scenario_dormant():
    engine = AMLEngine()
    ctx = RuleContext(
        user_id="user_dormant_005",
        transaction_amount=75_000.0,
        transaction_type="CASH_DEPOSIT",
        transaction_time=NOW,
        user_age_days=1000,
        user_occupation="Salaried",
        user_risk_tier="LOW",
        user_avg_transaction=5_000.0,
        user_last_activity_days=240,
    )
    results = engine.evaluate(ctx)
    score = engine.compute_transaction_risk(results)
    max_sev = engine.get_max_severity(results)
    print_scenario("Dormant Wake-up (240 days, ₹75,000)", results, score, max_sev)
    rule_ids = [r.rule_id for r in results]
    assert "R-301" in rule_ids, "Dormant rule (R-301) should have triggered"


# ──────────────────────────────────────────────
# Scenario 6: KYC Profile Mismatch
# ──────────────────────────────────────────────

def scenario_kyc_mismatch():
    engine = AMLEngine()

    # Student with ₹7,50,000 monthly volume (threshold for Student = ₹50,000)
    history = [
        {"amount": 200_000.0, "timestamp": NOW - timedelta(days=10), "type": "WIRE_TRANSFER", "id": "tx_k1"},
        {"amount": 300_000.0, "timestamp": NOW - timedelta(days=5),  "type": "WIRE_TRANSFER", "id": "tx_k2"},
    ]

    ctx = RuleContext(
        user_id="user_student_006",
        transaction_amount=250_000.0,   # Current tx brings total to 750,000
        transaction_type="WIRE_TRANSFER",
        transaction_time=NOW,
        user_age_days=120,
        user_occupation="Student",
        user_risk_tier="LOW",
        user_avg_transaction=5_000.0,
        user_last_activity_days=5,
        recent_transactions=history,
    )
    results = engine.evaluate(ctx)
    score = engine.compute_transaction_risk(results)
    max_sev = engine.get_max_severity(results)
    print_scenario("KYC Mismatch (Student, ₹7,50,000 volume)", results, score, max_sev)
    rule_ids = [r.rule_id for r in results]
    assert "R-501" in rule_ids, "KYC mismatch rule (R-501) should have triggered"


# ──────────────────────────────────────────────
# Scenario 7: Multiple Rules (Structuring + Dormant)
# ──────────────────────────────────────────────

def scenario_multi_rule():
    engine = AMLEngine()

    # Dormant account (200 days) with current large tx AND structuring history
    # Current tx = ₹55,000 → triggers dormant (> 50k) but NOT in structuring range
    # History has 3 txs in [40k, 50k) within 72h → triggers structuring from history alone
    history = [
        {"amount": 45_000.0, "timestamp": NOW - timedelta(hours=20), "type": "CASH_DEPOSIT", "id": "tx_m1"},
        {"amount": 45_000.0, "timestamp": NOW - timedelta(hours=12), "type": "CASH_DEPOSIT", "id": "tx_m2"},
        {"amount": 45_000.0, "timestamp": NOW - timedelta(hours=4),  "type": "CASH_DEPOSIT", "id": "tx_m3"},
    ]

    ctx = RuleContext(
        user_id="user_multi_007",
        transaction_amount=55_000.0,
        transaction_type="CASH_DEPOSIT",
        transaction_time=NOW,
        user_age_days=500,
        user_occupation="Salaried",
        user_risk_tier="LOW",
        user_avg_transaction=3_000.0,
        user_last_activity_days=200,
        recent_transactions=history,
    )
    results = engine.evaluate(ctx)
    score = engine.compute_transaction_risk(results)
    max_sev = engine.get_max_severity(results)
    print_scenario("Multi-Rule (Structuring + Dormant)", results, score, max_sev)
    rule_ids = [r.rule_id for r in results]
    assert "R-205" in rule_ids, "Structuring rule (R-205) should have triggered"
    assert "R-301" in rule_ids, "Dormant rule (R-301) should have triggered"
    assert score > 0, f"Combined score should be > 0, got {score}"
    print(f"  ℹ️  Combined risk score: {score}")


# ──────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────

def main():
    print("\n🔷 SENTINEL AML ENGINE — TEST SUITE 🔷\n")
    scenarios = [
        ("1. Normal Transaction",        scenario_normal),
        ("2. CTR Threshold",              scenario_ctr),
        ("3. Structuring (Smurfing)",     scenario_structuring),
        ("4. Sanctions Hit",              scenario_sanctions),
        ("5. Dormant Wake-up",            scenario_dormant),
        ("6. KYC Mismatch",              scenario_kyc_mismatch),
        ("7. Multi-Rule Trigger",         scenario_multi_rule),
    ]

    passed = 0
    failed = 0

    for name, fn in scenarios:
        try:
            fn()
            print(f"  ✅ {name} — PASSED")
            passed += 1
        except AssertionError as ae:
            print(f"  ❌ {name} — ASSERTION FAILED: {ae}")
            failed += 1
        except Exception as e:
            print(f"  ❌ {name} — ERROR: {e}")
            failed += 1

    print(f"\n{'=' * 70}")
    print(f"  RESULTS: {passed} passed, {failed} failed out of {len(scenarios)}")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
