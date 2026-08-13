"""Module 1 — Compréhension, catégorie, priorité, équipe.

Sortie JSON stricte via schéma Pydantic (si pydantic est installé,
sinon dict équivalent) :

    classification = classifier(question: str) -> dict
    # {"categorie": str, "priorite": str, "equipe": str, "confiance": float}

Catégories : Réseau, Électrique, Mécanique, Logiciel, Autre.
Priorités : Haute, Moyenne, Basse.
"""

from __future__ import annotations

import re

try:
    from pydantic import BaseModel, Field

    class Classification(BaseModel):
        """Schéma Pydantic : sortie JSON stricte du classifieur."""

        categorie: str = Field(description="Catégorie de la panne")
        priorite: str = Field(description="Priorité d'intervention")
        equipe: str = Field(description="Équipe de maintenance concernée")
        confiance: float = Field(ge=0.0, le=1.0, description="Confiance de la classification")

    _HAS_PYDANTIC = True
except ImportError:  # pragma: no cover - environnement sans pydantic
    _HAS_PYDANTIC = False

_MOTS_CATEGORIES = {
    "Réseau": [
        "reseau", "net", "ping", "wifi", "dns", "switch", "routeur", "connectivite",
        "connectivité", "vlan", "ip", "internet", "cable", "câble", "pare-feu", "parefeu",
        "paquets", "passerelle", "salle serveur",
    ],
    "Électrique": [
        "electrique", "électrique", "elec", "élec", "alim", "alimentation", "courant",
        "tension", "fusible", "disjoncteur", "onduleur", "court-circuit", "surtension",
        "voyant", "tableau electrique", "prises", "ampoule",
    ],
    "Mécanique": [
        "mecanique", "mécanique", "meca", "moteur", "vibration", "roulement", "courroie",
        "engrenage", "compresseur", "convoyeur", "pompe", "bruit", "grippage", "arbre",
        "fixations", "lubrification", "piece", "pièce",
    ],
    "Logiciel": [
        "logiciel", "log", "ecran", "écran", "bug", "windows", "application", "scada",
        "serveur", "mise a jour", "mise à jour", "plantage", "gelee", "gelée", "fige",
        "figé", "journal", "erreur memoire", "memoire", "réinitialisation",
        "reinitialisation", "poste", "config", "configuration",
    ],
}

_MOTS_PRIORITE_HAUTE = [
    "urgent", "urgence", "arret", "arrêt", "stopp", "production a l'arret",
    "production à l'arrêt", "critique", "incendie", "securite", "sécurité", "danger",
    "panne totale", "plus de courant", "surchauffe", "alarme", "accident", "bloque",
    "bloqué",
]

_MOTS_PRIORITE_BASSE = [
    "information", "info", "documentation", "conseil", "planifie", "planifié",
    "preventif", "préventif", "demande d'information", "renseignement", "question",
    "comment", "ou se trouve",
]

_EQUIPES = {
    "Réseau": "Équipe Réseau",
    "Électrique": "Équipe Électrique",
    "Mécanique": "Équipe Mécanique",
    "Logiciel": "Équipe Logiciel",
    "Autre": "Équipe Support Général",
}

_PONCTUATION_RE = re.compile(r"[^a-z0-9àâäéèêëîïôöùûüçœ ]", re.IGNORECASE)


def _normaliser(texte: str) -> str:
    return _PONCTUATION_RE.sub(" ", texte.lower())


def classifier(question: str, contexte: dict | None = None) -> dict:
    """Classifie une demande de maintenance (catégorie, priorité, équipe).

    Retourne une sortie JSON stricte (schéma Pydantic ou dict équivalent).
    """
    t = _normaliser(question or "")

    # --- catégorie : premier mot-clé trouvé (ordre du dict = priorité) ---
    categorie = "Autre"
    score = 0.0
    for cat, mots in _MOTS_CATEGORIES.items():
        for mot in mots:
            if mot in t:
                categorie = cat
                score = 0.95
                break
        if categorie != "Autre":
            break

    # --- priorité ---
    if any(m in t for m in _MOTS_PRIORITE_HAUTE):
        priorite = "Haute"
    elif any(m in t for m in _MOTS_PRIORITE_BASSE):
        priorite = "Basse"
    else:
        priorite = "Moyenne"

    classification = {
        "categorie": categorie,
        "priorite": priorite,
        "equipe": _EQUIPES[categorie],
        "confiance": round(score, 2),
    }

    if _HAS_PYDANTIC:
        try:
            return Classification(**classification).model_dump()
        except Exception:
            pass
    return classification