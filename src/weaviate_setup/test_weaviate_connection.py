import weaviate

# Connexion Weaviate Local (Docker)
client = weaviate.connect_to_local(
    host="localhost",
    port=   ,
    grpc_port=50051
)

if client.is_ready():
    print("=" * 70)
    print("Connexion reussie - Weaviate Local (Docker)")
    print("=" * 70)
    
    # Afficher les collections existantes
    collections = client.collections.list_all()
    print(f"\nCollections disponibles: {list(collections.keys())}")
    
    # Afficher tous les objets avec leurs vecteurs
    if "WebLink" in collections:
        col = client.collections.get("WebLink")
        count = col.aggregate.over_all(total_count=True).total_count
        print(f"Nombre total d'objets dans WebLink: {count}")
        
        print("\n" + "=" * 70)
        print("LISTE DES LIENS VECTORISES")
        print("=" * 70)
        
        # Recuperer tous les objets avec leurs vecteurs
        results = col.query.fetch_objects(
            limit=100,
            include_vector=True,
            return_properties=["url", "title", "content", "source", "topics"]
        )
        
        for i, obj in enumerate(results.objects, 1):
            print(f"\n{'='*70}")
            print(f"OBJET #{i}")
            print(f"{'='*70}")
            print(f"ID: {obj.uuid}")
            print(f"Titre: {obj.properties.get('title', 'N/A')}")
            print(f"URL: {obj.properties.get('url', 'N/A')}")
            print(f"Source: {obj.properties.get('source', 'N/A')}")
            print(f"Topics: {obj.properties.get('topics', [])}")
            
            # Afficher un extrait du contenu
            content = obj.properties.get('content', '')
            if content:
                print(f"Contenu (extrait): {content[:200]}...")
            
            # Afficher le vecteur (premiers et derniers elements)
            if obj.vector:
                vec = obj.vector.get('default', [])
                if vec:
                    print(f"\nVecteur (dimension: {len(vec)}):")
                    print(f"  Premiers 5 elements: {vec[:5]}")
                    print(f"  Derniers 5 elements: {vec[-5:]}")
            
        print("\n" + "=" * 70)
        print(f"TOTAL: {count} liens vectorises")
        print("=" * 70)
else:
    print("Erreur de connexion")

client.close()
