# gcrbot/src/gcrbot/service.py
"""
Service layer pour connecter l'interface Streamlit au système multi-agents.
Utilise GCRBotOrchestrator pour router les questions vers le bon agent.
"""

import os
import sys
import logging
from datetime import datetime
from typing import Optional, Dict, Any

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gcrbot.service")

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION ENVIRONNEMENT (AVANT tout import CrewAI)
# ═══════════════════════════════════════════════════════════════════════════════

# Désactivation télémétrie CrewAI
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_STORAGE_DIR"] = "./memory_storage"

# Fix Windows event loop
if sys.platform == 'win32':
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Charger les variables d'environnement
from dotenv import load_dotenv
load_dotenv()

# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON ORCHESTRATEUR (évite réinitialisation à chaque requête)
# ═══════════════════════════════════════════════════════════════════════════════

_orchestrator = None
_initialization_error = None


def _initialize_orchestrator():
    """Initialise l'orchestrateur multi-agents une seule fois."""
    global _orchestrator, _initialization_error
    
    if _initialization_error:
        raise _initialization_error
    
    if _orchestrator is not None:
        return _orchestrator
    
    try:
        logger.info(" Initialisation de l'orchestrateur multi-agents...")
        
        # Ajouter le chemin src au path si nécessaire
        import sys
        src_path = os.path.join(os.path.dirname(__file__), '..')
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
        
        # Import après configuration environnement
        from gcrbot.crew import GCRBotOrchestrator
        
        _orchestrator = GCRBotOrchestrator()
        
        logger.info("✅ Orchestrateur initialisé avec succès")
        return _orchestrator
        
    except Exception as e:
        _initialization_error = e
        logger.error(f"❌ Erreur initialisation orchestrateur: {e}")
        raise


# ═══════════════════════════════════════════════════════════════════════════════
# FONCTION PRINCIPALE
# ═══════════════════════════════════════════════════════════════════════════════

def answer_question(question: str, timeout: int = 180) -> str:
    """
    Répond à une question en utilisant le système multi-agents.
    Route automatiquement vers l'agent approprié (Emploi, Stage, Conversation).
    
    Args:
        question: La question de l'utilisateur
        timeout: Timeout en secondes (défaut: 180s)
        
    Returns:
        Réponse de l'agent ou message d'erreur user-friendly
    """
    # Validation input
    if not question or not question.strip():
        return "👋 Pose-moi une question sur l'ENIG, les stages, Mitacs, emplois du temps, etc."
    
    question = question.strip()
    logger.info(f"📥 Question: {question[:100]}...")
    
    try:
        # Récupérer ou créer l'orchestrateur
        orchestrator = _initialize_orchestrator()
        
        # Exécuter via l'orchestrateur (route vers le bon agent)
        logger.info("⏳ Traitement en cours...")
        start_time = datetime.now()
        
        result = orchestrator.process_question(question)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"✅ Réponse générée en {elapsed:.1f}s")
        
        # Extraire la réponse
        if result is not None:
            response = result.raw if hasattr(result, 'raw') else str(result)
            
            # Nettoyer la réponse - enlever les logs de réflexion de l'agent
            response = _clean_agent_response(response)
            
            # Vérification qualité minimale
            if len(response) < 10:
                logger.warning("⚠️ Réponse trop courte")
                return "❌ Je n'ai pas pu trouver une réponse satisfaisante. Essaie de reformuler ta question."
            
            return response
        else:
            logger.warning("⚠️ Résultat vide")
            return "❌ Je n'ai pas trouvé de réponse. Essaie de reformuler ta question ou d'être plus précis."
            
    except Exception as e:
        return _handle_error(e)


