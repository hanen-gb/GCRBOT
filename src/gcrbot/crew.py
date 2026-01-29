# gcrbot/src/gcrbot/crew.py
"""
Configuration du Crew CrewAI pour GCRBOT.
Architecture Multi-Agents : Orchestrateur + Emplois + Stages + Conversation
Support Multi-Langue : Français, Anglais, Arabe
"""

import os
import re
from crewai.project import CrewBase, agent, task, crew
from crewai import Agent, Task, Crew, Process

from .tools_core_optimized import (
    search_weaviate,
    smart_site_search,
    extract_web_content,
    semantic_search_in_text,
    reset_tool_counters
)

# Tool spécifique pour l'extraction des emplois du temps
from .tools_emploi import extract_emploi_page

# Tools pour l'agent Document
from .tools_document import (
    process_uploaded_document,
    search_in_documents,
    summarize_document,
    list_documents,
    answer_from_document
)


# ═══════════════════════════════════════════════════════════════════════════════
# DÉTECTION DE LANGUE
# ═══════════════════════════════════════════════════════════════════════════════
def detect_language(text: str) -> str:
    """Détecte la langue : 'fr', 'en', 'ar'"""
    text_lower = text.lower()
    
    # Caractères arabes
    if re.search(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+', text):
        return 'ar'
    
    # Mots-clés anglais
    english_words = ['i', 'you', 'the', 'is', 'are', 'hello', 'hi', 'how', 'what', 'where', 
                     'when', 'schedule', 'internship', 'student', 'help', 'need', 'want',
                     'please', 'thank', 'thanks', 'course', 'week', 'teacher']
    
    # Mots-clés français
    french_words = ['je', 'tu', 'le', 'la', 'est', 'sont', 'bonjour', 'salut', 'comment',
                    'quoi', 'où', 'quand', 'emploi', 'stage', 'étudiant', 'aide', 'besoin',
                    'merci', 'cours', 'semaine', 'professeur']
    
    en_count = sum(1 for w in english_words if f" {w} " in f" {text_lower} " or text_lower.startswith(w + " "))
    fr_count = sum(1 for w in french_words if f" {w} " in f" {text_lower} " or text_lower.startswith(w + " "))
    
    return 'en' if en_count > fr_count else 'fr'


def get_language_name(lang_code: str) -> str:
    return {'fr': 'Français', 'en': 'English', 'ar': 'العربية'}.get(lang_code, 'Français')


# ═══════════════════════════════════════════════════════════════════════════════
# DÉTECTION DU TYPE DE QUESTION (AMÉLIORÉE)
# ═══════════════════════════════════════════════════════════════════════════════
def detect_question_type(question: str) -> str:
    """
    Détecte : 'conversation', 'emploi', 'stage', ou 'document'
    
    PRIORITÉ : 
    1. D'abord vérifier si c'est une question sur les DOCUMENTS uploadés
    2. Ensuite vérifier s'il y a une DEMANDE D'INFORMATION (stage/emploi)
    3. Enfin vérifier si c'est une conversation pure
    """
    q = question.lower()
    
    # ═══════════════════════════════════════════════════════════════════════
    # ÉTAPE 0 : Vérifier DOCUMENTS UPLOADÉS (priorité maximale)//étape hors objectifs : amliorations
    # ═══════════════════════════════════════════════════════════════════════
    
    # Mots-clés indiquant une question sur les documents uploadés
    doc_keywords = [
        # Références explicites aux documents uploadés/téléchargés
        'fichier', 'fichiers', 'document uploadé', 'document ajouté',
        'le document', 'ce document', 'mon document', 'mes documents',
        'le fichier', 'ce fichier', 'mon fichier', 'mes fichiers',
        'uploaded', 'the file', 'the document', 'my document',
        'téléchargé', 'telechargé', 'telecharge', 'téléchargés', 'telechargés',
        'documents téléchargés', 'documents telechargés', 'fichiers téléchargés',
        'chargé', 'charge', 'charger',
        # Actions sur documents (avec variantes orthographiques)
        'résumé du', 'résumer', 'summarize', 'summary', 'resume le',
        'resume', 'resumé', 'resumer',  # variantes sans accents
        'reformulation', 'reformuler', 'reformule',
        'parle de quoi', 'about what', 'de quoi parle', 'autour de quoi',
        'contenu du', 'content of', 'dans le fichier', 'in the file',
        'cherche dans', 'search in', 'trouve dans', 'find in',
        'ce ocument', 'ce doc', 'sur ce doc',  # fautes de frappe courantes
        # Questions directes sur le contenu uploadé
        'selon le document', 'according to the document',
        'd\'après le fichier', 'based on the file',
        'le pdf', 'le word', 'le excel', 'the pdf',
        # Lister les documents
        'liste des documents', 'list documents', 'documents indexés',
        'quels documents', 'which documents',
        # Noms de fichiers courants
        '.pdf', '.docx', '.xlsx', '.txt',
    ]
    
    for kw in doc_keywords:
        if kw in q:
            return 'document'
    
    # Vérifier si des documents sont indexés ET la question semble les concerner
    try:
        from gcrbot.tools_document import has_indexed_documents, get_indexed_filenames
        if has_indexed_documents():
            filenames = get_indexed_filenames()
            # Si la question mentionne un nom de fichier indexé
            for filename in filenames:
                name_without_ext = filename.rsplit('.', 1)[0].lower()
                if name_without_ext in q or filename.lower() in q:
                    return 'document'
            
            # NOUVEAU: Si la question est une suite logique d'une conversation sur les documents
            # (résumé, détails, explique, etc. sans contexte spécifique)
            continuation_keywords = [
                'résumé', 'resume', 'détaillé', 'detaille', 'détails', 'details',
                'explique', 'explain', 'plus de détails', 'more details',
                'continue', 'suite', 'encore', 'autre', 'other',
                'chapitre', 'chapter', 'section', 'partie',
                'exercice', 'exercise', 'exemple', 'example',
                'quoi d\'autre', 'what else', 'et après', 'and then',
            ]
            
            for kw in continuation_keywords:
                if kw in q:
                    # C'est probablement une suite de la conversation sur les documents
                    return 'document'
    except:
        pass
    
    # ═══════════════════════════════════════════════════════════════════════
    # ÉTAPE 1 : Vérifier EMPLOIS DU TEMPS (priorité haute)
    # ═══════════════════════════════════════════════════════════════════════
    emploi_kw = [
        'emploi du temps', 'emplois du temps', 'edt', 
        'horaire', 'horaires', 'schedule', 'timetable',
        'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi',
        'monday', 'tuesday', 'wednesday', 'thursday', 'friday',
        'salle', 'salles', 'room', 'amphi',
        'disponibilité', 'disponible', 'available',
        'gcr1', 'gcr2', 'gcr3', 'groupe v',
        'جدول', 'توقيت', 'حصة'
    ]
    
    for kw in emploi_kw:
        if kw in q:
            return 'emploi'
    
    if re.search(r'semaine\s*\d+|week\s*\d+', q):
        return 'emploi'
    
    # ═══════════════════════════════════════════════════════════════════════
    # ÉTAPE 2 : Vérifier STAGES/PROCÉDURES (priorité haute)
    # ═══════════════════════════════════════════════════════════════════════
    stage_kw = [
        # Programmes
        'mitacs', 'mitcas', 'globalink', 
        # Stages
        'stage', 'stages', 'pfe', 'initiation', 'perfectionnement',
        'internship', 'تدريب',
        # Procédures
        'inscription', 'inscrire', 'procédure', 'procedure',
        'document', 'formulaire', 'convention',
        # Questions d'info
        "c'est quoi", "c quoi", "what is", "qu'est-ce que", "ما هو",
        'définition', 'definition', 'expliquer', 'explain',
        # Organisations
        'enig', 'université', 'university',
        # Listes
        'liste', 'programmes', 'programs', 'formations',
        # Localisation
        'où se trouve', 'where is', 'bureau', 'contact',
    ]
    
    for kw in stage_kw:
        if kw in q:
            return 'stage'
    
    # ═══════════════════════════════════════════════════════════════════════
    # ÉTAPE 3 : Vérifier si c'est une DEMANDE avec mots interrogatifs
    # ═══════════════════════════════════════════════════════════════════════
    # Si la phrase contient "je veux", "I want", "comment", "how to" + autre chose
    # C'est probablement une demande, pas juste de la conversation
    demand_indicators = [
        'je veux', 'je voudrais', 'je cherche', 'je souhaite',
        'i want', 'i need', 'i would like',
        'comment', 'how to', 'how do',
        'quels sont', 'quelles sont', 'what are',
        'peux-tu', 'can you', 'could you',
        'أريد', 'كيف',
    ]
    
    has_demand = any(ind in q for ind in demand_indicators)
    
    if has_demand:
        # C'est une demande - router vers stage par défaut (pas conversation)
        return 'stage'
    
    # ═══════════════════════════════════════════════════════════════════════
    # ÉTAPE 4 : Vérifier CONVERSATION (seulement si pas de demande)
    # ═══════════════════════════════════════════════════════════════════════
    # Conversation = salutations, humeur, humour, motivation, soutien
    
    # Salutations pures
    pure_greetings = ['bonjour', 'bonsoir', 'salut', 'coucou', 'hello', 'hi', 'hey',
                      'مرحبا', 'السلام عليكم', 'أهلا', 'yo', 'wesh', 'cava']
    
    # Au revoir
    goodbyes = ['au revoir', 'bye', 'goodbye', 'مع السلامة', 'à bientôt', 'a plus',
                'ciao', 'bonne nuit', 'good night']
    
    # Remerciements
    thanks_only = ['merci', 'thanks', 'thank you', 'شكرا', 'merci beaucoup']
    
    # Humeur/bien-être/émotions
    mood_kw = ['ça va', 'comment vas', 'how are', 'كيف حالك',
               'stressé', 'stress', 'fatigué', 'fatigue', 'épuisé', 'tired',
               'triste', 'sad', 'déprimé', 'depressed', 'anxieux', 'anxious',
               'démotivé', 'j\'en peux plus', 'je craque', 'je vais bien',
               'je me sens', 'i feel', 'i am fine', 'pas bien', 'mal',
               'nul', 'je suis nul', 'j\'arrive pas', 'j\'y arrive pas']
    
    # Humour / Détente
    humor_kw = ['blague', 'joke', 'rire', 'laugh', 'funny', 'drôle', 'humour',
                'raconte', 'tell me a joke', 'fais moi rire', 'marrant',
                'lol', 'mdr', 'haha', 'ptdr']
    
    # Motivation / Coaching
    motivation_kw = ['motivation', 'motivé', 'envie de rien', 'pas envie',
                     'j\'abandonne', 'je lâche', 'courage', 'encourage',
                     'conseil', 'advice', 'help me', 'aide moi', 'réviser',
                     'productif', 'productive', 'procrastine', 'procrastination']
    
    # Questions sur le bot
    bot_questions = ['qui es-tu', 'qui es tu', 'who are you', 'من أنت',
                     'tu es qui', 'what are you', 'ton nom', 'your name',
                     'tu fais quoi', 'what do you do', 'tes capacités']
    
    words = question.split()
    
    # Si c'est JUSTE une salutation (1-4 mots)
    if len(words) <= 4:
        for greet in pure_greetings + goodbyes + thanks_only:
            if greet in q:
                return 'conversation'
    
    # Si c'est une question sur l'humeur, le bot, l'humour ou la motivation
    for kw in mood_kw + bot_questions + humor_kw + motivation_kw:
        if kw in q:
            return 'conversation'
    
    # ═══════════════════════════════════════════════════════════════════════
    # ÉTAPE 5 : Par défaut → STAGE (le plus général)
    # ═══════════════════════════════════════════════════════════════════════
    return 'stage'


# ═══════════════════════════════════════════════════════════════════════════════
# CREW 1 : EMPLOIS DU TEMPS
# ═══════════════════════════════════════════════════════════════════════════════
@CrewBase
class EmploiCrew:
    agents_config = "config/agents_emploi.yaml"
    tasks_config = "config/tasks_emploi.yaml"

    @agent
    def emploi_agent(self) -> Agent:
        agent_cfg = self.agents_config.get("emploi_agent", {}) if isinstance(self.agents_config, dict) else {}
        return Agent(
            config=agent_cfg,
            # Tools: search_weaviate (partagé) + extract_emploi_page (spécifique pour PDFs)
            tools=[search_weaviate, extract_emploi_page],
            llm=agent_cfg.get("llm", os.getenv("MODEL", "gemini-2.5-flash-lite")),
            verbose=True, allow_delegation=False, max_iter=5, max_execution_time=120,
        )

    @task
    def emploi_task(self) -> Task:
        return Task(config=self.tasks_config['emploi_task'], agent=self.emploi_agent())

    @crew
    def crew(self) -> Crew:
        reset_tool_counters()
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True, memory=False)


