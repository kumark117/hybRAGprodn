import pytest

from app.evaluation.metrics import hit_rate, mrr, ndcg_at_k, precision_at_k, recall_at_k


def test_retrieval_metrics() -> None:
    retrieved = ["a", "b", "c"]
    relevant = ["c", "z"]
    assert recall_at_k(retrieved, relevant, 3) == 0.5
    assert precision_at_k(retrieved, relevant, 3) == pytest.approx(1 / 3)
    assert mrr(retrieved, relevant) == pytest.approx(1 / 3)
    assert hit_rate(retrieved, relevant, 3) == 1.0
    assert ndcg_at_k(retrieved, relevant, 3) > 0
