"""
Test scénario : l'humain REFUSE l'action sensible proposée.
Vérifie que le refus bloque bien l'exécution de l'outil (aucun redémarrage réel).
"""

from langgraph.types import Command
from src.agent import build_graph

app = build_graph()
config = {"configurable": {"thread_id": "test-refus"}}

ticket_initial = {
    "ticket_brut": "Le serveur web de production ne répond plus depuis 10 minutes.",
    "categorie": "infrastructure",
    "priorite": "critique",
    "equipe": "infrastructure",
    "action_proposee": {
        "tool": "redemarrer_service",
        "args": {"equipement_id": "SRV-WEB-01"},
        "justification": "Le diagnostic montre un serveur injoignable, un redémarrage est proposé.",
    },
}

resultat = app.invoke(ticket_initial, config=config)

if "__interrupt__" in resultat:
    print("Le graphe est en pause, en attente d'une validation humaine :")
    print(resultat["__interrupt__"])
    print("\n>>> L'humain REFUSE l'action <<<\n")
    resultat = app.invoke(Command(resume={"decision": "refuse"}), config=config)

print("Résultat final :")
print(resultat["resultat_final"])

assert resultat["resultat_final"]["statut"] == "action_refusee", "Le refus n'a pas bloqué l'action !"
assert "resultat_outil" not in resultat["resultat_final"], "L'outil sensible a été exécuté malgré le refus !"
print("\n✅ Test réussi : le refus humain a bien bloqué l'action sensible.")