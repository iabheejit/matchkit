"""Similarity calculations for the matching engine."""
import numpy as np
from typing import List, Optional, Set


def cosine_similarity(a: Optional[List[float]], b: Optional[List[float]]) -> float:
    """Calculate cosine similarity between two embedding vectors.

    Returns a value between -1.0 and 1.0. Returns 0.0 if either vector is None,
    empty, or a zero vector.
    """
    if a is None or b is None:
        return 0.0
    if len(a) == 0 or len(b) == 0:
        return 0.0
    if len(a) != len(b):
        raise ValueError(f"Vector dimension mismatch: {len(a)} vs {len(b)}")

    a_arr = np.array(a, dtype=np.float64)
    b_arr = np.array(b, dtype=np.float64)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a_arr, b_arr) / (norm_a * norm_b))


def jaccard_similarity(set_a: Optional[Set[str]], set_b: Optional[Set[str]]) -> float:
    """Calculate Jaccard similarity between two sets.

    Returns |A ∩ B| / |A ∪ B|. Returns 0.0 if either set is None or empty.
    """
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0
