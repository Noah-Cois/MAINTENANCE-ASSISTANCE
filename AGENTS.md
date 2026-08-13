# AGENTS.md

## Repository state
- Hackathon project `MAINTENANCE-ASSISTANCE`: agent IA d'assistance à la maintenance industrielle (sujet "AI Engineering & ML").
- Subject PDF (reference, outside repo): `D:\LastMiniProjet note\sujet-maintenance-assistance.pdf`
- Remote: https://github.com/Noah-Cois/MAINTENANCE-ASSISTANCE.git
- **Le projet complet est implémenté et testé** : `app.py` (UI Streamlit), `src/` (tous les modules), `data/*.json` (données fictives), `tests/test_scenarios.py` (4 scénarios obligatoires, verts avec `python3 tests/test_scenarios.py`). `README.md` = rapport technique.
- Vérifier la syntaxe : `python3 -m py_compile app.py src/*.py` (pas de pip/streamlit dans cet environnement — lancer `run.bat` sur Windows pour tester l'UI).

## Architecture (à respecter impérativement)
```
maintenance_assistance/
├── data/    connaissances_kb.json · equipements.json · utilisateurs.json
├── src/     __init__.py · classifier.py · diagnosis.py · rag.py
│            tools.py · guardrails.py · observability.py · llm.py
│            agent.py (+ mock_agent.py : fallback de dev)
├── tests/   test_scenarios.py
├── app.py · logo_ispm.png (logo école, mode clair) · logo_ispm_dark.png (mode sombre)
├── run.sh (Linux) · run.bat (Windows) · README.md
```
- Ne pas renommer/déplacer ces fichiers ni ajouter de nouveaux modules sans raison.
- Le `_init_.py` du plan original est un typo : le fichier correct est `__init__.py`.

## Contrat d'interface agent (app.py <-> src/agent.py)
- `app.py` importe `src.agent.Agent` et retombe sur `src.mock_agent.MockAgent` (contrat en tête de `mock_agent.py`). L'agent expose `run(question, session_id) -> dict` et `resume(session_id, approbation) -> dict`, state aux clés : `etape`, `classification`, `questions`, `reponse{texte,sources}`, `pending_validation{action,description,equipement}`, `ticket_created`.
- Tout changement de ce contrat casse app.py et tests/test_scenarios.py — à vérifier par les 4 scénarios.

## Stack & conventions
- Python. UI: Streamlit. RAG: ChromaDB si installé, sinon repli BM25 pur Python (ChromaDB n'a pas de wheels sur Python 3.14). Sorties JSON strictes via schémas Pydantic (fallback dict si pydantic absent). Observabilité: LangSmith si `LANGSMITH_API_KEY`, sinon JSONL `logs/runs.jsonl`.
- Outils agent imposés (mocks dans `tools.py`, tickets en mémoire) : `rechercher_utilisateur`, `creer_ticket`, `consulter_equipement`, `mettre_a_jour_ticket`, `verifier_etat_service`, `affecter_ticket`, `rechercher_incidents_actifs`, `escalader_vers_technicien`.
- Exigences du sujet : réponses RAG avec sources citées (ex. `KB-NET-04`) ; garde-fous anti-insultes / injection / demandes incomplètes ; validation humaine des actions.

## Branches
- `main` / `origin/main`: primary branch. `devTsila` (local, contient le travail) and `origin/Josia`: work branches. Faire des commits réguliers pour ne pas perdre le travail (déjà arrivé une fois).

## Roles
- 4 développeurs (binômes A: RAG/classification, B: agent/UI). L'utilisateur est **Développeur 4 (30%)** : UI Streamlit avec boutons de validation humaine, observabilité (LangSmith/Phoenix), rapport technique.