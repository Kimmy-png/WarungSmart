from __future__ import annotations

from html import escape

import streamlit as st

from warungsmart.services.insights import Insight


def kpi_card(label: str, value: str, tone: str = "") -> None:
    st.markdown(f'<div class="wcard"><div class="label">{escape(label)}</div>'
                f'<div class="value {tone}">{escape(value)}</div></div>', unsafe_allow_html=True)


def card(title: str, body_html: str, extra_class: str = "") -> None:
    st.markdown(f'<div class="wcard {extra_class}"><h2>{title}</h2>{body_html}</div>',
                unsafe_allow_html=True)


def insight_card(items: list[Insight], title: str = "✦ AI Insight") -> None:
    body = "".join(f'<div class="insight"><strong>{escape(i.title)}</strong>{escape(i.body)}</div>'
                   for i in items) or '<div class="insight">Belum ada insight. Catat penjualan terlebih dahulu.</div>'
    card(title, body, "ai")


def note(text_html: str) -> None:
    st.markdown(f'<div class="note">{text_html}</div>', unsafe_allow_html=True)


def info(text: str) -> None:
    st.markdown(f'<div class="empty">{escape(text)}</div>', unsafe_allow_html=True)
