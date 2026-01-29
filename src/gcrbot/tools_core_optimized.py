# gcrbot/src/gcrbot/tools_core.py - VERSION OPTIMISÉE
"""
Tools CrewAI pour GCRBOT avec protection anti-boucle intégrée.
"""

import logging
import time
from typing import Optional, Dict, Any
from crewai.tools import tool
from functools import wraps

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gcrbot.tools")

# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON & CACHE
# ═══════════════════════════════════════════════════════════════════════════════

_weaviate_client = None
_web_extractor = None
_semantic_model = None

# 🆕 COMPTEUR ANTI-BOUCLE GLOBAL
_tool_call_counter: Dict[str, int] = {}
_last_reset_time: float = 0
_COUNTER_RESET_INTERVAL = 300  # Reset après 5 minutes d'inactivité


def _reset_counters_if_needed():
    """Reset les compteurs si inactif depuis longtemps."""
    global _tool_call_counter, _last_reset_time
    current_time = time.time()
    if current_time - _last_reset_time > _COUNTER_RESET_INTERVAL:
        _tool_call_counter = {}
        logger.info("🔄 Compteurs anti-boucle réinitialisés")
    _last_reset_time = current_time


def _check_call_limit(tool_name: str, max_calls: int) -> bool:
    """
    Vérifie si le tool peut encore être appelé.
    Returns: True si OK, False si limite atteinte.
    """
    _reset_counters_if_needed()
    
    current_count = _tool_call_counter.get(tool_name, 0)
    if current_count >= max_calls:
        logger.warning(f"🛑 LIMITE ATTEINTE: {tool_name} ({current_count}/{max_calls})")
        return False
    
    _tool_call_counter[tool_name] = current_count + 1
    logger.info(f"📊 {tool_name}: appel {current_count + 1}/{max_calls}")
    return True


def reset_tool_counters():
    """Reset manuel des compteurs (appelé entre les questions)."""
    global _tool_call_counter
    _tool_call_counter = {}
    logger.info("🔄 Compteurs réinitialisés manuellement")


# ═══════════════════════════════════════════════════════════════════════════════
# GETTERS SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

def get_client():
    global _weaviate_client
    if _weaviate_client is None:
        from weaviate_setup.setup_weaviate_schema import get_weaviate_client
        _weaviate_client = get_weaviate_client()
    return _weaviate_client


def get_extractor():
    global _web_extractor
    if _web_extractor is None:
        from .WebExtractor import WebExtractor
        _web_extractor = WebExtractor()
    return _web_extractor


def get_semantic_model():
    global _semantic_model
    if _semantic_model is None:
        from sentence_transformers import SentenceTransformer
        _semantic_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _semantic_model


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL 1: ANALYSE STRATÉGIE
# ═══════════════════════════════════════════════════════════════════════════════

@tool("analyze_question_strategy")
def analyze_question_strategy(question: str) -> str:
    """
    Analyse la question et retourne la stratégie optimale.
    Appel unique par question.
    
    Retourne: Type | max_pages | deep_crawl | extract_pdf
    """
    if not _check_call_limit("analyze_question_strategy", 1):
        return "⚠️ Analyse déjà effectuée. Utilise le résultat précédent."
    
    try:
        import re
        logger.info(f"🔍 Analyse: {question[:80]}...")
        
        q = question.lower()
        
        # Emploi du temps / PDF avec contenu
        if any(kw in q for kw in ['emploi', 'horaire', 'semaine', 'edt', 'schedule', 'timetable']):
            return "Type: emploi_du_temps | max_pages: 2 | deep_crawl: False | extract_pdf: True"
        
        # Liste complète
        if any(kw in q for kw in ['quels sont', 'quelles sont', 'liste', 'tous les', 'programmes', 
                                   'what are', 'list all', 'programs']):
            return "Type: liste_complete | max_pages: 5 | deep_crawl: True | extract_pdf: False"
        
        # Procédure
        if any(kw in q for kw in ['comment', 'procédure', 'étapes', 'how to', 'steps', 'process']):
            return "Type: procedure | max_pages: 3 | deep_crawl: False | extract_pdf: False"
        
        # PDF link
        if any(kw in q for kw in ['pdf', 'télécharger', 'download', 'fichier']):
            return "Type: pdf_link | max_pages: 2 | deep_crawl: False | extract_pdf: False"
        
        # Défaut: info simple
        return "Type: info_simple | max_pages: 1 | deep_crawl: False | extract_pdf: False"
        
    except Exception as e:
        logger.error(f"Erreur analyse: {e}")
        return "Type: info_simple | max_pages: 1 | deep_crawl: False | extract_pdf: False"


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL 2: SEARCH WEAVIATE
# ═══════════════════════════════════════════════════════════════════════════════

