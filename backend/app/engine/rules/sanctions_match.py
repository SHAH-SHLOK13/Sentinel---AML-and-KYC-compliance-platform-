from app.engine.rules.base import AMLRule, RuleContext, RuleResult, Severity
import random

# Simulating an external provider for the sake of "Complete Code"
class MockSanctionsProvider:
    def screen_entity(self, name: str) -> dict:
        # Simulation logic:
        # In a real app, this calls an API.
        if name.lower() == "osama bin laden":
            return {"score": 1.0, "status": "MATCH", "list": "OFAC_SDN"}
        if "kim" in name.lower() and "jong" in name.lower():
            return {"score": 0.95, "status": "MATCH", "list": "UN_SANCTIONS"}
        if name == "ERROR_TEST":
            raise Exception("API Connection Failed")
        return {"score": 0.0, "status": "CLEAN", "list": None}

class SanctionsMatchRule(AMLRule):
    """
    Critical Rule: Screens user against sanctions lists.
    """

    def __init__(self):
        self.provider = MockSanctionsProvider()

    @property
    def rule_id(self) -> str:
        return "R-001"

    @property
    def rule_name(self) -> str:
        return "Global Sanctions Hit"

    @property
    def default_severity(self) -> Severity:
        return Severity.CRITICAL

    def evaluate(self, context: RuleContext) -> RuleResult:
        triggered = False
        confidence = 0.0
        explanation = ""
        evidence = {}
        
        # We assume the user's name is available via context.user_id or we'd need a name field.
        # For this implementation, let's assume user_id might contain the name or we define a mock name lookup.
        # In a real scenario, RuleContext would likely have `user_name`. 
        # Using `user_id` as the name proxy for this specific code block requirement.
        target_name = context.user_id 

        try:
            result = self.provider.screen_entity(target_name)
            score = result.get("score", 0.0)
            
            if score > 0.80:
                triggered = True
                confidence = score
                explanation = (f"User matched against {result.get('list')} "
                               f"with confidence score {score}.")
                evidence = result
            
        except Exception as e:
            # Fail-open / Conservative approach
            triggered = True
            confidence = 0.5 # Medium confidence, but CRITICAL severity forces review
            explanation = "Unable to verify sanctions status — manual review required (Provider Down)."
            evidence = {"error": str(e)}

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            triggered=triggered,
            severity=self.default_severity,
            confidence=confidence,
            explanation=explanation,
            evidence=evidence
        )
