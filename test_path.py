#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'gcrbot', 'src'))

from gcrbot.tools_document import DOC_DB_PATH, EMBEDDINGS_FILE, list_documents_direct, clear_all_documents

print(f"DOC_DB_PATH: {DOC_DB_PATH}")
print(f"Existe: {os.path.exists(DOC_DB_PATH)}")
print(f"EMBEDDINGS_FILE: {EMBEDDINGS_FILE}")
print(f"Existe: {os.path.exists(EMBEDDINGS_FILE)}")

print("\n=== Contenu docDB ===")
if os.path.exists(DOC_DB_PATH):
    for f in os.listdir(DOC_DB_PATH):
        print(f"  - {f}")

print("\n=== list_documents_direct ===")
print(list_documents_direct())
