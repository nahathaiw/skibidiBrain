"""Tiny dependency-free BM25 for keyword (lexical) retrieval.

Used alongside dense embeddings for hybrid search — BM25 catches exact terms
(ticker symbols, product/person names, phrases like "DMA probe") that embeddings
tend to blur. Corpora here are small (hundreds of headlines), so the simple
O(query_terms x docs) scoring is plenty fast.
"""
from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if len(t) >= 2]


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = docs
        self.n = len(docs)
        self.doc_len = [len(d) for d in docs]
        self.avgdl = (sum(self.doc_len) / self.n) if self.n else 0.0
        self.tf = [Counter(d) for d in docs]
        df: Counter = Counter()
        for d in docs:
            df.update(set(d))
        # Robertson-Sparck-Jones idf with +1 to keep it non-negative.
        self.idf = {
            t: math.log(1 + (self.n - f + 0.5) / (f + 0.5)) for t, f in df.items()
        }

    def scores(self, query: str) -> list[float]:
        out = [0.0] * self.n
        for term in set(tokenize(query)):
            idf = self.idf.get(term)
            if idf is None:
                continue
            for i in range(self.n):
                f = self.tf[i].get(term, 0)
                if not f:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * self.doc_len[i] / self.avgdl)
                out[i] += idf * (f * (self.k1 + 1)) / denom
        return out