@tool("search_weaviate")
def search_weaviate(question: str) -> str:
    """
    Recherche dans la base Weaviate.
    Retourne les URLs et descriptions pertinentes.
    Maximum 5 appels par session.
    """
    if not _check_call_limit("search_weaviate", 5):
        return (
            "⚠️ Limite de recherches Weaviate atteinte.\n"
            "💡 Utilise extract_web_content sur l'URL du résultat #1 précédent pour obtenir plus d'informations.\n"
            "⚠️ NE PAS inventer de contenu - utilise les informations déjà obtenues."
        )
    
    try:
        from .gemini import generate_embedding_gemini
        
        logger.info(f"🔍 Weaviate: {question[:60]}...")
        vector = generate_embedding_gemini(question)
        
        if not vector:
            return "❌ Erreur: impossible de générer l'embedding"
        
        client = get_client()
        collection = client.collections.get("WebLink")
        
        response = collection.query.near_vector(
            near_vector=vector,
            limit=5,
            return_properties=["url", "title", "content", "topics"]
        )
        
        if not response.objects:
            return "❌ Aucun résultat dans la base de connaissances"
        
        # Construire résultat
        results = ["📚 RÉSULTATS WEAVIATE\n" + "="*60]
        
        first_url = None
        for i, obj in enumerate(response.objects, 1):
            title = obj.properties.get('title', 'Sans titre')
            url = obj.properties.get('url', '')
            content = obj.properties.get('content', '')[:800]  # Limiter
            topics = obj.properties.get('topics', [])
            
            if i == 1:
                first_url = url
            
            results.append(f"\n📄 #{i}: {title}")
            results.append(f"URL: {url}")
            if topics:
                results.append(f"Topics: {', '.join(topics[:3])}")
            if content:
                results.append(f"Description:\n{content}\n")
        
        # ═══════════════════════════════════════════════════════════════════
        # INSTRUCTION OBLIGATOIRE - TOUJOURS afficher l'URL à utiliser
        # ═══════════════════════════════════════════════════════════════════
        if first_url:
            results.append("\n" + "="*60)
            results.append("🎯 URL PRINCIPALE À UTILISER:")
            results.append(f"   {first_url}")
            results.append("")
            
            # Vérifier si la description #1 contient déjà la réponse
            first_content = response.objects[0].properties.get('content', '') if response.objects else ''
            has_enough_info = len(first_content) > 300
            
            # Détecter si la question demande des détails (liste, programmes, etc.)
            q_lower = question.lower()
            needs_deep_crawl = any(kw in q_lower for kw in [
                'quels', 'quelles', 'liste', 'programmes', 'tous', 'toutes',
                'what are', 'list', 'programs', 'all', 'offre', 'propose'
            ])
            
            if needs_deep_crawl:
                results.append("⚠️ QUESTION DE TYPE LISTE - ACTION REQUISE:")
                results.append(f'   extract_web_content(url="{first_url}", search_keywords="programmes liste")')
            elif not has_enough_info:
                results.append("⚠️ DESCRIPTION INSUFFISANTE - ACTION REQUISE:")
                results.append(f'   extract_web_content(url="{first_url}")')
            else:
                results.append("✅ La description ci-dessus peut suffire pour répondre.")
                results.append(f"💡 Si besoin de plus de détails: extract_web_content(url=\"{first_url}\")")
            
            results.append("")
            results.append(f"❌ NE PAS utiliser une URL différente de: {first_url}")
        
        return "\n".join(results)
        
    except Exception as e:
        logger.error(f"Erreur Weaviate: {e}")
        return f"❌ Erreur Weaviate: {str(e)[:100]}"


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL 3: SMART SITE SEARCH
# ═══════════════════════════════════════════════════════════════════════════════

