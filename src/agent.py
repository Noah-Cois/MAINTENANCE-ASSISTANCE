"""Agent de maintenance — orchestrateur des modules.

Implémente le contrat d'interface utilisé par app.py (Dev 4) :

    state = agent.run(question: str, session_id: str) -> dict
    state = agent.resume(session_id: str, approbation: bool) -> dict

Format du state (dict) :
    {
        "etape": "classification" | "diagnostic" | "validation" | "termine",
        "classification": {"categorie", "priorite", "equipe", "confiance"} | None,
        "questions": [str, ...],
        "reponse": {"texte": str, "sources": [str, ...]} | None,
        "pending_validation": {"action", "description", "equipement"} | None,
        "ticket_created": bool,
    }

Pipeline (par tour) :
    guardrails -> classifier -> diagnosis -> rag (recherche) -> tools (ticket)
La validation humaine interrompt le flux : `resume()` reprend après décision.
"""

from __future__ import annotations

from src import llm, observability
from src.classifier import classifier
from src.diagnosis import est_complete, extraire_informations, generer_questions
from src.guardrails import verifier_demande
from src.rag import citer_sources, rechercher
from src.tools import creer_ticket, escalader_vers_technicien

_ETAPES = ("classification", "diagnostic", "validation", "termine")


def _reponse_rag(question: str, classification: dict | None = None) -> dict:
    """Construit la réponse : rédaction LLM (Gemini) si disponible,
    sinon procédures RAG + sources citées."""
    resultats = rechercher(question, top_k=3)
    sources = citer_sources(resultats)

    if not resultats:
        return {
            "texte": "Aucune procédure trouvée dans la base de connaissances. "
                     "La procédure générale KB-GEN-01 s'applique : escalade vers le technicien de garde.",
            "sources": ["KB-GEN-01"],
        }

    texte = llm.rediger_reponse(question, classification, resultats)
    if not texte:
        lignes = ["Voici les procédures recommandées :"]
        for r in resultats:
            lignes.append(f"- [{r['source']}] {r['contenu']}")
        texte = "\n".join(lignes)
    return {"texte": texte, "sources": sources}


class Agent:
    """Agent de maintenance : pipeline complet avec validation humaine."""

    def __init__(self) -> None:
        self._sessions: dict[str, dict] = {}

    def _session(self, session_id: str) -> dict:
        return self._sessions.setdefault(
            session_id,
            {"etape": "classification", "contexte": {"equipement": None, "symptomes": [], "code_erreur": None}},
        )

    # ------------------------------------------------------------------ run
    def run(self, question: str, session_id: str) -> dict:
        session = self._session(session_id)
        question = (question or "").strip()
        ctx = session["contexte"]

        # --- 1. garde-fous (Module 6) ---
        garde = verifier_demande(question)
        if not garde["valide"]:
            session["etape"] = "termine"
            observability.log_run(session_id, "guardrails", question, garde["raison"], None, extra={"garde_fou": garde["type"]})
            return {
                "etape": "termine",
                "classification": None,
                "questions": [],
                "reponse": {"texte": f"🚫 Demande bloquée : {garde['raison']}", "sources": []},
                "pending_validation": None,
                "ticket_created": False,
            }

        # --- 2. extraction d'infos (Module 2) + accumulation du contexte ---
        infos = extraire_informations(question, session)
        ctx.update(
            {
                "equipement": infos["equipement"] or ctx.get("equipement"),
                "symptomes": infos["symptomes"] or ctx.get("symptomes") or [],
                "code_erreur": infos["code_erreur"] or ctx.get("code_erreur"),
            }
        )

        # --- 3. classification (Module 1) ---
        classification = classifier(question, ctx)

        # --- 4. demande incomplète -> questions ciblées (Module 2) ---
        if not est_complete(infos):
            session["etape"] = "diagnostic"
            observability.log_run(
                session_id, "diagnostic", question, None, None,
                extra={"classification": classification, "questions": infos},
            )
            return {
                "etape": "diagnostic",
                "classification": classification,
                "questions": generer_questions(infos),
                "reponse": None,
                "pending_validation": None,
                "ticket_created": False,
            }

        # --- 5. réponse RAG avec sources citées (Module 3) ---
        ctx["description"] = question
        reponse = _reponse_rag(question, classification)

        # --- 6. action proposée -> validation humaine (Module 4 + interruption) ---
        session["etape"] = "validation"
        observability.log_run(
            session_id, "validation", question, reponse["texte"], reponse["sources"],
            extra={"classification": classification, "llm": llm.derniere_appel()},
        )
        return {
            "etape": "validation",
            "classification": classification,
            "questions": [],
            "reponse": reponse,
            "pending_validation": {
                "action": "creer_ticket",
                "description": (
                    f"Créer un ticket de maintenance pour {ctx['equipement']} "
                    f"(catégorie {classification['categorie']}, priorité {classification['priorite']}, "
                    f"{classification['equipe']}) : {question}"
                ),
                "equipement": ctx["equipement"],
            },
            "ticket_created": False,
        }

    # ------------------------------------------------------------------ resume
    def resume(self, session_id: str, approbation: bool) -> dict:
        session = self._session(session_id)
        ctx = session["contexte"]
        session["etape"] = "termine"

        if not approbation:
            return {
                "etape": "termine",
                "classification": None,
                "questions": [],
                "reponse": {"texte": "Action refusée : aucun ticket n'a été créé.", "sources": []},
                "pending_validation": None,
                "ticket_created": False,
            }

        classification = classifier(ctx.get("description") or "")
        reponse = _reponse_rag(ctx.get("description") or "", classification)

        ticket = creer_ticket(
            description=ctx.get("description", ""),
            equipement=ctx.get("equipement", ""),
            categorie=classification["categorie"],
            priorite=classification["priorite"],
        )

        if classification["categorie"] == "Autre":
            # panne non identifiée -> escalade vers le technicien de garde
            ticket_id = ticket.get("ticket", {}).get("id", "TK-????")
            escalader_vers_technicien(ticket_id=ticket_id, technicien="Franck Razafindrakoto")

        ticket_id = ticket.get("ticket", {}).get("id", "TK-????")
        observability.log_run(
            session_id, "ticket", ctx.get("description", ""), reponse["texte"], reponse["sources"],
            extra={"ticket_id": ticket_id, "approbation": True},
        )
        return {
            "etape": "termine",
            "classification": None,
            "questions": [],
            "reponse": {
                "texte": f"✅ Ticket {ticket_id} créé.\n\n{reponse['texte']}",
                "sources": reponse["sources"],
            },
            "pending_validation": None,
            "ticket_created": True,
        }