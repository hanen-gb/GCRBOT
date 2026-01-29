# gcrbot/src/gcrbot/tools_emploi.py
"""
Tool spécifique pour l'extraction des emplois du temps (PDFs).
Utilisé uniquement par l'agent Emploi du Temps.
Inclut l'extraction complète du contenu PDF avec pdfplumber.
"""

import logging
import re
import requests
import tempfile
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import Optional
from crewai.tools import tool

try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gcrbot.tools_emploi")


def extract_pdf_content(pdf_url: str, session: requests.Session) -> str:
    """
    Extrait le contenu d'un PDF d'emploi du temps.
    Format texte narratif simple : PAGE X - Groupe > Jour > liste des cours.
    """
    if not PDF_SUPPORT:
        return "Module pdfplumber non installe"
    
    try:
        logger.info(f"Telechargement PDF: {pdf_url}")
        
        resp = session.get(pdf_url, timeout=30)
        
        if resp.status_code == 404:
            return "PDF non trouve (404)"
        
        resp.raise_for_status()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(resp.content)
            tmp_path = tmp.name
        
        try:
            content_parts = []
            jours_semaine = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi']
            
            with pdfplumber.open(tmp_path) as pdf:
                total_pages = len(pdf.pages)
                logger.info(f"PDF: {total_pages} pages (groupes)")
                
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text() or ""
                    tables = page.extract_tables()
                    
                    if not text.strip() and not tables:
                        continue
                    
                    # Extraire titre du groupe
                    lines = text.strip().split('\n')
                    groupe_name = ""
                    
                    for line in lines[:5]:
                        if 'GCR' in line:
                            # Extraire juste "GCR1A", "GCR2B", etc.
                            match = re.search(r'GCR\d[AB]?', line)
                            if match:
                                groupe_name = match.group()
                            break
                    
                    # Titre de la page
                    content_parts.append("")
                    if groupe_name:
                        content_parts.append(f"PAGE {page_num} - Emploi du temps Groupe {groupe_name}")
                    else:
                        content_parts.append(f"PAGE {page_num}")
                    
                    # Extraire emploi depuis le tableau
                    if tables:
                        for table in tables:
                            if not table or len(table) < 2:
                                continue
                            
                            # Ligne 0 = horaires
                            header = table[0] if table[0] else []
                            horaires = []
                            for h in header:
                                h_str = str(h).strip() if h else ""
                                if '-' in h_str and ':' in h_str:
                                    # Reformater horaire: "08:15 - 09:45" -> "08h15 - 09h45"
                                    horaires.append(h_str)
                            
                            # Collecter les cours par jour
                            jours_trouves = []
                            
                            for row in table[1:]:
                                if not row:
                                    continue
                                
                                jour = str(row[0]).strip() if row[0] else ""
                                
                                # Identifier le jour
                                jour_valide = None
                                for j in jours_semaine:
                                    if j in jour:
                                        jour_valide = j
                                        break
                                
                                if not jour_valide:
                                    continue
                                
                                jours_trouves.append(jour_valide)
                                
                                # Collecter cours du jour
                                cours_list = []
                                for idx, cell in enumerate(row[1:], 0):
                                    if cell:
                                        cell_str = str(cell).strip()
                                        if cell_str and cell_str != '-' and len(cell_str) > 1:
                                            # Nettoyer: remplacer sauts de ligne par des espaces
                                            cell_str = re.sub(r'\s*\n\s*', ' ', cell_str)
                                            cell_str = re.sub(r' {2,}', ' ', cell_str)
                                            # Formater: "PROF - SALLE" -> "(PROF - SALLE)"
                                            cell_str = cell_str.strip()
                                            
                                            if idx < len(horaires):
                                                cours_list.append(f"- {horaires[idx]} : {cell_str}")
                                            else:
                                                cours_list.append(f"- {cell_str}")
                                
                                # Afficher le jour
                                content_parts.append("")
                                content_parts.append(jour_valide)
                                if cours_list:
                                    content_parts.extend(cours_list)
                                else:
                                    content_parts.append("- rien")
                            
                            # Ajouter les jours manquants
                            for j in jours_semaine:
                                if j not in jours_trouves:
                                    content_parts.append("")
                                    content_parts.append(j)
                                    content_parts.append("- rien")
                    
                    # Texte brut si pas de tableau
                    elif text.strip():
                        text_clean = re.sub(r'\n{3,}', '\n\n', text)
                        content_parts.append(text_clean[:800])
            
            if content_parts:
                return "\n".join(content_parts)
            else:
                return "PDF vide"
                
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass
                
    except Exception as e:
        logger.error(f"Erreur extraction PDF: {e}")
        return f"Erreur: {str(e)}"


