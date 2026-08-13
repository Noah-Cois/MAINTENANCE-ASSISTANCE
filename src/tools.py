"""Module 4 — Définition et exécution des outils de l'agent (mocks).

Les 8 outils imposés par le sujet, simulés à partir des données fictives
(data/equipements.json, data/utilisateurs.json) et d'un registre de tickets
en mémoire :

    rechercher_utilisateur        creer_ticket
    consulter_equipement          mettre_a_jour_ticket
    verifier_etat_service         affecter_ticket
    rechercher_incidents_actifs   escalader_vers_technicien

Interface :
    resultat = executer_tool(nom: str, **args) -> dict
"""

from __future__ import annotations

import json
import itertools
from pathlib import Path
from typing import Any, Callable

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_TICKETS: list[dict] = []
_TICKET_COUNTER = itertools.count(1)

# ---------------------------------------------------------------- données
_JSON_CACHE: dict[str, dict] = {}


def _lire_json(nom: str) -> dict:
    if nom not in _JSON_CACHE:
        _JSON_CACHE[nom] = json.loads((_DATA_DIR / nom).read_text(encoding="utf-8"))
    return _JSON_CACHE[nom]


def _equipements() -> list:
    return _lire_json("equipements.json").get("equipements", [])


def _utilisateurs() -> list:
    return _lire_json("utilisateurs.json").get("utilisateurs", [])


# ---------------------------------------------------------------- outils
def rechercher_utilisateur(nom: str = "", role: str = "") -> dict:
    """Recherche un utilisateur par nom ou rôle."""
    resultats = []
    for u in _utilisateurs():
        if nom and nom.lower() not in u["nom"].lower():
            continue
        if role and role.lower() not in u["role"].lower():
            continue
        resultats.append(u)
    return {"outil": "rechercher_utilisateur", "trouves": resultats, "total": len(resultats)}


def consulter_equipement(code: str = "") -> dict:
    """Consulte la fiche d'un équipement par son code."""
    for e in _equipements():
        if code.upper() == e["code"]:
            return {"outil": "consulter_equipement", "equipement": e, "trouve": True}
    return {"outil": "consulter_equipement", "equipement": None, "trouve": False}


def verifier_etat_service(service: str = "") -> dict:
    """Vérifie l'état global des équipements d'un service."""
    equipements = [e for e in _equipements() if not service or e["service"] == service]
    etats = {}
    for e in equipements:
        etats[e["code"]] = e["etat"]
    return {"outil": "verifier_etat_service", "service": service or "tous", "etats": etats}


def rechercher_incidents_actifs(equipement: str = "") -> dict:
    """Recherche les incidents actifs (tickets non clos) sur un équipement."""
    actifs = [
        t for t in _TICKETS if t.get("statut") not in ("clos", "cloture", "ferme")
    ]
    if equipement:
        actifs = [t for t in actifs if t.get("equipement") == equipement.upper()]
    return {"outil": "rechercher_incidents_actifs", "incidents": actifs, "total": len(actifs)}


def creer_ticket(description: str = "", equipement: str = "", categorie: str = "Autre", priorite: str = "Moyenne", utilisateur: str = "Alice Rakoto") -> dict:
    """Crée un ticket de maintenance (mock : registre en mémoire)."""
    numero = next(_TICKET_COUNTER)
    ticket = {
        "id": f"TK-{numero:04d}",
        "description": description,
        "equipement": equipement.upper() if equipement else None,
        "categorie": categorie,
        "priorite": priorite,
        "utilisateur": utilisateur,
        "statut": "ouvert",
    }
    _TICKETS.append(ticket)
    return {"outil": "creer_ticket", "ticket": ticket, "cree": True}


def mettre_a_jour_ticket(ticket_id: str = "", statut: str = "", **details: Any) -> dict:
    """Met à jour le statut d'un ticket."""
    for t in _TICKETS:
        if t["id"] == ticket_id:
            if statut:
                t["statut"] = statut
            t.update(details)
            return {"outil": "mettre_a_jour_ticket", "ticket": t, "mis_a_jour": True}
    return {"outil": "mettre_a_jour_ticket", "mis_a_jour": False, "raison": f"Ticket {ticket_id} introuvable"}


def affecter_ticket(ticket_id: str = "", technicien: str = "") -> dict:
    """Affecte un ticket à un technicien."""
    return mettre_a_jour_ticket(ticket_id=ticket_id, technicien=technicien, statut="affecte")


def escalader_vers_technicien(ticket_id: str = "", technicien: str = "Franck Razafindrakoto") -> dict:
    """Escalade un ticket vers un technicien (garde)."""
    return mettre_a_jour_ticket(ticket_id=ticket_id, technicien=technicien, statut="escalade")


# ---------------------------------------------------------------- registre
_REGISTRE: dict[str, Callable[..., dict]] = {
    "rechercher_utilisateur": rechercher_utilisateur,
    "creer_ticket": creer_ticket,
    "consulter_equipement": consulter_equipement,
    "mettre_a_jour_ticket": mettre_a_jour_ticket,
    "verifier_etat_service": verifier_etat_service,
    "affecter_ticket": affecter_ticket,
    "rechercher_incidents_actifs": rechercher_incidents_actifs,
    "escalader_vers_technicien": escalader_vers_technicien,
}


def executer_tool(nom: str, **args: Any) -> dict:
    """Exécute un outil de l'agent par son nom et retourne un résultat JSON."""
    outil = _REGISTRE.get(nom)
    if outil is None:
        return {"outil": nom, "erreur": f"Outil inconnu : {nom}"}
    return outil(**args)