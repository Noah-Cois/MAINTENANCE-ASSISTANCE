# MAINTENANCE-ASSISTANCE

Agent IA d'assistance à la maintenance industrielle — projet de hackathon "AI Engineering & ML" (8h, équipe de 4).

## Rapport technique

> Rédigé au fil de l'eau par le **Développeur 4** (UI, observabilité, rapport).

### 1. Contexte

L'utilisateur (agent de maintenance) décrit une panne en langage naturel. Le système doit :
classifier la demande (catégorie, priorité, équipe), poser des questions ciblées si des informations manquent,
rechercher la procédure pertinente dans la base de connaissances (**en citant les sources**, ex. `KB-NET-04`),
puis proposer des actions (création de ticket, escalade) **soumises à validation humaine**.

### 2. Architecture

```
┌─────────────┐     ┌──────────────────────────────────────────────┐
│  app.py     │────▶│  Agent (LangGraph — Dev 3)                   │
│  (Streamlit │     │  classifier → diagnosis → RAG → tools        │
│   UI, Dev4) │◀────│  (interruption → validation humaine)         │
└──────┬──────┘     └──────────────────────────────────────────────┘
       │                          │
       │ logs / métriques         │ données fictives
       ▼                          ▼
┌─────────────┐     ┌──────────────────────────────────────────────┐
│ observability│     │ data/ : connaissances_kb.json,              │
│ (LangSmith / │     │         equipements.json, utilisateurs.json │
│  JSONL, Dev4)│     └──────────────────────────────────────────────┘
└─────────────┘
```

### 3. Modules (`src/`)

| Fichier | Rôle | Dev |
|---|---|---|
| `classifier.py` | Compréhension, catégorie, priorité, équipe (sorties JSON strictes Pydantic) | 2 |
| `diagnosis.py` | Extraction d'infos & questions ciblées | 2 |
| `rag.py` | Recherche documentaire (ChromaDB/FAISS) & citation des sources | 1 |
| `tools.py` | Mocks des 8 outils imposés + interruption LangGraph | 3 |
| `guardrails.py` | Anti-insultes / injection / demandes incomplètes | 2 |
| `observability.py` | Traces, latence, métriques (LangSmith ou JSONL local) | **4** |
| `mock_agent.py` | Agent mock temporaire (remplacé par l'agent LangGraph) | **4** |

### 4. Choix techniques

- **UI** : Streamlit — chat simple, métriques en sidebar, boutons de validation humaine.
- **Agent** : LangGraph — graphe de nœuds avec interruption pour validation humaine.
- **RAG** : ChromaDB (base vectorielle locale) + chunking de la KB.
- **Sorties** : schémas Pydantic → JSON strict.
- **Observabilité** : LangSmith si `LANGSMITH_API_KEY` définie, sinon repli local `logs/runs.jsonl`
  (latence par étape, sources citées, volume de requêtes, tickets créés).

### 5. Interface (Dev 4)

- Chat : l'utilisateur décrit sa panne.
- Affichage de la classification (catégorie, priorité, équipe, confiance).
- Questions de diagnostic si équipement non identifié.
- Réponse RAG avec **sources citées** dans un expander.
- **Validation humaine** : toute action proposée (ex. `creer_ticket`) affiche une carte
  "Valider / Refuser" — l'agent ne l'exécute qu'après approbation.

### 6. Outils de l'agent (mocks imposés)

`rechercher_utilisateur`, `creer_ticket`, `consulter_equipement`, `mettre_a_jour_ticket`,
`verifier_etat_service`, `affecter_ticket`, `rechercher_incidents_actifs`, `escalader_vers_technicien`.

### 7. Scénarios de test (`tests/test_scenarios.py`)

4 scénarios obligatoires à implémenter par le binôme A (jeux de test sur le contrat agent) :
1. Demande complète → classification + réponse RAG avec sources citées.
2. Demande incomplète → questions ciblées jusqu'à complétude.
3. Demande avec insultes / injection → blocage par les garde-fous.
4. Création de ticket → validation humaine (acceptée / refusée).

### 8. Lancement

```bash
./run.sh          # crée .venv, installe requirements.txt, lance streamlit
# ou : streamlit run app.py
```

### 9. État d'avancement

- [x] Architecture du projet (data/, src/, tests/, app.py, run.sh, README.md)
- [x] UI Streamlit + validation humaine (app.py) — Dev 4
- [x] Observabilité LangSmith/JSONL + métriques sidebar (observability.py) — Dev 4
- [x] Rapport technique (ce document) — Dev 4
- [ ] Agent LangGraph réel + mocks des outils (Dev 3)
- [ ] RAG + chunking + base vectorielle (Dev 1)
- [ ] Classifier, diagnosis, guardrails, sorties Pydantic (Dev 2)
- [ ] Données fictives `data/*.json` (Dev 1/2)
- [ ] Tests des 4 scénarios + fusion des branches