"""Module d'observabilité : traces, latence et métriques (LangSmith ou repli local JSONL).

- Si la variable d'environnement LANGSMITH_API_KEY (ou LANGCHAIN_API_KEY) est définie,
  les runs sont envoyés vers LangSmith.
- Sinon, repli local : chaque run est appendé dans logs/runs.jsonl et les métriques
  agrégées sont exposées via get_metrics() (affichées dans la sidebar de l'UI).
L'observabilité ne doit JAMAIS faire échouer l'application : tout est en try/except.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional

_PROJECT = "maintenance-assistance"
_LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOGS_FILE = _LOGS_DIR / "runs.jsonl"

_BACKEND: Optional[str] = None  # "langsmith" | "jsonl"
_LANGSMITH: Any = None

_METRICS = {"runs": 0, "latence_total_ms": 0.0, "tickets_crees": 0, "escalades": 0}


def _backend() -> str:
    global _BACKEND
    if _BACKEND is None:
        _BACKEND = "langsmith" if (os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")) else "jsonl"
    return _BACKEND


def setup_observability(project: str = _PROJECT) -> str:
    """Initialise LangSmith si une clé est disponible, sinon active le repli JSONL.

    Retourne le nom du backend actif ("langsmith" ou "jsonl").
    """
    global _LANGSMITH
    _LOGS_DIR.mkdir(parents=True, exist_ok=True)
    if _backend() == "langsmith":
        try:
            from langsmith import Client

            _LANGSMITH = Client(project_name=project)
        except Exception:
            global _BACKEND
            _BACKEND = "jsonl"
    return _backend()


def _write_jsonl(record: dict) -> None:
    try:
        _LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with _LOGS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def log_run(
    session_id: str,
    etape: str,
    question: str,
    reponse: Optional[str] = None,
    sources: Optional[list[str]] = None,
    latence_ms: float = 0.0,
    extra: Optional[dict] = None,
) -> None:
    """Enregistre un run (une étape de la conversation) côté LangSmith et/ou JSONL."""
    global _LANGSMITH
    _METRICS["runs"] += 1
    _METRICS["latence_total_ms"] += latence_ms
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "etape": etape,
        "question": question,
        "reponse": reponse,
        "sources": sources or [],
        "latence_ms": round(latence_ms, 2),
        "backend": _backend(),
    }
    if extra:
        record.update(extra)
    if _backend() == "langsmith" and _LANGSMITH is not None:
        try:
            _LANGSMITH.create_run(
                name=f"run_{etape}",
                inputs={"question": question, "session_id": session_id},
                outputs={"reponse": reponse, "sources": sources},
                run_type="chain",
                extra={"metadata": {"session_id": session_id, "sources": sources}},
            )
        except Exception:
            pass
    _write_jsonl(record)


def increment(metric: str, value: int = 1) -> None:
    """Incrémente un compteur de métrique (ex: tickets_crees, escalades)."""
    if metric in _METRICS:
        _METRICS[metric] += value


def get_metrics() -> dict[str, Any]:
    """Métriques agrégées affichées dans la sidebar de l'UI."""
    runs = _METRICS["runs"]
    return {
        "backend": _backend(),
        "requetes": runs,
        "latence_moyenne_ms": round(_METRICS["latence_total_ms"] / runs, 2) if runs else 0.0,
        "tickets_crees": _METRICS["tickets_crees"],
        "escalades": _METRICS["escalades"],
    }


def trace(fn: Callable) -> Callable:
    """Décorateur : mesure la latence d'une fonction et l'enregistre."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        result = fn(*args, **kwargs)
        latence_ms = (time.perf_counter() - start) * 1000
        _write_jsonl(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "fonction": fn.__name__,
                "latence_ms": round(latence_ms, 2),
                "backend": _backend(),
            }
        )
        return result

    return wrapper