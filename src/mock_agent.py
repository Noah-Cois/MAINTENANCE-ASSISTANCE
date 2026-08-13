"""Agent mock TEMPORAIRE pour développer l'UI (Dev 4).

À REMPLACER par l'agent LangGraph réel (Dev 3) dans src/agent.py.
L'application (app.py) essaie d'abord d'importer src.agent.Agent et
retombe sur ce mock si l'agent réel n'existe pas encore.

CONTRAT D'INTERFACE (à respecter par l'agent réel) :

    state = agent.run(question: str, session_id: str) -> dict
    state = agent.resume(session_id: str, approbation: bool) -> dict

Format du state (dict) :
    {
        "etape": "classification" | "diagnostic" | "validation" | "termine",
        "classification": {"categorie": str, "priorite": str, "equipe": str, "confiance": float} | None,
        "questions": [str, ...],                                  # questions de diagnostic posées
        "reponse": {"texte": str, "sources": [str, ...]} | None,  # réponse RAG avec sources citées (ex: KB-NET-04)
        "pending_validation": {
            "action": "creer_ticket" | "escalader_vers_technicien" | ...,
            "description": str,
            "equipement": str,
        } | None,
        "ticket_created": bool,
    }
"""

from __future__ import annotations

import re
from typing import Optional

# Base de connaissances fictive (binôme A fournira data/connaissances_kb.json)
_RAG_MOCK = {
    "Réseau": {
        "texte": (
            "D'après la fiche technique KB-NET-04 : vérifier d'abord les connecteurs réseau, "
            "redémarrer le switch du secteur, puis tester la connectivité avec un ping. "
            "Si le problème persiste, vérifier la configuration DNS et l'état du pare-feu."
        ),
        "sources": ["KB-NET-04", "KB-NET-07"],
    },
    "Électrique": {
        "texte": (
            "D'après la fiche KB-ELEC-02 : contrôler l'alimentation de l'équipement, "
            "vérifier le fusible et les connecteurs d'arrivée courant avant tout démontage. "
            "Ne jamais intervenir sans couper l'alimentation principale."
        ),
        "sources": ["KB-ELEC-02", "KB-ELEC-05"],
    },
    "Mécanique": {
        "texte": (
            "D'après la fiche KB-MECA-01 : vérifier les fixations, contrôler le niveau de "
            "lubrification et inspecter les pièces d'usure. Un bruit anormal peut provenir "
            "d'un roulement en fin de vie (voir KB-MECA-05)."
        ),
        "sources": ["KB-MECA-01", "KB-MECA-05"],
    },
    "Logiciel": {
        "texte": (
            "D'après la fiche KB-LOG-03 : redémarrer le service, vérifier les journaux "
            "d'erreurs, puis appliquer la procédure de réinitialisation décrite en KB-LOG-06 "
            "si le dysfonctionnement persiste."
        ),
        "sources": ["KB-LOG-03", "KB-LOG-06"],
    },
    "Autre": {
        "texte": (
            "La panne ne correspond pas aux fiches existantes. La procédure générale KB-GEN-01 "
            "s'applique : rassembler les informations (équipement, symptômes, code erreur) "
            "puis escalader vers le technicien de garde."
        ),
        "sources": ["KB-GEN-01"],
    },
}

_CATEGORIES = {
    "reseau": "Réseau",
    "net": "Réseau",
    "ping": "Réseau",
    "wifi": "Réseau",
    "dns": "Réseau",
    "elec": "Électrique",
    "alim": "Électrique",
    "courant": "Électrique",
    "meca": "Mécanique",
    "moteur": "Mécanique",
    "vibration": "Mécanique",
    "log": "Logiciel",
    "logiciel": "Logiciel",
    "ecran": "Logiciel",
    "bug": "Logiciel",
    "windows": "Logiciel",
}

_EQUIPES = {
    "Réseau": "Équipe Réseau",
    "Électrique": "Équipe Électrique",
    "Mécanique": "Équipe Mécanique",
    "Logiciel": "Équipe Logiciel",
    "Autre": "Équipe Support Général",
}

_MOTIFS_URGENTS = ["urgent", "arret", "arrêt", "stopp", "production", "critique", "incendie", "panne totale"]

_EQUIPEMENT_RE = re.compile(r"\bKB-[A-Z]{3,6}-\d{2}\b", re.IGNORECASE)


class MockAgent:
    """Implémente le contrat d'interface avec une logique simple basée sur des règles."""

    def __init__(self) -> None:
        self._sessions: dict[str, dict] = {}

    # ------------------------------------------------------------------ helpers
    def _classifier(self, texte: str) -> dict:
        t = texte.lower()
        categorie = "Autre"
        for mot, cat in _CATEGORIES.items():
            if mot in t:
                categorie = cat
                break
        priorite = "Haute" if any(m in t for m in _MOTIFS_URGENTS) else "Moyenne"
        return {
            "categorie": categorie,
            "priorite": priorite,
            "equipe": _EQUIPES[categorie],
            "confiance": round(0.85, 2),
        }

    def _equipement_detecte(self, texte: str) -> Optional[str]:
        m = _EQUIPEMENT_RE.search(texte)
        return m.group(0).upper() if m else None

    # ------------------------------------------------------------------ contrat
    def run(self, question: str, session_id: str) -> dict:
        session = self._sessions.setdefault(
            session_id, {"etape": "classification", "contexte": {"equipement": None}}
        )
        question = question.strip()
        ctx = session["contexte"]

        equipement = self._equipement_detecte(question)
        if equipement is not None:
            ctx["equipement"] = equipement
        elif session["etape"] == "diagnostic":
            ctx["equipement"] = question

        classification = self._classifier(question)

        # 1) Il manque l'équipement concerné -> question ciblée (module 2)
        if ctx["equipement"] is None:
            session["etape"] = "diagnostic"
            return {
                "etape": "diagnostic",
                "classification": classification,
                "questions": [
                    "Quel est le code de l'équipement concerné ? (ex: KB-NET-04, KB-ELEC-02)"
                ],
                "reponse": None,
                "pending_validation": None,
                "ticket_created": False,
            }

        # 2) Informations suffisantes -> demande de validation humaine (création ticket)
        ctx["description"] = question
        session["etape"] = "validation"
        return {
            "etape": "validation",
            "classification": classification,
            "questions": [],
            "reponse": None,
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

    def resume(self, session_id: str, approbation: bool) -> dict:
        session = self._sessions.get(session_id)
        if session is None:
            return {
                "etape": "termine",
                "classification": None,
                "questions": [],
                "reponse": {"texte": "Session inconnue.", "sources": []},
                "pending_validation": None,
                "ticket_created": False,
            }
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

        categorie = self._classifier(ctx.get("description", "") or "")["categorie"]
        fiche = _RAG_MOCK.get(categorie, _RAG_MOCK["Autre"])
        ticket_id = f"TK-{abs(hash(session_id)) % 10000:04d}"
        return {
            "etape": "termine",
            "classification": None,
            "questions": [],
            "reponse": {
                "texte": (
                    f"Ticket {ticket_id} créé pour {ctx['equipement']}.\n\n{fiche['texte']}"
                ),
                "sources": fiche["sources"],
            },
            "pending_validation": None,
            "ticket_created": True,
        }