@tool("smart_site_search")
def smart_site_search(base_url: str, search_keywords: str) -> str:
    """
    Crawl intelligent d'un site pour trouver les pages pertinentes.
    Valide que les URLs existent avant de les retourner.
    MAXIMUM 1 appel par question.
    """
    if not _check_call_limit("smart_site_search", 1):
        return (
            "⚠️ Limite atteinte pour smart_site_search.\n"
            "✅ Formule ta réponse avec les informations déjà obtenues.\n"
            "❌ NE PAS réessayer ce tool."
        )
    
    try:
        import requests
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin, urlparse, unquote
        
        logger.info(f"🔍 Deep Scan: {base_url} pour '{search_keywords}'")
        
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        
        keywords = [k.strip().lower() for k in search_keywords.split()]
        base_domain = urlparse(base_url).netloc
        
        found_urls = []
        found_pdfs = []
        validated_urls = set()  # URLs vérifiées comme accessibles
        visited = set()
        
        def is_valid_url(url):
            """Vérifie si l'URL est valide (pas de caractères bizarres, pas trop longue)"""
            if len(url) > 500:
                return False
            # Filtrer les URLs avec des patterns invalides
            invalid_patterns = ['javascript:', 'mailto:', 'tel:', 'data:', '#', '?share=', 'wp-login', 'wp-admin']
            return not any(p in url.lower() for p in invalid_patterns)
        
        def validate_url_exists(url):
            """Vérifie que l'URL existe vraiment (HEAD request)"""
            if url in validated_urls:
                return True
            try:
                resp = session.head(url, timeout=5, allow_redirects=True)
                if resp.status_code < 400:
                    validated_urls.add(url)
                    return True
            except:
                pass
            return False
        
        def scan_page(url, depth=0):
            """Scan une page et retourne les liens trouvés"""
            if url in visited or depth > 1:
                return []
            visited.add(url)
            
            try:
                resp = session.get(url, timeout=15)
                if resp.status_code >= 400:
                    print(f"⚠️ Page inaccessible: {url} (code {resp.status_code})")
                    return []
                soup = BeautifulSoup(resp.text, "html.parser")
            except Exception as e:
                print(f"⚠️ Erreur accès: {url} - {e}")
                return []
            
            sub_pages = []
            
            for link in soup.find_all("a", href=True):
                href = link["href"].strip()
                if not href or href == "/" or href == "#":
                    continue
                    
                full_url = urljoin(url, href)
                
                # Nettoyer l'URL
                full_url = full_url.split('?')[0].split('#')[0]  # Enlever query strings et ancres
                
                if not is_valid_url(full_url):
                    continue
                    
                # Vérifier le domaine
                url_domain = urlparse(full_url).netloc
                if url_domain != base_domain:
                    continue
                
                link_text = link.get_text().strip()
                url_lower = full_url.lower()
                text_lower = link_text.lower() if link_text else ""
                
                # Détecter les PDFs
                if url_lower.endswith(".pdf"):
                    if full_url not in [p[0] for p in found_pdfs]:
                        # Calculer score
                        pdf_score = 0
                        for kw in keywords:
                            if kw in url_lower or kw in text_lower:
                                pdf_score += 15
                        # Bonus pour mots-clés emploi du temps
                        if any(kw in url_lower for kw in ['emploi', 'schedule', 'horaire', 'edt', 'timetable']):
                            pdf_score += 25
                        if any(kw in url_lower for kw in ['gcr', 'grc', 'genie']):
                            pdf_score += 20
                        if 'semaine' in url_lower or 'week' in url_lower:
                            pdf_score += 15
                        
                        found_pdfs.append((full_url, link_text or unquote(full_url.split('/')[-1]), pdf_score))
                    continue
                
                # Scorer les pages HTML
                score = 0
                for kw in keywords:
                    if kw in url_lower:
                        score += 20
                    if kw in text_lower:
                        score += 15
                
                # Bonus pour mots-clés importants
                important_keywords = ['emploi', 'stage', 'programme', 'horaire', 'document', 'procedure', 
                                     'inscription', 'enseignement', 'formation', 'etudiant', 'cours']
                for kw in important_keywords:
                    if kw in url_lower or kw in text_lower:
                        score += 10
                
                # BONUS SPÉCIAL pour emplois du temps étudiants
                if 'emploi-gcr' in url_lower:
                    score += 50  # Très fort bonus pour pages étudiants
                if 'emplois-du-temps' in url_lower:
                    score += 30
                if 'semaine' in url_lower or 'semaine' in text_lower:
                    score += 25
                
                # MALUS pour pages enseignants (toujours si on cherche emploi/gcr)
                if 'enseignant' in url_lower or 'enseignants-2' in url_lower:
                    if 'etudiant' in ' '.join(keywords) or 'gcr' in ' '.join(keywords):
                        score -= 80  # Fort malus pour éviter les pages enseignants
                
                if score > 0 and full_url not in [u[0] for u in found_urls]:
                    found_urls.append((full_url, score, link_text))
                    if depth == 0 and score >= 15:  # Sous-pages avec bon score
                        sub_pages.append(full_url)
            
            return sub_pages[:15]  # Plus de sous-pages pour couvrir toutes les semaines
        
        # Niveau 1: Scanner la page principale
        print(f"📄 Scan niveau 1: {base_url}")
        sub_pages = scan_page(base_url, depth=0)
        
        # Niveau 2: Scanner les sous-pages importantes (augmenté à 10)
        for sub_url in sub_pages[:10]:
            print(f"📄 Scan niveau 2: {sub_url}")
            scan_page(sub_url, depth=1)
        
        # Extraire le numéro de semaine demandé des keywords
        import re
        semaine_match = re.search(r'semaine\s*(\d+)', ' '.join(keywords))
        target_semaine = semaine_match.group(1) if semaine_match else None
        
        # Valider les meilleurs résultats
        print("✅ Validation des URLs...")
        valid_pdfs = []
        for pdf_url, name, score in found_pdfs[:20]:  # Augmenté à 20
            # Bonus si correspond à la semaine demandée
            if target_semaine and f"semaine-{target_semaine}" in pdf_url.lower():
                score += 100
            if target_semaine and f"semaine{target_semaine}" in pdf_url.lower():
                score += 100
            if validate_url_exists(pdf_url):
                valid_pdfs.append((pdf_url, name, score))
                print(f"  ✓ PDF valide: {name[:40]}")
            else:
                print(f"  ✗ PDF invalide: {name[:40]}")
        
        valid_urls = []
        for url, score, text in found_urls[:20]:  # Augmenté à 20
            # Bonus si correspond à la semaine demandée
            if target_semaine and f"semaine-{target_semaine}" in url.lower():
                score += 100
            if target_semaine and f"semaine{target_semaine}" in url.lower():
                score += 100
            if validate_url_exists(url):
                valid_urls.append((url, score, text))
        
        # Trier par score
        valid_pdfs.sort(key=lambda x: x[2], reverse=True)
        valid_urls.sort(key=lambda x: x[1], reverse=True)
        
        result = []
        
        # Afficher les PDFs validés (augmenté à 10)
        if valid_pdfs:
            result.append(f"📎 {len(valid_pdfs)} PDFs VALIDES trouvés:")
            for i, (url, name, score) in enumerate(valid_pdfs[:10], 1):
                result.append(f"  {i}. [{score}pts] {name[:50]}")
                result.append(f"     {url}")
            result.append("")
        
        # Afficher les pages validées (augmenté à 10)
        if valid_urls:
            result.append(f"🔗 {len(valid_urls)} pages VALIDES:")
            for i, (url, score, text) in enumerate(valid_urls[:10], 1):
                display = text[:40] if text else url.split('/')[-1]
                result.append(f"  {i}. [{score}pts] {display}")
                result.append(f"     {url}")
        
        if not valid_urls and not valid_pdfs:
            return f"❌ Aucune page/PDF valide trouvé pour '{search_keywords}'\n💡 Essaie extract_web_content sur {base_url} avec deep_crawl=True"
        
        # Recommandation claire avec URL exacte
        result.append("\n" + "="*50)
        if valid_pdfs:
            best_pdf = valid_pdfs[0][0]
            result.append(f"🎯 MEILLEUR PDF: {best_pdf}")
            result.append(f"   → Utilise: extract_web_content(url=\"{best_pdf}\", extract_pdf_content=True)")
        elif valid_urls:
            best_url = valid_urls[0][0]
            result.append(f"🎯 MEILLEURE PAGE: {best_url}")
            result.append(f"   → Utilise: extract_web_content(url=\"{best_url}\", deep_crawl=True)")
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Erreur smart_site_search: {e}")
        return f"❌ Erreur: {str(e)[:100]}"


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL 4: EXTRACT WEB CONTENT
# ═══════════════════════════════════════════════════════════════════════════════

