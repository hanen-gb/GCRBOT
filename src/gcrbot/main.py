#!/usr/bin/env python
"""
GCRBOT - Système Multi-Agents pour l'ENIG
Architecture : Orchestrateur + Emplois + Stages + Conversation
Support Multi-Langue : Français, Anglais, Arabe
"""

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

import asyncio
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import warnings
import os
import re
from datetime import datetime
from dotenv import load_dotenv

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# Désactivation télémétrie
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_STORAGE_DIR"] = "./memory_storage"

from gcrbot.crew import GCRBotOrchestrator, detect_question_type, detect_language, get_language_name


def configure_gemini():
    """Configure et vérifie la clé Gemini"""
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("⚠️ Aucune clé Gemini trouvée dans .env")
    print("✅ Clé Gemini détectée")


def ensure_storage_dir():
    """Crée le dossier de stockage mémoire"""
    storage_dir = os.environ.get("CREWAI_STORAGE_DIR", "./memory_storage")
    os.makedirs(storage_dir, exist_ok=True)
    return storage_dir


# ═══════════════════════════════════════════════════════════════════════════════
# 🧠 MÉMOIRE CONTEXTUELLE AMÉLIORÉE
# ═══════════════════════════════════════════════════════════════════════════════
def extract_topic_from_history(conversation_history: list) -> str:
    """
    Extrait le sujet principal des derniers échanges.
    Cherche dans les questions ET réponses récentes.
    """
    if not conversation_history:
        return None
    
    # Sujets à détecter (entités importantes)
    known_topics = {
        # Programmes/Organisations
        'mitacs': 'Mitacs',
        'globalink': 'Globalink/Mitacs',
        'enig': 'ENIG',
        'enigplus': 'ENIGPlus',
        # Stages
        'pfe': 'PFE',
        'stage initiation': 'stage d\'initiation',
        'stage perfectionnement': 'stage de perfectionnement',
        # Emplois du temps
        'emploi du temps': 'emploi du temps',
        'gcr': 'GCR',
    }
    
    # Chercher dans les 3 derniers échanges (du plus récent au plus ancien)
    for turn in reversed(conversation_history[-3:]):
        user_q = turn.get('user', '').lower()
        agent_resp = turn.get('agent', '').lower()
        
        # Chercher dans la question utilisateur
        for keyword, topic_name in known_topics.items():
            if keyword in user_q:
                return topic_name
        
        # Chercher aussi dans la réponse de l'agent
        for keyword, topic_name in known_topics.items():
            if keyword in agent_resp:
                return topic_name
    
    return None


def needs_context(question: str) -> bool:
    """
    Détermine si la question nécessite un contexte.
    Retourne True si la question utilise des pronoms/références.
    """
    question_lower = question.lower()
    
    # Pronoms et références qui nécessitent un contexte
    context_indicators = [
        # Pronoms FR
        "qu'il", "qu'elle", "qu'ils", "qu'elles",
        "il offre", "elle offre", "ils offrent",
        "ses programmes", "ses services", "son site",
        "leur", "leurs",
        "ce programme", "cette organisation", "cet organisme",
        "y postuler", "s'y inscrire",
        # Pronoms EN  
        "it offers", "they offer", "its programs", "their",
        "this program", "this organization",
        # Questions sans sujet clair
        "quels sont les", "quelles sont les",
        "comment faire", "comment postuler",
        "c'est quand", "c'est où",
    ]
    
    for indicator in context_indicators:
        if indicator in question_lower:
            return True
    
    # Question très courte sans sujet = besoin de contexte
    words = question.split()
    if len(words) <= 5:
        # Vérifier s'il y a un sujet clair
        subjects = ['mitacs', 'enig', 'globalink', 'pfe', 'stage', 'emploi', 'gcr']
        has_subject = any(subj in question_lower for subj in subjects)
        if not has_subject:
            return True
    
    return False


