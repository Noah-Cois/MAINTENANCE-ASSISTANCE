"""Intégration LLM optionnelle (Gemini) — Développeur 4.

Ajoute une rédaction de réponse par un modèle génératif (Gemini) lorsque
la clé API est disponible ; sinon (ou en cas d'erreur réseau/quota),
l'agent retombe sur sa réponse déterministe (règles + RAG). Les sources
citées restent celles du RAG, quel que soit le mode.

Zéro dépendance : appel REST via urllib (stdlib) — fonctionne sans pip.

Configuration :
    GEMINI_API_KEY   clé API (https://aistudio.google.com/apikey, free tier)
    GEMINI_MODEL     modèle (défaut: gemini-2.5-flash)
La clé peut aussi être placée dans un fichier `.env` à la racine du projet
(une ligne `GEMINI_API_KEY=...`), chargé automatiquement.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{modele}:generateContent"

_derniere_appel: dict = {"utilise": False, "modele": None, "duree_ms": None, "erreur": None}


def _charger_dotenv() -> None:
    """Charge un éventuel .env à la racine du projet (sans dépendance)."""
    chemin = Path(__file__).resolve().parent.parent / ".env"
    if not chemin.is_file():
        return
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if ligne and not ligne.startswith("#") and "=" in ligne:
            cle, _, valeur = ligne.partition("=")
            os.environ.setdefault(cle.strip(), valeur.strip())


_charger_dotenv()


def disponible() -> bool:
    return bool(os.getenv("GEMINI_API_KEY"))


def modele() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def derniere_appel() -> dict:
    """Infos du dernier appel LLM (pour l'observabilité) : utilise/modele/duree_ms/erreur."""
    return dict(_derniere_appel)


def _appel_gemini(prompt: str) -> str | None:
    cle = os.getenv("GEMINI_API_KEY")
    url = _ENDPOINT.format(modele=modele()) + "?key=" + cle
    corps = json.dumps(
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1024},
        }
    ).encode("utf-8")
    requete = urllib.request.Request(
        url, data=corps, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(requete, timeout=45) as reponse:
        donnees = json.loads(reponse.read().decode("utf-8"))
    try:
        return donnees["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, TypeError):
        return None


def rediger_reponse(question: str, classification: dict | None, resultats: list[dict]) -> str | None:
    """Rédige la réponse finale avec Gemini à partir du contexte RAG.

    Retourne None si la clé est absente ou si l'appel échoue (réseau,
    quota, format inattendu) : l'agent utilise alors sa réponse par défaut.
    """
    if not disponible():
        return None

    bloc_fiches = "\n".join(
        f"[{r['source']}] {r['contenu']}" for r in resultats
    ) or "Aucune fiche trouvée."
    classification_ligne = (
        f"{classification['categorie']} / priorité {classification['priorite']} / {classification['equipe']}"
        if classification
        else "non précisée"
    )
    prompt = (
        "Tu es un assistant IA d'assistance à la maintenance industrielle.\n\n"
        f"Panne signalée par l'opérateur : {question}\n"
        f"Classification : {classification_ligne}\n\n"
        "Procédures de la base de connaissances (à utiliser en priorité) :\n"
        f"{bloc_fiches}\n\n"
        "Rédige une réponse concise, structurée et actionnable en français :\n"
        "1) le diagnostic le plus probable,\n"
        "2) les actions immédiates à réaliser (sécurité d'abord),\n"
        "3) si un ticket de maintenance doit être créé, le mentionner.\n"
        "Cite les sources entre parenthèses quand tu utilises une fiche (ex: KB-NET-04)."
    )

    debut = time.monotonic()
    try:
        texte = _appel_gemini(prompt)
        _derniere_appel.update(
            {
                "utilise": texte is not None,
                "modele": modele(),
                "duree_ms": int((time.monotonic() - debut) * 1000),
                "erreur": None if texte is not None else "réponse vide",
            }
        )
        return texte
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError) as exc:
        _derniere_appel.update(
            {
                "utilise": False,
                "modele": modele(),
                "duree_ms": int((time.monotonic() - debut) * 1000),
                "erreur": str(exc),
            }
        )
        return None