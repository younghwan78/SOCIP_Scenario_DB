"""Right inspector panel — scenario summary, risk cards, notes, gate inspector."""
from __future__ import annotations

import html as html_mod
import streamlit as st

from scenario_db.api.schemas.view import RiskCard, ViewResponse, ViewSummary
from dashboard.components.viewer_theme import SEVERITY_BG, SEVERITY_COLOR


def _escape(s: str | None) -> str:
    """HTML-escape a value from DB/API data before interpolation into innerHTML."""
    return html_mod.escape(str(s or ""))


def _metric_row(label: str, value: str) -> str:
    return f"""
    <div style="display:flex;justify-content:space-between;align-items:center;
         padding:4px 0;border-bottom:1px solid #F3F4F6;">
      <span style="color:#9CA3AF;font-size:11px;">{label}</span>
      <span style="color:#111827;font-size:12px;font-weight:500;">{value}</span>
    </div>"""


def _risk_card(risk: RiskCard) -> str:
    sev_color = SEVERITY_COLOR.get(risk.severity, "#6B7280")
    sev_bg = SEVERITY_BG.get(risk.severity, "#F3F4F6")
    return f"""
    <div style="background:white;border:1px solid #E5E7EB;border-radius:10px;
         padding:10px 12px;margin-bottom:8px;border-left:3px solid {sev_color};">
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
        <span style="background:{sev_color};color:white;font-size:10px;font-weight:700;
              border-radius:50%;width:18px;height:18px;display:inline-flex;
              align-items:center;justify-content:center;">{_escape(risk.id)}</span>
        <span style="font-size:12px;font-weight:700;color:#111827;">{_escape(risk.title)}</span>
      </div>
      <div style="font-size:11px;color:#6B7280;margin-bottom:4px;">
        Component: {_escape(risk.component)}
      </div>
      <div style="font-size:11px;color:#374151;margin-bottom:6px;line-height:1.4;">
        {_escape(risk.description)}
      </div>
      <div style="display:flex;gap:6px;align-items:center;">
        <span style="background:{sev_bg};color:{sev_color};font-size:10px;font-weight:600;
              border-radius:4px;padding:2px 7px;">{_escape(risk.severity)}</span>
        <span style="font-size:10px;color:#9CA3AF;">Impact: {_escape(risk.impact)}</span>
      </div>
    </div>"""


