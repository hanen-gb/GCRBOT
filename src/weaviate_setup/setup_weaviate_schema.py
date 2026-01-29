#!/usr/bin/env python
import json
import weaviate
from weaviate.classes.config import Property, DataType, Configure
import openai
import time
import os

# -----------------------------
# 🔹 CONFIGURATION (préférer les variables d'environnement)
# -----------------------------
# Weaviate Local (Docker) - par défaut localhost:8080
WEAVIATE_HOST = os.getenv("WEAVIATE_HOST", "localhost")
WEAVIATE_HTTP_PORT = int(os.getenv("WEAVIATE_HTTP_PORT", "8080"))
WEAVIATE_GRPC_PORT = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))

COLLECTION_NAME = os.getenv("WEAVIATE_COLLECTION", "WebLink")
LINKDB_PATH = os.getenv("LINKDB_PATH", r"C:\Users\Hanen GB\Desktop\GCRBOT\gcrbot\data\linkdb.json")

# Charger le fichier .env
load_dotenv()

# Configuration Gemini via OpenAI-compatible API
openai.api_key = os.getenv("GEMINI_API_KEY")
openai.base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
# -----------------------------
# 🔹 UTILITAIRES
# -----------------------------
def get_client():
    """Connexion Weaviate Local (Docker)."""
    return weaviate.connect_to_local(
        host=WEAVIATE_HOST,
        port=WEAVIATE_HTTP_PORT,
        grpc_port=WEAVIATE_GRPC_PORT,
        skip_init_checks=True
    )

# --- Compatibilité ascendante :
def get_weaviate_client():
    """
    Fonction exposée pour les autres modules qui importent
    get_weaviate_client depuis weaviate_setup.setup_weaviate_schema.
    Elle appelle get_client() en interne.
    """
    return get_client()

def generate_embedding_gemini(text):
    """Créer un embedding vectoriel avec Gemini."""
    try:
        response = openai.embeddings.create(
            model="text-embedding-004",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"❌ Erreur d'embedding : {e}")
        return None

# -----------------------------
# 🔹 PROCESSUS PRINCIPAL (NE S'EXÉCUTE QUE SI LANCÉ DIRECTEMENT)
# -----------------------------
def setup_collection_and_import(linkdb_path=LINKDB_PATH, collection_name=COLLECTION_NAME):
    """
    Fonction réutilisable pour recréer la collection et importer linkdb.json.
    On garde ce code hors du top-level pour éviter d'exécuter lors d'un import.
    """
    print("\n🚀 Initialisation du setup Weaviate...\n")
    client = get_client()

    if not client.is_ready():
        raise SystemExit("❌ Erreur : Weaviate non disponible")

    # 1️⃣ Supprimer collection existante
    try:
        if client.collections.exists(collection_name):
            client.collections.delete(collection_name)
            print(f"🗑️ Ancienne collection '{collection_name}' supprimée.")
            time.sleep(2)
    except Exception as e:
        print("⚠️ Erreur suppression (ignorée si inexistante):", e)

    # 2️⃣ Créer une nouvelle collection
    client.collections.create(
        name=collection_name,
        description="Liens web vectorisés pour le RAG Web de GCRBOT (Mitacs, ENIG, emplois GCR, etc.)",
        vectorizer_config=Configure.Vectorizer.none(),
        properties=[
            Property(name="url", data_type=DataType.TEXT),
            Property(name="title", data_type=DataType.TEXT),
            Property(name="content", data_type=DataType.TEXT),
            Property(name="source", data_type=DataType.TEXT),
            Property(name="topics", data_type=DataType.TEXT_ARRAY)
        ]
    )
    print(f"✅ Nouvelle collection '{collection_name}' créée.\n")

    # 3️⃣ Charger linkdb.json
    try:
        with open(linkdb_path, "r", encoding="utf-8") as f:
            linkdb = json.load(f)
        print(f"✅ {len(linkdb)} liens chargés depuis {linkdb_path}\n")
    except FileNotFoundError:
        print(f"❌ Fichier non trouvé : {linkdb_path}")
        client.close()
        return

    # 4️⃣ Ajouter les objets dans Weaviate
    collection = client.collections.get(collection_name)
    success_count = 0
    error_count = 0

    with collection.batch.dynamic() as batch:
        for item in linkdb:
            try:
                desc = item.get("description", "")
                vector = generate_embedding_gemini(desc)
                if not vector:
                    error_count += 1
                    continue

                batch.add_object(
                    properties={
                        "url": item.get("url", ""),
                        "title": item.get("name", ""),
                        "content": desc,
                        "source": item.get("category", ""),
                        "topics": item.get("topics", [])
                    },
                    vector=vector
                )

                success_count += 1
                print(f"🔗 Ajouté : {item.get('name', 'Sans nom')}")

            except Exception as e:
                error_count += 1
                print(f"❌ Erreur pour {item.get('name', 'inconnu')} : {e}")

    client.close()
    print(f"\n🎯 Terminé ! ✅ {success_count} ajoutés | ❌ {error_count} erreurs\n")


if __name__ == "__main__":
    # si tu exécutes ce fichier directement : lance le setup complet
    setup_collection_and_import()
