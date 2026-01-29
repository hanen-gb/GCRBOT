# gcrbot/src/gcrbot/gemini.py

import google.generativeai as genai

# ----------------------------- 
# 🔹 Config Gemini API
# ----------------------------- 
genai.configure(api_key=GEMINI_API_KEY)

def generate_embedding_gemini(text: str):
    """
    Génère un embedding vectoriel avec Google Gemini.
    
    Args:
        text: Le texte à vectoriser
        
    Returns:
        Liste de floats représentant l'embedding, ou None en cas d'erreur
    """
    try:
        # ✅ Syntaxe correcte pour Google Gemini API
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="retrieval_query"  # Pour les requêtes de recherche
        )
        return result['embedding']
        
    except Exception as e:
        print(f"❌ Erreur d'embedding Gemini : {e}")
        return None


def generate_text_gemini(prompt: str):
    """
    Génère du texte avec Gemini pour reformuler les réponses.
    
    Args:
        prompt: Le prompt contenant la question et les résultats
        
    Returns:
        Texte généré par Gemini
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        print(f"❌ Erreur de génération de texte Gemini : {e}")
        return None


# Test si exécuté directement
if __name__ == "__main__":
    # Test embedding
    test_text = "Quels sont les documents nécessaires pour un stage à l'étranger ?"
    embedding = generate_embedding_gemini(test_text)
    
    if embedding:
        print(f"✅ Embedding généré avec succès ({len(embedding)} dimensions)")
        print(f"Premiers éléments : {embedding[:5]}")
    else:
        print("❌ Échec de la génération de l'embedding")
    
    # Test génération de texte
    test_prompt = "Réponds en français : Quels sont les avantages d'un stage à l'étranger ?"
    response = generate_text_gemini(test_prompt)
    if response:
        print(f"\n✅ Texte généré :\n{response}")