def render_inspector(view: ViewResponse) -> None:
    """Render the right-side inspector panel using Streamlit markdown."""
    s = view.summary

    # ── Scenario summary ──────────────────────────────────────────────────
    st.markdown(
        '<p style="font-size:10px;font-weight:700;color:#9CA3AF;'
        'letter-spacing:0.08em;text-transform:uppercase;margin-bottom:6px;">'
        'SCENARIO</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<p style="font-size:18px;font-weight:700;color:#111827;line-height:1.2;">'
        f'{_escape(s.name)}</p>'
        f'<p style="font-size:12px;color:#6B7280;margin-bottom:10px;">{_escape(s.subtitle)}</p>',
        unsafe_allow_html=True,
    )

    metrics_html = (
        _metric_row("Period",     f"{_escape(str(s.period_ms))} ms")
        + _metric_row("Budget",     f"{_escape(str(s.budget_ms))} ms")
        + _metric_row("Resolution", _escape(s.resolution))
        + _metric_row("Frame Rate", f"{_escape(str(s.fps))} fps")
        + _metric_row("Variant",    _escape(s.variant_label))
    )
    st.markdown(
        f'<div style="background:#F9FAFB;border:1px solid #E5E7EB;border-radius:8px;'
        f'padding:8px 10px;margin-bottom:14px;">{metrics_html}</div>',
        unsafe_allow_html=True,
    )

    # ── Risks ─────────────────────────────────────────────────────────────
    if view.risks:
        st.markdown(
            f'<p style="font-size:10px;font-weight:700;color:#9CA3AF;'
            f'letter-spacing:0.08em;text-transform:uppercase;margin-bottom:6px;">'
            f'RISKS ({len(view.risks)})</p>',
            unsafe_allow_html=True,
        )
        for risk in view.risks:
            st.markdown(_risk_card(risk), unsafe_allow_html=True)
        st.markdown("<div style='margin-bottom:10px;'></div>", unsafe_allow_html=True)

    # ── Notes ─────────────────────────────────────────────────────────────
    if s.notes:
        st.markdown(
            '<p style="font-size:10px;font-weight:700;color:#9CA3AF;'
            'letter-spacing:0.08em;text-transform:uppercase;margin-bottom:6px;">'
            'NOTES</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="background:#F9FAFB;border:1px solid #E5E7EB;border-radius:8px;'
            f'padding:10px 12px;font-size:11px;color:#374151;line-height:1.5;">'
            f'{_escape(s.notes)}',
            unsafe_allow_html=True,
        )
        if s.captured_at:
            st.markdown(
                f'<p style="font-size:10px;color:#9CA3AF;margin-top:6px;">'
                f'Captured: {_escape(s.captured_at)}</p></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Gate inspector (VIEW-04 — GateExecutionResult 표시)
# ---------------------------------------------------------------------------

# Gate status badge 색상 (D-06: PASS/WARN/BLOCK/WAIVER_REQUIRED 구분)
_GATE_STATUS_STYLE: dict[str, dict[str, str]] = {
    "PASS":            {"border": "#D1D5DB", "bg": "#F9FAFB", "text": "#374151"},
    "WARN":            {"border": "#F59E0B", "bg": "#FFFBEB", "text": "#92400E"},
    "BLOCK":           {"border": "#EF4444", "bg": "#FEF2F2", "text": "#991B1B"},
    "WAIVER_REQUIRED": {"border": "#8B5CF6", "bg": "#F5F3FF", "text": "#5B21B6"},
}


def render_gate_inspector(gate) -> None:
    """Gate 실행 결과를 인스펙터 패널에 표시 (status badge + matched_rules risk card).

    VIEW-04: GateExecutionResult를 인스펙터 패널 + risk card로 표시.
    gate: GateExecutionResult (import 지연 — circular import 방지)
    """
    from scenario_db.gate.models import GateExecutionResult  # noqa: F401 (type hint용)

    status_str = str(gate.status)   # GateResultStatus는 StrEnum → str() 사용
    style = _GATE_STATUS_STYLE.get(status_str, _GATE_STATUS_STYLE["PASS"])

    # ── Status badge ──────────────────────────────────────────────────────
    st.markdown(
        '<p style="font-size:10px;font-weight:700;color:#9CA3AF;'
        'letter-spacing:0.08em;text-transform:uppercase;margin-bottom:6px;">'
        'GATE STATUS</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="border:2px solid {style["border"]};background:{style["bg"]};'
        f'border-radius:8px;padding:8px 12px;margin-bottom:10px;">'
        f'<span style="font-size:14px;font-weight:700;color:{style["text"]};">'
        f'{status_str}</span></div>',
        unsafe_allow_html=True,
    )

    # ── Matched issues (issue id 목록) ────────────────────────────────────
    if gate.matched_issues:
        st.markdown(
            '<p style="font-size:10px;font-weight:700;color:#9CA3AF;'
            'letter-spacing:0.08em;text-transform:uppercase;margin-bottom:4px;">'
            'MATCHED ISSUES</p>',
            unsafe_allow_html=True,
        )
        issues_html = "".join(
            f'<span style="display:inline-block;background:#FEE2E2;color:#991B1B;'
            f'border-radius:4px;padding:2px 7px;font-size:10px;font-weight:600;'
            f'margin:0 4px 4px 0;">{_escape(iss)}</span>'
            for iss in gate.matched_issues
        )
        st.markdown(
            f'<div style="margin-bottom:10px;">{issues_html}</div>',
            unsafe_allow_html=True,
        )

    # ── Missing waivers ───────────────────────────────────────────────────
    if gate.missing_waivers:
        st.markdown(
            '<p style="font-size:10px;font-weight:700;color:#9CA3AF;'
            'letter-spacing:0.08em;text-transform:uppercase;margin-bottom:4px;">'
            'MISSING WAIVERS</p>',
            unsafe_allow_html=True,
        )
        waivers_html = "".join(
            f'<span style="display:inline-block;background:#F5F3FF;color:#5B21B6;'
            f'border-radius:4px;padding:2px 7px;font-size:10px;font-weight:600;'
            f'margin:0 4px 4px 0;">{_escape(w)}</span>'
            for w in gate.missing_waivers
        )
        st.markdown(
            f'<div style="margin-bottom:10px;">{waivers_html}</div>',
            unsafe_allow_html=True,
        )

    # ── Matched rules (risk card style) ──────────────────────────────────
    if gate.matched_rules:
        st.markdown(
            f'<p style="font-size:10px;font-weight:700;color:#9CA3AF;'
            f'letter-spacing:0.08em;text-transform:uppercase;margin-bottom:6px;">'
            f'MATCHED RULES ({len(gate.matched_rules)})</p>',
            unsafe_allow_html=True,
        )
        for rule_match in gate.matched_rules:
            rule_status = str(rule_match.result)
            rule_style = _GATE_STATUS_STYLE.get(rule_status, _GATE_STATUS_STYLE["PASS"])
            msg = rule_match.message or ""
            st.markdown(
                f'<div style="background:white;border:1px solid #E5E7EB;border-radius:8px;'
                f'padding:8px 10px;margin-bottom:6px;'
                f'border-left:3px solid {rule_style["border"]};">'
                f'<div style="font-size:11px;font-weight:700;color:#111827;">'
                f'{_escape(rule_match.rule_id)}</div>'
                f'<div style="font-size:10px;color:#6B7280;margin-top:2px;">{_escape(msg)}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
