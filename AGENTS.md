# AGENTS.md

## Repository state
- Hackathon project `MAINTENANCE-ASSISTANCE`: agent IA d'assistance à la maintenance industrielle (sujet "AI Engineering & ML").
- Subject PDF (reference, outside repo): `D:\LastMiniProjet note\sujet-maintenance-assistance.pdf`
- Remote: https://github.com/Noah-Cois/MAINTENANCE-ASSISTANCE.git
- Seul le scaffold du Dev 4 existe pour l'instant : `app.py` (UI Streamlit + validation humaine), `src/observability.py` (LangSmith ou repli JSONL `logs/runs.jsonl`), `src/mock_agent.py` (mock temporaire), `requirements.txt`, `run.sh`, `README.md` (rapport technique). `data/` et `tests/` existent (vides, `.gitkeep`). Modules `classifier.py`, `diagnosis.py`, `rag.py`, `tools.py`, `guardrails.py`, `src/agent.py` et `data/*.json` : **pas encore créés** (binômes A et Dev 3) — ne pas les créer pour eux.

## Branches
- `main` / `origin/main`: primary branch. `devTsila` (local) and `origin/Josia`: work branches, no code yet.

## Contrat d'interface agent (Dev 4 -> Dev 3)
- `app.py` importe `src.agent.Agent` et retombe sur `src.mock_agent.MockAgent` (contrat documenté en tête de `mock_agent.py`). Dev 3 doit fournir `src/agent.py` avec `run(question, session_id) -> dict` et `resume(session_id, approbation) -> dict`, state aux clés : `etape`, `classification`, `questions`, `reponse{texte,sources}`, `pending_validation{action,description,equipement}`, `ticket_created`.
- Vérifier l'app avec : `python3 -m py_compile app.py src/*.py` (pas de pip/streamlit dans cet environnement).

## Planned stack (from project plan, not yet in repo)
- Python. UI: Streamlit. Agent: LangGraph. RAG: ChromaDB/FAISS + chunking de la KB. Sorties JSON strictes via schémas Pydantic. Observabilité: LangSmith ou Phoenix.
- Layout prévu: `data/` (`connaissances_kb.json`, `equipements.json`, `utilisateurs.json` — données fictives), `src/` (`classifier.py`, `diagnosis.py`, `rag.py`, `tools.py`, `guardrails.py`, `observability.py`), `tests/test_scenarios.py` (4 scénarios obligatoires), `app.py`, `requirements.txt`, `run.sh`, `README.md` (rapport technique).
- Outils agent imposés (à mocker) : `rechercher_utilisateur`, `creer_ticket`, `consulter_equipement`, `mettre_a_jour_ticket`, `verifier_etat_service`, `affecter_ticket`, `rechercher_incidents_actifs`, `escalader_vers_technicien`.
- Exigences : les réponses RAG doivent citer leurs sources (ex. `KB-NET-04`) ; garde-fous anti-insultes / injection / demandes incomplètes ; validation humaine via interruption.

## Roles
- 4 développeurs (binômes A: RAG/classification, B: agent/UI). L'utilisateur est **Développeur 4 (30%)** : UI Streamlit avec boutons de validation humaine, observabilité (LangSmith/Phoenix), rapport technique.
