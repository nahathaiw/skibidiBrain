"""Preset ticker lists.

MAGIC_MONITOR: first 25 tickers from the Syrius Magic Monitor PDF
(prediction/Syrius Magic Monitor - 20220506 - 1850.pdf). Capped well below the
full ~368 to stay within Yahoo rate limits when quoting/scanning the list.
"""
from __future__ import annotations

MAGIC_MONITOR: list[str] = [
    'JPNL', 'BRZU', 'EDZ', 'SPXL', 'HIBS', 'EDC',
    'HIBL', 'HIPR', 'EZU', 'EWG', 'RSP', 'QQQ',
    'FXI', 'EWW', 'EWU', 'EWA', 'EWZ', 'EWC',
    'EEM', 'EWQ', 'EWH', 'INDA', 'EWJ', 'EWY',
    'EWT',
]
