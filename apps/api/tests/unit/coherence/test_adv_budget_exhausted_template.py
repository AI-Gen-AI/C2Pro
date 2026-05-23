def test_adv_budget_exhausted_has_complete_template():
    from src.coherence.alert_generator import RULE_SEVERITIES, RULE_TITLES, TEMPLATES
    assert "ADV-BUDGET-EXHAUSTED" in RULE_TITLES
    assert "ADV-BUDGET-EXHAUSTED" in RULE_SEVERITIES
    assert "ADV-BUDGET-EXHAUSTED" in TEMPLATES

    title = RULE_TITLES["ADV-BUDGET-EXHAUSTED"]
    assert isinstance(title, str) and len(title) > 0

    sev = RULE_SEVERITIES["ADV-BUDGET-EXHAUSTED"]
    # Severity must be low-urgency: either AlertSeverity.INFO/LOW enum value
    # or the string "info"/"low". Accept any of those shapes.
    sev_str = getattr(sev, "value", sev)  # enum → its .value; str → itself
    assert str(sev_str).lower() in ("info", "low"), f"unexpected severity {sev!r}"

    tmpl = TEMPLATES["ADV-BUDGET-EXHAUSTED"]
    assert isinstance(tmpl, str) and "budget" in tmpl.lower()


def test_adv_budget_exhausted_passes_orphan_check():
    """assert_v1_rule_ids_have_alert_templates must NOT raise for ADV-BUDGET-EXHAUSTED.
    Use the registry's own assertion if available, else inline the check."""
    from src.coherence.alert_generator import RULE_SEVERITIES, RULE_TITLES, TEMPLATES
    # If the registry exposes the assertion utility, exercise it:
    try:
        from src.coherence.rules_engine.registry import (
            assert_v1_rule_ids_have_alert_templates,
        )

        # Pass the ADV rule_id in via a tiny fake evaluator-like shim so the
        # assertion checks our new entries specifically.
        class _ShimEvaluator:
            rule_id = "ADV-BUDGET-EXHAUSTED"

        assert_v1_rule_ids_have_alert_templates(evaluators=[_ShimEvaluator()])
    except ImportError:
        # If the registry doesn't expose it, the in-line presence check above
        # is sufficient.
        assert "ADV-BUDGET-EXHAUSTED" in RULE_TITLES
        assert "ADV-BUDGET-EXHAUSTED" in RULE_SEVERITIES
        assert "ADV-BUDGET-EXHAUSTED" in TEMPLATES
