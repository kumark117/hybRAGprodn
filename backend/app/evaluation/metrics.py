"""Visible retrieval evaluation metrics: Recall@K, Precision@K, MRR, HitRate, nDCG."""

from __future__ import annotations

import math


def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    top = set(retrieved_ids[:k])
    return len(top.intersection(relevant_ids)) / len(set(relevant_ids))


def precision_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    if k <= 0:
        return 0.0
    top = retrieved_ids[:k]
    hits = sum(1 for item in top if item in set(relevant_ids))
    return hits / k


def mrr(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
    relevant = set(relevant_ids)
    for rank, item in enumerate(retrieved_ids, start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


def hit_rate(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    return 1.0 if set(retrieved_ids[:k]).intersection(relevant_ids) else 0.0


def dcg(relevances: list[float]) -> float:
    return sum(rel / math.log2(idx + 2) for idx, rel in enumerate(relevances))


def ndcg_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    relevant = set(relevant_ids)
    gains = [1.0 if item in relevant else 0.0 for item in retrieved_ids[:k]]
    ideal = sorted(gains, reverse=True)
    ideal_dcg = dcg(ideal)
    if ideal_dcg == 0:
        return 0.0
    return dcg(gains) / ideal_dcg


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
