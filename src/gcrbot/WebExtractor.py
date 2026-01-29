import os
import re
import mimetypes
import tempfile
from typing import List, Set, Optional

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

from pdfminer.high_level import extract_pages, extract_text
from pdfminer.layout import LAParams, LTTextContainer, LTChar, LTAnno, LTFigure


def _deduplicate_content(content: str) -> str:
    """
    Supprime les blocs strictement identiques qui apparaissent plusieurs fois.
    Simple mais suffisant pour éviter les répétitions massives.
    """
    seen = set()
    blocks = content.split("\n\n")
    unique_blocks = []
    for block in blocks:
        key = block.strip()
        if key and key not in seen:
            seen.add(key)
            unique_blocks.append(block)
    return "\n\n".join(unique_blocks)


class WebExtractor:
    """
    Extracteur web universel pour GCRBot.
    - Exploration HTML (page principale + pages internes)
    - Détection des PDFs
    - Extraction avancée du contenu PDF (optionnelle)
    - Priorisation par mots-clés selon le type de question
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; GCRBot/1.0; +https://gcrbot.ai)"
        })
        self.visited_urls: Set[str] = set()
        self.pdf_links: List[str] = []

    # ======================================================================
    # 🎯 MÉTHODE PRINCIPALE
    # ======================================================================
    def extract_site_content(
        self,
        url: str,
        max_pages: int = 10,
        deep_crawl: bool = True,
        extract_pdf_content: bool = False,
        priority_keywords: Optional[List[str]] = None,
    ) -> str:
        """
        🔍 MOTEUR DE RECHERCHE INTELLIGENT
        
        Stratégie:
        1. Scanner la page principale avec recherche sémantique
        2. Si match trouvé → Retourner immédiatement
        3. Sinon → Explorer les pages internes par score de pertinence
        4. Stopper dès qu'un bon match est trouvé
        
        Args:
            url: URL de départ
            max_pages: Nombre max de pages à explorer
            deep_crawl: Si True, explore les pages internes
            extract_pdf_content: Si True, extrait le contenu des PDFs
            priority_keywords: Mots-clés de la question utilisateur
        """
        self.visited_urls.clear()
        self.pdf_links.clear()
        
        # Construire la requête de recherche à partir des mots-clés
        search_query = " ".join(priority_keywords) if priority_keywords else ""
        
        print(f"🔍 Recherche: '{search_query}' sur {url}")
        
        # ══════════════════════════════════════════════════════════════════
        # ÉTAPE 1: Scanner la page principale
        # ══════════════════════════════════════════════════════════════════
        main_content = self._extract_single_page(url, extract_pdf_content)
        
        if main_content:
            match_score = self._semantic_match_score(main_content, search_query)
            print(f"📊 Page principale: score={match_score}")
            
            # Si bon match sur la page principale → Retour immédiat
            if match_score >= 60:
                print(f"✅ MATCH sur page principale (score={match_score})")
                return self._format_result(main_content, url, match_score)
        
        # ══════════════════════════════════════════════════════════════════
        # ÉTAPE 2: Explorer les pages internes (si deep_crawl activé)
        # ══════════════════════════════════════════════════════════════════
        if not deep_crawl:
            return self._format_result(main_content or "", url, 0)
        
        # Collecter tous les liens internes avec leurs scores de titre
        internal_links = self._get_scored_internal_links(url, search_query)
        
        if not internal_links:
            print("⚠️ Aucun lien interne trouvé")
            return self._format_result(main_content or "", url, 0)
        
        print(f"🔗 {len(internal_links)} pages internes à explorer")
        
        best_content = main_content or ""
        best_score = self._semantic_match_score(main_content, search_query) if main_content else 0
        best_url = url
        pages_explored = 1
        
        # Explorer les pages par ordre de score décroissant
        for page_url, title_score in internal_links[:max_pages]:
            if page_url in self.visited_urls:
                continue
            
            pages_explored += 1
            page_name = page_url.split('/')[-1][:30] or page_url.split('/')[-2][:30]
            print(f"🔗 [{pages_explored}/{max_pages}] {page_name} (titre={title_score})")
            
            page_content = self._extract_single_page(page_url, extract_pdf_content)
            
            if not page_content:
                continue
            
            # Scorer le contenu de cette page
            content_score = self._semantic_match_score(page_content, search_query)
            total_score = (title_score + content_score) // 2
            
            print(f"   📊 contenu={content_score}, total={total_score}")
            
            # Mettre à jour le meilleur résultat
            if total_score > best_score:
                best_score = total_score
                best_content = page_content
                best_url = page_url
            
            # ⚡ STOP INTELLIGENT: Bon match trouvé
            if total_score >= 70:
                print(f"🎯 MATCH TROUVÉ! score={total_score}, arrêt")
                return self._format_result(best_content, best_url, best_score)
            
            # Si on a déjà un score acceptable et exploré plusieurs pages, arrêter
            if best_score >= 50 and pages_explored >= 4:
                print(f"✅ Score acceptable ({best_score}), arrêt après {pages_explored} pages")
                break
        
        # ══════════════════════════════════════════════════════════════════
        # ÉTAPE 3: Retourner le meilleur résultat trouvé
        # ══════════════════════════════════════════════════════════════════
        print(f"✅ Fin: {pages_explored} pages, meilleur score={best_score}")
        return self._format_result(best_content, best_url, best_score)
    
    def _semantic_match_score(self, content: str, query: str) -> int:
        """
        Calcule un score de match sémantique entre le contenu et la requête.
        Score de 0 à 100.
        """
        if not content or not query:
            return 20 if content and len(content) > 200 else 0
        
        content_lower = content.lower()
        query_lower = query.lower()
        query_words = [w.strip() for w in query_lower.split() if len(w.strip()) > 2]
        
        if not query_words:
            return 20 if len(content) > 200 else 0
        
        score = 0
        matched_words = 0
        
        # Score par mot-clé trouvé
        for word in query_words:
            count = content_lower.count(word)
            if count > 0:
                matched_words += 1
                score += min(count * 8, 25)  # Max 25 points par mot
        
        # Bonus pour le ratio de mots matchés
        match_ratio = matched_words / len(query_words)
        score += int(match_ratio * 30)  # Max 30 points
        
        # Bonus pour contenu riche
        if len(content) >= 500:
            score += 10
        elif len(content) >= 200:
            score += 5
        
        return min(score, 100)
    
    def _get_scored_internal_links(self, base_url: str, query: str) -> List[tuple]:
        """
        Récupère les liens internes et les score par pertinence du titre/URL.
        Retourne: [(url, score), ...] trié par score décroissant
        """
        try:
            resp = self.session.get(base_url, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            print(f"❌ Erreur récupération liens: {e}")
            return []
        
        base_domain = urlparse(base_url).netloc
        query_words = [w.lower() for w in query.split() if len(w) > 2]
        
        scored_links = []
        seen_urls = set()
        
        for link in soup.find_all("a", href=True):
            href = link["href"].strip()
            if href.startswith("#") or href.startswith("mailto:") or href.startswith("javascript:"):
                continue
            
            full_url = urljoin(base_url, href)
            
            # Même domaine seulement
            if urlparse(full_url).netloc != base_domain:
                continue
            
            clean_url = full_url.split("#")[0].split("?")[0]
            
            if clean_url in seen_urls or clean_url == base_url:
                continue
            seen_urls.add(clean_url)
            
            # Exclure les pages non pertinentes
            url_lower = clean_url.lower()
            if any(x in url_lower for x in ['login', 'contact', 'privacy', 'cookie', 'footer']):
                continue
            
            # Scorer par le titre du lien et l'URL
            link_text = link.get_text().strip().lower()
            url_path = url_lower.split('/')[-1] if '/' in url_lower else url_lower
            combined = f"{link_text} {url_path}"
            
            score = 0
            for word in query_words:
                if word in combined:
                    score += 30
                if word in url_path:
                    score += 20  # Bonus si dans l'URL
            
            # Bonus pour mots-clés importants
            important_words = ['programme', 'stage', 'internship', 'procedure', 'list', 'all', 'nos-']
            for iw in important_words:
                if iw in combined:
                    score += 10
            
            if score > 0:
                scored_links.append((clean_url, score))
        
        # Trier par score décroissant
        scored_links.sort(key=lambda x: x[1], reverse=True)
        
        if scored_links:
            print(f"🏆 Top liens: {[(u.split('/')[-1][:20], s) for u, s in scored_links[:3]]}")
        
        return scored_links
    
    def _format_result(self, content: str, url: str, score: int) -> str:
        """Formate le résultat final - propre et sans doublons."""
        if not content:
            return f"❌ Aucun contenu trouvé\n📌 URL: {url}"
        
        # Nettoyer et dédupliquer le contenu
        content = self._clean_content(content)
        
        # Limiter la taille
        if len(content) > 6000:
            content = content[:6000] + "\n\n[...contenu tronqué]"
        
        # Format propre
        result = f"{content}\n\n📌 Source: {url}"
        
        # Ajouter les PDFs si disponibles (sans doublons)
        if self.pdf_links:
            unique_pdfs = list(dict.fromkeys(self.pdf_links))[:3]
            if unique_pdfs:
                result += f"\n📎 PDFs: {', '.join([os.path.basename(p) for p in unique_pdfs])}"
        
        return result
    
    def _clean_content(self, content: str) -> str:
        """Nettoie le contenu: supprime doublons, lignes vides excessives, sources répétées."""
        if not content:
            return ""
        
        # Supprimer les lignes "📌 Source:" en double dans le contenu
        lines = content.split('\n')
        cleaned_lines = []
        seen_lines = set()
        last_was_empty = False
        
        for line in lines:
            line_stripped = line.strip()
            
            # Ignorer les lignes de source répétées (on ajoutera une seule à la fin)
            if line_stripped.startswith('📌 Source:'):
                continue
            
            # Ignorer les lignes "=== RÉSULTAT" ou "=== CONTENU"
            if line_stripped.startswith('==='):
                continue
            
            # Éviter les lignes vides consécutives
            if not line_stripped:
                if last_was_empty:
                    continue
                last_was_empty = True
            else:
                last_was_empty = False
            
            # Éviter les doublons de contenu (paragraphes identiques)
            if len(line_stripped) > 50:
                # Utiliser les premiers 100 caractères comme clé
                key = line_stripped[:100].lower()
                if key in seen_lines:
                    continue
                seen_lines.add(key)
            
            cleaned_lines.append(line)
        
        # Rejoindre et nettoyer
        result = '\n'.join(cleaned_lines)
        
        # Supprimer les espaces multiples
        while '\n\n\n' in result:
            result = result.replace('\n\n\n', '\n\n')
        
        return result.strip()

    # ======================================================================
    # 🌐 EXTRACTION D’UNE SEULE PAGE
    # ======================================================================
    def _extract_single_page(self, url: str, extract_pdf_content: bool = False) -> str:
        """Extrait le contenu d'une seule page (HTML ou PDF)."""
        if url in self.visited_urls:
            return ""

        self.visited_urls.add(url)

        try:
            resp = self.session.get(url, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"❌ Erreur: {url} - {e}")
            return ""

        content_type = resp.headers.get("Content-Type", "").lower()

        # ---- Cas PDF direct
        if "pdf" in content_type or url.lower().endswith(".pdf"):
            if url not in self.pdf_links:
                self.pdf_links.append(url)
                print(f"📥 PDF trouvé: {os.path.basename(url)}")

            if extract_pdf_content:
                return self._extract_pdf_from_url_advanced(url)
            else:
                return f"[PDF détecté : {os.path.basename(url)}]"

        # ---- Cas HTML
        soup = BeautifulSoup(resp.text, "html.parser")
        text = self._extract_text(soup)

        # Chercher TOUS les liens PDF (méthode améliorée)
        file_links = self._extract_file_links(soup, base_url=url)
        
        # Chercher aussi les liens PDF dans les attributs href et src
        for tag in soup.find_all(['a', 'embed', 'iframe', 'object']):
            href = tag.get('href') or tag.get('src') or tag.get('data')
            if href and '.pdf' in href.lower():
                full_url = urljoin(url, href)
                if full_url not in file_links:
                    file_links.append(full_url)
                    print(f"🔍 PDF trouvé (attribut): {full_url}")
        
        pdf_contents = []
        pdf_extracted_count = 0
        MAX_PDF_EXTRACT = 3
        
        print(f"📎 {len(file_links)} fichiers détectés, extract_pdf_content={extract_pdf_content}")
        
        for link in file_links:
            if link.lower().endswith(".pdf") and link not in self.pdf_links:
                self.pdf_links.append(link)
                print(f"📎 PDF détecté: {os.path.basename(link)}")
                
                # EXTRACTION AUTOMATIQUE DU CONTENU PDF si demandé
                if extract_pdf_content and pdf_extracted_count < MAX_PDF_EXTRACT:
                    print(f"📥 Extraction PDF ({pdf_extracted_count+1}/{MAX_PDF_EXTRACT}): {os.path.basename(link)}")
                    try:
                        pdf_content = self._extract_pdf_from_url_advanced(link)
                        if pdf_content and "❌" not in pdf_content and len(pdf_content) > 100:
                            pdf_contents.append(pdf_content)
                            pdf_extracted_count += 1
                            print(f"✅ PDF extrait: {len(pdf_content)} caractères")
                        else:
                            print(f"⚠️ PDF vide ou erreur: {link}")
                    except Exception as e:
                        print(f"❌ Erreur extraction PDF {link}: {e}")

        # Ajouter le contenu des PDFs au texte de la page
        if pdf_contents:
            text += "\n\n" + "="*60 + "\n"
            text += "📄 CONTENU DES PDFs EXTRAITS\n"
            text += "="*60 + "\n\n"
            text += "\n\n".join(pdf_contents)
        elif extract_pdf_content and self.pdf_links:
            # Si on n'a pas pu extraire mais on a des liens
            text += "\n\n" + "="*60 + "\n"
            text += "📎 LIENS PDF DISPONIBLES (contenu non extrait)\n"
            text += "="*60 + "\n"
            for pdf_link in self.pdf_links:
                text += f"📎 {pdf_link}\n"

        return text

    # ======================================================================
    # 🔍 DÉTECTION DES PAGES INTERNES IMPORTANTES
    # ======================================================================
    def _find_important_internal_pages(
        self,
        base_url: str,
        priority_keywords: Optional[List[str]] = None
    ) -> List[str]:
        """
        Trouve les pages internes "intéressantes" à explorer.
        AMÉLIORATION: Score les pages par pertinence et trie par score décroissant.

        - Si priority_keywords est fourni : on les priorise fortement
        - Sinon : on utilise un set de mots-clés génériques (emploi, programme, stage...)
        """
        try:
            resp = self.session.get(base_url, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
        except Exception:
            return []

        if priority_keywords:
            print(f"🎯 Recherche ciblée sur : {', '.join(priority_keywords)}")
            target_keywords = [kw.lower() for kw in priority_keywords]
        else:
            print("🌍 Recherche universelle (tous mots-clés)")
            target_keywords = [
                # Emplois du temps
                "emploi", "schedule", "horaire", "semaine", "week", "timetable",
                # Programmes / formations
                "programme", "programs", "offerings", "resources", "formation",
                "courses", "training", "opportunities", "modules",
                # Stages
                "stage", "intern", "opportunit", "bourse", "scholarship",
                # Actualités
                "actualit", "news", "event", "annonce",
                # Documents
                "pdf", "document", "téléchar", "download",
                # Mots spécifiques
                "gcr", "globalink", "mitacs",
            ]

        # Structure pour scorer les pages: {url: score}
        scored_links: dict = {}
        base_domain = urlparse(base_url).netloc

        # Mots-clés à exclure (pages non pertinentes)
        exclude_keywords = [
            "contact", "login", "connexion", "privacy", "cookie", "legal", 
            "mentions", "cgu", "cgv", "footer", "header", "sidebar",
            "nous-contacter", "nous-joindre", "connecter", "inscription"
        ]

        for link in soup.find_all("a", href=True):
            href = link["href"].strip()
            if href.startswith("#") or href.startswith("mailto:") or href.startswith("javascript:"):
                continue

            full_url = urljoin(base_url, href)
            if urlparse(full_url).netloc != base_domain:
                continue

            clean_url = full_url.split("#")[0].split("?")[0]
            
            # Eviter les doublons avec la page de base
            if clean_url == base_url or clean_url in self.visited_urls:
                continue
            
            url_lower = clean_url.lower()
            link_text = link.get_text().strip().lower()
            combined_text = f"{url_lower} {link_text}"

            # Exclure les pages non pertinentes
            if any(excl in url_lower for excl in exclude_keywords):
                continue

            # Calculer le score de pertinence
            score = 0
            matched_keywords = []
            
            for kw in target_keywords:
                if kw in url_lower:
                    score += 10  # Fort bonus si dans l'URL
                    matched_keywords.append(f"url:{kw}")
                if kw in link_text:
                    score += 5   # Bonus si dans le texte du lien
                    matched_keywords.append(f"text:{kw}")
            
            # Bonus pour les pages "nos-programmes", "all-programs", "liste"
            high_value_patterns = [
                "nos-programme", "our-program", "all-program", "liste",
                "catalogue", "catalog", "offres", "offerings", "tous-les",
                "toutes-les", "discover", "explore", "overview"
            ]
            for pattern in high_value_patterns:
                if pattern in url_lower or pattern in link_text:
                    score += 15  # Très fort bonus
                    matched_keywords.append(f"high:{pattern}")
            
            # Bonus pour les liens avec des chiffres (pages de détail)
            if re.search(r"/\w+-?\d+/?", clean_url, re.I):
                score += 2

            if score > 0 and clean_url not in scored_links:
                scored_links[clean_url] = score
                if matched_keywords:
                    print(f"🎯 Score {score}: {clean_url} ({', '.join(matched_keywords[:3])})")

        # Trier par score décroissant
        sorted_links = sorted(scored_links.items(), key=lambda x: x[1], reverse=True)
        
        # Retourner les URLs triées (maximum 30)
        final_links = [url for url, score in sorted_links[:30]]
        
        if final_links:
            print(f"📊 Top 5 pages: {[f'{url.split('/')[-2] if url.endswith('/') else url.split('/')[-1]}({scored_links[url]})' for url in final_links[:5]]}")
        
        return final_links

    # ======================================================================
    # 📄 EXTRACTION PDF AVANCÉE - 
    # ======================================================================
    def _extract_pdf_from_url_advanced(self, url: str) -> str:
        """
        EXTRACTION PDF COMPLÈTE - Multi-stratégie
        
        Stratégie 1: Extraction avec LAParams optimisés pour tableaux
        Stratégie 2: Extraction texte brut si stratégie 1 échoue
        Stratégie 3: Extraction élément par élément pour contenu fragmenté
        """
        try:
            print(f"📥 Téléchargement PDF : {url}")
            
            # Headers pour éviter les blocages
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/pdf,*/*',
                'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
            }
            
            resp = self.session.get(url, timeout=60, headers=headers)
            print(f"📥 Status: {resp.status_code}, Content-Type: {resp.headers.get('Content-Type', 'unknown')}")
            resp.raise_for_status()
            
            # Vérifier que c'est bien un PDF
            content_type = resp.headers.get('Content-Type', '').lower()
            if 'pdf' not in content_type and not url.lower().endswith('.pdf'):
                print(f"⚠️ Le contenu n'est pas un PDF: {content_type}")
                return f"❌ [Le lien ne pointe pas vers un PDF: {content_type}]"
            
            print(f"📥 Taille du PDF: {len(resp.content)} bytes")

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(resp.content)
                tmp_path = tmp_file.name
                print(f"📥 PDF sauvegardé: {tmp_path}")

            # Stratégie 1: LAParams optimisés pour emplois du temps / tableaux
            print("🔄 Stratégie 1: Extraction structurée...")
            pages_content = self._extract_pdf_strategy1(tmp_path)
            
            # Si peu de contenu, essayer stratégie 2
            total_chars = sum(len(p) for p in pages_content)
            if total_chars < 200:
                print("⚠️ Peu de contenu avec stratégie 1, essai stratégie 2...")
                pages_content = self._extract_pdf_strategy2(tmp_path)
            
            # Si toujours peu de contenu, essayer stratégie 3
            total_chars = sum(len(p) for p in pages_content)
            if total_chars < 200:
                print("⚠️ Peu de contenu avec stratégie 2, essai stratégie 3...")
                pages_content = self._extract_pdf_strategy3(tmp_path)

            os.remove(tmp_path)

            if not pages_content or all(len(p.strip()) < 20 for p in pages_content):
                return f"❌ [PDF détecté mais contenu non extractible (peut-être scanné/image) : {os.path.basename(url)}]\n📎 Lien direct: {url}"

            total_pages = len(pages_content)
            result = (
                f"📖 DOCUMENT PDF : {os.path.basename(url)}\n"
                f"📊 Nombre de pages : {total_pages}\n"
                f"📎 Lien direct: {url}\n\n"
                + "\n\n".join(pages_content)
                + f"\n\n{'='*60}\n"
                f"✅ FIN DU DOCUMENT ({total_pages} pages)\n"
                f"{'='*60}\n"
            )
            print(f"✅ Extraction PDF terminée : {total_pages} pages, {total_chars} caractères")
            return result

        except Exception as e:
            print(f"❌ Erreur extraction PDF {url}: {e}")
            return f"❌ [PDF détecté mais extraction impossible : {os.path.basename(url)}]\n📎 Lien direct: {url}"

    def _extract_pdf_strategy1(self, tmp_path: str) -> List[str]:
        """
        Stratégie 1: Extraction optimisée pour EMPLOIS DU TEMPS
        - Détecte la structure en tableau (lignes/colonnes)
        - Organise par JOUR et par HORAIRE
        - Garde toutes les cellules même vides
        """
        laparams = LAParams(
            line_margin=0.3,
            word_margin=0.1,
            char_margin=1.0,
            boxes_flow=None,  # Préserver l'ordre visuel
            detect_vertical=True,
            all_texts=True,
        )
        
        pages_content: List[str] = []
        page_num = 1
        
        # Jours de la semaine pour détection
        jours = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche',
                 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        
        for page_layout in extract_pages(tmp_path, laparams=laparams):
            # Collecter tous les éléments avec leurs positions
            elements = []
            for element in page_layout:
                if isinstance(element, LTTextContainer):
                    text = element.get_text().strip()
                    if text:
                        x0 = element.x0 if hasattr(element, 'x0') else 0
                        y0 = element.y0 if hasattr(element, 'y0') else 0
                        x1 = element.x1 if hasattr(element, 'x1') else x0 + 50
                        y1 = element.y1 if hasattr(element, 'y1') else y0 + 10
                        elements.append({
                            'text': text,
                            'x0': x0, 'y0': y0,
                            'x1': x1, 'y1': y1,
                            'center_y': (y0 + y1) / 2,
                            'center_x': (x0 + x1) / 2
                        })
            
            if not elements:
                pages_content.append(
                    f"{'='*60}\n📄 PAGE {page_num}\n{'='*60}\n⚠️ [Page vide ou image]\n"
                )
                page_num += 1
                continue
            
            # Regrouper par lignes (même position Y approximative)
            elements.sort(key=lambda e: -e['center_y'])  # Haut vers bas
            
            rows = []
            current_row = []
            last_y = None
            row_threshold = 8  # Tolérance pour considérer même ligne
            
            for elem in elements:
                if last_y is None or abs(elem['center_y'] - last_y) < row_threshold:
                    current_row.append(elem)
                    last_y = elem['center_y'] if last_y is None else (last_y + elem['center_y']) / 2
                else:
                    if current_row:
                        # Trier la ligne de gauche à droite
                        current_row.sort(key=lambda e: e['x0'])
                        rows.append(current_row)
                    current_row = [elem]
                    last_y = elem['center_y']
            
            if current_row:
                current_row.sort(key=lambda e: e['x0'])
                rows.append(current_row)
            
            # Formater le contenu de façon structurée
            formatted_content = []
            current_day = None
            
            for row in rows:
                row_texts = [e['text'].replace('\n', ' ').strip() for e in row]
                row_text = ' | '.join(row_texts)
                
                # Détecter si c'est un jour
                row_lower = row_text.lower()
                detected_day = None
                for jour in jours:
                    if jour in row_lower:
                        detected_day = jour.capitalize()
                        break
                
                if detected_day and detected_day != current_day:
                    current_day = detected_day
                    formatted_content.append(f"\n📅 {current_day.upper()}")
                    formatted_content.append("-" * 40)
                
                # Nettoyer et ajouter la ligne
                clean_row = self._clean_schedule_row(row_text)
                if clean_row:
                    formatted_content.append(clean_row)
            
            page_text = "\n".join(formatted_content)
            
            if len(page_text.strip()) > 10:
                pages_content.append(
                    f"{'='*60}\n"
                    f"📄 PAGE {page_num}\n"
                    f"{'='*60}\n"
                    f"{page_text}\n"
                )
                print(f"✅ Page {page_num} : {len(page_text)} caractères")
            else:
                pages_content.append(
                    f"{'='*60}\n📄 PAGE {page_num}\n{'='*60}\n⚠️ [Page vide ou image]\n"
                )
                print(f"⚠️ Page {page_num} : peu de contenu")
            
            page_num += 1
        
        return pages_content

    def _clean_schedule_row(self, row: str) -> str:
        """Nettoie une ligne d'emploi du temps"""
        # Supprimer les espaces multiples
        row = re.sub(r'\s+', ' ', row).strip()
        
        # Si la ligne ne contient que des séparateurs ou espaces
        if re.match(r'^[\s|_\-=]+$', row):
            return ""
        
        # Supprimer les lignes trop courtes (probablement du bruit)
        if len(row) < 3:
            return ""
        
        return row

    def _extract_pdf_strategy2(self, tmp_path: str) -> List[str]:
        """Stratégie 2: Extraction texte brut complète"""
        try:
            # Extraction texte brut de tout le PDF
            full_text = extract_text(tmp_path)
            
            if not full_text or len(full_text.strip()) < 20:
                return []
            
            clean_text = self._clean_pdf_text(full_text)
            
            # Diviser en pages approximatives (par saut de page ou longueur)
            pages = clean_text.split('\x0c')  # Form feed = saut de page
            if len(pages) == 1:
                # Pas de sauts de page, diviser par lignes
                lines = clean_text.split('\n')
                chunk_size = max(50, len(lines) // 3)
                pages = ['\n'.join(lines[i:i+chunk_size]) for i in range(0, len(lines), chunk_size)]
            
            pages_content = []
            for i, page in enumerate(pages, 1):
                if page.strip():
                    pages_content.append(
                        f"{'='*60}\n"
                        f"📄 PAGE {i}\n"
                        f"{'='*60}\n"
                        f"{page.strip()}\n"
                    )
            
            return pages_content
            
        except Exception as e:
            print(f"⚠️ Stratégie 2 échouée: {e}")
            return []

    def _extract_pdf_strategy3(self, tmp_path: str) -> List[str]:
        """Stratégie 3: Extraction caractère par caractère (pour PDFs difficiles)"""
        laparams = LAParams(
            line_margin=1.0,
            word_margin=0.5,
            char_margin=3.0,
            boxes_flow=0.5,
            detect_vertical=True,
            all_texts=True,
        )
        
        pages_content = []
        page_num = 1
        
        for page_layout in extract_pages(tmp_path, laparams=laparams):
            chars = []
            
            def extract_chars(element):
                if isinstance(element, LTChar):
                    chars.append(element.get_text())
                elif isinstance(element, LTAnno):
                    chars.append(element.get_text())
                elif hasattr(element, '__iter__'):
                    for child in element:
                        extract_chars(child)
            
            for element in page_layout:
                extract_chars(element)
            
            page_text = ''.join(chars)
            
            if len(page_text.strip()) > 10:
                clean_text = self._clean_pdf_text(page_text)
                pages_content.append(
                    f"{'='*60}\n"
                    f"📄 PAGE {page_num}\n"
                    f"{'='*60}\n"
                    f"{clean_text}\n"
                )
            
            page_num += 1
        
        return pages_content

    def _clean_pdf_text(self, text: str) -> str:
        """Nettoie le texte PDF tout en préservant la structure"""
        # Supprimer caractères de contrôle sauf newlines
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        
        # Normaliser les espaces multiples (mais garder newlines)
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Supprimer lignes vides multiples
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Supprimer espaces en début/fin de ligne
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)
        
        return text.strip()

    # ======================================================================
    # 📝 EXTRACTION TEXTE HTML
    # ======================================================================
    def _extract_text(self, soup: BeautifulSoup) -> str:
        """Nettoie le HTML et extrait le texte principal."""
        for tag in soup(["script", "style", "noscript", "footer", "nav", "aside"]):
            tag.decompose()

        text_parts: List[str] = []

        main_content = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", class_=re.compile(r"content|main|entry|post", re.I))
        )
        target = main_content if main_content else soup.body

        if target:
            for element in target.find_all(["h1", "h2", "h3", "h4", "h5", "p", "li", "td", "a"]):
                text = element.get_text(separator=" ", strip=True)
                if text and len(text) > 3:
                    text_parts.append(text)

        full_text = "\n\n".join(text_parts)
        return re.sub(r"\n{3,}", "\n\n", full_text)

    # ======================================================================
    # 📎 DÉTECTION DES LIENS DE FICHIERS
    # ======================================================================
    def _extract_file_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extrait les liens de fichiers téléchargeables (PDF, DOCX, XLSX, etc.)."""
        file_links: List[str] = []

        for link in soup.find_all("a", href=True):
            href = link["href"].strip()
            full_url = urljoin(base_url, href)

            if re.search(r"\.(pdf|docx?|xlsx?|pptx?|zip|rar)$", full_url, re.I):
                file_links.append(full_url)
            else:
                mime_type, _ = mimetypes.guess_type(full_url)
                if mime_type and any(
                    ext in mime_type for ext in ["pdf", "word", "excel", "powerpoint"]
                ):
                    file_links.append(full_url)

        return list(set(file_links))
