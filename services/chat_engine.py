"""The chat brain: system prompt + the OpenAI tool-calling loop.

Keeps all LLM orchestration in one place so the UI (views/chat_view.py) only has
to call run_chat(). Live-data tool results are cached to respect rate limits.
"""
from __future__ import annotations

import json
from datetime import date

import streamlit as st
from openai import OpenAI

from services.finance_tools import TOOL_FUNCTIONS, TOOL_SCHEMAS

CHAT_MODEL = "gpt-4o-mini"  # fast + cheap; swap for gpt-4o for higher quality

SYSTEM_PROMPT = """You are a helpful financial research assistant for Yahoo Finance data.
Today's date is {today}. Resolve relative/partial dates (e.g. "June 8") against it; \
assume the current year unless the user says otherwise, and never use a future date.

Rules:
- For live numbers (prices, market cap, P/E, financials, returns), ALWAYS call a \
tool to fetch fresh data. Never guess or recall numbers.
- For DATE-SPECIFIC questions ("what happened with AAPL on June 8", "why was it \
bearish that day"), FIRST call get_price_on_date to confirm the actual move (up/down \
and by how much). THEN get the news for that day: check the dated NEWS CONTEXT, and if \
it has nothing from that date, call get_news_on_date(symbol, date) to fetch historical \
news. State the real % move and explain it with the news you found.
- The NEWS CONTEXT items are tagged with their publish date. For a date question, rely \
on items on or near that date; ignore unrelated ones.
- If get_news_on_date returns configured=false or no articles, say so plainly (e.g. \
"I don't have news from that day") and explain only what the price data shows. Be honest.
- For general news/sentiment questions, use the NEWS CONTEXT and cite sources as [1], [2].
- For prediction/forecast questions ("will X go up", "outlook next week"), call \
get_price_prediction and report the signal + expected move, but ALWAYS flag it as an \
experimental, in-sample heuristic and NOT financial advice.
- Be concise. Use bullet points and tables where helpful.
- End any answer involving a buy/sell/hold judgment with: "This is not financial advice."
"""


@st.cache_data(ttl=900, show_spinner=False)
def cached_tool_call(name: str, args_json: str) -> str:
    """Cache live data 15 min to respect Yahoo rate limits. Keyed by name+args."""
    args = json.loads(args_json)
    result = TOOL_FUNCTIONS[name](**args)
    return json.dumps(result, default=str)


def run_chat(client: OpenAI, messages: list[dict], news_context: str) -> str:
    """Tool-calling loop: let the model fetch live data, then answer."""
    convo = [{"role": "system", "content": SYSTEM_PROMPT.format(today=date.today().isoformat())}]
    convo.append({"role": "system", "content": f"NEWS CONTEXT:\n{news_context}"})
    convo.extend(messages)

    for _ in range(5):  # cap tool-call rounds
        resp = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=convo,
            tools=TOOL_SCHEMAS,
            temperature=0.2,
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return msg.content or ""

        convo.append(msg.model_dump(exclude_none=True))
        for call in msg.tool_calls:
            result = cached_tool_call(call.function.name, call.function.arguments)
            convo.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": result,
            })
    return "Sorry, I couldn't complete that request."
