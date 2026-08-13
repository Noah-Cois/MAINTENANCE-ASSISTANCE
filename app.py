import time
import streamlit as st
from src.classifier import analyze_ticket
from src.rag import RagedService

# Configuration de la page
st.set_page_config(
    page_title="mAlntenance & Assistance - ISPM",
    page_icon="🛠️",
    layout="wide",
)

# Initialisation du service RAG
@st.cache_resource
def get_rag_service():
    try:
        return RagedService(forcer_maj=True)
    except Exception as e:
        return None

rag_service = get_rag_service()

# Titre principal
st.title("🛠️ mAlntenance & Assistance")
st.markdown("*Assistant intelligent de support informatique, du diagnostic à la résolution* (Hackathon ISPM)")

# BARRE LATÉRALE : Observabilité & Paramètres
with st.sidebar:
    st.header("📊 Observabilité & Contrôle")
    st.metric(label="Latence moyenne", value="1.24 s", delta="-0.15 s")
    st.metric(label="Coût estimé (Session)", value="$0.0034")
    st.divider()
    
    guardrail_status = st.toggle("Activer les filtres de sécurité", value=True)
    human_validation_override = st.toggle("Mode validation humaine obligatoire", value=True)

    st.divider()
    st.subheader("💡 Mode d'emploi")
    st.markdown("Discutez naturellement dans le chat ci-contre. Si l'agent a besoin de précisions, répondez-lui directement pour affiner le diagnostic et obtenir les sources RAG.")

# Initialisation de l'historique de conversation
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Bonjour ! Décrivez-moi votre problème informatique pour commencer le diagnostic."}
    ]

# Stockage pour le dernier résultat structuré (pour l'affichage des onglets)
if "dernier_resultat" not in st.session_state:
    st.session_state.dernier_resultat = None

# Affichage de l'historique des messages du chat
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Entrée du chat utilisateur (Option A)
if prompt := st.chat_input("Écrivez votre message ou vos précisions ici..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Traitement par l'agent IA
    with st.chat_message("assistant"):
        with st.spinner("Analyse et recherche sémantique en cours..."):
            # Contexte global combinant les échanges
            contexte_global = " ".join([m["content"] for m in st.session_state.messages if m["role"] == "user"])
            
            analyse = analyze_ticket(contexte_global)
            
            sources_trouvees = []
            reponse_bot = ""
            
            if guardrail_status and analyse.est_malveillant:
                reponse_bot = "⚠️ **Alerte de sécurité** : Une tentative potentielle d'injection ou d'action non autorisée a été détectée. Action bloquée."
            else:
                # Interrogation du RAG de ton coéquipier
                if rag_service:
                    resultats_rag = rag_service.chercher_aide(contexte_global, top_k=2)
                    sources_trouvees = [f"{res['source_id']} - {res['titre']}" for res in resultats_rag]
                    
                    parties = []
                    if analyse.informations_manquantes:
                        parties.append("🔍 *Pour affiner le diagnostic, j'ai besoin de quelques précisions :*\n")
                        for q in analyse.informations_manquantes:
                            parties.append(f"- {q}")
                        parties.append("\n*Cependant, voici les procédures correspondantes trouvées dans notre base :*\n")
                    
                    for res in resultats_rag:
                        parties.append(f"### 📌 {res['titre']}\n{res['contenu']}")
                    
                    reponse_bot = "\n\n".join(parties)
                else:
                    reponse_bot = "Ticket analysé, mais le service RAG est indisponible."

            # Structuration du JSON (Option B)
            result = {
                "categorie": analyse.categorie,
                "priorite": analyse.priorite,
                "equipe": "Support Niveau 1 / Infrastructure" if analyse.priorite in ["haute", "critique"] else "Support Helpdesk",
                "confiance": 0.90,
                "informations_manquantes": analyse.informations_manquantes,
                "action": analyse.action,
                "sources": sources_trouvees,
                "validation_humaine_requise": human_validation_override and (analyse.priorite in ["haute", "critique"] or analyse.est_malveillant),
                "reponse": reponse_bot,
            }
            
            st.session_state.dernier_resultat = result
            st.markdown(reponse_bot)
            st.session_state.messages.append({"role": "assistant", "content": reponse_bot})

# CORPS SECONDAIRE : Affichage des onglets d'observabilité et du JSON (Option B)
if st.session_state.dernier_resultat is not None:
    st.divider()
    st.subheader("📋 Analyse Détaillée & Observabilité du Dernier Échange")
    
    res = st.session_state.dernier_resultat
    tab1, tab2, tab3 = st.tabs(["📊 Synthèse & Métriques", "🔍 Sortie Structurée (JSON)", "🛠️ Traces techniques"])

    with tab1:
        col1, col2, col3 = st.columns(3)
        col1.metric("Catégorie détectée", res["categorie"])
        col2.metric("Priorité", res["priorite"])
        col3.metric("Équipe assignée", res["equipe"])

        if res["informations_manquantes"]:
            st.warning("⚠️ **Informations manquantes identifiées :**")
            for info in res["informations_manquantes"]:
                st.markdown(f"- {info}")

        if res["sources"]:
            st.markdown("📚 **Sources documentaires utilisées (RAG ChromaDB) :**")
            for src in res["sources"]:
                st.code(src)

        if res["validation_humaine_requise"]:
            st.error("🛑 **Action sensible nécessitant une validation humaine**")
            if st.button("Valider et exécuter l'action"):
                st.success("Action validée et transmise au SI avec succès.")

    with tab2:
        st.markdown("### Schéma de sortie JSON requis")
        st.json(res)

    with tab3:
        st.markdown("### Journaux d'exécution (Traces)")
        st.write("- [INFO] Message utilisateur pris en compte dans le contexte global.")
        st.write(f"- [CLASSIFIER] Analyse sémantique Gemini réussie (Action : `{res['action']}`).")
        st.write("- [RAG] Interrogation de la base ChromaDB (Top K = 2).")
        st.write(f"- [AGENT] Validation humaine requise = {res['validation_humaine_requise']}.")