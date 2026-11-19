"""
Streamlit chat UI for the DarGlobal & Wasalt assistant.

Run:
    streamlit run streamlit_app.py

Needs:
    OPENROUTER_API_KEY as an environment variable
    or in .streamlit/secrets.toml

Without a key, the bot still works in retrieval-only mode.
"""

import asyncio
import os
from pathlib import Path

import streamlit as st

from app.chatcore import answer
from app.rag import load_index


CHUNKS = os.environ.get(
    "CHUNKS_PATH",
    "data/processed/chunks.jsonl"
)

MAX_USER_MESSAGES = 40

SUGGESTIONS = [
    "Which DarGlobal projects are in Oman?",
    "Who are DarGlobal's brand partners?",
    "What is Wasalt and who owns it?",
    "Tell me about Trump Mansions in Riyadh",
    "What did DarGlobal announce in November 2026?",
]

WELCOME = (
    "Hello! I can answer questions about **DarGlobal** "
    "(projects, locations, brand partners, press) and "
    "**Wasalt** (features, property types, how it works). "
    "Pick an example or type your own question."
)


st.set_page_config(
    page_title="DarGlobal & Wasalt Assistant",
    page_icon="🏙️",
    layout="centered"
)


def _secret(name):
    if os.environ.get(name):
        return os.environ[name]

    try:
        return st.secrets.get(name, "")
    except Exception:
        return ""


_key = _secret("OPENROUTER_API_KEY")

if _key:
    os.environ["OPENROUTER_API_KEY"] = _key


@st.cache_resource(show_spinner="Loading knowledge base…")
def get_index():
    if not Path(CHUNKS).exists():
        import process_data
        process_data.main()

    return load_index(CHUNKS)


# ---------------- Session State ----------------

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending" not in st.session_state:
    st.session_state.pending = None


def clear_chat():
    st.session_state.messages = []
    st.session_state.pending = None


def queue_prompt(text):
    st.session_state.pending = text


def render_meta(m):
    if m.get("sources"):
        st.caption(
            "Sources: "
            + " · ".join(
                f"[{s['title']}]({s['url']})"
                for s in m["sources"]
            )
        )

    if m.get("mode") == "retrieval-only":
        st.caption(
            "⚠️ AI model unavailable (rate limit or no key) "
            "- showing the most relevant data instead."
        )

    elif m.get("model"):
        st.caption(f"Model: {m['model']}")


# ---------------- Header + History ----------------

st.title("🏙️ DarGlobal & Wasalt Assistant")

st.caption(
    "Answers come from a curated dataset of public "
    "DarGlobal and Wasalt pages (collected 19 Nov 2026). "
    "Informational only, not financial advice."
)


if not st.session_state.messages:
    with st.chat_message("assistant"):
        st.markdown(WELCOME)

    for i, suggestion in enumerate(SUGGESTIONS):
        st.button(
            suggestion,
            key=f"sug{i}",
            on_click=queue_prompt,
            args=(suggestion,)
        )


for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

        if m["role"] == "assistant":
            render_meta(m)


# ---------------- Handle New Input ----------------

prompt = st.chat_input(
    "Ask about DarGlobal projects, partners, news, or Wasalt…",
    max_chars=1000
)

if not prompt and st.session_state.pending:
    prompt = st.session_state.pending
    st.session_state.pending = None


if prompt:
    n_user = sum(
        1 for m in st.session_state.messages
        if m["role"] == "user"
    )

    if n_user >= MAX_USER_MESSAGES:
        st.warning(
            "This chat reached its message limit. "
            "Please clear the chat to start a new one."
        )

    else:
        history = [
            {
                "role": m["role"],
                "content": m["content"]
            }
            for m in st.session_state.messages
        ][-6:]

        st.session_state.messages.append({
            "role": "user",
            "content": prompt
        })

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                result = asyncio.run(
                    answer(
                        get_index(),
                        prompt,
                        history
                    )
                )

            st.markdown(result["answer"])
            render_meta(result)

        st.session_state.messages.append({
            "role": "assistant",
            "content": result["answer"],
            "sources": result.get("sources"),
            "mode": result.get("mode"),
            "model": result.get("model"),
        })


# ---------------- Sidebar ----------------

with st.sidebar:
    st.header("Chat")

    st.button(
        "🗑️ Clear chat",
        on_click=clear_chat,
        use_container_width=True,
        disabled=not st.session_state.messages
    )

    transcript = "\n\n".join(
        f"{'You' if m['role'] == 'user' else 'Assistant'}: "
        f"{m['content']}"
        for m in st.session_state.messages
    )

    st.download_button(
        "⬇️ Download chat",
        transcript or " ",
        file_name="chat.txt",
        use_container_width=True,
        disabled=not st.session_state.messages
    )

    st.caption(
        f"Messages in this chat: "
        f"{len(st.session_state.messages)}"
    )

    st.divider()
    st.subheader("Status")

    if os.environ.get("OPENROUTER_API_KEY"):
        st.success("AI model: connected (OpenRouter)")
    else:
        st.warning(
            "No OPENROUTER_API_KEY: retrieval-only mode"
        )

    st.caption(
        f"Knowledge base: {len(get_index().chunks)} chunks"
    )

    st.divider()

    st.caption(
        "Built with Streamlit, BM25 retrieval "
        "and a free OpenRouter model."
    )