def process_document(filepath: str, question: str = "") -> str:
    """
    Traite un document uploadé et/ou répond à une question dessus.
    
    Args:
        filepath: Chemin vers le fichier uploadé
        question: Question optionnelle sur le document
        
    Returns:
        Résultat du traitement ou réponse
    """
    if not filepath or not os.path.exists(filepath):
        return "❌ Fichier non trouvé."
    
    logger.info(f"📄 Traitement document: {os.path.basename(filepath)}")
    
    try:
        orchestrator = _initialize_orchestrator()
        
        start_time = datetime.now()
        result = orchestrator.process_document(filepath, question)
        elapsed = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"✅ Document traité en {elapsed:.1f}s")
        
        if result is not None:
            response = result.raw if hasattr(result, 'raw') else str(result)
            return response
        else:
            return "❌ Erreur lors du traitement du document."
            
    except Exception as e:
        return _handle_error(e)


def answer_document_question(question: str) -> str:
    """
    Répond à une question concernant les documents uploadés.
    
    Args:
        question: Question sur les documents indexés
        
    Returns:
        Réponse basée sur les documents
    """
    if not question or not question.strip():
        return "❌ Veuillez poser une question sur vos documents."
    
    logger.info(f"📚 Question document: {question[:100]}...")
    
    try:
        # Import direct du tool de recherche
        from gcrbot.tools_document import answer_from_document
        
        result = answer_from_document(question)
        return result
        
    except Exception as e:
        return _handle_error(e)


def _clean_agent_response(response: str) -> str:
    """
    Nettoie la réponse de l'agent en enlevant les logs de réflexion.
    Extrait seulement la réponse finale destinée à l'utilisateur.
    """
    import re
    
    if not response:
        return response
    
    # Patterns à supprimer (logs de réflexion de l'agent)
    patterns_to_remove = [
        # Pensées de l'agent en anglais
        r"The user has sent.*?(?=\n\n|\Z)",
        r"According to my instructions.*?(?=\n\n|\Z)",
        r"My goal is to.*?(?=\n\n|\Z)",
        r"My plan is to:.*?(?=\n\n|\Z)",
        r"I should also.*?(?=\n\n|\Z)",
        r"Therefore,.*?(?=\n\n|\Z)",
        r"Thought:.*?(?=\n|$)",
        r"Action:.*?(?=\n|$)",
        r"Action Input:.*?(?=\n|$)",
        r"Previous Action:.*?(?=\n|$)",
        # Réflexions de l'agent
        r"The previous.*?(?=\n\n|\Z)",
        r"Let's think about.*?(?=\n\n|\Z)",
        r"Let's make a decision.*?(?=\n\n|\Z)",
        r"The fact that.*?(?=\n\n|\Z)",
        r"This is not an answer.*?(?=\n\n|\Z)",
        r"This is a problem.*?(?=\n\n|\Z)",
        r"Perhaps I should.*?(?=\n\n|\Z)",
        r"What if I use.*?(?=\n\n|\Z)",
        r"I must use.*?(?=\n\n|\Z)",
        r"the final answer to the original input question.*?(?=\n\n|\Z)",
        # Labels de structure
        r"Greeting:.*?(?=\n|$)",
        r"Enthusiasm:.*?(?=\n|$)",
        r"Inquiry:.*?(?=\n|$)",
        r"Emoji:.*?(?=\n|$)",
        # Icônes de rôle au début
        r"^👤🤖",
        r"^🤖👤",
    ]
    
    cleaned = response
    
    for pattern in patterns_to_remove:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
    
    # Nettoyer les lignes vides multiples
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    
    # Supprimer les espaces en début/fin
    cleaned = cleaned.strip()
    
    # Si le nettoyage a trop supprimé, retourner l'original
    if len(cleaned) < 10 and len(response) > 10:
        # Essayer d'extraire juste après "Final Answer:" ou la dernière partie
        final_match = re.search(r'Final Answer:\s*(.*)', response, re.DOTALL | re.IGNORECASE)
        if final_match:
            cleaned = final_match.group(1).strip()
        else:
            # Prendre la dernière phrase significative
            lines = [l.strip() for l in response.split('\n') if l.strip() and not l.startswith(('Thought:', 'Action:', 'The user'))]
            if lines:
                cleaned = lines[-1]
    
    return cleaned if cleaned else response