# ═══════════════════════════════════════════════════════════════════════════════
# CREW 2 : STAGES & PROCÉDURES
# ═══════════════════════════════════════════════════════════════════════════════
@CrewBase
class StageCrew:
    agents_config = "config/agents_stage.yaml"
    tasks_config = "config/tasks_stage.yaml"

    @agent
    def stage_agent(self) -> Agent:
        agent_cfg = self.agents_config.get("stage_agent", {}) if isinstance(self.agents_config, dict) else {}
        return Agent(
            config=agent_cfg,
            tools=[search_weaviate, smart_site_search, extract_web_content, semantic_search_in_text],
            llm=agent_cfg.get("llm", os.getenv("MODEL", "gemini-2.5-flash-lite")),
            verbose=True, allow_delegation=False, max_iter=8, max_execution_time=300,
        )

    @task
    def stage_task(self) -> Task:
        return Task(config=self.tasks_config['stage_task'], agent=self.stage_agent())

    @crew
    def crew(self) -> Crew:
        reset_tool_counters()
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True, memory=False)


# ═══════════════════════════════════════════════════════════════════════════════
# CREW 3 : CONVERSATION
# ═══════════════════════════════════════════════════════════════════════════════
@CrewBase
class ConversationCrew:
    agents_config = "config/agents_conversation.yaml"
    tasks_config = "config/tasks_conversation.yaml"

    @agent
    def conversation_agent(self) -> Agent:
        agent_cfg = self.agents_config.get("conversation_agent", {}) if isinstance(self.agents_config, dict) else {}
        return Agent(
            config=agent_cfg,
            tools=[],  # Pas de tools pour la conversation
            llm=agent_cfg.get("llm", os.getenv("MODEL", "gemini-2.5-flash-lite")),
            verbose=True, allow_delegation=False, max_iter=3, max_execution_time=60,
        )

    @task
    def conversation_task(self) -> Task:
        return Task(config=self.tasks_config['conversation_task'], agent=self.conversation_agent())

    @crew
    def crew(self) -> Crew:
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True, memory=False)


