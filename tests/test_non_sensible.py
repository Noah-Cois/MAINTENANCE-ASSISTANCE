"""
Test scénario : action NON sensible (consulter_equipement).
Vérifie que le graphe s'exécute d'un seul coup, sans jamais passer par
la pause de validation humaine.
"""

from src.agent import build_graph

app = build_graph()
config = {"configurable": {"thread_id": "test-non-sensible"}}

ticket_initial = {
    "ticket_brut": "Pouvez-vous vérifier l'état du serveur web ?",
    "categorie": "infrastructure",
    "priorite": "moyenne",
    "equipe": "infrastructure",
    "action_proposee": {
        "tool": "consulter_equipement",
        "args": {"equipement_id": "SRV-WEB-01"},
        "justification": "Vérification de routine demandée par l'utilisateur.",
    },
}

resultat = app.invoke(ticket_initial, config=config)

assert "__interrupt__" not in resultat, "Le graphe s'est arrêté alors que l'action n'est pas sensible !"
print("Résultat final (aucune pause, comme attendu) :")
print(resultat["resultat_final"])

assert resultat["resultat_final"]["statut"] == "traite"
assert resultat["resultat_final"]["resultat_outil"]["trouve"] is True
print("\n✅ Test réussi : l'action non sensible s'est exécutée directement, sans validation humaine.")