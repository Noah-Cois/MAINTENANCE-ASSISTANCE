"""Module 3 — Recherche documentaire (RAG) & citation des sources.

Deux moteurs, sélectionnés automatiquement :
- **RAG Fusion** (ChromaDB + embeddings HuggingFace) : utilisé si les
  dépendances sont installées ET que `HUGGINGFACEHUB_API_TOKEN` est définie
  (voir `requirements.txt` — nécessite Python ≤ 3.13 pour ChromaDB).
- **Repli BM25** pur Python : fonctionne partout, sans dépendance ni clé.

- Chunking de data/connaissances_kb.json (une fiche = titre, symptômes,
  étapes de procédure).
- Exigence sujet : les réponses citent leurs sources (ex: KB-NET-04).

Interface (stable pour l'agent et les tests) :
    resultats = rechercher(question: str, top_k: int = 3) -> list[dict]
    sources = citer_sources(resultats: list) -> list[str]
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
from pathlib import Path
from typing import Optional

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_KB_FILE = _DATA_DIR / "connaissances_kb.json"
_BASE_DIR = _DATA_DIR.parent
_CHROMA_DIR = _BASE_DIR / "chroma_db"

try:  # pragma: no cover - RAG Fusion optionnel (deps absentes sur Python 3.14)
    from langchain_chroma import Chroma
    from langchain_core.documents import Document
    from langchain_huggingface import HuggingFaceEndpointEmbeddings

    _HAS_FUSION_RAG = True
except ImportError:  # pragma: no cover
    _HAS_FUSION_RAG = False

_PONCTUATION_RE = re.compile(r"[^a-z0-9àâäéèêëîïôöùûüçœ ]", re.IGNORECASE)

_CHUNKS: list[dict] | None = None
_SERVICE: Optional["RagedService"] = None
_SERVICE_TENTE = False


# ------------------------------------------------------------------ chargement
def _lire_kb() -> list:
    """Lit la base de connaissances (data/connaissances_kb.json)."""
    data = json.loads(_KB_FILE.read_text(encoding="utf-8"))
    return data.get("fiches", [])


def decouper_chunks(fiches: list | None = None) -> list:
    """Découpe la KB en chunks (chunking) : titre, symptômes, étapes de procédure."""
    fiches = fiches if fiches is not None else _lire_kb()
    chunks = []
    for fiche in fiches:
        source = fiche["id"]
        chunks.append({"contenu": fiche["titre"], "source": source, "categorie": fiche["categorie"], "poids": 3})
        if fiche.get("symptomes"):
            chunks.append(
                {
                    "contenu": "Symptômes : " + ", ".join(fiche["symptomes"]),
                    "source": source,
                    "categorie": fiche["categorie"],
                    "poids": 2,
                }
            )
        for etape in fiche.get("procedure", []):
            chunks.append({"contenu": etape, "source": source, "categorie": fiche["categorie"], "poids": 1})
    return chunks


# ------------------------------------------------------------------ RAG Fusion
class RagedService:
    """Moteur de la branche Fusion : base vectorielle ChromaDB + embeddings HuggingFace.

    Chargé de manière paresseuse : si le token HF est absent ou si l'API
    échoue, l'agent retombe automatiquement sur le repli BM25.
    """

    def __init__(self, forcer_maj: bool = False) -> None:
        if not os.environ.get("HUGGINGFACEHUB_API_TOKEN"):
            raise ValueError(
                "La variable HUGGINGFACEHUB_API_TOKEN est manquante dans l'environnement."
            )
        self.embeddings = HuggingFaceEndpointEmbeddings(
            model="sentence-transformers/all-MiniLM-L6-v2"
        )
        self.vector_store = None

        if forcer_maj and _CHROMA_DIR.exists():
            shutil.rmtree(_CHROMA_DIR)
        self._charger_ou_creer_base()

    def _charger_ou_creer_base(self) -> None:
        if _CHROMA_DIR.exists():
            self.vector_store = Chroma(
                persist_directory=str(_CHROMA_DIR), embedding_function=self.embeddings
            )
            return

        if not _KB_FILE.exists():
            raise FileNotFoundError(f"Base de connaissances introuvable : {_KB_FILE}")

        kb_data = _lire_kb()
        documents = []
        for item in kb_data:
            symptomes = ", ".join(item.get("symptomes") or [])
            procedure = "; ".join(item.get("procedure") or [])
            texte_complet = (
                f"Titre: {item['titre']}\n"
                f"Symptômes: {symptomes}\n"
                f"Procédure: {procedure}"
            )
            documents.append(
                Document(
                    page_content=texte_complet,
                    metadata={
                        "id": item["id"],
                        "categorie": item["categorie"],
                        "titre": item["titre"],
                    },
                )
            )

        self.vector_store = Chroma.from_documents(
            documents=documents,
            embedding=self.embeddings,
            persist_directory=str(_CHROMA_DIR),
        )

    def chercher_aide(self, texte_incident: str, top_k: int = 2) -> list:
        """Recherche par similarité vectorielle, retourne une liste structurée."""
        resultats = self.vector_store.similarity_search_with_score(texte_incident, k=top_k)
        reponses = []
        for doc, score in resultats:
            reponses.append(
                {
                    "source_id": doc.metadata["id"],
                    "titre": doc.metadata["titre"],
                    "contenu": doc.page_content,
                    "score_distance": round(score, 2),
                    "est_fiable": score < 1.30,
                }
            )
        return reponses


def _obtenir_service() -> "RagedService | None":
    """Retourne le service RAG Fusion s'il est disponible, sinon None."""
    global _SERVICE, _SERVICE_TENTE
    if _SERVICE_TENTE:
        return _SERVICE
    _SERVICE_TENTE = True
    if not _HAS_FUSION_RAG:
        return None
    try:
        _SERVICE = RagedService()
    except Exception:
        _SERVICE = None
    return _SERVICE


