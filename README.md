# GCRBOT - ENIG Multi-Agent Assistant

Intelligent multi-agent assistant for students of the **Networks and Communications Engineering (GCR)** track at the National School of Engineers of Gabès (ENIG).

---

## 📋 Table of contents

1. [Overview](#-overview)
2. [Features](#-features)
3. [Architecture](#-architecture)
4. [Installation](#-installation)
5. [Configuration](#-configuration)
6. [Usage](#-usage)
7. [File structure](#-file-structure)
8. [The 4 Agents](#-the-4-agents)
9. [The Tools](#-the-tools)
10. [Technologies used](#-technologies-used)


---

##  Overview

GCRBOT is an intelligent chatbot built on **CrewAI** and **Google Gemini** that uses a multi-agent architecture to answer GCR students' questions. The system automatically routes each question to the appropriate specialized agent.

### Supported languages
- 🇫🇷 French
- 🇬🇧 English
- 🇸🇦 Arabic

---

## ✨ Features

### 📅 Timetable Agent
- Extracts timetables from ENIGPlus
- Supports both students AND teachers
- Full PDF content extraction (page by page)
- Clear, readable output format
- Downloadable PDF link

### 📋 Internships & Procedures Agent
- Information on mandatory internships (initiation, advanced, final-year project)
- Mitacs Canada program
- Registration procedures
- Semantic deep crawling of websites
- Intelligent search across content

### 💬 Conversation Agent
- Greetings and goodbyes
- Emotional support (stress, fatigue, motivation)
- Study success tips
- Bot self-introduction
- Warm, emoji-filled replies

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                            USER                              │
│                    (CLI or Streamlit)                       │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                       ORCHESTRATOR                           │
│              (Language detection + Routing)                  │
│                                                             │
│  Question ──► Analysis ──► Detected type ──► Assigned agent│
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┬───────────────┐
          ▼               ▼               ▼               ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│   AGENT     │   │   AGENT     │   │   AGENT     │   │   AGENT     │
│  TIMETABLE  │   │ INTERNSHIP  │   │CONVERSATION │   │  DOCUMENT   │
│             │   │             │   │             │   │             │
│ • Weaviate  │   │ • Weaviate  │   │ (No tools)  │   │ • Index     │
│ • PDF Extract│  │ • Crawling  │   │             │   │ • Search    │
└──────┬──────┘   └──────┬──────┘   └─────────────┘   └──────┬──────┘
       │                 │                                   │
       ▼                 ▼                                   ▼
┌─────────────────────────────────────────────────────────────┐
│                         WEAVIATE                             │
│                   (Vector database)                          │
│                                                             │
│  Indexed URLs: ENIGPlus, ENIG, Mitacs, etc.                 │
│  Uploaded documents: PDF, DOCX, XLSX, TXT                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔄 Detailed Workflow: User → Orchestrator Agent → Child Agent → Tools → Result

GCRBOT follows a 5-step workflow:

### Step 1: User Input (User Prompt)
```
┌──────────────────────────────────────────────────────────────┐
│  👤 USER                                                     │
│  ─────────────────                                           │
│  • Asks a question via CLI (main.py) or Streamlit (app.py)  │
│  • Languages: French, English, Arabic                       │
│  • Can upload a document (PDF, DOCX, XLSX, TXT)              │
│                                                              │
│  Examples:                                                   │
│  - "Student timetable week 14"                              │
│  - "What is Mitacs?"                                         │
│  - "Summarize the uploaded document"                         │
│  - "Hello!"                                                  │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
```

### Step 2: Orchestrator Agent (GCRBotOrchestrator)
```
┌──────────────────────────────────────────────────────────────┐
│   ORCHESTRATOR (crew.py)                                    │
│  ─────────────────────────────                               │
│  Class: GCRBotOrchestrator                                    │
│                                                              │
│  A. LANGUAGE DETECTION (detect_language)                     │
│     ├── Arabic characters → 'ar'                             │
│     ├── English keywords → 'en'                              │
│     └── Default → 'fr'                                       │
│                                                              │
│  B. TYPE DETECTION (detect_question_type)                    │
│     Detection priority:                                       │
│     1. 📄 DOCUMENT: "file", "summary", "this document"      │
│     2. 📅 TIMETABLE: "timetable", "week X", "schedule"       │
│     3. 📋 INTERNSHIP: "mitacs", "internship", "procedure"    │
│     4. 💬 CONVERSATION: "hello", "how are you", "thanks"     │
│                                                              │
│  C. ROUTING TO THE APPROPRIATE AGENT                          │
│     orchestrator.process_question(question)                  │
│     → Selects the matching Crew                              │
│     → Enriches with a language instruction                   │
│     → Adds memory context if needed                          │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
```

### Step 3: Child Agent (Specialized Crew)
```
┌──────────────────────────────────────────────────────────────┐
│   CHILD AGENTS (CrewAI)                                     │
│  ─────────────────────────────                               │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 📅 EmploiCrew (emploi_agent)                           │ │
│  │    Config: agents_emploi.yaml, tasks_emploi.yaml       │ │
│  │    Role: ENIG Timetable Specialist                     │ │
│  │    LLM: gemini-2.5-flash-lite                          │ │
│  │    max_iter: 5 | timeout: 120s                         │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 📋 StageCrew (stage_agent)                             │ │
│  │    Config: agents_stage.yaml, tasks_stage.yaml         │ │
│  │    Role: ENIG Internships & Procedures Specialist       │ │
│  │    LLM: gemini-2.5-flash-lite                          │ │
│  │    max_iter: 8 | timeout: 300s                         │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 💬 ConversationCrew (conversation_agent)               │ │
│  │    Config: agents_conversation.yaml                     │ │
│  │    Role: Students' Virtual Friend                       │ │
│  │    LLM: gemini-2.5-flash-lite                          │ │
│  │    max_iter: 3 | timeout: 60s | NO TOOLS                │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 📄 DocumentCrew (document_agent)                       │ │
│  │    Config: agents_document.yaml, tasks_document.yaml   │ │
│  │    Role: Uploaded Document Analyst                      │ │
│  │    LLM: gemini-2.5-flash-lite                          │ │
│  │    max_iter: 5 | timeout: 120s                         │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
```

### Step 4: Tool Execution
```
┌──────────────────────────────────────────────────────────────┐
│  🛠️ TOOLS (Specialized tools)                                │
│  ─────────────────────────────                               │
│                                                              │
│  ┌─────────────────── SHARED TOOLS ─────────────────────┐   │
│  │ (tools_core_optimized.py)                            │   │
│  │                                                       │   │
│  │ 🔍 search_weaviate(question)                         │   │
│  │    → Vector search in Weaviate                        │   │
│  │    → Returns relevant URLs                            │   │
│  │                                                       │   │
│  │ 🌐 extract_web_content(url, keywords)                │   │
│  │    → Semantic deep crawling                            │   │
│  │    → BeautifulSoup extraction                         │   │
│  │                                                       │   │
│  │ 🔎 smart_site_search(url, keywords)                  │   │
│  │    → Searches a site's internal pages                 │   │
│  │                                                       │   │
│  │ 📝 semantic_search_in_text(text, query)              │   │
│  │    → Semantic search within long text                 │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────── TIMETABLE TOOL ───────────────────┐   │
│  │ (tools_emploi.py)                                    │   │
│  │                                                       │   │
│  │ 📅 extract_emploi_page(url, semaine)                 │   │
│  │    → Downloads the PDF from ENIGPlus                  │   │
│  │    → Parses it with pdfplumber                        │   │
│  │    → Extracts content page by page                    │   │
│  │    → Returns formatted timetable + PDF link            │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────── DOCUMENT TOOLS ───────────────────┐   │
│  │ (tools_document.py)                                  │   │
│  │                                                       │   │
│  │ 📤 process_uploaded_document(filepath)               │   │
│  │    → Indexes the document in Weaviate                 │   │
│  │                                                       │   │
│  │ 🔍 search_in_documents(query)                        │   │
│  │    → Searches indexed documents                       │   │
│  │                                                       │   │
│  │ 📋 summarize_document(filename)                      │   │
│  │    → Generates a document summary                     │   │
│  │                                                       │   │
│  │ 📚 list_documents()                                  │   │
│  │    → Lists available documents                        │   │
│  │                                                       │   │
│  │ 💬 answer_from_document(question)                    │   │
│  │    → Answers based on the document's content           │   │
│  └───────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
```

### Step 5: Final Result
```
┌──────────────────────────────────────────────────────────────┐
│  📤 RESULT                                                   │
│  ───────────                                                 │
│                                                              │
│  A. AGENT PROCESSING                                         │
│     • The agent uses tools to gather information            │
│     • The LLM (Gemini) formulates the final answer          │
│     • Reply in the detected language (FR/EN/AR)              │
│                                                              │
│  B. CLEANUP (service.py → _clean_agent_response)             │
│     • Removes the agent's reasoning/thought logs             │
│     • Extracts the final answer                              │
│     • Quality check (minimum length)                         │
│                                                              │
│  C. DISPLAY                                                  │
│     CLI: Formatted reply in the terminal                     │
│     Streamlit: Styled chat bubble                             │
│                                                              │
│  D. HISTORY SAVING                                           │
│     • Contextual memory (last 10 exchanges)                  │
│     • File session_YYYYMMDD_HHMMSS.txt                       │
└──────────────────────────────────────────────────────────────┘
```

### Full Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          GCRBOT PROCESSING FLOW                             │
└─────────────────────────────────────────────────────────────────────────────┘

  👤 User Input                    🎯 Orchestrator                🤖 Agent
  ═════════════                    ════════════════                ══════════
       │                                 │                              │
       │  "Timetable week 14"           │                              │
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
       │                                 │    → ENIGPlus URL            │
       │                                 │           │                  │
       │                                 │    extract_emploi_page()     │
       │                                 │    → PDF content             │
       │                                 │           │                  │
       │                                 │           ▼                  │
       │                                 │    LLM formulates the reply  │
       │                                 │◄──────────────────────────────┤
       │                                 │                              │
       │    📤 Formatted reply          │                              │
       │◄────────────────────────────────┤                              │
       │                                 │                              │
       ▼                                 ▼                              ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                                                                         │
  │   📅 TIMETABLE - WEEK 14                                               │
  │   ════════════════════════════════                                      │
  │                                                                         │
  │   PAGE 1 - Group GCR1A                                                 │
  │   • Monday 08:15-09:45: Microwaves (BENZINA H.)                        │
  │   • Tuesday 10:00-11:30: Networks (AHMED M.)                           │
  │   ...                                                                   │
  │                                                                         │
  │   📎 PDF: https://enigplus.enig.rnu.tn/...                             │
  │                                                                         │
  └─────────────────────────────────────────────────────────────────────────┘
```

### Document Workflow Example

```
  👤 User                          🎯 Orchestrator              📄 DocumentAgent
  ════════                         ════════════════              ═══════════════
       │                                 │                              │
       │  [Upload report.pdf]           │                              │
       │  "Summarize this document"     │                              │
       ├────────────────────────────────►│                              │
       │                                 │                              │
       │                    detect_question_type()                      │
       │                    → "summarize" + file → 'document'           │
       │                                 │                              │
       │                                 │  DocumentCrew.kickoff()      │
       │                                 ├──────────────────────────────►│
       │                                 │                              │
       │                                 │     process_uploaded_document()
       │                                 │     → Weaviate indexing      │
       │                                 │              │               │
       │                                 │     summarize_document()     │
       │                                 │     → Summary generated      │
       │                                 │              │               │
       │                                 │◄──────────────────────────────┤
       │                                 │                              │
       │    📋 Document summary         │                              │
       │◄────────────────────────────────┤                              │
       │                                 │                              │
```

---

## 💻 Installation

### Prerequisites
- Python 3.12+
- Google AI account (for the Gemini API)
- Docker Desktop (for local Weaviate)

### Steps

1. **Clone the project**
```bash
```

2. **Create the virtual environment**
```bash
```

3. **Activate the environment**
```powershell
# Windows PowerShell
.\venv312\Scripts\Activate.ps1

# Windows CMD
.\venv312\Scripts\activate.bat
```

4. **Install dependencies**
```bash
pip install crewai crewai-tools google-generativeai weaviate-client requests beautifulsoup4 pdfplumber streamlit
```

5. **Start local Weaviate (Docker)**
```bash
# Create the folder for Weaviate
mkdir C:\Users\user\Desktop\weaviate_local
cd C:\Users\user\Desktop\weaviate_local

# Create the docker-compose.yml file (see the Weaviate section below)
# Then start Weaviate
docker compose up -d
```

---

## ⚙ Configuration

### Environment variables

Create a `.env` file in `gcrbot/`:

```env
# Google Gemini API
GOOGLE_API_KEY=your_gemini_key
GEMINI_API_KEY=your_gemini_key

# Local Weaviate (Docker)
WEAVIATE_HOST=localhost
WEAVIATE_HTTP_PORT=8080
WEAVIATE_GRPC_PORT=50051

# LLM model
MODEL=gemini-2.5-flash-lite
```

### Local Weaviate (Docker)

The system uses **local Weaviate** as the vector database to index URLs.

#### Docker configuration (`docker-compose.yml`)

```yaml
services:
  weaviate:
    image: semitechnologies/weaviate:latest
    ports:
    
```

#### Useful Docker commands

```bash
# Start Weaviate
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f weaviate

# Stop Weaviate
docker compose down
```

#### Test the Weaviate connection

```bash
# From the gcrbot/src folder
python -m weaviate_setup.test_weaviate_connection
```



---

##  Usage

### CLI Mode (Terminal)

```bash
cd gcrbot\src
python -m gcrbot.main
```

Example interaction:
```
🤖 GCRBOT - ENIG Multi-Agent Assistant
============================================================
👤 You: student timetable week 14
⏳ Processing...
📅 → TIMETABLE Agent

PAGE 1 - Timetable Group GCR1A
Monday
- 08:15 - 09:45: Microwaves1 (BENZINA H.)
...
```

### Streamlit Mode (Web interface)

```bash
streamlit run app.py
```

Open in the browser: `http://localhost:8501`

---

## 📁 File structure

```
GCRBOT/
│
├── README.md                       # This file
├── app.py                          # Streamlit interface
├── images/                         # Interface assets
│
└── src/
    ├── weaviate_setup/             # Weaviate schema setup and connection test
    └── gcrbot/
        │
        ├── main.py                 # CLI entry point
        ├── crew.py                 # Orchestrator and the 4 specialized crews
        ├── service.py              # Service for Streamlit
        ├── gemini.py               # Gemini API configuration
        │
        ├── tools_core_optimized.py # Shared tools
        ├── tools_emploi.py         # PDF extraction tool
        ├── tools_document.py       # Uploaded-document indexing and search tools
        ├── WebExtractor.py         # Semantic deep-crawling engine
        │
        └── config/
            ├── __init__.py
            ├── agents_emploi.yaml        # Timetable Agent config
            ├── tasks_emploi.yaml
            ├── agents_stage.yaml         # Internship Agent config
            ├── tasks_stage.yaml
            ├── agents_conversation.yaml  # Conversation Agent config
            ├── tasks_conversation.yaml
            ├── agents_document.yaml      # Document Agent config
            └── tasks_document.yaml
```

### File descriptions

| File | Description |
|---------|-------------|
| `main.py` | CLI entry point, interactive loop, language detection |
| `crew.py` | Defines the 4 Crews (EmploiCrew, StageCrew, ConversationCrew, DocumentCrew) and the orchestrator |
| `service.py` | Interface between Streamlit and the multi-agent system |
| `gemini.py` | Google Gemini API configuration and initialization |
| `tools_core_optimized.py` | Shared tools: search_weaviate, extract_web_content, smart_site_search, semantic_search_in_text |
| `tools_emploi.py` | Specialized tool: extract_emploi_page (timetable PDF extraction) |
| `WebExtractor.py` | Deep-crawling engine with semantic scoring |

---

## 🤖 The 4 Agents

### 1. Timetable Agent (`emploi_agent`)

**Config files:** `agents_emploi.yaml`, `tasks_emploi.yaml`

**Role:** ENIG Timetable Specialist

**Tools used:**
- `search_weaviate`: finds the timetable's URL
- `extract_emploi_page`: extracts the requested week's PDF content

**Workflow:**
1. Search in Weaviate → gets the URL (students or teachers)
2. PDF extraction → content page by page
3. Formatting → structured reply with the PDF link

**Example questions:**
- "student timetable week 14"
- "teacher timetable week 10"

---

### 2. Internships & Procedures Agent (`stage_agent`)

**Config files:** `agents_stage.yaml`, `tasks_stage.yaml`

**Role:** ENIG Internships, Procedures and Information Specialist

**Tools used:**
- `search_weaviate`: finds the relevant URL
- `smart_site_search`: finds a site's internal pages
- `extract_web_content`: extracts content via deep crawling
- `semantic_search_in_text`: semantic search within text

**Workflow:**
1. Weaviate search → main URL (#1)
2. Intelligent extraction via semantic crawling
3. If insufficient → searches internal pages
4. Formats the reply with sources

**Example questions:**
- "what are the Mitacs programs?"
- "how do I apply for a final-year internship?"
- "ENIG registration procedure"

---

### 3. Conversation Agent (`conversation_agent`)

**Config files:** `agents_conversation.yaml`, `tasks_conversation.yaml`

**Role:** ENIG Students' Virtual Friend

**Tools used:** None (direct LLM replies)

**Message types handled:**
- Greetings: "Hello", "Hi", "مرحبا"
- Mood: "I'm stressed", "How are you?"
- Advice: "Any tips to succeed?"
- Bot: "Who are you?"
- Goodbyes: "Bye", "See you soon"

**Example questions:**
- "Hi!"
- "I'm tired"
- "Thank you very much"

---

### 4. Document Agent (`document_agent`)

**Config files:** `agents_document.yaml`, `tasks_document.yaml`

**Role:** Document Analysis Expert

**Tools used:**
- `process_uploaded_document`: processes and indexes an uploaded file (PDF, DOCX, XLSX, TXT)
- `search_in_documents`: searches across all indexed documents
- `summarize_document`: summarizes a document
- `list_documents`: lists the indexed documents
- `answer_from_document`: answers a question from a document's content

**Workflow:**
1. Upload → the document is processed and indexed
2. Question → relevant passages are retrieved from the indexed content
3. Answer or summary in the user's language, using the recent conversation context

**Example questions:**
- "Summarize the uploaded document"
- "What does this document say about the exam schedule?"

---

## 🛠 The Tools

### 1. `search_weaviate`
```python
search_weaviate(question: str) -> str
```
Searches the Weaviate database and returns the relevant URLs.

### 2. `extract_web_content`
```python
extract_web_content(url: str, search_keywords: str = "") -> str
```
Extracts a web page's content via semantic deep crawling.

### 3. `smart_site_search`
```python
smart_site_search(url: str, search_keywords: str) -> str
```
Searches a site's internal pages matching the keywords.

### 4. `semantic_search_in_text`
```python
semantic_search_in_text(text: str, query: str) -> str
```
Semantic search within a long text.

### 5. `extract_emploi_page`
```python
extract_emploi_page(url: str, semaine: int = None) -> str
```
Extracts a specific week's timetable, including:
- Downloading and parsing the PDF
- Page-by-page extraction (groups GCR1A, GCR1B, etc.)
- Readable text format with days and time slots
- Automatic student/teacher filtering

---

## 🔧 Technologies used

| Technology | Usage |
|-------------|-------------|
| **CrewAI** | Multi-agent framework |
| **Google Gemini** | LLM (gemini-2.5-flash-lite) |
| **Weaviate** | Vector database |
| **pdfplumber** | PDF content extraction |
| **BeautifulSoup** | HTML parsing |
| **Requests** | HTTP requests |
| **Streamlit** | Web interface |
| **Python 3.12** | Programming language |

---



```


---

## 👨‍💻 Author

Project developed for students of the **GCR** track at **ENIG** (National School of Engineers of Gabès).
by student Goubaa Hanen

---

## 📄 License

This project is for educational use at ENIG.

---

**🎓 Enjoy using GCRBOT!**
