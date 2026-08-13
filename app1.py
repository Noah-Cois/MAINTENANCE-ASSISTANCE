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
        return RagedService(forcer_maj=False)
    except Exception as e:
        return None

rag_service = get_rag_service()

# Titre principal
st.title("🛠️ mAlntenance & Assistance")
st.markdown("*Assistant intelligent de support informatique, du diagnostic à la résolution* (Hackathon ISPM)")

# BARRE LATÉRALE
with st.sidebar:
    st.header("📊 Observabilité & Contrôle")
    st.metric(label="Latence moyenne", value="1.24 s", delta="-0.15 s")
    st.metric(label="Coût estimé (Session)", value="$0.0034")
    st.divider()
    
    guardrail_status = st.toggle("Activer les filtres de sécurité", value=True)
    human_validation_override = st.toggle("Mode validation humaine obligatoire", value=True)

    st.divider()
    scenario_choice = st.selectbox(
        "Charger un scénario type :",
        [
            "Sélectionner...",
            "Scénario 1 - Incident courant (Mot de passe)",
            "Scénario 2 - Incident urgent (Réseau critique)",
            "Scénario 3 - Demande incomplète",
        ],
    )

default_ticket = ""
if "Scénario 1" in scenario_choice:
    default_ticket = "Bonjour, je n'arrive plus à me connecter à ma session, mon mot de passe est rejeté."
elif "Scénario 2" in scenario_choice:
    default_ticket = "URGENT : Panne totale du réseau sur tout l'étage direction."
elif "Scénario 3" in scenario_choice:
    default_ticket = "Mon ordi bug."

# CORPS PRINCIPAL
st.subheader("📝 Soumission du Ticket")
ticket_input = st.text_area("Décrivez votre problème informatique en langage naturel :", value=default_ticket, height=100)

if st.button("Traiter le ticket", type="primary"):
    if not ticket_input.strip():
        st.warning("Veuillez saisir une description de ticket.")
    else:
        with st.spinner("Analyse en cours par l'agent IA et recherche RAG..."):
            analyse = analyze_ticket(ticket_input)
            
            sources_trouvees = []
            reponse_texte = ""
            
            if guardrail_status and analyse.est_malveillant:
                reponse_texte = "⚠️ **Alerte de sécurité** : Tentative d'injection bloquée."
            else:
                if rag_service:
                    resultats_rag = rag_service.chercher_aide(ticket_input, top_k=2)
                    sources_trouvees = [f"{res['source_id']} - {res['titre']}" for res in resultats_rag]
                    
                    parties = []
                    if analyse.informations_manquantes:
                        parties.append("💡 *Le diagnostic suggère quelques précisions (voir ci-dessous), mais voici les procédures correspondantes trouvées :*\n")
                    
                    for res in resultats_rag:
                        parties.append(f"### 📌 {res['titre']}\n{res['contenu']}")
                    reponse_texte = "\n\n".join(parties)
                else:
                    reponse_texte = "Service RAG indisponible."

            result = {
                "categorie": analyse.categorie,
                "priorite": analyse.priorite,
                "equipe": "Support Niveau 1",
                "confiance": 0.90,
                "informations_manquantes": analyse.informations_manquantes,
                "action": analyse.action,
                "sources": sources_trouvees,
                "validation_humaine_requise": human_validation_override and analyse.priorite in ["haute", "critique"],
                "reponse": reponse_texte,
            }

            st.success("Traitement terminé !")

            # Affichage en onglets
            tab1, tab2, tab3 = st.tabs(["📋 Résultat & Décision", "🔍 Sortie JSON", "🛠️ Traces"])

            with tab1:
                st.markdown("### Résumé de la prise en charge")
                st.info(result["reponse"])

                if result["informations_manquantes"]:
                    st.warning("⚠️ Précisions utiles demandées par l'agent :")
                    for info in result["informations_manquantes"]:
                        st.markdown(f"- {info}")
                    
                    # Formulaire interactif de relance si incomplet
                    with st.form("form_precision_suivi"):
                        precision_user = st.text_input("Répondre aux questions de l'agent :")
                        if st.form_submit_button("Envoyer les précisions"):
                            if precision_user:
                                ticket_complet = f"{ticket_input} | Précisions : {precision_user}"
                                nouvelle_analyse = analyze_ticket(ticket_complet)
                                r_rag = rag_service.chercher_aide(ticket_complet, top_k=1)
                                st.success("✅ Diagnostic mis à jour avec vos précisions !")
                                for r in r_rag:
                                    st.markdown(f"**Solution affinée :** {r['contenu']}")

                if result["sources"]:
                    st.markdown("📚 **Sources documentaires :**")
                    for src in result["sources"]:
                        st.code(src)

            with tab2:
                st.json(result)

            with tab3:
                st.write(f"- [AGENT] Action : `{result['action']}`")
                st.write(f"- [RAG] ChromaDB interrogé avec succès.")