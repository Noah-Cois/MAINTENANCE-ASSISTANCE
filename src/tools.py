"""
Module 4 : Outils de l'agent (mocks)
-------------------------------------
Développeur 3 - Expert Agent & Outils Python

Ces fonctions simulent les intégrations avec les systèmes réels
(ITSM, inventaire, annuaire utilisateurs...) puisqu'aucune vraie
infrastructure n'est disponible pendant le hackathon.

Elles sont décorées avec @tool (langchain_core) pour être
directement appelables par l'agent LangGraph, avec description
et schéma d'arguments auto-générés à partir du docstring/typing.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TICKETS_FILE = DATA_DIR / "tickets.json"
EQUIPEMENTS_FILE = DATA_DIR / "equipements.json"
UTILISATEURS_FILE = DATA_DIR / "utilisateurs.json"


def _load_json(path: Path) -> list:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data: list) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Outils "lecture" (jamais sensibles)
# ---------------------------------------------------------------------------

@tool
def rechercher_utilisateur(identifiant: str) -> dict:
    """Recherche un utilisateur dans l'annuaire par son identifiant (ex: 'j.dupont').
    Retourne son nom, service, poste, téléphone et l'équipement qui lui est assigné.
    """
    utilisateurs = _load_json(UTILISATEURS_FILE)
    for u in utilisateurs:
        if u["identifiant"].lower() == identifiant.lower():
            return {"trouve": True, **u}
    return {"trouve": False, "erreur": f"Aucun utilisateur trouvé pour '{identifiant}'"}


@tool
def consulter_equipement(equipement_id: str) -> dict:
    """Consulte les informations d'un équipement (serveur, poste, imprimante...) via son identifiant.
    Retourne le statut, le type, le service propriétaire et le niveau de criticité.
    """
    equipements = _load_json(EQUIPEMENTS_FILE)
    for e in equipements:
        if e["id"].lower() == equipement_id.lower():
            return {"trouve": True, **e}
    return {"trouve": False, "erreur": f"Aucun équipement trouvé pour '{equipement_id}'"}


@tool
def executer_diagnostic(cible: str, type_test: str = "ping") -> dict:
    """Exécute un diagnostic simulé (ping, verification_logs, charge_cpu) sur une cible
    (identifiant d'équipement ou IP). Retourne un résultat mocké mais cohérent avec
    le statut réel de l'équipement dans l'inventaire.
    """
    equipements = _load_json(EQUIPEMENTS_FILE)
    cible_connue = next(
        (e for e in equipements if e["id"].lower() == cible.lower() or e.get("ip") == cible),
        None,
    )

    if type_test == "ping":
        if cible_connue and cible_connue.get("statut") == "en_panne":
            return {"cible": cible, "type_test": type_test, "resultat": "injoignable", "perte_paquets": "100%"}
        return {"cible": cible, "type_test": type_test, "resultat": "joignable", "latence_ms": 12}

    if type_test == "verification_logs":
        criticite_haute = cible_connue and cible_connue.get("criticite") in ("haute", "critique")
        return {
            "cible": cible,
            "type_test": type_test,
            "resultat": "logs_analyses",
            "erreurs_recentes": ["CPU > 90% pendant 15 min"] if criticite_haute else [],
        }

    if type_test == "charge_cpu":
        criticite_haute = cible_connue and cible_connue.get("criticite") in ("haute", "critique")
        return {
            "cible": cible,
            "type_test": type_test,
            "resultat": "mesure_effectuee",
            "charge_cpu_pourcent": 92 if criticite_haute else 34,
        }

    return {"cible": cible, "type_test": type_test, "erreur": "Type de test non reconnu"}


# ---------------------------------------------------------------------------
# Outils "écriture" (impact limité)
# ---------------------------------------------------------------------------

@tool
def creer_ticket(titre: str, description: str, categorie: str, priorite: str, equipe: str) -> dict:
    """Crée un nouveau ticket de support dans le système ITSM (mock).
    Retourne l'identifiant généré et le ticket créé.
    """
    tickets = _load_json(TICKETS_FILE)
    ticket_id = f"TCK-{uuid.uuid4().hex[:8].upper()}"
    ticket = {
        "ticket_id": ticket_id,
        "titre": titre,
        "description": description,
        "categorie": categorie,
        "priorite": priorite,
        "equipe": equipe,
        "statut": "ouvert",
        "cree_le": datetime.now(timezone.utc).isoformat(),
        "historique": [{"action": "creation", "date": datetime.now(timezone.utc).isoformat()}],
    }
    tickets.append(ticket)
    _save_json(TICKETS_FILE, tickets)
    return ticket


@tool
def mettre_a_jour_ticket(ticket_id: str, statut: Optional[str] = None, note: Optional[str] = None) -> dict:
    """Met à jour le statut et/ou ajoute une note à un ticket existant (mock)."""
    tickets = _load_json(TICKETS_FILE)
    for t in tickets:
        if t["ticket_id"] == ticket_id:
            if statut:
                t["statut"] = statut
            entry = {"action": "mise_a_jour", "date": datetime.now(timezone.utc).isoformat()}
            if statut:
                entry["nouveau_statut"] = statut
            if note:
                entry["note"] = note
            t["historique"].append(entry)
            _save_json(TICKETS_FILE, tickets)
            return {"trouve": True, **t}
    return {"trouve": False, "erreur": f"Ticket '{ticket_id}' introuvable"}


# ---------------------------------------------------------------------------
# Outil "sensible" -> doit systématiquement passer par la validation humaine
# ---------------------------------------------------------------------------

@tool
def redemarrer_service(equipement_id: str) -> dict:
    """ACTION SENSIBLE : redémarre un service ou un serveur (mock).
    Impacte potentiellement la production : cette action ne doit JAMAIS
    être exécutée directement par l'agent, elle doit toujours transiter
    par le nœud de validation humaine (voir agent.py).
    """
    equipements = _load_json(EQUIPEMENTS_FILE)
    equip = next((e for e in equipements if e["id"].lower() == equipement_id.lower()), None)
    if not equip:
        return {"succes": False, "erreur": f"Équipement '{equipement_id}' introuvable"}
    return {
        "succes": True,
        "equipement_id": equipement_id,
        "action": "redemarrage",
        "statut_apres": "actif",
        "date": datetime.now(timezone.utc).isoformat(),
    }


TOOLS = [
    rechercher_utilisateur,
    consulter_equipement,
    executer_diagnostic,
    creer_ticket,
    mettre_a_jour_ticket,
    redemarrer_service,
]

# Outils considérés comme sensibles : le graphe (agent.py) doit
# obligatoirement passer par une pause / validation humaine avant
# de les exécuter. À enrichir avec l'équipe "guardrails" si besoin.
SENSITIVE_TOOLS = {"redemarrer_service"}
