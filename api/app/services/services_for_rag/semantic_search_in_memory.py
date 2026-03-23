from dataclasses import dataclass
from pprint import pprint
from typing import List, Tuple, Dict, Any
import numpy as np


@dataclass
class Document:
    """Represents a document with its embedding and metadata"""

    id: str
    # content: str  # or filename
    embedding: np.ndarray
    # source: str = None


# Threshold recommendations for OpenAI embeddings:
SIMILARITY_THRESHOLDS = {
    "very_high": 0.90,  # Almost identical content
    "high": 0.85,  # Very similar content
    "medium": 0.75,  # Similar content (recommended default)
    "low": 0.65,  # Somewhat related content
    "very_low": 0.55,  # Loosely related content
    "experimental_low": 0.2,  # experimental
}


class SemanticSearchInMemory:
    def __init__(self, documents: List[Document]):
        """
        Initialize the semantic search with a list of documents

        Args:
            documents: List of Document objects with embeddings
        """
        self.documents = documents
        # Stack all embeddings into a matrix for efficient computation
        self.embeddings_matrix = np.stack([doc.embedding for doc in documents])

    def cosine_similarity(
        self, query_embedding: np.ndarray, doc_embeddings: np.ndarray
    ) -> np.ndarray:
        """
        Compute cosine similarity between query and document embeddings

        Args:
            query_embedding: Query embedding vector (1536,)
            doc_embeddings: Document embeddings matrix (n_docs, 1536)

        Returns:
            Array of similarity scores
        """
        # Normalize vectors
        query_norm = query_embedding / np.linalg.norm(query_embedding)
        doc_norms = doc_embeddings / np.linalg.norm(
            doc_embeddings, axis=1, keepdims=True
        )

        # Compute cosine similarity
        similarities = np.dot(doc_norms, query_norm)
        return similarities

    def search(
        self, query_embedding: np.ndarray, threshold: float = 0.75, top_k: int = None
    ) -> List[Tuple[Document, float]]:
        """
        Perform semantic search

        Args:
            query_embedding: The embedding of the search query
            threshold: Minimum similarity score (0.75 is a good default for OpenAI embeddings)
            top_k: Maximum number of results to return (None = return all above threshold)

        Returns:
            List of (Document, similarity_score) tuples, sorted by similarity descending
        """
        # Compute similarities
        similarities = self.cosine_similarity(query_embedding, self.embeddings_matrix)
        print("Similarities:")
        pprint(similarities)

        # Filter by threshold
        print("threshold=", threshold)
        above_threshold = similarities >= threshold

        if not np.any(above_threshold):
            return []
        print("above threshold:", above_threshold)

        # Get documents and scores above threshold
        filtered_docs = [
            (self.documents[i], similarities[i])
            for i in range(len(self.documents))
            if above_threshold[i]
        ]

        # Sort by similarity (descending)
        filtered_docs.sort(key=lambda x: x[1], reverse=True)

        # Apply top_k limit if specified
        if top_k is not None:
            filtered_docs = filtered_docs[:top_k]

        print(f"Found {len(filtered_docs)} similar documents")
        return filtered_docs

    def search_with_scores(
        self, query_embedding: np.ndarray, threshold: float = 0.75, top_k: int = None
    ) -> Dict[str, Any]:
        """
        Perform semantic search and return detailed results

        Returns:
            Dictionary with search results and metadata
        """
        results = self.search(query_embedding, threshold, top_k)

        return {
            "query_results": [
                {
                    "document_id": doc.id,
                    # 'content': doc.content,
                    "similarity_score": float(score),
                    # 'source': doc.source
                }
                for doc, score in results
            ],
            "total_matches": len(results),
            "threshold_used": threshold,
            "max_score": float(results[0][1]) if results else 0.0,
            "min_score": float(results[-1][1]) if results else 0.0,
        }