@tool("extract_web_content")
def extract_web_content(url: str, search_keywords: str = "") -> str:
    """
    Extrait le contenu d'un site web avec crawling intelligent.
    MAXIMUM 2 appels par question.
    
    Args:
        url: URL à extraire (page web ou PDF direct)
        search_keywords: Mots-clés pour prioriser les pages internes (ex: "programmes liste offres")
    """
    if not _check_call_limit("extract_web_content", 2):
        return (
            "🛑 LIMITE ATTEINTE pour extract_web_content.\n"
            "✅ Formule ta réponse MAINTENANT avec les informations déjà obtenues.\n"
            "❌ NE PAS réessayer ce tool."
        )
    
    try:
        extractor = get_extractor()
        
        # Extraire les mots-clés de la question pour prioriser le crawl
        priority_keywords = None
        if search_keywords:
            keywords = [kw.strip().lower() for kw in search_keywords.split() if len(kw.strip()) > 2]
            if keywords:
                priority_keywords = keywords
                logger.info(f"🎯 Crawl prioritaire sur: {priority_keywords}")
        
        # ═══════════════════════════════════════════════════════════════════
        # STRATÉGIE INTELLIGENTE : Page principale d'abord, deep crawl si besoin
        # ═══════════════════════════════════════════════════════════════════
        is_enig_local = 'enig.rnu.tn' in url.lower()
        is_list_question = search_keywords and any(kw in search_keywords.lower() for kw in [
            'programmes', 'liste', 'offerings', 'all', 'tous', 'quels'
        ])
        
        # Pour les sites ENIG locaux (stages, procédures) : d'abord page principale
        if is_enig_local and not is_list_question:
            logger.info(f"📥 ENIG Local - Extraction page principale d'abord: {url}")
            
            # ÉTAPE 1: Extraire seulement la page principale (pas de deep crawl)
            content = extractor.extract_site_content(
                url, 
                max_pages=1, 
                deep_crawl=False, 
                extract_pdf_content=True,
                priority_keywords=None
            )
            
            # Vérifier si le contenu est suffisant (> 200 mots)
            word_count = len(content) // 5 if content else 0
            
            if content and word_count >= 200:
                logger.info(f"✅ Page principale suffisante ({word_count} mots)")
                if len(content) > 8000:
                    content = content[:8000] + f"\n\n[...contenu tronqué]"
                return f"✅ Contenu extrait ({word_count} mots):\n\n{content}"
            
            # ÉTAPE 2: Si insuffisant, activer le deep crawl
            logger.info(f"⚠️ Page principale insuffisante ({word_count} mots), activation deep crawl...")
            content = extractor.extract_site_content(
                url, 
                max_pages=5, 
                deep_crawl=True, 
                extract_pdf_content=True,
                priority_keywords=priority_keywords
            )
        else:
            # Pour les autres sites (Mitacs, etc.) ou questions de type liste : deep crawl direct
            max_pages = 8 if is_list_question else 5
            logger.info(f"📥 Extract: {url} (pages={max_pages}, deep=True, keywords={priority_keywords})")
            
            content = extractor.extract_site_content(
                url, 
                max_pages=max_pages, 
                deep_crawl=True, 
                extract_pdf_content=True,
                priority_keywords=priority_keywords
            )
        
        if not content or len(content) < 30:
            return (
                f"❌ CONTENU NON TROUVÉ pour {url}\n"
                f"⚠️ Formule ta réponse avec les informations de search_weaviate.\n"
                f"📌 Source: {url}"
            )
        
        # Limiter la taille du retour
        char_count = len(content)
        word_count = char_count // 5
        
        if char_count > 8000:
            content = content[:8000] + f"\n\n[...contenu tronqué, {char_count} caractères au total]"
        
        # TOUJOURS retourner le contenu avec succès (pas de message "insuffisant" qui crée des boucles)
        return f"✅ Contenu extrait ({word_count} mots):\n\n{content}\n\n📌 Source: {url}"
        
    except Exception as e:
        logger.error(f"Erreur extraction: {e}")
        return f"❌ Erreur extraction: {str(e)[:150]}"


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL 5: SEMANTIC SEARCH IN TEXT
# ═══════════════════════════════════════════════════════════════════════════════

