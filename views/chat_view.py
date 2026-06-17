"""Chat page: RAG + tool-calling chatbot UI."""
from __future__ import annotations

import streamlit as st
from openai import OpenAI

from rag import retriever
from services import chat_engine


def render(client: OpenAI, index):
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    if prompt := st.chat_input("Ask about a stock…"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                chunks = retriever.retrieve(client, index, prompt, k=6)
                context = retriever.format_context(chunks)
                answer = chat_engine.run_chat(client, st.session_state.messages, context)
                st.markdown(answer)
                if chunks:
                    with st.expander("📰 News sources used"):
                        for i, c in enumerate(chunks, 1):
                            st.markdown(f"**[{i}] {c.title}** — {c.publisher}  \n{c.link}")

        st.session_state.messages.append({"role": "assistant", "content": answer})