# ═══════════════════════════════════════════════════════════════════════════════
# CREW 4 : DOCUMENT (Analyse de fichiers uploadés)
# ═══════════════════════════════════════════════════════════════════════════════
@CrewBase
class DocumentCrew:
    agents_config = "config/agents_document.yaml"
    tasks_config = "config/tasks_document.yaml"

    @agent
    def document_agent(self) -> Agent:
        agent_cfg = self.agents_config.get("document_agent", {}) if isinstance(self.agents_config, dict) else {}
        return Agent(
            config=agent_cfg,
            tools=[process_uploaded_document, search_in_documents, summarize_document, list_documents, answer_from_document],
            llm=agent_cfg.get("llm", os.getenv("MODEL", "gemini-2.5-flash-lite")),
            verbose=True, allow_delegation=False, max_iter=5, max_execution_time=120,
        )

    @task
    def document_task(self) -> Task:
        return Task(config=self.tasks_config['document_task'], agent=self.document_agent())

    @crew
    def crew(self) -> Crew:
        reset_tool_counters()
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True, memory=False)


# ═══════════════════════════════════════════════════════════════════════════════
# ORCHESTRATEUR PRINCIPAL (Multi-langue)
# ═══════════════════════════════════════════════════════════════════════════════
class GCRBotOrchestrator:
    """Orchestrateur avec détection de langue et routage intelligent."""
    
    def __init__(self):
        self.emploi_crew = None
        self.stage_crew = None
        self.conversation_crew = None
        self.document_crew = None
        self.current_language = 'fr'
        self.pending_document = None  # Pour stocker le chemin du document uploadé
        # Mémoire de contexte pour l'agent Document (historique des échanges)
        self.document_context = []  # Liste de {"role": "user/assistant", "content": "..."}
        self.max_context_history = 10  # Garder les 10 derniers échanges
    
    def set_pending_document(self, filepath: str):
        """Définit un document en attente de traitement."""
        self.pending_document = filepath
    
    def add_to_document_context(self, role: str, content: str):
        """Ajoute un échange à la mémoire de contexte des documents."""
        self.document_context.append({"role": role, "content": content[:500]})  # Limiter la taille
        # Garder seulement les N derniers échanges
        if len(self.document_context) > self.max_context_history * 2:
            self.document_context = self.document_context[-self.max_context_history * 2:]
    
    def get_document_context_string(self) -> str:
        """Retourne le contexte formaté pour l'agent."""
        if not self.document_context:
            return ""
        
        context_parts = ["\n📝 HISTORIQUE DES ÉCHANGES PRÉCÉDENTS SUR LES DOCUMENTS:"]
        context_parts.append("=" * 50)
        
        for exchange in self.document_context[-6:]:  # Derniers 6 échanges (3 Q/R)
            role_label = "👤 Utilisateur" if exchange["role"] == "user" else "🤖 Assistant"
            context_parts.append(f"{role_label}: {exchange['content']}")
        
        context_parts.append("=" * 50)
        context_parts.append("⚠️ Utilise ce contexte pour comprendre les références comme 'ce document', 'le fichier', etc.")
        
        return "\n".join(context_parts)
    
    def clear_document_context(self):
        """Efface le contexte des documents (nouvelle session)."""
        self.document_context = []
    
    def _get_crew(self, crew_type):
        if crew_type == 'emploi':
            if not self.emploi_crew: self.emploi_crew = EmploiCrew()
            return self.emploi_crew
        elif crew_type == 'stage':
            if not self.stage_crew: self.stage_crew = StageCrew()
            return self.stage_crew
        elif crew_type == 'document':
            if not self.document_crew: self.document_crew = DocumentCrew()
            return self.document_crew
        else:
            if not self.conversation_crew: self.conversation_crew = ConversationCrew()
            return self.conversation_crew
    
    def process_document(self, filepath: str, question: str = "") -> str:
        """Traite un document uploadé."""
        reset_tool_counters()
        
        # Si pas de question, juste indexer le document
        if not question or question.strip() == "":
            question = f"[DOCUMENT_UPLOAD:{filepath}] Traite et indexe ce nouveau document."
        else:
            question = f"[DOCUMENT:{filepath}] {question}"
        
        print(f"\n📄 Document : {os.path.basename(filepath)}")
        print(f"📚 → Agent DOCUMENT")
        
        crew = self._get_crew('document').crew()
        result = crew.kickoff(inputs={"question": question})
        
        return str(result)
    
    def process_question(self, question: str, is_document_query: bool = False) -> str:
        # IMPORTANT: Reset des compteurs avant chaque nouvelle question
        reset_tool_counters()
        
        # Détection langue et type
        self.current_language = detect_language(question)
        question_type = detect_question_type(question)
        
        # AMÉLIORATION: Si on a un contexte document récent et la question est ambiguë,
        # forcer le routing vers l'agent Document
        if question_type != 'document' and len(self.document_context) > 0:
            # Vérifier si la question semble être une continuation
            q_lower = question.lower()
            continuation_words = ['résumé', 'resume', 'détail', 'detail', 'explique', 
                                  'encore', 'autre', 'plus', 'suite', 'chapitre',
                                  'exercice', 'exemple', 'quoi', 'comment', 'pourquoi']
            
            # Si c'est une question courte avec des mots de continuation
            if len(question.split()) <= 10:
                for word in continuation_words:
                    if word in q_lower:
                        print(f"🔄 Contexte document actif → Rerouting vers DOCUMENT")
                        question_type = 'document'
                        break
        
        lang_name = get_language_name(self.current_language)
        
        # Labels
        emojis = {'conversation': '💬', 'emploi': '📅', 'stage': '📋', 'document': '📄'}
        labels = {
            'fr': {'conversation': 'CONVERSATION', 'emploi': 'EMPLOIS DU TEMPS', 'stage': 'STAGES', 'document': 'DOCUMENTS'},
            'en': {'conversation': 'CONVERSATION', 'emploi': 'TIMETABLES', 'stage': 'INTERNSHIPS', 'document': 'DOCUMENTS'},
            'ar': {'conversation': 'محادثة', 'emploi': 'جداول', 'stage': 'تدريب', 'document': 'وثائق'},
        }
        
        print(f"\n🌍 Langue : {lang_name}")
        print(f"🎯 Type : {labels.get(self.current_language, labels['fr']).get(question_type)}")
        print(f"{emojis[question_type]} → Agent {question_type.upper()}")
        
        # Instruction langue
        lang_inst = {'fr': "Réponds en français.", 'en': "Answer in English.", 'ar': "أجب بالعربية."}
        enriched = f"{question}\n\n[INSTRUCTION: {lang_inst.get(self.current_language, lang_inst['fr'])}]"
        
        # Pour l'agent Document, ajouter le contexte de mémoire
        if question_type == 'document':
            # Ajouter la question au contexte
            self.add_to_document_context("user", question)
            
            # Enrichir avec l'historique des échanges précédents
            context_str = self.get_document_context_string()
            if context_str:
                enriched = f"{enriched}\n{context_str}"
            
            print(f"📝 Contexte mémoire: {len(self.document_context)} échanges")
        
        # Exécution
        crew = self._get_crew(question_type).crew()
        result = crew.kickoff(inputs={"question": enriched, "language": self.current_language})
        
        result_str = str(result)
        
        # Pour l'agent Document, sauvegarder la réponse dans le contexte
        if question_type == 'document':
            # Limiter la taille de la réponse sauvegardée
            self.add_to_document_context("assistant", result_str[:500])
        
        return result_str


# Compatibilité 
class StageWebCrew(StageCrew):
    @task
    def stage_web_task(self) -> Task:
        return self.stage_task()
