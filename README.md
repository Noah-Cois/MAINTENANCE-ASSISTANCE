# MAINTENANCE-ASSISTANCE

Agent IA d'assistance à la maintenance industrielle — projet de hackathon "AI Engineering & ML" (8h, équipe de 4).

## Rapport technique

### 1. Contexte

L'utilisateur (agent de maintenance) décrit une panne en langage naturel. Le système doit :
classifier la demande (catégorie, priorité, équipe), poser des questions ciblées si des informations manquent,
rechercher la procédure pertinente dans la base de connaissances (**en citant les sources**, ex. `KB-NET-04`),
puis proposer des actions (création de ticket, escalade) **soumises à validation humaine**.

### 2. Architecture

```
┌─────────────┐     ┌──────────────────────────────────────────────────┐
│  app.py     │────▶│  Agent (src/agent.py)                            │
│  (Streamlit)│     │  guardrails → classifier → diagnosis → RAG       │
│             │◀────│  → tools (ticket) — validation humaine (resume)  │
└──────┬──────┘     └──────────────────────────────────────────────────┘
       │                          │
       │ logs / métriques         │ données fictives
       ▼                          ▼
┌─────────────┐     ┌──────────────────────────────────────────────────┐
│ observability│     │ data/ : connaissances_kb.json,                  │
│ (LangSmith / │     │         equipements.json, utilisateurs.json     │
│  JSONL)      │     └──────────────────────────────────────────────────┘
└─────────────┘
```

### 3. Modules (`src/`)

| Fichier | Rôle | État |
|---|---|---|
| `guardrails.py` | Anti-insultes / anti-injection / demandes incomplètes | ✅ implémenté |
| `classifier.py` | Catégorie, priorité, équipe (sortie JSON stricte, schéma Pydantic) | ✅ implémenté |
| `diagnosis.py` | Extraction d'infos (équipement, symptômes, code erreur) + questions ciblées | ✅ implémenté |
| `rag.py` | Chunking de la KB, recherche (ChromaDB **ou** repli BM25) + citation des sources | ✅ implémenté |
| `tools.py` | Les 8 outils imposés (mocks basés sur `data/*.json`) | ✅ implémenté |
| `agent.py` | Orchestrateur `run()`/`resume()` + validation humaine | ✅ implémenté |
| `llm.py` | Rédaction des réponses par Gemini (REST stdlib, optionnel — repli automatique) | ✅ implémenté |
| `observability.py` | Traces, latence, métriques (LangSmith ou JSONL local) | ✅ implémenté |
| `mock_agent.py` | Fallback si `agent.py` indisponible (développement UI) | ✅ |

### 4. Choix techniques

- **UI** : Streamlit — chat, métriques en sidebar, boutons de validation humaine.
- **Agent** : pipeline déterministe par étapes (fonctionne sans LLM ni clé API) ;
  le contrat `run()`/`resume()` reproduit l'interruption LangGraph (human-in-the-loop).
- **RAG** : chunking des fiches (titre, symptômes, étapes) ; ChromaDB si installé,
  sinon repli **BM25** pur Python (indispensable : ChromaDB n'a pas de wheels sur Python 3.14).
- **Sorties** : schéma **Pydantic** pour la classification (dict équivalent si pydantic absent).
- **Observabilité** : LangSmith si `LANGSMITH_API_KEY` définie, sinon `logs/runs.jsonl`
  (latence par étape, sources citées, volume de requêtes, tickets créés).
- **LLM (optionnel)** : rédaction des réponses par **Gemini** (`gemini-2.5-flash`, free tier)
  via REST stdlib (zéro dépendance) quand `GEMINI_API_KEY` est définie (variable d'environnement
  ou `.env` à la racine) ; repli automatique sur la réponse déterministe si la clé est absente
  ou en cas d'erreur réseau/quota — les sources citées restent celles du RAG dans les deux modes.
- **Données** : 3 fichiers fictifs dans `data/` (10 fiches KB, 9 équipements, 6 utilisateurs).

### 5. Interface (Dev 4)

- Chat : l'utilisateur décrit sa panne.
- Affichage de la classification (catégorie, priorité, équipe, confiance).
- Questions de diagnostic si équipement/symptômes non identifiés.
- Réponse RAG avec **sources citées** (`KB-...`) dans un expander.
- **Validation humaine** : toute action proposée (ex. `creer_ticket`) affiche une carte
  "Valider / Refuser" — l'agent n'exécute qu'après approbation.

### 6. Outils de l'agent (mocks imposés)

`rechercher_utilisateur`, `creer_ticket`, `consulter_equipement`, `mettre_a_jour_ticket`,
`verifier_etat_service`, `affecter_ticket`, `rechercher_incidents_actifs`, `escalader_vers_technicien`
— exécutables via `tools.executer_tool(nom, **args)`, tickets mockés en mémoire (`TK-0001`, ...).

### 7. Scénarios de test (`tests/test_scenarios.py`)

Les 4 scénarios obligatoires sont codés et **passent** :

```bash
python3 tests/test_scenarios.py
```

1. Demande complète → classification + réponse RAG avec sources citées. ✅
2. Demande incomplète → questions ciblées jusqu'à complétude. ✅
3. Insultes / injection → blocage par les garde-fous (module + agent). ✅
4. Création de ticket → validation humaine acceptée / refusée. ✅

### 8. Lancement

```bash
./run.sh              # Linux/WSL : venv + pip install + streamlit
run.bat               # Windows : pip install + streamlit
python3 tests/test_scenarios.py   # vérification des scénarios
```

### 9. État d'avancement

- [x] Architecture complète (data/, src/, tests/, app.py, run.sh/run.bat, README.md)
- [x] Tous les modules implémentés et testés (4 scénarios OK)
- [x] UI Streamlit + validation humaine (app.py)
- [x] Observabilité LangSmith/JSONL + métriques sidebar (observability.py)
- [x] Données fictives `data/*.json` (10 fiches, 9 équipements, 6 utilisateurs)
- [x] LLM optionnel : rédaction Gemini (REST stdlib, repli automatique, `.env`)
- [ ] Optionnel : ChromaDB sur Python ≤ 3.13, garde-fous LLM avancés
- [ ] Fusion des branches de l'équipe (binôme A : améliorations RAG/prompts, Dev 3 : LangGraph)