def _handle_error(error: Exception) -> str:
    """Gère les erreurs et retourne un message user-friendly."""
    logger.error(f"❌ Erreur: {error}")
    
    error_msg = str(error).lower()
    
    # Erreurs de connexion
    if any(word in error_msg for word in ["weaviate", "connection", "connect", "refused"]):
        return (
            "❌ Erreur de connexion à la base de données.\n\n"
            "Vérifie que Weaviate est démarré:\n"
            "```\ndocker start weaviate\n```"
        )
    
    # Erreurs API
    if any(word in error_msg for word in ["api", "key", "quota", "rate limit", "401", "403"]):
        return (
            "❌ Erreur d'API (quota dépassé ou clé invalide).\n\n"
            "Vérifie ta clé GEMINI_API_KEY dans le fichier .env"
        )
    
    # Timeout
    if "timeout" in error_msg:
        return (
            "❌ La requête a pris trop de temps.\n\n"
            "Essaie une question plus simple ou réessaie dans quelques secondes."
        )
    
    # Erreur générique
    return f"❌ Une erreur est survenue. Réessaie dans quelques instants.\n\nDétail: {str(error)[:200]}"


# ═══════════════════════════════════════════════════════════════════════════════
# FONCTIONS UTILITAIRES
# ═══════════════════════════════════════════════════════════════════════════════

def health_check() -> Dict[str, Any]:
    """
    Vérifie l'état de tous les composants du système.
    
    Returns:
        Dict avec le statut de chaque composant
    """
    status = {
        "orchestrator": {"ok": False, "message": "Non initialisé"},
        "weaviate": {"ok": False, "message": "Non vérifié"},
        "gemini": {"ok": False, "message": "Non vérifié"},
        "timestamp": datetime.now().isoformat()
    }
    
    # Test Orchestrateur
    try:
        _initialize_orchestrator()
        status["orchestrator"] = {"ok": True, "message": "Initialisé (3 agents)"}
    except Exception as e:
        status["orchestrator"] = {"ok": False, "message": str(e)[:100]}
    
    # Test Weaviate
    try:
        import weaviate
        weaviate_url = os.getenv("WEAVIATE_URL", "http://localhost:8080")
        client = weaviate.Client(weaviate_url)
        if client.is_ready():
            status["weaviate"] = {"ok": True, "message": "Connecté"}
        else:
            status["weaviate"] = {"ok": False, "message": "Non prêt"}
    except Exception as e:
        status["weaviate"] = {"ok": False, "message": str(e)[:100]}
    
    # Test Gemini
    try:
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if api_key:
            status["gemini"] = {"ok": True, "message": "Clé API configurée"}
        else:
            status["gemini"] = {"ok": False, "message": "Clé API manquante"}
    except Exception as e:
        status["gemini"] = {"ok": False, "message": str(e)[:100]}
    
    return status


def reset_orchestrator():
    """Force la réinitialisation de l'orchestrateur (utile après une erreur)."""
    global _orchestrator, _initialization_error
    _orchestrator = None
    _initialization_error = None
    logger.info("🔄 Orchestrateur réinitialisé")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST LOCAL
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🧪 Test du service GCRBOT\n")
    
    # Health check
    print("📊 Health Check:")
    status = health_check()
    for component, info in status.items():
        if component != "timestamp":
            icon = "✅" if info.get("ok") else "❌"
            print(f"  {icon} {component}: {info.get('message', info)}")
    
    print("\n" + "="*50)
    
    # Test question
    test_question = "C'est quoi Mitacs?"
    print(f"\n💬 Question test: {test_question}")
    print("\n⏳ Traitement...\n")
    
    response = answer_question(test_question)
    print(f"📤 Réponse:\n{response}")
