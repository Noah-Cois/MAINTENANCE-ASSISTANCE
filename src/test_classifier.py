from src.classifier import analyze_ticket
import os

# S'assurer que la clé API est définie (ou l'insérer temporairement pour le test)
# os.environ["OPENAI_API_KEY"] = "ta_cle_api_ici"

if __name__ == "__main__":
    ticket_test = "Bonjour, mon ordinateur ne s'allume plus du tout depuis ce matin."
    print("Analyse du ticket en cours...")
    
    resultat = analyze_ticket(ticket_test)
    
    print("\n--- RÉSULTAT STRUCTURÉ (JSON) ---")
    print(resultat.model_dump_json(indent=2))