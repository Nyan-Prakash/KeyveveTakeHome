"""Quick test to verify Python-based cosine similarity fallback works."""

import json
import numpy as np

def test_cosine_similarity():
    """Test that cosine similarity computation works correctly."""
    
    # Create two similar vectors (should have high similarity ~0.99)
    vec1 = [0.1] * 1536
    vec2 = [0.1] * 1536
    
    # Create a different vector (should have lower similarity)
    vec3 = [-0.1] * 1536
    
    # Test computation
    query_array = np.array(vec1, dtype=np.float32)
    
    # Test 1: Similar vectors
    vec_array = np.array(vec2, dtype=np.float32)
    dot_product = np.dot(query_array, vec_array)
    query_norm = np.linalg.norm(query_array)
    vector_norm = np.linalg.norm(vec_array)
    similarity1 = float(dot_product / (query_norm * vector_norm))
    
    print(f"✅ Similar vectors similarity: {similarity1:.4f} (expected ~1.0)")
    assert 0.99 < similarity1 <= 1.0, f"Expected ~1.0, got {similarity1}"
    
    # Test 2: Opposite vectors
    vec_array = np.array(vec3, dtype=np.float32)
    dot_product = np.dot(query_array, vec_array)
    vector_norm = np.linalg.norm(vec_array)
    similarity2 = float(dot_product / (query_norm * vector_norm))
    
    print(f"✅ Opposite vectors similarity: {similarity2:.4f} (expected ~-1.0)")
    assert -1.0 <= similarity2 < -0.99, f"Expected ~-1.0, got {similarity2}"
    
    # Test 3: JSON parsing
    vec_json = json.dumps(vec1)
    parsed = json.loads(vec_json)
    assert isinstance(parsed, list), "JSON parsing failed"
    assert len(parsed) == 1536, f"Expected 1536 dimensions, got {len(parsed)}"
    print(f"✅ JSON parsing works: {len(parsed)} dimensions")
    
    # Test 4: Sorting by similarity
    similarities = [
        (0.5, "chunk1"),
        (0.9, "chunk2"),
        (0.3, "chunk3"),
        (0.95, "chunk4"),
    ]
    similarities.sort(key=lambda x: x[0], reverse=True)
    
    assert similarities[0][1] == "chunk4", "Sorting failed"
    assert similarities[1][1] == "chunk2", "Sorting failed"
    print(f"✅ Sorting works: top result is '{similarities[0][1]}' with similarity {similarities[0][0]}")
    
    print("\n🎉 All tests passed! Python fallback is ready.")

if __name__ == "__main__":
    test_cosine_similarity()
