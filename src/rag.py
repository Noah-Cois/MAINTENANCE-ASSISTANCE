import os
import json
import shutil
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEndpointEmbeddings

# Récupération des chemins relatifs selon l'architecture du projet
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(BASE_DIR, "data", "connaissances_kb.json")
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")

class RagedService:
    def __init__(self, forcer_maj=False):
        import streamlit as st

        # 1. Récupération sécurisée du token (Streamlit Secrets prioritaire, puis .env local)
        hf_token = None
        try:
            if hasattr(st, "secrets") and "HUGGINGFACEHUB_API_TOKEN" in st.secrets:
                hf_token = st.secrets["HUGGINGFACEHUB_API_TOKEN"]
        except Exception:
            pass
            
        if not hf_token:
            hf_token = os.environ.get("HUGGINGFACEHUB_API_TOKEN")

        # 2. Sécurité : On vérifie que le token est bien trouvé
        if not hf_token:
            raise ValueError("Erreur : La variable HUGGINGFACEHUB_API_TOKEN est manquante dans les secrets Streamlit ou l'environnement.")

        # 3. On l'injecte dans os.environ pour que LangChain / les bibliothèques le détectent automatiquement
        os.environ["HUGGINGFACEHUB_API_TOKEN"] = hf_token

        # 4. Initialisation du modèle d'embedding en passant explicitement le token (recommandé)
        self.embeddings = HuggingFaceEndpointEmbeddings(
            model="sentence-transformers/all-MiniLM-L6-v2",
            huggingfacehub_api_token=hf_token
        )
        self.vector_store = None
        
        # Si mise à jour forcée demandée, on nettoie l'ancien dossier
        if forcer_maj and os.path.exists(CHROMA_DIR):
            print("🔄 Suppression de l'ancienne base vectorielle locale...")
            shutil.rmtree(CHROMA_DIR)
            
        self._charger_ou_creer_base()
    def _charger_ou_creer_base(self):
        """Charge la base existante ou crée une nouvelle base ChromaDB."""
        if os.path.exists(CHROMA_DIR):
            print("💾 Chargement de la base vectorielle ChromaDB existante...")
            self.vector_store = Chroma(persist_directory=CHROMA_DIR, embedding_function=self.embeddings)
        else:
            print("⏳ Dossier chroma_db introuvable. Initialisation et génération des embeddings...")
            if not os.path.exists(JSON_PATH):
                raise FileNotFoundError(f"Le fichier source de connaissances est introuvable : {JSON_PATH}")

            with open(JSON_PATH, "r", encoding="utf-8") as f:
                kb_data = json.load(f)

            documents = []
            for item in kb_data:
                texte_complet = f"Titre: {item['titre']}\nDescription: {item['description']}\nSolutions: {item['solutions']}"
                doc = Document(
                    page_content=texte_complet,
                    metadata={"id": item["id"], "categorie": item["categorie"], "titre": item["titre"]}
                )
                documents.append(doc)

            self.vector_store = Chroma.from_documents(
                documents=documents,
                embedding=self.embeddings,
                persist_directory=CHROMA_DIR
            )
            print("🚀 Nouvelle base ChromaDB initialisée localement !")

    def chercher_aide(self, texte_incident: str, top_k: int = 2):
        """Recherche par similarité vectorielle et retourne un dictionnaire structuré."""
        resultats = self.vector_store.similarity_search_with_score(texte_incident, k=top_k)
        
        reponses_formatees = []
        for doc, score in resultats:
            # Ajustement du seuil de confiance (distance)
            fiable = True if score < 1.30 else False
            
            reponses_formatees.append({
                "source_id": doc.metadata["id"],
                "titre": doc.metadata["titre"],
                "contenu": doc.page_content,
                "score_distance": round(score, 2),
                "est_fiable": fiable
            })
            
        return reponses_formatees

# Zone de test local autonome pour vous (le Dev 1)
if __name__ == "__main__":
    # Pour vos tests personnels uniquement, on simule le chargement du .env
    from dotenv import load_dotenv
    load_dotenv()
    
    # On force la mise à jour si on a modifié le JSON
    service_rag = RagedService(forcer_maj=True)
    
    print("\n🔍 Test de recherche locale :")
    incident_test = "Problème d'accès au réseau sans fil de l'entreprise"
    trouvailles = service_rag.chercher_aide(incident_test)
    print(json.dumps(trouvailles, indent=2, ensure_ascii=False))