def build_contextual_question(question: str, conversation_history: list) -> str:
    """
    Enrichit la question avec le contexte de la conversation.
    """
    if not conversation_history:
        return question
    
    question_lower = question.lower()
    
    # Sujets autonomes - la question contient déjà un sujet clair
    autonomous_subjects = [
        'mitacs', 'globalink', 'enig', 'enigplus', 'gcr',
        'emploi du temps', 'semaine', 'horaire',
        'stage', 'pfe', 'initiation', 'perfectionnement',
        'inscription', 'procédure',
        'bonjour', 'salut', 'hello', 'hi', 'مرحبا',
    ]
    
    for subject in autonomous_subjects:
        if subject in question_lower:
            # La question a déjà un sujet, pas besoin de contexte
            return question
    
    # Vérifier si la question nécessite un contexte
    if needs_context(question):
        topic = extract_topic_from_history(conversation_history)
        
        if topic:
            # Enrichir la question avec le contexte
            enriched = f"{question} (concernant {topic})"
            print(f"🧠 Contexte ajouté: '{topic}'")
            print(f"   Question enrichie: {enriched}")
            return enriched
    
    return question


def run():
    """Fonction principale avec orchestration multi-agents multi-langue."""
    configure_gemini()
    storage_dir = ensure_storage_dir()

    # Initialiser l'orchestrateur
    orchestrator = GCRBotOrchestrator()
    
    # Messages de bienvenue multi-langue
    print("\n" + "="*60)
    print("🤖 GCRBOT - Assistant Multi-Agents ENIG")
    print("="*60)
    print("   📅 Agent Emplois du Temps")
    print("   📋 Agent Stages & Procédures")
    print("   💬 Agent Conversation")
    print("-"*60)
    print("🌍 Langues supportées : Français | English | العربية")
    print("-"*60)
    print("💡 Tape 'exit' ou 'quit' pour quitter\n")

    conversation_history = []

    while True:
        try:
            question = input("👤 Vous : ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Au revoir ! / Goodbye! / مع السلامة!")
            break

        if not question:
            continue

        if question.lower() in ["exit", "quit"]:
            lang = orchestrator.current_language
            bye_msg = {
                'fr': "👋 Au revoir ! Bonne continuation !",
                'en': "👋 Goodbye! Good luck with your studies!",
                'ar': "👋 مع السلامة! بالتوفيق في دراستك!"
            }
            print(bye_msg.get(lang, bye_msg['fr']))
            break

        # Enrichir la question avec le contexte mémoire
        contextual_question = build_contextual_question(question, conversation_history)

        try:
            print("⏳ Traitement...\n")
            
            # Utiliser l'orchestrateur
            result = orchestrator.process_question(contextual_question)

            # Affichage de la réponse (sans Rich pour éviter les conflits)
            sep = "=" * 60
            print(f"\n{sep}")
            print("💬 Réponse")
            print(sep)
            print(str(result))
            print("")

            # Enregistrer dans l'historique (question originale + enrichie)
            conversation_history.append({
                "timestamp": datetime.now().isoformat(),
                "user": question,
                "contextual": contextual_question if contextual_question != question else None,
                "language": orchestrator.current_language,
                "type": detect_question_type(contextual_question),
                "agent": str(result)
            })
            
            # Limiter à 10 derniers échanges
            if len(conversation_history) > 10:
                conversation_history = conversation_history[-10:]

        except Exception as e:
            print(f"❌ Erreur : {e}")
            import traceback
            traceback.print_exc()

    # Sauvegarde finale
    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_file = os.path.join(storage_dir, f"session_{ts}.txt")
        
        import io
        content = io.StringIO()
        content.write("="*60 + "\n")
        content.write("SESSION HISTORY - GCRBOT Multi-Agents\n")
        content.write("="*60 + "\n")
        
        for i, turn in enumerate(conversation_history, 1):
            lang = turn.get('language', 'fr')
            qtype = turn.get('type', 'unknown')
            content.write(f"\n[{i}] {qtype.upper()} | {lang.upper()}\n")
            content.write(f"USER: {turn.get('user', '')}\n")
            if turn.get('contextual'):
                content.write(f"ENRICHED: {turn['contextual']}\n")
            content.write(f"AGENT: {turn.get('agent', '')[:200]}...\n")
        
        with open(session_file, "w", encoding="utf-8") as f:
            f.write(content.getvalue())
        
        print(f"💾 Historique sauvegardé : {session_file}")
    except Exception as e:
        print(f"⚠️ Erreur sauvegarde : {e}")


if __name__ == "__main__":
    run()