# ------------------------------------------------------------------ recherche
def _tokens(texte: str) -> list:
    return _PONCTUATION_RE.sub(" ", texte.lower()).split()


def _bm25(chunks: list, query_tokens: list, top_k: int) -> list:
    """Score BM25 simple (k1=1.5, b=0.75) — déterministe, sans dépendance."""
    n = len(chunks)
    doc_lens = [len(_tokens(c["contenu"])) for c in chunks]
    avg_len = sum(doc_lens) / max(n, 1)
    docs_contenant = {}

    for c, doc_len in zip(chunks, doc_lens):
        toks = set(_tokens(c["contenu"]))
        for t in toks:
            docs_contenant[t] = docs_contenant.get(t, 0) + 1

    scores = []
    for idx, (c, doc_len) in enumerate(zip(chunks, doc_lens)):
        toks = _tokens(c["contenu"])
        freq = {t: toks.count(t) for t in set(toks)}
        score = 0.0
        for t in query_tokens:
            if t not in freq:
                continue
            idf = math.log(1 + (n - docs_contenant.get(t, 0) + 0.5) / (docs_contenant.get(t, 0) + 0.5))
            tf = freq[t] * (1.5 + 1) / (freq[t] + 1.5 * (1 - 0.75 + 0.75 * doc_len / max(avg_len, 1)))
            score += idf * tf
        score *= c.get("poids", 1)
        scores.append((score, idx))

    scores.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "contenu": chunks[idx]["contenu"],
            "source": chunks[idx]["source"],
            "categorie": chunks[idx]["categorie"],
            "score": round(score, 4),
        }
        for score, idx in scores[:top_k]
        if score > 0
    ]


def rechercher(question: str, top_k: int = 3) -> list:
    """Recherche les chunks les plus pertinents dans la base de connaissances.

    RAG Fusion (ChromaDB) si disponible, sinon repli BM25.
    Retourne : [{"contenu": str, "source": str, "score": float}, ...]
    """
    service = _obtenir_service()
    if service is not None:
        try:
            resultats = service.chercher_aide(question, top_k=top_k)
            return [
                {
                    "contenu": r["contenu"],
                    "source": r["source_id"],
                    "categorie": "",
                    "score": r["score_distance"],
                    "fiable": r["est_fiable"],
                }
                for r in resultats
            ]
        except Exception:
            pass  # repli BM25

    global _CHUNKS
    if _CHUNKS is None:
        _CHUNKS = decouper_chunks()
    return _bm25(_CHUNKS, _tokens(question or ""), top_k)


def citer_sources(resultats: list) -> list:
    """Extrait la liste des sources citées, dédupliquée et ordonnée (ex: ["KB-NET-04"])."""
    vus: list = []
    for r in resultats:
        if r.get("source") and r["source"] not in vus:
            vus.append(r["source"])
    return vus