#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test du systeme de documents"""

import sys
import os

# Fix encodage Windows
sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'gcrbot', 'src'))

from gcrbot.tools_document import (
    process_document_direct, 
    list_documents_direct, 
    has_indexed_documents,
    get_indexed_filenames
)

print("=== Test list_documents_direct ===")
result = list_documents_direct()
print(result)

print("\n=== Test has_indexed_documents ===")
print(f"Documents indexes: {has_indexed_documents()}")

print("\n=== Test get_indexed_filenames ===")
print(f"Fichiers: {get_indexed_filenames()}")

print("\n=== Test detect_question_type ===")
from gcrbot.crew import detect_question_type

test_questions = [
    "resume le document",
    "de quoi parle le fichier?",
    "liste des documents",
    "c'est quoi Mitacs?",
    "emploi du temps GCR2",
    "bonjour",
    "summarize the file",
    "what is in my document",
]

for q in test_questions:
    result = detect_question_type(q)
    print(f"  '{q}' -> {result}")

print("\n=== Tests termines avec succes ===")
