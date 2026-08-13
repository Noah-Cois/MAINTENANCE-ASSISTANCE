"""
Squelette de l'agent (LangGraph) + système d'interruption pour validation humaine
-----------------------------------------------------------------------------------
Développeur 3 - Expert Agent & Outils Python

Ce fichier construit la machine à états (graphe) qui orchestre le cycle de
vie d'un ticket. Les nœuds "classification" et "rag" sont des placeholders
en attendant les modules classifier.py et rag.py des autres développeurs :
il suffit de remplacer leur corps par un appel aux vraies fonctions, la
forme de l'état (TicketState) ne change pas.

Le cœur de MA responsabilité :
  - guardrails (déclenchement de la pause pour les outils sensibles)
  - validation_humaine (interrupt() + reprise via Command(resume=...))
  - execution_outil (appel réel des outils définis dans tools.py)
"""

from typing import TypedDict, Annotated, Optional

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

from src.tools import TOOLS, SENSITIVE_TOOLS


class TicketState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    ticket_brut: str
    categorie: Optional[str]
    priorite: Optional[str]
    equipe: Optional[str]
    confiance: Optional[float]
    sources: list
    action_proposee: Optional[dict]     # {"tool": str, "args": dict, "justification": str}
    validation_requise: bool
    validation_decision: Optional[str]  # "approuve" | "refuse"
    resultat_outil: Optional[dict]
    resultat_final: Optional[dict]


# ---------------------------------------------------------------------------
# Nœuds placeholders (à remplacer par les modules des autres devs)
# ---------------------------------------------------------------------------

def node_classification(state: TicketState) -> dict:
    """Placeholder - sera remplacé par src/classifier.py."""
    return {
        "categorie": state.get("categorie", "non_classifie"),
        "priorite": state.get("priorite", "moyenne"),
        "equipe": state.get("equipe", "support_niveau_1"),
        "confiance": state.get("confiance", 0.5),
    }


def node_rag(state: TicketState) -> dict:
    """Placeholder - sera remplacé par src/rag.py."""
    return {"sources": state.get("sources", [])}


# ---------------------------------------------------------------------------
# Nœuds sous ma responsabilité
# ---------------------------------------------------------------------------

def node_guardrails(state: TicketState) -> dict:
    """Détecte si l'action proposée fait partie des outils sensibles.
    La détection avancée (prompt injection, cas limites métier) revient au
    module guardrails.py dédié ; ici on ne gère que le déclenchement de la
    pause pour les outils marqués SENSITIVE_TOOLS.
    """
    action = state.get("action_proposee")
    requiert_validation = bool(action) and action.get("tool") in SENSITIVE_TOOLS
    return {"validation_requise": requiert_validation}


def node_validation_humaine(state: TicketState) -> dict:
    """Met le graphe en pause et attend la décision d'un humain (bouton UI
    Approuver / Refuser dans Streamlit/Chainlit). Reprend l'exécution via :

        app.invoke(Command(resume={"decision": "approuve"}), config=config)
    """
    action = state["action_proposee"]
    decision = interrupt(
        {
            "type": "validation_requise",
            "message": "Une action sensible nécessite une validation humaine avant exécution.",
            "action_proposee": action,
        }
    )
    return {"validation_decision": decision.get("decision", "refuse")}


TOOLS_BY_NAME = {t.name: t for t in TOOLS}


def node_execution_outil(state: TicketState) -> dict:
    """Exécute réellement l'outil demandé (après validation si nécessaire)."""
    action = state["action_proposee"]
    tool_fn = TOOLS_BY_NAME.get(action["tool"])
    if tool_fn is None:
        return {"resultat_outil": {"erreur": f"Outil inconnu : {action['tool']}"}}
    resultat = tool_fn.invoke(action.get("args", {}))
    return {"resultat_outil": resultat}


def node_sortie(state: TicketState) -> dict:
    """Construit la sortie JSON structurée finale du traitement du ticket."""
    if state.get("validation_requise") and state.get("validation_decision") != "approuve":
        return {
            "resultat_final": {
                "statut": "action_refusee",
                "categorie": state.get("categorie"),
                "priorite": state.get("priorite"),
                "equipe": state.get("equipe"),
                "message": "L'action sensible proposée a été refusée par le validateur humain.",
            }
        }
    return {
        "resultat_final": {
            "statut": "traite",
            "categorie": state.get("categorie"),
            "priorite": state.get("priorite"),
            "equipe": state.get("equipe"),
            "confiance": state.get("confiance"),
            "sources": state.get("sources", []),
            "resultat_outil": state.get("resultat_outil"),
        }
    }


# ---------------------------------------------------------------------------
# Routage conditionnel
# ---------------------------------------------------------------------------

def route_apres_guardrails(state: TicketState) -> str:
    return "validation_humaine" if state.get("validation_requise") else "execution_outil"


def route_apres_validation(state: TicketState) -> str:
    return "execution_outil" if state.get("validation_decision") == "approuve" else "sortie"


# ---------------------------------------------------------------------------
# Construction du graphe
# ---------------------------------------------------------------------------

def build_graph():
    graph = StateGraph(TicketState)

    graph.add_node("classification", node_classification)
    graph.add_node("rag", node_rag)
    graph.add_node("guardrails", node_guardrails)
    graph.add_node("validation_humaine", node_validation_humaine)
    graph.add_node("execution_outil", node_execution_outil)
    graph.add_node("sortie", node_sortie)

    graph.add_edge(START, "classification")
    graph.add_edge("classification", "rag")
    graph.add_edge("rag", "guardrails")

    graph.add_conditional_edges(
        "guardrails",
        route_apres_guardrails,
        {"validation_humaine": "validation_humaine", "execution_outil": "execution_outil"},
    )
    graph.add_conditional_edges(
        "validation_humaine",
        route_apres_validation,
        {"execution_outil": "execution_outil", "sortie": "sortie"},
    )
    graph.add_edge("execution_outil", "sortie")
    graph.add_edge("sortie", END)

    # Le checkpointer est OBLIGATOIRE pour que interrupt()/Command(resume=...)
    # fonctionnent : il permet au graphe de se "souvenir" où il s'est arrêté.
    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


# ---------------------------------------------------------------------------
# Démo autonome : scénario "serveur saturé" -> action sensible -> pause -> reprise
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = build_graph()
    config = {"configurable": {"thread_id": "demo-scenario-2"}}

    ticket_initial = {
        "ticket_brut": "Le serveur web de production ne répond plus depuis 10 minutes.",
        "categorie": "infrastructure",
        "priorite": "critique",
        "equipe": "infrastructure",
        "action_proposee": {
            "tool": "redemarrer_service",
            "args": {"equipement_id": "SRV-WEB-01"},
            "justification": "Le diagnostic montre un serveur injoignable, un redémarrage est proposé.",
        },
    }

    resultat = app.invoke(ticket_initial, config=config)

    if "__interrupt__" in resultat:
        print("Le graphe est en pause, en attente d'une validation humaine :")
        print(resultat["__interrupt__"])
        # Dans l'UI Streamlit/Chainlit, ceci correspond au clic sur "Approuver".
        decision_humaine = {"decision": "approuve"}
        resultat = app.invoke(Command(resume=decision_humaine), config=config)

    print("Résultat final :")
    print(resultat["resultat_final"])