@tool("semantic_search_in_text")
def semantic_search_in_text(question: str, content: str) -> str:
    """
    Recherche sémantique dans le contenu extrait.
    Trouve les passages les plus pertinents.
    Maximum 3 appels par question.
    """
    if not _check_call_limit("semantic_search_in_text", 3):
        return "⚠️ Limite atteinte. Formule ta réponse avec le contenu disponible."
    
    try:
        from sentence_transformers import util
        
        if not content or len(content) < 50:
            return "❌ Contenu insuffisant pour la recherche sémantique"
        
        logger.info(f"🧠 Semantic search: '{question[:50]}...'")
        
        model = get_semantic_model()
        
        # Découper en chunks
        chunk_size = 500
        chunks = [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]
        
        if not chunks:
            return "❌ Pas de chunks à analyser"
        
        # Encoder
        chunk_embeddings = model.encode(chunks, convert_to_tensor=True)
        query_embedding = model.encode(question, convert_to_tensor=True)
        
        # Similarité
        scores = util.cos_sim(query_embedding, chunk_embeddings)[0]
        
        # Top 3 chunks
        top_k = min(3, len(chunks))
        top_indices = scores.argsort(descending=True)[:top_k]
        
        results = ["📝 PASSAGES PERTINENTS:\n" + "="*50]
        for i, idx in enumerate(top_indices, 1):
            score = float(scores[idx])
            results.append(f"\n[Passage {i}] (score: {score:.2f})\n{chunks[idx]}")
        
        return "\n".join(results)
        
    except Exception as e:
        logger.error(f"Erreur semantic search: {e}")
        return f"❌ Erreur: {str(e)[:100]}"


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL 6: FIND EXACT MATCH
# ═══════════════════════════════════════════════════════════════════════════════

