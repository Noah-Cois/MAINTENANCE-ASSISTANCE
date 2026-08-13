"""Interface de démonstration (Streamlit) — Développeur 4.

UI du projet MAINTENANCE-ASSISTANCE :
- chat avec l'agent de maintenance,
- affichage de la classification (catégorie, priorité, équipe),
- questions de diagnostic ciblées,
- réponse RAG avec sources citées (ex: KB-NET-04),
- boutons de VALIDATION HUMAINE pour les actions proposées par l'agent
  (création de ticket, escalade, ...),
- sidebar d'observabilité (métriques de latence et de volume).

Lancement : streamlit run app.py (ou ./run.sh)
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import streamlit as st

from src import llm, observability

try:
    from src.agent import Agent  # agent LangGraph réel (Dev 3)
except ImportError:
    from src.mock_agent import MockAgent as Agent  # agent mock temporaire


st.set_page_config(page_title="Maintenance Assistance", page_icon="🔧", layout="wide")

try:
    _theme = st.get_option("theme.base")
    _logo_path = Path(__file__).resolve().parent / (
        "logo_ispm_dark.png" if _theme == "dark" else "logo_ispm.png"
    )
    if _logo_path.is_file():
        st.logo(_logo_path, size="large")
except Exception:
    pass  # logo facultatif : ne jamais bloquer l'app

_BACKEND = observability.setup_observability()


def _new_session() -> None:
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.messages = []
    st.session_state.state = None
    st.session_state.pending = False


if "session_id" not in st.session_state:
    _new_session()

agent = Agent()


# --------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("🔍 Observabilité")
    st.caption(f"Backend : **{_BACKEND}**")
    metrics = observability.get_metrics()
    col1, col2 = st.columns(2)
    col1.metric("Requêtes", metrics["requetes"])
    col2.metric("Latence moy. (ms)", metrics["latence_moyenne_ms"])
    col1.metric("Tickets créés", metrics["tickets_crees"])
    col2.metric("Escalades", metrics["escalades"])
    st.caption("Logs bruts : `logs/runs.jsonl` (repli local si pas de clé LangSmith)")
    if llm.disponible():
        st.caption(f"🤖 LLM : **Gemini actif** (`{llm.modele()}`)")
    else:
        st.caption("⚙️ LLM : non configuré (clé `GEMINI_API_KEY` manquante) — repli règles + RAG")
    if st.button("🔄 Nouvelle conversation", use_container_width=True):
        _new_session()
        st.rerun()


# --------------------------------------------------------------------------- helpers d'affichage
def _show_classification(c: dict) -> None:
    with st.container(border=True):
        st.markdown("**🧠 Classification**")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Catégorie", c["categorie"])
        c2.metric("Priorité", c["priorite"])
        c3.metric("Équipe", c["equipe"])
        c4.metric("Confiance", f"{c.get('confiance', 0):.0%}")


def _show_reponse(r: dict, llm_utilise: bool | None = None) -> None:
    st.markdown(r["texte"])
    if llm_utilise is not None:
        if llm_utilise:
            st.caption("🤖 Rédigé par **Gemini** (LLM)")
        else:
            st.caption("⚙️ Rédigé par les **règles + RAG** (LLM indisponible)")
    if r.get("sources"):
        with st.expander("📚 Sources citées"):
            st.markdown("Les sources proviennent du RAG (indépendantes du LLM) :")
            for s in r["sources"]:
                st.markdown(f"- `{s}`")


def _show_questions(qs: list[str]) -> None:
    st.markdown("**❓ Questions de diagnostic**")
    for q in qs:
        st.info(q)


def _render_message(msg: dict) -> None:
    role = msg["role"]
    kind = msg.get("kind", "text")
    with st.chat_message(role):
        if kind == "text":
            st.markdown(msg["content"])
        elif kind == "classification":
            _show_classification(msg["content"])
        elif kind == "questions":
            _show_questions(msg["content"])
        elif kind == "reponse":
            _show_reponse(msg["content"], msg.get("llm"))


# --------------------------------------------------------------------------- historique
for msg in st.session_state.messages:
    _render_message(msg)


# --------------------------------------------------------------------------- validation humaine
if st.session_state.pending and st.session_state.state:
    state = st.session_state.state
    pv = state.get("pending_validation")
    if pv:
        st.divider()
        st.warning(f"⚠️ **Validation humaine requise — action proposée : `{pv['action']}`**")
        st.markdown(pv["description"])
        c1, c2 = st.columns(2)
        if c1.button("✔ Valider", key="btn_valider", type="primary", use_container_width=True):
            with st.spinner("L'agent exécute l'action..."):
                start = time.perf_counter()
                new_state = agent.resume(st.session_state.session_id, approbation=True)
                latence_ms = (time.perf_counter() - start) * 1000
            if new_state.get("ticket_created"):
                observability.increment("tickets_crees")
            observability.log_run(
                st.session_state.session_id,
                "validation",
                pv["description"],
                new_state.get("reponse", {}).get("texte"),
                new_state.get("reponse", {}).get("sources"),
                latence_ms,
            )
            st.session_state.state = new_state
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "kind": "reponse",
                    "content": new_state["reponse"],
                    "llm": llm.derniere_appel().get("utilise", False),
                }
            )
            st.session_state.pending = False
            st.rerun()
        if c2.button("✖ Refuser", key="btn_refuser", use_container_width=True):
            new_state = agent.resume(st.session_state.session_id, approbation=False)
            st.session_state.state = new_state
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "kind": "reponse",
                    "content": new_state["reponse"],
                    "llm": llm.derniere_appel().get("utilise", False),
                }
            )
            st.session_state.pending = False
            st.rerun()


# --------------------------------------------------------------------------- saisie utilisateur
prompt = st.chat_input("Décrivez votre panne (ex: le réseau ne répond plus sur KB-NET-04)")

if prompt:
    st.session_state.messages.append({"role": "user", "kind": "text", "content": prompt})
    with st.spinner("L'agent analyse votre demande..."):
        start = time.perf_counter()
        state = agent.run(prompt, st.session_state.session_id)
        latence_ms = (time.perf_counter() - start) * 1000

    st.session_state.state = state

    if state.get("classification"):
        st.session_state.messages.append(
            {"role": "assistant", "kind": "classification", "content": state["classification"]}
        )
    if state.get("questions"):
        st.session_state.messages.append({"role": "assistant", "kind": "questions", "content": state["questions"]})
    if state.get("reponse"):
        st.session_state.messages.append(
            {
                "role": "assistant",
                "kind": "reponse",
                "content": state["reponse"],
                "llm": llm.derniere_appel().get("utilise", False),
            }
        )
        observability.log_run(
            st.session_state.session_id,
            "rag",
            prompt,
            state["reponse"].get("texte"),
            state["reponse"].get("sources"),
            latence_ms,
            extra={"classification": state.get("classification")},
        )
    else:
        observability.log_run(
            st.session_state.session_id,
            "classification",
            prompt,
            None,
            None,
            latence_ms,
            extra={"classification": state.get("classification"), "questions": state.get("questions")},
        )

    st.session_state.pending = state.get("pending_validation") is not None
    st.rerun()