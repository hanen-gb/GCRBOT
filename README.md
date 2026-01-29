# GCRBOT - Assistant Multi-Agents ENIG

Assistant intelligent multi-agents pour les étudiants de la filière **Génie Réseaux et Communications (GCR)** de l'École Nationale d'Ingénieurs de Gabès (ENIG).

---

## 📋 Table des matières

1. [Présentation](#-présentation)
2. [Fonctionnalités](#-fonctionnalités)
3. [Architecture](#-architecture)
4. [Installation](#-installation)
5. [Configuration](#-configuration)
6. [Utilisation](#-utilisation)
7. [Structure des fichiers](#-structure-des-fichiers)
8. [Les 3 Agents](#-les-3-agents)
9. [Les Tools](#-les-tools)
10. [Technologies utilisées](#-technologies-utilisées)


---

##  Présentation

GCRBOT est un chatbot intelligent basé sur **CrewAI** et **Google Gemini** qui utilise une architecture multi-agents pour répondre aux questions des étudiants GCR. Le système route automatiquement les questions vers l'agent spécialisé approprié.

### Langues supportées
- 🇫🇷 Français
- 🇬🇧 English
- 🇸🇦 العربية

---

## ✨ Fonctionnalités

### 📅 Agent Emplois du Temps
- Extraction des emplois du temps depuis ENIGPlus
- Support étudiants ET enseignants
- Extraction complète du contenu PDF (page par page)
- Format de sortie clair et lisible
- Lien PDF téléchargeable

### 📋 Agent Stages & Procédures
- Informations sur les stages obligatoires (initiation, perfectionnement, PFE)
- Programme Mitacs Canada
- Procédures d'inscription
- Deep crawling sémantique des sites web
- Recherche intelligente dans les contenus

### 💬 Agent Conversation
- Salutations et au revoir
- Support émotionnel (stress, fatigue, motivation)
- Conseils pour réussir ses études
- Présentation du bot
- Réponses chaleureuses avec emojis

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        UTILISATEUR                          │
│                    (CLI ou Streamlit)                       │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    ORCHESTRATEUR                            │
│              (Détection langue + Routage)                   │
│                                                             │
│  Question ──► Analyse ──► Type détecté ──► Agent assigné   │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┬───────────────┐
          ▼               ▼               ▼               ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│   AGENT     │   │   AGENT     │   │   AGENT     │   │   AGENT     │
│   EMPLOI    │   │   STAGE     │   │ CONVERSATION│   │  DOCUMENT   │
│             │   │             │   │             │   │             │
│ • Weaviate  │   │ • Weaviate  │   │ (Pas de     │   │ • Index     │
│ • PDF Extract│  │ • Crawling  │   │  tools)     │   │ • Search    │
└──────┬──────┘   └──────┬──────┘   └─────────────┘   └──────┬──────┘
       │                 │                                   │
       ▼                 ▼                                   ▼
┌─────────────────────────────────────────────────────────────┐
│                      WEAVIATE                               │
│              (Base de données vectorielle)                  │
│                                                             │
│  URLs indexées : ENIGPlus, ENIG, Mitacs, etc.              │
│  Documents uploadés : PDF, DOCX, XLSX, TXT                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔄 Workflow Détaillé : User → Agent Orchestrateur → Agent Enfant → Tools → Résultat

Le système GCRBOT suit un workflow en 5 étapes principales :

### Étape 1 : Entrée Utilisateur (User Prompt)
```
┌──────────────────────────────────────────────────────────────┐
│  👤 UTILISATEUR                                              │
│  ─────────────────                                           │
│  • Pose une question via CLI (main.py) ou Streamlit (app.py)│
│  • Langues : Français, English, العربية                      │
│  • Peut uploader un document (PDF, DOCX, XLSX, TXT)          │
│                                                              │
│  Exemples :                                                  │
│  - "Emploi étudiants semaine 14"                            │
│  - "C'est quoi Mitacs ?"                                    │
│  - "Résume le document uploadé"                             │
│  - "Bonjour !"                                              │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
```

### Étape 2 : Agent Orchestrateur (GCRBotOrchestrator)
```
┌──────────────────────────────────────────────────────────────┐
│   ORCHESTRATEUR (crew.py)                                  │
│  ─────────────────────────────                               │
│  Classe : GCRBotOrchestrator                                 │
│                                                              │
│  A. DÉTECTION DE LANGUE (detect_language)                   │
│     ├── Caractères arabes → 'ar'                            │
│     ├── Mots-clés anglais → 'en'                            │
│     └── Par défaut → 'fr'                                   │
│                                                              │
│  B. DÉTECTION DU TYPE (detect_question_type)                │
│     Priorité de détection :                                  │
│     1. 📄 DOCUMENT : "fichier", "résumé", "ce document"     │
│     2. 📅 EMPLOI : "emploi du temps", "semaine X", "horaire"│
│     3. 📋 STAGE : "mitacs", "stage", "pfe", "procédure"     │
│     4. 💬 CONVERSATION : "bonjour", "ça va", "merci"        │
│                                                              │
│  C. ROUTAGE VERS L'AGENT APPROPRIÉ                          │
│     orchestrator.process_question(question)                  │
│     → Sélectionne le Crew correspondant                      │
│     → Enrichit avec instruction de langue                    │
│     → Ajoute contexte mémoire si nécessaire                 │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
```

### Étape 3 : Agent Enfant (Crew Spécialisé)
```
┌──────────────────────────────────────────────────────────────┐
│   AGENTS ENFANTS (CrewAI)                                  │
│  ─────────────────────────────                               │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 📅 EmploiCrew (emploi_agent)                           │ │
│  │    Config : agents_emploi.yaml, tasks_emploi.yaml      │ │
│  │    Rôle : Spécialiste Emplois du Temps ENIG            │ │
│  │    LLM : gemini-2.5-flash-lite                         │ │
│  │    max_iter: 5 | timeout: 120s                         │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 📋 StageCrew (stage_agent)                             │ │
│  │    Config : agents_stage.yaml, tasks_stage.yaml        │ │
│  │    Rôle : Spécialiste Stages & Procédures ENIG         │ │
│  │    LLM : gemini-2.5-flash-lite                         │ │
│  │    max_iter: 8 | timeout: 300s                         │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 💬 ConversationCrew (conversation_agent)               │ │
│  │    Config : agents_conversation.yaml                    │ │
│  │    Rôle : Ami Virtuel des Étudiants                    │ │
│  │    LLM : gemini-2.5-flash-lite                         │ │
│  │    max_iter: 3 | timeout: 60s | PAS DE TOOLS           │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 📄 DocumentCrew (document_agent)                       │ │
│  │    Config : agents_document.yaml, tasks_document.yaml  │ │
│  │    Rôle : Analyste de Documents Uploadés               │ │
│  │    LLM : gemini-2.5-flash-lite                         │ │
│  │    max_iter: 5 | timeout: 120s                         │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
```

### Étape 4 : Exécution des Tools
```
┌──────────────────────────────────────────────────────────────┐
│  🛠️ TOOLS (Outils Spécialisés)                              │
│  ─────────────────────────────                               │
│                                                              │
│  ┌─────────────────── TOOLS PARTAGÉS ───────────────────┐   │
│  │ (tools_core_optimized.py)                            │   │
│  │                                                       │   │
│  │ 🔍 search_weaviate(question)                         │   │
│  │    → Recherche vectorielle dans Weaviate              │   │
│  │    → Retourne URLs pertinentes                        │   │
│  │                                                       │   │
│  │ 🌐 extract_web_content(url, keywords)                │   │
│  │    → Deep crawling sémantique                         │   │
│  │    → Extraction BeautifulSoup                         │   │
│  │                                                       │   │
│  │ 🔎 smart_site_search(url, keywords)                  │   │
│  │    → Recherche pages internes d'un site               │   │
│  │                                                       │   │
│  │ 📝 semantic_search_in_text(text, query)              │   │
│  │    → Recherche sémantique dans texte long             │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────── TOOL EMPLOI ──────────────────────┐   │
│  │ (tools_emploi.py)                                    │   │
│  │                                                       │   │
│  │ 📅 extract_emploi_page(url, semaine)                 │   │
│  │    → Télécharge le PDF depuis ENIGPlus               │   │
│  │    → Parse avec pdfplumber                            │   │
│  │    → Extrait contenu page par page                    │   │
│  │    → Retourne emploi formaté + lien PDF               │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────── TOOLS DOCUMENT ───────────────────┐   │
│  │ (tools_document.py)                                  │   │
│  │                                                       │   │
│  │ 📤 process_uploaded_document(filepath)               │   │
│  │    → Indexe le document dans Weaviate                 │   │
│  │                                                       │   │
│  │ 🔍 search_in_documents(query)                        │   │
│  │    → Recherche dans les documents indexés             │   │
│  │                                                       │   │
│  │ 📋 summarize_document(filename)                      │   │
│  │    → Génère un résumé du document                     │   │
│  │                                                       │   │
│  │ 📚 list_documents()                                  │   │
│  │    → Liste les documents disponibles                  │   │
│  │                                                       │   │
│  │ 💬 answer_from_document(question)                    │   │
│  │    → Répond basé sur le contenu du document           │   │
│  └───────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
```

### Étape 5 : Résultat Final
```
┌──────────────────────────────────────────────────────────────┐
│  📤 RÉSULTAT                                                 │
│  ───────────                                                 │
│                                                              │
│  A. TRAITEMENT PAR L'AGENT                                  │
│     • L'agent utilise les tools pour collecter les infos    │
│     • Le LLM (Gemini) formule la réponse finale             │
│     • Réponse dans la langue détectée (FR/EN/AR)            │
│                                                              │
│  B. NETTOYAGE (service.py → _clean_agent_response)          │
│     • Suppression des logs de réflexion de l'agent          │
│     • Extraction de la réponse finale                        │
│     • Vérification qualité (longueur minimale)              │
│                                                              │
│  C. AFFICHAGE                                               │
│     CLI : Réponse formatée dans le terminal                  │
│     Streamlit : Bulle de chat avec style                     │
│                                                              │
│  D. SAUVEGARDE HISTORIQUE                                   │
│     • Mémoire contextuelle (10 derniers échanges)            │
│     • Fichier session_YYYYMMDD_HHMMSS.txt                   │
└──────────────────────────────────────────────────────────────┘
```

### Schéma de Flux Complet

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FLUX DE TRAITEMENT GCRBOT                         │
└─────────────────────────────────────────────────────────────────────────────┘

  👤 User Input                    🎯 Orchestrateur                🤖 Agent
  ═════════════                    ════════════════                ══════════
       │                                 │                              │
       │  "Emploi semaine 14"           │                              │
       ├────────────────────────────────►│                              │
       │                                 │                              │
       │                    detect_language()                           │
       │                    detect_question_type()                      │
       │                    → Type: 'emploi'                            │
       │                                 │                              │
       │                                 │  EmploiCrew.kickoff()        │
       │                                 ├──────────────────────────────►│
       │                                 │                              │
       │                                 │              🛠️ Tools         │
       │                                 │              ════════         │
       │                                 │                   │          │
       │                                 │    search_weaviate()         │
       │                                 │    → URL ENIGPlus            │
       │                                 │           │                  │
       │                                 │    extract_emploi_page()     │
       │                                 │    → Contenu PDF             │
       │                                 │           │                  │
       │                                 │           ▼                  │
       │                                 │    LLM formule réponse       │
       │                                 │◄──────────────────────────────┤
       │                                 │                              │
       │    📤 Réponse formatée         │                              │
       │◄────────────────────────────────┤                              │
       │                                 │                              │
       ▼                                 ▼                              ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                                                                         │
  │   📅 EMPLOI DU TEMPS - SEMAINE 14                                      │
  │   ════════════════════════════════                                      │
  │                                                                         │
  │   PAGE 1 - Groupe GCR1A                                                │
  │   • Lundi 08:15-09:45 : Micro-ondes (BENZINA H.)                       │
  │   • Mardi 10:00-11:30 : Réseaux (AHMED M.)                             │
  │   ...                                                                   │
  │                                                                         │
  │   📎 PDF: https://enigplus.enig.rnu.tn/...                             │
  │                                                                         │
  └─────────────────────────────────────────────────────────────────────────┘
```

### Exemple de Workflow Document

```
  👤 User                          🎯 Orchestrateur              📄 DocumentAgent
  ════════                         ════════════════              ═══════════════
       │                                 │                              │
       │  [Upload rapport.pdf]           │                              │
       │  "Résume ce document"           │                              │
       ├────────────────────────────────►│                              │
       │                                 │                              │
       │                    detect_question_type()                      │
       │                    → "résume" + fichier → 'document'           │
       │                                 │                              │
       │                                 │  DocumentCrew.kickoff()      │
       │                                 ├──────────────────────────────►│
       │                                 │                              │
       │                                 │     process_uploaded_document()
       │                                 │     → Indexation Weaviate    │
       │                                 │              │               │
       │                                 │     summarize_document()     │
       │                                 │     → Résumé généré          │
       │                                 │              │               │
       │                                 │◄──────────────────────────────┤
       │                                 │                              │
       │    📋 Résumé du document       │                              │
       │◄────────────────────────────────┤                              │
       │                                 │                              │
```

---

## 💻 Installation

### Prérequis
- Python 3.12+
- Compte Google AI (pour Gemini API)
- Docker Desktop (pour Weaviate local)

### Étapes

1. **Cloner le projet**
```bash
```

2. **Créer l'environnement virtuel**
```bash
```

3. **Activer l'environnement**
```powershell
# Windows PowerShell
.\venv312\Scripts\Activate.ps1

# Windows CMD
.\venv312\Scripts\activate.bat
```

4. **Installer les dépendances**
```bash
pip install crewai crewai-tools google-generativeai weaviate-client requests beautifulsoup4 pdfplumber streamlit
```

5. **Démarrer Weaviate Local (Docker)**
```bash
# Créer le dossier pour Weaviate
mkdir C:\Users\user\Desktop\weaviate_local
cd C:\Users\user\Desktop\weaviate_local

# Créer le fichier docker-compose.yml (voir section Weaviate ci-dessous)
# Puis lancer Weaviate
docker compose up -d
```

---

## ⚙ Configuration

### Variables d'environnement

Créer un fichier `.env` dans `gcrbot/` :

```env
# Google Gemini API
GOOGLE_API_KEY=votre_clé_gemini
GEMINI_API_KEY=votre_clé_gemini

# Weaviate Local (Docker)
WEAVIATE_HOST=localhost
WEAVIATE_HTTP_PORT=8080
WEAVIATE_GRPC_PORT=50051

# Modèle LLM
MODEL=gemini-2.5-flash-lite
```

### Weaviate Local (Docker)

Le système utilise **Weaviate Local** comme base de données vectorielle pour indexer les URLs.

#### Configuration Docker (`docker-compose.yml`)

```yaml
services:
  weaviate:
    image: semitechnologies/weaviate:latest
    ports:
    
```

#### Commandes Docker utiles

```bash
# Démarrer Weaviate
docker compose up -d

# Vérifier le statut
docker compose ps

# Voir les logs
docker compose logs -f weaviate

# Arrêter Weaviate
docker compose down
```

#### Tester la connexion Weaviate

```bash
# Depuis le dossier gcrbot/src
python -m weaviate_setup.test_weaviate_connection
```



---

##  Utilisation

### Mode CLI (Terminal)

```bash
cd gcrbot\src
python -m gcrbot.main
```

Exemple d'interaction :
```
🤖 GCRBOT - Assistant Multi-Agents ENIG
============================================================
👤 Vous : emploi étudiants semaine 14
⏳ Traitement...
📅 → Agent EMPLOI

PAGE 1 - Emploi du temps Groupe GCR1A
Lundi
- 08:15 - 09:45 : Dispo & Micro-ondes1 (BENZINA H.)
...
```

### Mode Streamlit (Interface Web)

```bash
streamlit run app.py
```

Ouvrir dans le navigateur : `http://localhost:8501`

---

## 📁 Structure des fichiers

```
C:\Users\Hanen GB\Desktop\GCRBOT\
│
├── README.md                       # Ce fichier
├── app.py                          # Interface Streamlit
├── venv312\                        # Environnement Python 3.12
│
└── gcrbot\
    └── src\
        └── gcrbot\
            │
            ├── main.py             # Point d'entrée CLI
            ├── crew.py             # Orchestrateur multi-agents
            ├── service.py          # Service pour Streamlit
            ├── gemini.py           # Configuration Gemini API
            │
            ├── tools_core_optimized.py   # Tools partagés
            ├── tools_emploi.py           # Tool extraction PDF
            ├── WebExtractor.py           # Deep crawling sémantique
            │
            └── config\
                ├── __init__.py
                ├── agents_emploi.yaml        # Config Agent Emploi
                ├── tasks_emploi.yaml
                ├── agents_stage.yaml         # Config Agent Stage
                ├── tasks_stage.yaml
                ├── agents_conversation.yaml  # Config Agent Conversation
                └── tasks_conversation.yaml
```

### Description des fichiers

| Fichier | Description |
|---------|-------------|
| `main.py` | Point d'entrée CLI, boucle interactive, détection de langue |
| `crew.py` | Définition des 3 Crews (EmploiCrew, StageCrew, ConversationCrew) et orchestrateur |
| `service.py` | Interface entre Streamlit et le système multi-agents |
| `gemini.py` | Configuration et initialisation de l'API Google Gemini |
| `tools_core_optimized.py` | Tools partagés : search_weaviate, extract_web_content, smart_site_search, semantic_search_in_text |
| `tools_emploi.py` | Tool spécialisé : extract_emploi_page (extraction PDF emplois du temps) |
| `WebExtractor.py` | Moteur de deep crawling avec scoring sémantique |

---

## 🤖 Les 3 Agents

### 1. Agent Emploi du Temps (`emploi_agent`)

**Fichiers config :** `agents_emploi.yaml`, `tasks_emploi.yaml`

**Role :** Spécialiste Emplois du Temps ENIG

**Tools utilisés :**
- `search_weaviate` : Recherche l'URL des emplois du temps
- `extract_emploi_page` : Extrait le contenu PDF de la semaine demandée

**Workflow :**
1. Recherche dans Weaviate → Obtient l'URL (étudiants ou enseignants)
2. Extraction du PDF → Contenu page par page
3. Formatage → Réponse structurée avec lien PDF

**Exemple de question :**
- "emploi étudiants semaine 14"
- "emploi du temps des profs semaine 10"

---

### 2. Agent Stages & Procédures (`stage_agent`)

**Fichiers config :** `agents_stage.yaml`, `tasks_stage.yaml`

**Role :** Spécialiste Stages, Procédures et Informations ENIG

**Tools utilisés :**
- `search_weaviate` : Recherche l'URL pertinente
- `smart_site_search` : Trouve les pages internes d'un site
- `extract_web_content` : Extrait le contenu avec deep crawling
- `semantic_search_in_text` : Recherche sémantique dans le texte

**Workflow :**
1. Recherche Weaviate → URL principale (#1)
2. Extraction intelligente avec crawling sémantique
3. Si insuffisant → Recherche de pages internes
4. Formatage avec sources

**Exemple de question :**
- "quels sont les programmes de Mitacs ?"
- "comment postuler pour un stage PFE ?"
- "procédure d'inscription ENIG"

---

### 3. Agent Conversation (`conversation_agent`)

**Fichiers config :** `agents_conversation.yaml`, `tasks_conversation.yaml`

**Role :** Ami Virtuel des Étudiants ENIG

**Tools utilisés :** Aucun (réponses directes du LLM)

**Types de messages gérés :**
- Salutations : "Bonjour", "Hello", "مرحبا"
- Humeur : "Je suis stressé", "Ça va ?"
- Conseils : "Un conseil pour réussir ?"
- Bot : "Qui es-tu ?"
- Au revoir : "Bye", "À bientôt"

**Exemple de question :**
- "Salut !"
- "Je suis fatigué"
- "Merci beaucoup"

---

## 🛠 Les Tools

### 1. `search_weaviate`
```python
search_weaviate(question: str) -> str
```
Recherche dans la base Weaviate et retourne les URLs pertinentes.

### 2. `extract_web_content`
```python
extract_web_content(url: str, search_keywords: str = "") -> str
```
Extrait le contenu d'une page web avec deep crawling sémantique.

### 3. `smart_site_search`
```python
smart_site_search(url: str, search_keywords: str) -> str
```
Recherche les pages internes d'un site correspondant aux mots-clés.

### 4. `semantic_search_in_text`
```python
semantic_search_in_text(text: str, query: str) -> str
```
Recherche sémantique dans un texte long.

### 5. `extract_emploi_page`
```python
extract_emploi_page(url: str, semaine: int = None) -> str
```
Extrait l'emploi du temps d'une semaine spécifique, incluant :
- Téléchargement et parsing du PDF
- Extraction page par page (groupes GCR1A, GCR1B, etc.)
- Format texte lisible avec jours et horaires
- Filtrage automatique étudiants/enseignants

---

## 🔧 Technologies utilisées

| Technologie | Utilisation |
|-------------|-------------|
| **CrewAI** | Framework multi-agents |
| **Google Gemini** | LLM (gemini-2.5-flash-lite) |
| **Weaviate** | Base de données vectorielle |
| **pdfplumber** | Extraction de contenu PDF |
| **BeautifulSoup** | Parsing HTML |
| **Requests** | Requêtes HTTP |
| **Streamlit** | Interface web |
| **Python 3.12** | Langage de programmation |

---



```


---

## 👨‍💻 Auteur

Projet développé pour les étudiants de la filière **GCR** de l'**ENIG** (École Nationale d'Ingénieurs de Gabès).
par étudiante Goubaa Hanen

---

## 📄 Licence

Ce projet est à usage éducatif pour l'ENIG.

---

**🎓 Bonne utilisation de GCRBOT !**
