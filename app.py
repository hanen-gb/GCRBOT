import streamlit as st
import sys
import os

# Ajouter le chemin src au path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'gcrbot', 'src'))

from gcrbot.service import answer_question, process_document
from gcrbot.tools_document import (
    process_document_direct, 
    list_documents_direct, 
    search_documents_direct,
    has_indexed_documents,
    get_indexed_filenames,
    clear_all_documents
)
from datetime import datetime
import uuid
import shutil

# Dossier de stockage des documents
DOC_DB_PATH = os.path.join(os.path.dirname(__file__), 'docDB')

# =========================
# 🧹 NETTOYAGE AU DÉMARRAGE (documents temporaires par session)
# =========================
if "session_initialized" not in st.session_state:
    st.session_state["session_initialized"] = True
    # Nettoyer les documents de la session précédente
    clear_all_documents()
    print("🧹 Nouvelle session - Documents précédents effacés")

# =========================
# ⚙️ CONFIG DE LA PAGE
# =========================
# Charger l'icône ENIG
ENIG_ICON_PATH = os.path.join(os.path.dirname(__file__), 'images', 'enig.png')

st.set_page_config(
    page_title="GCRBot – Assistant ENIG",
    page_icon=ENIG_ICON_PATH,
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# 🎨 STYLE GLOBAL (CSS)
# =========================
st.markdown("""
<style>
/* Imports de fonts */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* Variables globales - Style Claude */
:root {
    --primary-color: #8b6f47;
    --primary-hover: #6b5739;
    --bg-main: #ffffff;
    --bg-secondary: #f9f7f4;
    --bg-user: #e8e3db;
    --bg-bot: #f5f5f5;
    --text-primary: #2d2d2d;
    --text-secondary: #6b6b6b;
    --border-color: #e0ddd7;
    --shadow-sm: 0 1px 3px rgba(0,0,0,0.08);
    --shadow-md: 0 4px 6px rgba(0,0,0,0.05);
    --accent-warm: #a68a64;
}

/* Reset & Base */
* {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

.block-container {
    padding: 2rem 3rem;
    max-width: 100%;
}

/* Sidebar styling */
[data-testid="stSidebar"] {
    background: var(--bg-secondary);
    border-right: 1px solid var(--border-color);
}

[data-testid="stSidebar"] .block-container {
    padding: 1.5rem 1rem;
}

/* Override Streamlit button primary color */
.stButton > button[kind="primary"] {
    background-color: var(--primary-color) !important;
    border-color: var(--primary-color) !important;
    color: white !important;
}

.stButton > button[kind="primary"]:hover {
    background-color: var(--primary-hover) !important;
    border-color: var(--primary-hover) !important;
}

/* Header principal */
.main-header {
    text-align: center;
    margin-bottom: 2rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid var(--border-color);
}

.main-header h1 {
    font-size: 2rem;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 0.5rem;
}

.main-header p {
    font-size: 1rem;
    color: var(--text-secondary);
}

/* Zone de chat */
.chat-container {
    max-width: 900px;
    margin: 0 auto;
    padding-bottom: 8rem;
}

.chat-message {
    display: flex;
    margin-bottom: 1.5rem;
    animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
    from {
        opacity: 0;
        transform: translateY(10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.chat-message.user {
    justify-content: flex-end;
}

.chat-message.bot {
    justify-content: flex-start;
}

.message-content {
    max-width: 75%;
    padding: 1rem 1.25rem;
    border-radius: 1rem;
    font-size: 0.95rem;
    line-height: 1.6;
    box-shadow: var(--shadow-sm);
}

.chat-message.user .message-content {
    background: var(--bg-user);
    color: var(--text-primary);
    border-bottom-right-radius: 0.25rem;
    border: 1px solid var(--border-color);
}

.chat-message.bot .message-content {
    background: var(--bg-bot);
    color: var(--text-primary);
    border-bottom-left-radius: 0.25rem;
    border: 1px solid var(--border-color);
}

.message-avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.2rem;
    margin: 0 0.75rem;
    flex-shrink: 0;
}

.chat-message.user .message-avatar {
    background: var(--accent-warm);
}

.chat-message.bot .message-avatar {
    background: #9ca3af;
}

/* Message de bienvenue */
.welcome-message {
    text-align: center;
    max-width: 600px;
    margin: 4rem auto;
    padding: 2rem;
}

.welcome-message h2 {
    font-size: 2rem;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 1rem;
}

.welcome-message p {
    font-size: 1.1rem;
    color: var(--text-secondary);
    margin-bottom: 2rem;
}

.features-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
    margin-top: 2rem;
}

.feature-card {
    padding: 1.25rem;
    background: var(--bg-secondary);
    border-radius: 0.75rem;
    border: 1px solid var(--border-color);
    text-align: center;
    transition: all 0.2s;
}

.feature-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
    border-color: var(--primary-color);
}

.feature-icon {
    font-size: 2rem;
    margin-bottom: 0.5rem;
}

.feature-title {
    font-weight: 600;
    font-size: 0.9rem;
    color: var(--text-primary);
}

/* Sidebar : historique */
.conversation-title {
    font-weight: 600;
    font-size: 0.9rem;
    color: var(--text-primary);
    margin-bottom: 0.25rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

/* Input zone Streamlit chat - Responsive avec sidebar */
[data-testid="stChatInput"] {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: white;
    border-top: 1px solid var(--border-color);
    padding: 1rem 2rem;
    z-index: 999;
    transition: left 0.3s ease, padding-left 0.3s ease;
}

/* Quand la sidebar est ouverte (expanded) */
[data-testid="stSidebar"][aria-expanded="true"] ~ [data-testid="stAppViewContainer"] [data-testid="stChatInput"] {
    left: 21rem;
}

/* Alternative: utiliser la largeur de la sidebar */
.stApp[data-testid="stAppViewContainer"] {
    transition: margin-left 0.3s ease;
}

/* Style pour le champ de saisie */
[data-testid="stChatInput"] > div {
    max-width: 900px;
    margin: 0 auto;
}

[data-testid="stChatInput"] textarea {
    border-radius: 1.5rem !important;
    border: 1px solid var(--border-color) !important;
    padding: 0.75rem 1.25rem !important;
    font-size: 0.95rem !important;
    transition: border-color 0.2s, box-shadow 0.2s;
}

[data-testid="stChatInput"] textarea:focus {
    border-color: var(--primary-color) !important;
    box-shadow: 0 0 0 2px rgba(139, 111, 71, 0.2) !important;
}

/* Bouton envoyer */
[data-testid="stChatInput"] button {
    background: var(--primary-color) !important;
    border-radius: 50% !important;
    width: 40px !important;
    height: 40px !important;
}

[data-testid="stChatInput"] button:hover {
    background: var(--primary-hover) !important;
}

/* Responsive */
@media (max-width: 768px) {
    .block-container {
        padding: 1rem;
    }
    
    .message-content {
        max-width: 85%;
    }
    
    .features-grid {
        grid-template-columns: 1fr;
    }
    
    [data-testid="stChatInput"] {
        padding: 0.75rem 1rem;
    }
}

/* Style pour le file uploader */
.upload-section {
    background: var(--bg-secondary);
    border: 2px dashed var(--border-color);
    border-radius: 1rem;
    padding: 1.5rem;
    text-align: center;
    margin-bottom: 1rem;
    transition: all 0.3s;
}

.upload-section:hover {
    border-color: var(--primary-color);
    background: #f5f3ee;
}

.upload-icon {
    font-size: 2.5rem;
    margin-bottom: 0.5rem;
}

.upload-text {
    color: var(--text-secondary);
    font-size: 0.9rem;
}

.document-badge {
    display: inline-flex;
    align-items: center;
    background: var(--bg-user);
    border: 1px solid var(--border-color);
    border-radius: 2rem;
    padding: 0.4rem 0.8rem;
    margin: 0.25rem;
    font-size: 0.85rem;
}

.document-badge .doc-icon {
    margin-right: 0.4rem;
}
</style>
""", unsafe_allow_html=True)

# =========================
# 🧠 INITIALISATION SESSION STATE
# =========================
if "conversations" not in st.session_state:
    st.session_state["conversations"] = {}

if "current_conversation_id" not in st.session_state:
    conv_id = str(uuid.uuid4())
    st.session_state["current_conversation_id"] = conv_id
    st.session_state["conversations"][conv_id] = {
        "id": conv_id,
        "title": "Nouvelle conversation",
        "messages": [],
        "created_at": datetime.now()
    }

# =========================
# 📌 FONCTIONS UTILITAIRES
# =========================
def create_new_conversation():
    """Créer une nouvelle conversation"""
    conv_id = str(uuid.uuid4())
    st.session_state["conversations"][conv_id] = {
        "id": conv_id,
        "title": "Nouvelle conversation",
        "messages": [],
        "created_at": datetime.now()
    }
    st.session_state["current_conversation_id"] = conv_id
    st.rerun()

def switch_conversation(conv_id):
    """Basculer vers une conversation existante"""
    st.session_state["current_conversation_id"] = conv_id
    st.rerun()

def delete_conversation(conv_id):
    """Supprimer une conversation"""
    if len(st.session_state["conversations"]) > 1:
        del st.session_state["conversations"][conv_id]
        if st.session_state["current_conversation_id"] == conv_id:
            st.session_state["current_conversation_id"] = list(st.session_state["conversations"].keys())[0]
        st.rerun()
    else:
        st.warning("Vous ne pouvez pas supprimer la dernière conversation.")

def get_conversation_title(messages):
    """Générer un titre basé sur le premier message"""
    if not messages:
        return "Nouvelle conversation"
    first_user_msg = next((m for m in messages if m["role"] == "user"), None)
    if first_user_msg:
        title = first_user_msg["content"][:50]
        return title + "..." if len(first_user_msg["content"]) > 50 else title
    return "Nouvelle conversation"

# =========================
# 🎯 SIDEBAR - HISTORIQUE
# =========================
# Charger l'image ENIG en base64 pour la sidebar
import base64
with open(ENIG_ICON_PATH, "rb") as img_file:
    enig_sidebar_base64 = base64.b64encode(img_file.read()).decode()

with st.sidebar:
    st.markdown(f"### <img src='data:image/png;base64,{enig_sidebar_base64}' style='width: 60px; height: 60px; vertical-align: middle; margin-right: 8px;'> GCRBot", unsafe_allow_html=True)
    
    if st.button("✏️ Nouvelle conversation", use_container_width=True, type="primary"):
        create_new_conversation()
    
    st.markdown("---")
    st.markdown("### 📚 Historique")
    
    sorted_convs = sorted(
        st.session_state["conversations"].values(),
        key=lambda x: x["created_at"],
        reverse=True
    )
    
    for conv in sorted_convs:
        is_active = conv["id"] == st.session_state["current_conversation_id"]
        title = get_conversation_title(conv["messages"])
        date_str = conv["created_at"].strftime("%d/%m/%Y %H:%M")
        icon = "💬" if not is_active else "📄"
        
        col1, col2 = st.columns([5, 1])
        with col1:
            if st.button(
                f"{icon} {title}",
                key=f"conv_{conv['id']}",
                use_container_width=True,
                help=date_str
            ):
                if not is_active:
                    switch_conversation(conv["id"])
        with col2:
            if len(st.session_state["conversations"]) > 1:
                if st.button("🗑️", key=f"del_{conv['id']}", help="Supprimer"):
                    delete_conversation(conv["id"])
    
    st.markdown("---")
    
    # =========================
    # 📄 SECTION UPLOAD DOCUMENTS
    # =========================
    st.markdown("### 📄 Documents")
    
    uploaded_file = st.file_uploader(
        "Ajouter un fichier",
        type=['pdf', 'docx', 'xlsx', 'txt'],
        help="Formats : PDF, Word, Excel, Texte",
        key="doc_uploader"
    )
    
    if uploaded_file is not None:
        # Sauvegarder le fichier dans docDB
        os.makedirs(DOC_DB_PATH, exist_ok=True)
        file_path = os.path.join(DOC_DB_PATH, uploaded_file.name)
        
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        # Traiter le document avec la fonction directe
        with st.spinner("📚 Indexation en cours..."):
            try:
                result = process_document_direct(file_path)
                if result.startswith("✅"):
                    st.success(f"✅ {uploaded_file.name} indexé avec succès!")
                    st.info(result)
                else:
                    st.error(result)
            except Exception as e:
                st.error(f"❌ Erreur: {str(e)}")
    
    # Afficher les documents indexés
    with st.expander("📚 Voir les documents indexés"):
        try:
            docs_list = list_documents_direct()
            st.text(docs_list)
        except Exception as e:
            st.text(f"Erreur: {str(e)}")
    
    st.markdown("---")
    st.markdown("""
    <div style='font-size: 0.8rem; color: #6b6b6b; padding: 1rem;'>
    <b>💡 Capacités :</b><br>
    📅 Emplois du temps<br>
    📚 Programmes ENIG<br>
    💼 Stages & Mitacs<br>
    📋 Procédures admin<br>
    📄 Analyse de documents
    </div>
    """, unsafe_allow_html=True)

# =========================
# 💬 ZONE DE CHAT PRINCIPALE
# =========================
current_conv = st.session_state["conversations"][st.session_state["current_conversation_id"]]

# Charger l'image ENIG en base64 pour le header
import base64
with open(ENIG_ICON_PATH, "rb") as img_file:
    enig_base64 = base64.b64encode(img_file.read()).decode()

st.markdown(f"""
<div class='main-header'>
    <h1><img src="data:image/png;base64,{enig_base64}" style="width: 80px; height: 80px; vertical-align: middle; margin-right: 12px;"> GCRBot</h1>
    <p>Votre assistant intelligent pour l'ENIG, stages et emplois du temps</p>
</div>
""", unsafe_allow_html=True)

if not current_conv["messages"]:
    # Message de bienvenue avec colonnes Streamlit natives
    st.markdown("""
    <div class='welcome-message'>
        <h2>👋 Bonjour cher GCRien !</h2>
        <p>Je suis GCRBot, votre assistant personnel pour tout ce qui concerne l'ENIG.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Grille de features avec colonnes Streamlit
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        <div class='feature-card'>
            <div class='feature-icon'>📅</div>
            <div class='feature-title'>Emplois du temps</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class='feature-card'>
            <div class='feature-icon'>💼</div>
            <div class='feature-title'>Stages & Mitacs</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class='feature-card'>
            <div class='feature-icon'>💬</div>
            <div class='feature-title'>Conversation & Motivation</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div class='feature-card'>
            <div class='feature-icon'>📄</div>
            <div class='feature-title'>Analyse de documents</div>
        </div>
        """, unsafe_allow_html=True)
else:
    chat_container = st.container()
    with chat_container:
        for msg in current_conv["messages"]:
            if msg["role"] == "user":
                st.markdown(f"""
                <div class='chat-message user'>
                    <div class='message-content'>{msg['content']}</div>
                    <div class='message-avatar'>👤</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class='chat-message bot'>
                    <div class='message-avatar'>🤖</div>
                    <div class='message-content'>{msg['content']}</div>
                </div>
                """, unsafe_allow_html=True)

# =========================
# 📝 INPUT UTILISATEUR
# =========================
user_input = st.chat_input("Posez votre question à GCRBot...")

if user_input:
    # Ajouter le message utilisateur
    current_conv["messages"].append({
        "role": "user",
        "content": user_input
    })
    
    # Appeler l'agent
    with st.spinner("🤔 GCRBot réfléchit..."):
        try:
            answer = answer_question(user_input)
        except Exception as e:
            answer = f"⚠️ Désolé, une erreur est survenue : `{str(e)}`"
    
    # Ajouter la réponse
    current_conv["messages"].append({
        "role": "bot",
        "content": answer
    })
    
    # Mettre à jour le titre si c'est le premier échange
    if len(current_conv["messages"]) == 2:
        current_conv["title"] = get_conversation_title(current_conv["messages"])
    
    st.rerun()
