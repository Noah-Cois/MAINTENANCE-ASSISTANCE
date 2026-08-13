"""Module 2 — Extraction d'informations & questions ciblées.

Interface :
    infos = extraire_informations(question: str, session: dict | None = None) -> dict
    questions = generer_questions(infos: dict) -> list[str]
    complete = est_complete(infos: dict) -> bool

Informations extraites :
    {"equipement": str | None, "symptomes": list[str], "code_erreur": str | None}
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_KB_EQUIPEMENT_RE = re.compile(r"\bKB-[A-Z]{3,6}-\d{2}\b", re.IGNORECASE)
_CODE_ERREUR_RE = re.compile(r"\b(?:err|erreur)[:\s]*(?:code\s*)?([A-Z]{2,6}-\d{2,5}|\d{3,5})\b", re.IGNORECASE)

_SYMPTOMES_CONNUS = [
    "pas de ping", "aucun ping", "plus de ping", "perte de connectivite",
    "connectivite", "reseau lent", "lent", "plus de courant", "pas de courant",
    "aucun courant", "coupure", "surchauffe", "bruit", "bruit anormal",
    "vibration", "vibrations", "ecran fige", "ecran bleu", "fige", "plantage",
    "ne repond plus", "ne répond plus", "ne repond pas", "ne fonctionne plus",
    "grippage", "s'arrête", "s'arrete", "s'arrête tout seul", "redemarre seul",
    "fuit", "fuite", "odeur", "étincelle", "etincelle", "panne totale", "en panne",
    "ne demarre pas", "ne démarre pas", "aucun voyant", "deconnexion",
    "deconnexions", "perte de paquets", "erreur",
]

_ACCENTS = str.maketrans("àâäéèêëîïôöùûüçÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ", "aaaeeeeiioouuucAAAEEEEIIOOUUUC")


def _normaliser(texte: str) -> str:
    return texte.lower().translate(_ACCENTS)


def _charger_codes_equipements() -> set:
    """Codes d'équipements connus depuis data/equipements.json."""
    try:
        data = json.loads((_DATA_DIR / "equipements.json").read_text(encoding="utf-8"))
        return {e["code"].upper() for e in data.get("equipements", [])}
    except Exception:
        return set()


def extraire_informations(question: str, session: dict | None = None) -> dict:
    """Extrait les informations utiles de la demande (équipement, symptômes, code erreur).

    `session` (optionnel) : contexte accumulé (réponses précédentes de l'utilisateur).
    """
    question = (question or "").strip()
    contexte = (session or {}).get("contexte", {}) or {}

    equipement = _KB_EQUIPEMENT_RE.search(question)
    if equipement:
        equipement_code = equipement.group(0).upper()
    else:
        # code nu (ex: NET-04) connu de l'inventaire
        for code in sorted(_charger_codes_equipements(), key=len, reverse=True):
            if re.search(rf"\b{code}\b", question.upper()):
                equipement_code = code
                break
        else:
            equipement_code = None

    code_erreur = None
    m = _CODE_ERREUR_RE.search(question)
    if m:
        code_erreur = m.group(1).upper()

    symptomes = [s for s in _SYMPTOMES_CONNUS if s in _normaliser(question)]

    # fusion avec le contexte accumulé (réponses aux questions précédentes)
    equipement_code = equipement_code or contexte.get("equipement")
    code_erreur = code_erreur or contexte.get("code_erreur")
    symptomes = symptomes or contexte.get("symptomes") or []

    return {"equipement": equipement_code, "symptomes": symptomes, "code_erreur": code_erreur}


def est_complete(infos: dict) -> bool:
    """Une demande est complète si l'équipement est identifié et qu'un symptôme est donné."""
    return bool(infos.get("equipement")) and bool(infos.get("symptomes"))


def generer_questions(infos: dict) -> list:
    """Génère les questions ciblées sur les informations manquantes."""
    questions = []
    if not infos.get("equipement"):
        questions.append("Quel est le code de l'équipement concerné ? (ex: KB-NET-04, KB-ELEC-02)")
    if not infos.get("symptomes"):
        questions.append("Quels sont les symptômes constatés ? (bruit, perte de connectivité, panne de courant...)")
    if not infos.get("code_erreur"):
        questions.append("Un code d'erreur est-il affiché ? (ex: ERR-NET-42)")
    return questions[:2]  # maximum 2 questions par tour pour rester conversationnel