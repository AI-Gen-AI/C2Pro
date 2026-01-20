# tests/utils/scorers.py
from typing import List, Dict, Any, Callable
from dateutil.parser import parse as parse_date
from thefuzz import fuzz

# --- Primitive Scorers ---

def score_string_similarity(expected: str, actual: str) -> float:
    """
    Scores string similarity using fuzzy matching (Levenshtein distance).
    Returns a score between 0.0 and 1.0.
    """
    if not expected and not actual:
        return 1.0
    if not expected or not actual:
        return 0.0
    return fuzz.ratio(str(expected), str(actual)) / 100.0

def score_date_match(expected: str, actual: str) -> float:
    """
    Scores if two date strings represent the same date, regardless of format.
    Returns 1.0 for a match, 0.0 otherwise.
    """
    try:
        expected_date = parse_date(expected).date()
        actual_date = parse_date(actual).date()
        return 1.0 if expected_date == actual_date else 0.0
    except (ValueError, TypeError):
        return 0.0

def score_amount_match(expected: float, actual: float, tolerance: float = 0.01) -> float:
    """
    Scores if two floats are within a given tolerance.
    Returns 1.0 for a match, 0.0 otherwise.
    """
    if expected is None and actual is None:
        return 1.0
    if expected is None or actual is None:
        return 0.0
    return 1.0 if abs(expected - actual) <= tolerance else 0.0

# --- Complex Scorer for Lists ---

def _calculate_f1(tp: int, fp: int, fn: int) -> Dict[str, float]:
    """Helper to calculate precision, recall, and F1 score."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    return {"precision": precision, "recall": recall, "f1_score": f1}

def score_object_list(
    expected_list: List[Dict[str, Any]],
    actual_list: List[Dict[str, Any]],
    id_key: str,
    item_scorer: Callable[[Dict[str, Any], Dict[str, Any]], float],
) -> Dict[str, Any]:
    """
    Compares two lists of objects (e.g., clauses, stakeholders) and calculates
    an F1 score for entity matching and an average score for attribute accuracy.

    Args:
        expected_list: The ground truth list of objects.
        actual_list: The list of objects returned by the AI.
        id_key: The key within each object to use for unique identification (e.g., 'name', 'clause_code').
        item_scorer: A function that takes (expected_item, actual_item) and returns a score [0,1].

    Returns:
        A dictionary containing F1 metrics, attribute score, and discrepancy details.
    """
    expected_map = {item.get(id_key): item for item in expected_list}
    actual_map = {item.get(id_key): item for item in actual_list}

    expected_ids = set(expected_map.keys())
    actual_ids = set(actual_map.keys())

    tp_ids = expected_ids.intersection(actual_ids)
    fp_ids = actual_ids - expected_ids
    fn_ids = expected_ids - actual_ids

    tp = len(tp_ids)
    fp = len(fp_ids)
    fn = len(fn_ids)

    f1_metrics = _calculate_f1(tp, fp, fn)

    # Calculate attribute accuracy for the true positives
    attribute_scores = []
    discrepancies = []
    for item_id in tp_ids:
        expected_item = expected_map[item_id]
        actual_item = actual_map[item_id]
        item_score = item_scorer(expected_item, actual_item)
        attribute_scores.append(item_score)
        if item_score < 1.0:
            discrepancies.append({
                "id": item_id,
                "score": item_score,
                "expected": expected_item,
                "actual": actual_item,
            })

    avg_attribute_score = sum(attribute_scores) / len(attribute_scores) if attribute_scores else 1.0
    
    # Combine F1 for entity matching and attribute score for a final score
    # We can weigh F1 score more heavily as finding the entity is most important.
    final_score = (f1_metrics["f1_score"] * 0.7) + (avg_attribute_score * 0.3)

    return {
        "final_score": final_score,
        "entity_matching": f1_metrics,
        "avg_attribute_score": avg_attribute_score,
        "true_positives": list(tp_ids),
        "false_positives": [actual_map[id] for id in fp_ids],
        "false_negatives": [expected_map[id] for id in fn_ids],
        "attribute_discrepancies": discrepancies,
    }