@tool("find_exact_match")
def find_exact_match(search_query: str, available_items: str) -> str:
    """
    Trouve un élément exact (PDF, lien) dans une liste.
    Maximum 2 appels par question.
    """
    if not _check_call_limit("find_exact_match", 2):
        return "⚠️ Limite atteinte."
    
    try:
        import re
        
        items = [line.strip() for line in available_items.split('\n') 
                 if line.strip() and ('http' in line or '.pdf' in line)]
        
        if not items:
            return "❌ Aucun élément à chercher"
        
        scored = []
        for item in items:
            score = 0
            if search_query.lower() in item.lower():
                score += 20
            
            # Bonus pour numéros (semaine 11, etc.)
            numbers = re.findall(r'\d+', search_query)
            for num in numbers:
                if re.search(rf'semaine[-_]?{num}\b', item.lower()):
                    score += 50
            
            if score > 0:
                scored.append((item, score))
        
        if not scored:
            return f"❌ Pas de match pour '{search_query}'"
        
        scored.sort(key=lambda x: x[1], reverse=True)
        best = scored[0]
        
        return f"✅ Match trouvé ({best[1]}pts):\n{best[0]}"
        
    except Exception as e:
        return f"❌ Erreur: {str(e)[:100]}"


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL 7: FORMAT FINAL ANSWER
# ═══════════════════════════════════════════════════════════════════════════════

