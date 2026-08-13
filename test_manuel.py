from src.tools import (
    rechercher_utilisateur, consulter_equipement,
    executer_diagnostic, creer_ticket,
    mettre_a_jour_ticket, redemarrer_service,
)

# Lecture
print(rechercher_utilisateur.invoke({"identifiant": "j.dupont"}))
print(consulter_equipement.invoke({"equipement_id": "SRV-WEB-01"}))
print(executer_diagnostic.invoke({"cible": "SRV-WEB-01", "type_test": "ping"}))

# Cas d'erreur (id inconnu) — vérifie que ça ne plante pas
print(consulter_equipement.invoke({"equipement_id": "XXX-INCONNU"}))

# Écriture
t = creer_ticket.invoke({
    "titre": "Serveur web injoignable",
    "description": "Timeout depuis 10 min",
    "categorie": "infrastructure",
    "priorite": "critique",
    "equipe": "infrastructure",
})
print(t)
print(mettre_a_jour_ticket.invoke({"ticket_id": t["ticket_id"], "statut": "en_cours"}))

# Sensible
print(redemarrer_service.invoke({"equipement_id": "SRV-WEB-01"}))