@tool("extract_emploi_page")
def extract_emploi_page(url: str, semaine: Optional[int] = None) -> str:
    """
    Extrait l'emploi du temps depuis la page ENIGPlus.
    Trouve automatiquement la semaine demandée ou la dernière disponible.
    FILTRE les liens pour rester sur le même type (étudiants OU enseignants).
    
    Args:
        url: URL de base des emplois du temps (étudiants ou enseignants)
        semaine: Numéro de semaine (optionnel, sinon prend la dernière)
    
    Returns:
        Contenu de l'emploi du temps avec lien PDF
    """
    try:
        logger.info(f"📥 Extraction emploi: {url}, semaine={semaine}")
        
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        
        # Déterminer le type demandé (étudiants ou enseignants)
        is_enseignant = "enseignants" in url.lower() or "enseignant" in url.lower()
        type_label = "ENSEIGNANTS" if is_enseignant else "ÉTUDIANTS"
        
        logger.info(f"📌 Type demandé: {type_label}")
        
        # Récupérer la page principale
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Chercher les liens vers les semaines - FILTRER par type
        semaine_links = []
        pdf_links = []
        
        for link in soup.find_all("a", href=True):
            href = link["href"].lower()
            full_url = urljoin(url, link["href"])
            text = link.get_text().lower()
            
            # FILTRE CRITIQUE: Ignorer les liens du mauvais type
            if is_enseignant:
                # On cherche enseignants -> ignorer les liens étudiants
                if "enseignement" in href and "enseignants" not in href:
                    continue
            else:
                # On cherche étudiants -> ignorer les liens enseignants
                if "enseignants" in href:
                    logger.info(f"⏭️ Ignoré (enseignants): {href[:50]}")
                    continue
            
            # Chercher les liens de semaine
            semaine_match = re.search(r'semaine[- ]?(\d+)', href + " " + text)
            if semaine_match:
                num = int(semaine_match.group(1))
                semaine_links.append((num, full_url, link.get_text().strip()))
                logger.info(f"✅ Semaine {num} trouvée: {full_url[:60]}")
            
            # Chercher les PDFs
            if ".pdf" in href:
                # Filtrer aussi les PDFs par type
                pdf_text = href + " " + text
                is_prof_pdf = "prof" in pdf_text or "enseignant" in pdf_text
                
                if is_enseignant and is_prof_pdf:
                    semaine_match = re.search(r'semaine[- ]?(\d+)', href)
                    if semaine_match:
                        pdf_links.append((int(semaine_match.group(1)), full_url))
                elif not is_enseignant and not is_prof_pdf:
                    semaine_match = re.search(r'semaine[- ]?(\d+)', href)
                    if semaine_match:
                        pdf_links.append((int(semaine_match.group(1)), full_url))
        
        # Trier par numéro de semaine décroissant
        semaine_links.sort(key=lambda x: x[0], reverse=True)
        pdf_links.sort(key=lambda x: x[0], reverse=True)
        
        logger.info(f"📊 Trouvé: {len(semaine_links)} pages semaine, {len(pdf_links)} PDFs")
        
        result = []
        result.append("=" * 60)
        result.append(f"📅 EMPLOIS DU TEMPS - {type_label} GCR")
        result.append("=" * 60)
        
        target_semaine = None
        target_url = None
        target_pdf = None
        
        if semaine:
            # Chercher la semaine spécifique
            for num, link_url, text in semaine_links:
                if num == semaine:
                    target_semaine = num
                    target_url = link_url
                    break
            
            for num, pdf_url in pdf_links:
                if num == semaine:
                    target_pdf = pdf_url
                    break
            
            if not target_url and not target_pdf:
                result.append(f"\n⚠️ Semaine {semaine} non trouvée pour {type_label}!")
                if semaine_links:
                    result.append(f"📆 Semaines disponibles: {[s[0] for s in semaine_links[:5]]}")
                    target_semaine = semaine_links[0][0]
                    target_url = semaine_links[0][1]
                    result.append(f"\n💡 Affichage de la dernière semaine disponible: {target_semaine}")
        else:
            # Prendre la dernière semaine
            if semaine_links:
                target_semaine = semaine_links[0][0]
                target_url = semaine_links[0][1]
            if pdf_links:
                target_pdf = pdf_links[0][1]
        
        if target_semaine:
            result.append(f"\n📆 Semaine: {target_semaine}")
        
        if target_url:
            result.append(f"🔗 Page: {target_url}")
            
            # Extraire le contenu de la page de la semaine
            try:
                page_resp = session.get(target_url, timeout=20)
                page_soup = BeautifulSoup(page_resp.text, "html.parser")
                
                # Extraire le contenu principal
                content_div = page_soup.find("div", class_="entry-content") or page_soup.find("article")
                if content_div:
                    text_content = content_div.get_text(separator="\n", strip=True)
                    text_content = re.sub(r'\n{3,}', '\n\n', text_content)
                    if len(text_content) > 2000:
                        text_content = text_content[:2000] + "..."
                    result.append(f"\n📋 Contenu:\n{text_content}")
                
                # Chercher le PDF dans cette page - FILTRER par type
                for a in page_soup.find_all("a", href=True):
                    href_lower = a["href"].lower()
                    if ".pdf" in href_lower:
                        # Vérifier que c'est le bon type
                        is_prof_pdf = "prof" in href_lower
                        if is_enseignant == is_prof_pdf or "prof" not in href_lower:
                            target_pdf = urljoin(target_url, a["href"])
                            break
                        
            except Exception as e:
                logger.warning(f"Erreur extraction page semaine: {e}")
        
        if target_pdf:
            result.append(f"\n📎 PDF: {target_pdf}")
            
            # EXTRACTION DU CONTENU PDF - PRIORITAIRE
            logger.info(f"📥 Extraction contenu PDF...")
            pdf_content = extract_pdf_content(target_pdf, session)
            
            if pdf_content and not pdf_content.startswith("⚠️") and not pdf_content.startswith("❌"):
                result.append("\n" + "="*60)
                result.append("📄 CONTENU COMPLET DU PDF (EMPLOI DU TEMPS)")
                result.append("="*60)
                
                # Limiter à 8000 caractères pour éviter troncature
                if len(pdf_content) > 8000:
                    result.append(pdf_content[:8000])
                    result.append("\n... [Contenu tronqué - voir PDF pour version complète]")
                else:
                    result.append(pdf_content)
            else:
                result.append(f"\n⚠️ Extraction PDF: {pdf_content}")
        
        result.append(f"\n📌 Source: {url}")
        
        # Si aucune semaine trouvée
        if not target_semaine and not target_pdf:
            result.append(f"\n⚠️ Aucun emploi du temps {type_label} trouvé sur cette page.")
            result.append("💡 Vérifiez que l'URL est correcte.")
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Erreur extraction emploi: {e}")
        return f"❌ Erreur extraction: {str(e)}\n📌 URL: {url}"


# Export du tool
__all__ = ['extract_emploi_page']
