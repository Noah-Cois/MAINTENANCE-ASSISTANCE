"""Module 3 — Recherche documentaire (RAG) & citation des sources.

- Chunking de data/connaissances_kb.json (une fiche = plusieurs chunks :
  titre, symptômes, chaque étape de procédure).
- Recherche : ChromaDB si installé (base vectorielle locale),
  sinon repli déterministe BM25 (fonctionne partout, sans dépendance).
- Exigence sujet : les réponses citent leurs sources (ex: KB-NET-04).

Interface :
    resultats = rechercher(question: str, top_k: int = 3) -> list[dict]
    sources = citer_sources(resultats: list) -> list[str]
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Optional

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_KB_FILE = _DATA_DIR / "connaissances_kb.json"

try:  # pragma: no cover - chromadb optionnel (wheels absentes sur Python 3.14)
    import chromadb

    _HAS_CHROMADB = True
except ImportError:
    _HAS_CHROMADB = False

_PONCTUATION_RE = re.compile(r"[^a-z0-9àâäéèêëîïôöùûüçœ ]", re.IGNORECASE)

_CHUNKS: list[dict] | None = None
_COLLECTION: Optional[object] = None


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


def _initialiser() -> tuple:
    """Initialise (et met en cache) les chunks et éventuellement la collection ChromaDB."""
    global _CHUNKS, _COLLECTION
    if _CHUNKS is None:
        _CHUNKS = decouper_chunks()
    if _HAS_CHROMADB and _COLLECTION is None:
        try:
            client = chromadb.PersistentClient(path=str(_DATA_DIR.parent / "chroma_db"))
            _COLLECTION = client.get_or_create_collection(name="kb")
            if _COLLECTION.count() != len(_CHUNKS):
                _COLLECTION.delete(ids=[str(i) for i in range(_COLLECTION.count())])
                _COLLECTION.add(
                    ids=[str(i) for i in range(len(_CHUNKS))],
                    documents=[c["contenu"] for c in _CHUNKS],
                    metadatas=[{"source": c["source"], "categorie": c["categorie"]} for c in _CHUNKS],
                )
        except Exception:
            _COLLECTION = None
    return _CHUNKS, _COLLECTION


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
        # poids du type de chunk + bonus si la catégorie correspond aux mots-clés
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

    Retourne : [{"contenu": str, "source": str, "score": float}, ...]
    """
    chunks, collection = _initialiser()
    query_tokens = _tokens(question or "")

    if _HAS_CHROMADB and collection is not None:
        try:
            res = collection.query(query_texts=[question], n_results=top_k)
            resultats = []
            for doc, meta, dist in zip(
                res["documents"][0], res["metadatas"][0], res["distances"][0]
            ):
                resultats.append(
                    {
                        "contenu": doc,
                        "source": meta.get("source", "KB-?"),
                        "categorie": meta.get("categorie", ""),
                        "score": round(1.0 - min(dist, 1.0), 4),
                    }
                )
            return resultats
        except Exception:
            pass  # repli BM25

    return _bm25(chunks, query_tokens, top_k)


def citer_sources(resultats: list) -> list:
    """Extrait la liste des sources citées, dédupliquée et ordonnée (ex: ["KB-NET-04"])."""
    vus: list = []
    for r in resultats:
        if r.get("source") and r["source"] not in vus:
            vus.append(r["source"])
    return vus