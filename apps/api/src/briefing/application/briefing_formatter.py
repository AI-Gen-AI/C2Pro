"""Pure text formatter for MorningBriefingProjection (ADR-021, TASK-V3-021-02)."""

from __future__ import annotations

from src.briefing.domain.projection import MorningBriefingProjection


class BriefingFormatter:
    """Stateless pure formatter — no I/O, no external calls."""

    @staticmethod
    def format_text(projection: MorningBriefingProjection) -> str:
        lines: list[str] = [
            f"Morning Briefing — Project {projection.project_id}",
            f"Period: {projection.period_start.date()} → {projection.period_end.date()}",
            "",
            f"New action items:  {projection.new_action_item_count}",
            f"Overdue reviews:   {projection.overdue_review_count}",
        ]

        if projection.health_deltas:
            lines.append("")
            lines.append("Health changes:")
            for delta in projection.health_deltas:
                sign = "+" if delta.delta >= 0 else ""
                lines.append(
                    f"  {delta.dimension}: {delta.previous:.2f} → {delta.current:.2f}"
                    f" ({sign}{delta.delta:.2f})"
                )

        if projection.trigger_events:
            lines.append("")
            lines.append("Events: " + ", ".join(projection.trigger_events))

        return "\n".join(lines)

    @staticmethod
    def format_subject(projection: MorningBriefingProjection) -> str:
        return (
            f"[C2Pro Briefing] Project {projection.project_id}"
            f" — {projection.new_action_item_count} new items,"
            f" {projection.overdue_review_count} overdue"
        )


__all__ = ["BriefingFormatter"]
