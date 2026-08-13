"""
app.py — Démo Streamlit de l'agent (Dev 3 : validation du mécanisme Human-in-the-Loop)
----------------------------------------------------------------------------------------
Ceci est un scaffold de démonstration pour MA partie (agent + outils + validation
humaine). L'interface finale complète (formulaire de saisie de ticket, historique,
branchement classifier.py/rag.py) sera fusionnée avec le reste de l'équipe.

Lancer avec :  streamlit run app.py
"""

import uuid

import streamlit as st
from langgraph.types import Command

from src.agent import build_graph

st.set_page_config(page_title="Assistant Maintenance - Démo Agent", page_icon="🛠️")
st.title("🛠️ Assistant de Maintenance — Démo Agent & Validation Humaine")
st.caption("Scénario type 2 : serveur de production injoignable → action sensible → validation humaine requise")

# --- Initialisation de l'agent et de l'état de session ---------------------

@st.cache_resource
def get_agent():
    return build_graph()

app = get_agent()

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "resultat" not in st.session_state:
    st.session_state.resultat = None
if "en_attente_validation" not in st.session_state:
    st.session_state.en_attente_validation = False

config = {"configurable": {"thread_id": st.session_state.thread_id}}

# --- Choix du scénario de démo ---------------------------------------------

st.subheader("1. Ticket entrant")

scenario = st.selectbox(
    "Scénario de démonstration",
    [
        "Serveur web injoignable (action sensible → validation requise)",
        "Consultation simple d'un équipement (pas de validation requise)",
    ],
)

if "sensible" in scenario or "Serveur web" in scenario:
    action_proposee = {
        "tool": "redemarrer_service",
        "args": {"equipement_id": "SRV-WEB-01"},
        "justification": "Le diagnostic montre un serveur injoignable, un redémarrage est proposé.",
    }
    ticket_brut = "Le serveur web de production ne répond plus depuis 10 minutes."
    priorite = "critique"
else:
    action_proposee = {
        "tool": "consulter_equipement",
        "args": {"equipement_id": "SRV-WEB-01"},
        "justification": "Vérification de routine demandée par l'utilisateur.",
    }
    ticket_brut = "Pouvez-vous vérifier l'état du serveur web ?"
    priorite = "moyenne"

st.text_area("Description du ticket", value=ticket_brut, disabled=True)

if st.button("🚀 Lancer le traitement", type="primary"):
    st.session_state.thread_id = str(uuid.uuid4())  # nouveau thread à chaque run
    config = {"configurable": {"thread_id": st.session_state.thread_id}}

    ticket_initial = {
        "ticket_brut": ticket_brut,
        "categorie": "infrastructure",
        "priorite": priorite,
        "equipe": "infrastructure",
        "action_proposee": action_proposee,
    }

    resultat = app.invoke(ticket_initial, config=config)
    st.session_state.resultat = resultat
    st.session_state.en_attente_validation = "__interrupt__" in resultat
    st.rerun()

# --- Zone de validation humaine ---------------------------------------------

st.subheader("2. Traitement par l'agent")

if st.session_state.resultat is None:
    st.info("Clique sur « Lancer le traitement » pour démarrer.")

elif st.session_state.en_attente_validation:
    interrupt_data = st.session_state.resultat["__interrupt__"][0].value
    action = interrupt_data["action_proposee"]

    st.warning("⏸️ **Action sensible détectée — validation humaine requise**")
    st.write(interrupt_data["message"])
    st.json(action)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Approuver", type="primary", use_container_width=True):
            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            resultat = app.invoke(Command(resume={"decision": "approuve"}), config=config)
            st.session_state.resultat = resultat
            st.session_state.en_attente_validation = False
            st.rerun()
    with col2:
        if st.button("❌ Refuser", use_container_width=True):
            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            resultat = app.invoke(Command(resume={"decision": "refuse"}), config=config)
            st.session_state.resultat = resultat
            st.session_state.en_attente_validation = False
            st.rerun()

else:
    resultat_final = st.session_state.resultat["resultat_final"]
    if resultat_final["statut"] == "action_refusee":
        st.error("❌ Action refusée par le validateur humain")
    else:
        st.success("✅ Ticket traité")
    st.json(resultat_final)