"""Module 6 — Sécurité : garde-fous (anti-insultes, anti-injection, demandes incomplètes).

Interface :
    resultat = verifier_demande(texte: str) -> dict
    # {"valide": bool, "raison": str | None, "type": "insulte"|"injection"|"incomplete"|None}

Détection déterministe par listes de motifs (fonctionne sans LLM ni API key) ;
le prompt système LLM (Dev 2) peut compléter cette couche.
"""

from __future__ import annotations

import re

_INSULTES = [
    "merde", "connard", "connasse", "salope", "pute", "putain", "fdp", "fils de pute",
    "encul", "encule", "connasse", "imbecile", "cretin", "abrut", "debile",
    "grosse merde", "ta gueule", "va chier", "batard", "ordure", "salaud",
    "trou du cul", "conard", "conasse", "encule",
]

_INJECTIONS = [
    "ignore", "ignorer", "oublie ce qui precede", "oublie les instructions",
    "instructions precedentes", "instructions précédentes", "prompt", "system prompt",
    "mot de passe", "mots de passe", "password", "secret", "confidentiel",
    "donne-moi", "donne moi", "revele", "reveler", "divulgue", "contourne", "bypass",
    "jailbreak", "agis comme", "agir comme", "hack", "pirat", "craque", "role system",
    "deviens", "tu es maintenant", "sans restriction", "aucune regle",
]

_COMPLETE_MIN_LENGTH = 10

_INSULTE_RE = re.compile(r"(?:^|\s)(" + "|".join(_INSULTES) + r")(?:$|[\s.,;:!?'\"\-])", re.IGNORECASE)
_INJECTION_RE = re.compile(r"(" + "|".join(_INJECTIONS) + r")", re.IGNORECASE)


def verifier_demande(texte: str) -> dict:
    """Vérifie une demande utilisateur contre les garde-fous.

    Retourne : {"valide": bool, "raison": str | None, "type": str | None}
    """
    texte = (texte or "").strip()

    if _INSULTE_RE.search(texte):
        return {"valide": False, "raison": "Langage insultant détecté.", "type": "insulte"}

    if _INJECTION_RE.search(texte):
        return {"valide": False, "raison": "Tentative de prompt injection détectée.", "type": "injection"}

    if len(texte) < _COMPLETE_MIN_LENGTH:
        return {
            "valide": False,
            "raison": "Demande trop courte pour être traitée.",
            "type": "incomplete",
        }

    return {"valide": True, "raison": None, "type": None}