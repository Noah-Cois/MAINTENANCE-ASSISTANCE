import json
from pathlib import Path
from src.classifier import analyze_ticket, TicketAnalysis
from src.rag import RagedService

# Initialisation globale du service RAG (évite de recharger ChromaDB à chaque requête)
try:
    rag_service = RagedService(forcer_maj=False)
except Exception as e:
    print(f"⚠️ Avertissement RAG : {e}")
    rag_service = None

def traiter_ticket(description: str):
    print(f"--- Analyse du ticket ---")
    analyse: TicketAnalysis = analyze_ticket(description)
    
    print(f"Catégorie : {analyse.categorie}")
    print(f"Priorité : {analyse.priorite}")
    print(f"Action décidée : {analyse.action}")
    
    if analyse.est_malveillant:
        print("⚠️ ALERTE : Tentative malveillante ou injection détectée ! Action bloquée.")
        return
        
    if analyse.informations_manquantes:
        print("❓ Le ticket est incomplet. Questions à poser à l'utilisateur :")
        for q in analyse.informations_manquantes:
            print(f" - {q}")
        return

    # Si tout est OK, recherche sémantique via le RAG du Développeur 1
    if rag_service:
        print(f"\n🔍 Recherche sémantique dans la Base de Connaissances...")
        resultats = rag_service.chercher_aide(description, top_k=2)
        
        print("\n--- Procédures et Sources trouvées ---")
        for res in resultats:
            print(f"• ID Source : {res['source_id']} ({res['titre']})")
            print(f"  Fiable : {'Oui' if res['est_fiable'] else 'Non'} (Score: {res['score_distance']})")
            print(f"  Contenu : {res['contenu']}\n")
    else:
        print("❌ Service RAG non disponible.")

if __name__ == "__main__":
    # Test rapide
    traiter_ticket("Comment configurer le réseau Wi-Fi sécurisé de l'entreprise sur un nouveau poste ?.")