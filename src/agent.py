import json
from pathlib import Path
from src.classifier import analyze_ticket, TicketAnalysis

def load_kb() -> list:
    kb_path = Path("data/connaissances_kb.json")
    if kb_path.exists():
        with open(kb_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

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

    # Si tout est OK, recherche dans la KB
    kb = load_kb()
    print(f"\n🔍 Recherche dans la base de connaissances ({len(kb)} articles)...")
    # Logique de matching simple ou RAG à connecter ici
    print("✓ Traitement standard prêt pour la suite.")

if __name__ == "__main__":
    # Test rapide
    traiter_ticket("Mon écran clignote et je n'ai plus internet depuis la salle 204.")