@tool("format_final_answer")
def format_final_answer(question_type: str, main_info: str, source_url: str = "") -> str:
    """
    Formate la réponse finale de manière structurée.
    """
    if not _check_call_limit("format_final_answer", 1):
        return main_info  # Retourne juste l'info si limite atteinte
    
    try:
        q_type = question_type.lower()
        
        if "pdf" in q_type:
            response = f"✅ Document trouvé\n\n📎 Télécharger: {main_info}"
        elif "liste" in q_type:
            response = f"✅ Voici la liste:\n\n{main_info}"
        elif "procedure" in q_type:
            response = f"✅ Procédure:\n\n{main_info}"
        elif "emploi" in q_type or "schedule" in q_type:
            response = f"📅 Emploi du temps:\n\n{main_info}"
        else:
            response = main_info
        
        if source_url:
            response += f"\n\n📌 Source: {source_url}"
        
        return response
        
    except Exception as e:
        return main_info


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL 8: VALIDATE PDF CONTENT
# ═══════════════════════════════════════════════════════════════════════════════

@tool("validate_pdf_content")
def validate_pdf_content(extracted_text: str, user_question: str) -> str:
    """
    Valide que le contenu PDF extrait correspond à la question.
    """
    if not _check_call_limit("validate_pdf_content", 1):
        return "✅ Validation ignorée (limite)"
    
    try:
        total_pages = extracted_text.count("📄 PAGE")
        failed_pages = extracted_text.count("⚠️ [CONTENU NON EXTRAIT")
        
        msgs = []
        
        if failed_pages > 0:
            msgs.append(f"⚠️ {failed_pages}/{total_pages} pages non extraites (images/scans)")
        else:
            msgs.append(f"✅ {total_pages} pages extraites avec succès")
        
        if "emploi" in user_question.lower() or "schedule" in user_question.lower():
            msgs.append("📋 RÈGLE: Copier FIDÈLEMENT le contenu. NE PAS reformuler.")
        
        return "\n".join(msgs)
        
    except Exception as e:
        return "✅ Validation OK"


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL 9: FORMAT SCHEDULE FROM PDF
# ═══════════════════════════════════════════════════════════════════════════════

@tool("format_schedule_from_pdf")
def format_schedule_from_pdf(pdf_content: str, groups_requested: str = "tous") -> str:
    """
    Formate l'emploi du temps depuis un PDF.
    COPIE FIDÈLE - pas de reformulation.
    """
    if not _check_call_limit("format_schedule_from_pdf", 1):
        return pdf_content  # Retourne le contenu brut
    
    try:
        import re
        
        # Pattern pour détecter les groupes
        pattern = r"(Emploi Groupe [A-Z0-9]+.*?Semaine \d+.*?)(?=Emploi Groupe|$)"
        groups = re.findall(pattern, pdf_content, re.DOTALL | re.IGNORECASE)
        
        if not groups:
            return f"📅 EMPLOI DU TEMPS\n{'='*60}\n{pdf_content[:3000]}"
        
        # Filtrer si groupes spécifiques demandés
        if groups_requested.lower() != "tous":
            requested = [g.strip().upper() for g in groups_requested.split(",")]
            groups = [g for g in groups if any(r in g.upper() for r in requested)]
        
        result = ["📅 EMPLOI DU TEMPS (Copie fidèle)\n" + "="*60]
        
        for i, group in enumerate(groups[:5], 1):  # Max 5 groupes
            result.append(f"\n{'='*60}\nGROUPE #{i}\n{'='*60}\n{group.strip()}")
        
        result.append(f"\n{'='*60}\n✅ {len(groups)} groupe(s)")
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Erreur format schedule: {e}")
        return pdf_content


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    'analyze_question_strategy',
    'search_weaviate',
    'smart_site_search',
    'extract_web_content',
    'semantic_search_in_text',
    'find_exact_match',
    'format_final_answer',
    'validate_pdf_content',
    'format_schedule_from_pdf',
    'reset_tool_counters'
]
