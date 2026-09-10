from __future__ import annotations

from src.security.autonomy import (
    AutonomyContext,
    AutonomyResult,
    evaluate_autonomy,
    requires_human_approval,
)


class TestRequiresHumanApprovalSimple:
    def test_normal_p4_no_approval(self):
        assert requires_human_approval(risk_level="normal", priority_level="P4") is False

    def test_risk_alto_requires_approval(self):
        assert requires_human_approval(risk_level="alto") is True

    def test_priority_p0_requires_approval(self):
        assert requires_human_approval(priority_level="P0") is True

    def test_priority_p1_requires_approval(self):
        assert requires_human_approval(priority_level="P1") is True

    def test_category_integridade_p0_requires_approval(self):
        assert requires_human_approval(category="Integridade", priority_level="P0") is True

    def test_category_seguranca_requires_approval(self):
        assert requires_human_approval(category="Segurança", priority_level="P3") is True

    def test_adversarial_threshold_requires_approval(self):
        assert requires_human_approval(injection_score=0.8) is True

    def test_adversarial_detected_flag_requires(self):
        assert requires_human_approval(adversarial_detected=True, injection_score=0.0) is True

    def test_history_considered_normal_escalates_to_approval(self):
        assert requires_human_approval(risk_level="normal", history_considered=True) is True


class TestEvaluateAutonomyContext:
    def test_normal_scenario_no_reasons(self):
        ctx = AutonomyContext(risk_level="normal", priority_level="P4")
        result = evaluate_autonomy(ctx)
        assert isinstance(result, AutonomyResult)
        assert result.requires_human_approval is False
        assert result.risk_escalated is False
        assert result.reasons == []

    def test_integridade_p0_reason_included(self):
        ctx = AutonomyContext(category="Integridade", priority_level="P0")
        result = evaluate_autonomy(ctx)
        assert result.requires_human_approval is True
        assert any("Integridade" in r for r in result.reasons)

    def test_adversarial_reason_included(self):
        ctx = AutonomyContext(injection_score=0.75, adversarial_detected=True)
        result = evaluate_autonomy(ctx)
        assert result.requires_human_approval is True
        assert any("adversarial" in r for r in result.reasons)

    def test_history_escalates_moderate_to_high(self):
        ctx = AutonomyContext(risk_level="moderado", history_considered=True)
        result = evaluate_autonomy(ctx)
        assert result.requires_human_approval is True
        assert result.risk_escalated is True
        assert any("histórico recente" in r for r in result.reasons)

    def test_to_dict_has_expected_keys(self):
        ctx = AutonomyContext(risk_level="alto")
        r = evaluate_autonomy(ctx)
        d = r.to_dict()
        assert set(d.keys()) == {"requires_human_approval", "reasons", "risk_escalated"}
