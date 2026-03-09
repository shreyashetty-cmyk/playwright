"""
Semantic Memory Module: Stores and retrieves research history using ChromaDB.
Enables cross-verification, knowledge persistence, and semantic search.
"""
import os
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime

try:
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer
    _CHROMADB_AVAILABLE = True
except ImportError:
    _CHROMADB_AVAILABLE = False
    chromadb = None
    SentenceTransformer = None

# Global model cache
_embedding_model = None

MEMORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "semantic_memory_db")


def _get_embedding_model():
    """Lazy load embedding model."""
    global _embedding_model
    if _embedding_model is None and _CHROMADB_AVAILABLE:
        try:
            _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception:
            pass
    return _embedding_model


class SemanticMemory:
    """Manages semantic memory for research history using ChromaDB."""
    
    def __init__(self, collection_name: str = "research_history"):
        if not _CHROMADB_AVAILABLE:
            self.available = False
            return
        
        self.available = True
        os.makedirs(MEMORY_DIR, exist_ok=True)
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=MEMORY_DIR,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        try:
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"description": "Research history and article summaries"}
            )
        except Exception as e:
            print(f"Warning: Could not initialize semantic memory: {e}")
            self.available = False
            return
        
        self.embedding_model = _get_embedding_model()
    
    def store_research(
        self,
        topic: str,
        article_url: str,
        article_text: str,
        summary: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Store a research article in semantic memory."""
        if not self.available or not article_text.strip():
            return False
        
        try:
            # Create document ID
            doc_id = f"{topic}_{article_url}".replace(" ", "_").replace("/", "_")[:200]
            
            # Prepare text for embedding (use summary if available, otherwise excerpt)
            text_to_embed = summary if summary else article_text[:2000]
            
            # Generate embedding
            if self.embedding_model:
                embedding = self.embedding_model.encode(text_to_embed).tolist()
            else:
                # Fallback: use text as-is (ChromaDB will handle embedding)
                embedding = None
            
            # Prepare metadata
            doc_metadata = {
                "topic": topic,
                "url": article_url,
                "timestamp": datetime.now().isoformat(),
                "text_length": len(article_text),
                "has_summary": summary is not None,
                **(metadata or {})
            }
            
            # Store in ChromaDB
            if embedding:
                self.collection.add(
                    ids=[doc_id],
                    embeddings=[embedding],
                    documents=[text_to_embed],
                    metadatas=[doc_metadata]
                )
            else:
                self.collection.add(
                    ids=[doc_id],
                    documents=[text_to_embed],
                    metadatas=[doc_metadata]
                )
            
            return True
        except Exception as e:
            print(f"Warning: Failed to store research in memory: {e}")
            return False
    
    def search_similar(
        self,
        query: str,
        topic: Optional[str] = None,
        n_results: int = 5
    ) -> List[Dict]:
        """Search for similar research articles."""
        if not self.available:
            return []
        
        try:
            # Build query
            where = {}
            if topic:
                where["topic"] = topic
            
            # Generate query embedding
            if self.embedding_model:
                query_embedding = self.embedding_model.encode(query).tolist()
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    where=where if where else None
                )
            else:
                results = self.collection.query(
                    query_texts=[query],
                    n_results=n_results,
                    where=where if where else None
                )
            
            # Format results
            formatted_results = []
            if results.get("ids") and len(results["ids"][0]) > 0:
                for i in range(len(results["ids"][0])):
                    formatted_results.append({
                        "id": results["ids"][0][i],
                        "document": results["documents"][0][i] if results.get("documents") else "",
                        "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                        "distance": results["distances"][0][i] if results.get("distances") else None
                    })
            
            return formatted_results
        except Exception as e:
            print(f"Warning: Semantic search failed: {e}")
            return []
    
    def get_topic_history(self, topic: str) -> List[Dict]:
        """Get all research history for a specific topic."""
        if not self.available:
            return []
        
        try:
            results = self.collection.get(
                where={"topic": topic}
            )
            
            formatted_results = []
            if results.get("ids"):
                for i in range(len(results["ids"])):
                    formatted_results.append({
                        "id": results["ids"][i],
                        "document": results["documents"][i] if results.get("documents") else "",
                        "metadata": results["metadatas"][i] if results.get("metadatas") else {}
                    })
            
            return formatted_results
        except Exception as e:
            print(f"Warning: Failed to get topic history: {e}")
            return []
    
    def cross_verify(
        self,
        new_text: str,
        topic: str,
        threshold: float = 0.7
    ) -> Dict:
        """Cross-verify new research against stored knowledge."""
        if not self.available:
            return {"verified": False, "similar_articles": [], "confidence": 0.0}
        
        # Search for similar content
        similar = self.search_similar(new_text[:500], topic=topic, n_results=3)
        
        # Calculate verification score
        verified = len(similar) > 0
        confidence = 1.0 - (similar[0]["distance"] if similar and similar[0].get("distance") else 1.0)
        
        return {
            "verified": verified and confidence >= threshold,
            "similar_articles": similar,
            "confidence": confidence,
            "match_count": len(similar)
        }


# Global instance
_memory_instance = None

def get_memory() -> SemanticMemory:
    """Get or create global semantic memory instance."""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = SemanticMemory()
    return _memory_instance
