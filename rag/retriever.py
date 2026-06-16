"""News RAG with a hybrid, reranked retrieval pipeline.

Pipeline (see retrieve()):
  detect ticker(s) in query
    -> hybrid candidate gen: BM25 (lexical) + cosine (dense), fused via RRF
    -> filter/boost to the asked ticker
    -> recency weighting (gentle, newer ranks higher)
    -> near-duplicate removal (same story, different outlet)
    -> LLM rerank the survivors for final relevance
    -> top-k

We only RAG over text (news headlines + summaries) — live numbers are always
fetched fresh in services/finance_tools.py.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

import numpy as np
import yfinance as yf

from . import news_finnhub
from .bm25 import BM25, tokenize

EMBED_MODEL = "text-embedding-3-small"
RERANK_MODEL = "gpt-4o-mini"

# Tuning knobs.
CANDIDATES = 20          # how many hybrid candidates to consider before rerank
RRF_K = 60               # reciprocal-rank-fusion constant
RECENCY_HALFLIFE = 14    # days; news this old gets a 0.5x recency weight
NEAR_DUP_SIM = 0.92      # cosine >= this between two chunks => duplicates

# Company-name suffixes to drop when deriving aliases.
_NAME_STOP = {
    "inc", "incorporated", "corp", "corporation", "co", "company", "ltd",
    "limited", "plc", "group", "holdings", "holding", "class", "the", "and",
}


@dataclass
class NewsChunk:
    text: str
    title: str
    publisher: str
    link: str
    published: str = ""   # ISO date string, "" if unknown
    ticker: str = ""      # symbol this chunk was fetched under


@dataclass
class NewsIndex:
    chunks: list[NewsChunk] = field(default_factory=list)
    matrix: np.ndarray | None = None         # (n_chunks, dim), L2-normalized
    bm25: BM25 | None = None
    symbols: list[str] = field(default_factory=list)
    aliases: dict[str, list[str]] = field(default_factory=dict)  # symbol -> name words

    def is_empty(self) -> bool:
        return self.matrix is None or len(self.chunks) == 0


# --- fetching -------------------------------------------------------------

def _parse_published(content: dict, item: dict) -> str:
    """Extract an ISO date (YYYY-MM-DD) from the many yfinance news shapes."""
    for key in ("pubDate", "displayTime"):
        val = content.get(key)
        if isinstance(val, str) and val:
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00")).date().isoformat()
            except ValueError:
                pass
    epoch = item.get("providerPublishTime") or content.get("providerPublishTime")
    if isinstance(epoch, (int, float)) and epoch > 0:
        return datetime.fromtimestamp(epoch, tz=timezone.utc).date().isoformat()
    return ""


def fetch_news(symbol: str, limit: int = 20) -> list[NewsChunk]:
    """Pull recent news items for a ticker from Yahoo Finance."""
    chunks: list[NewsChunk] = []
    try:
        items = yf.Ticker(symbol.upper()).news or []
    except Exception:  # noqa: BLE001
        items = []

    for item in items[:limit]:
        content = item.get("content", item)
        title = content.get("title") or item.get("title") or ""
        summary = (content.get("summary") or content.get("description")
                   or item.get("summary") or "")
        publisher = ((content.get("provider") or {}).get("displayName")
                     or item.get("publisher") or "Yahoo Finance")
        link = ((content.get("canonicalUrl") or {}).get("url")
                or content.get("link") or item.get("link") or "")
        published = _parse_published(content, item)
        body = f"{title}. {summary}".strip()
        if len(body) < 10:
            continue
        embed_text = f"[{published}] {body}" if published else body
        chunks.append(NewsChunk(text=embed_text, title=title, publisher=publisher,
                                link=link, published=published, ticker=symbol.upper()))
    return chunks


def fetch_finnhub_recent(symbol: str, days: int = 30) -> list[NewsChunk]:
    """Recent Finnhub company news as NewsChunks (empty if no API key)."""
    if not news_finnhub.has_key():
        return []
    today = datetime.now(tz=timezone.utc).date()
    items = news_finnhub.fetch_company_news(
        symbol, (today - timedelta(days=days)).isoformat(), today.isoformat(), limit=30
    )
    chunks: list[NewsChunk] = []
    for it in items:
        body = f"{it['headline']}. {it['summary']}".strip()
        if len(body) < 10:
            continue
        embed_text = f"[{it['date']}] {body}" if it["date"] else body
        chunks.append(NewsChunk(text=embed_text, title=it["headline"],
                                publisher=it["source"], link=it["url"],
                                published=it["date"], ticker=symbol.upper()))
    return chunks


def _aliases_for(symbol: str) -> list[str]:
    """Lowercased name words for a symbol, e.g. AAPL -> ['aapl','apple']."""
    out = {symbol.lower()}
    try:
        info = yf.Ticker(symbol.upper()).info or {}
        name = info.get("shortName") or info.get("longName") or ""
        for w in re.findall(r"[A-Za-z]+", name.lower()):
            if len(w) >= 3 and w not in _NAME_STOP:
                out.add(w)
    except Exception:  # noqa: BLE001
        pass
    return sorted(out)


# --- embedding + index build ---------------------------------------------

def _embed(client, texts: list[str]) -> np.ndarray:
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    vecs = np.array([d.embedding for d in resp.data], dtype=np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vecs / norms


def build_index(client, symbols: list[str], per_symbol: int = 15) -> NewsIndex:
    """Fetch news per symbol, embed, and build the hybrid index."""
    symbols = [s.upper() for s in symbols if s]
    all_chunks: list[NewsChunk] = []
    seen: set[str] = set()
    for sym in symbols:
        for chunk in fetch_news(sym, limit=per_symbol) + fetch_finnhub_recent(sym):
            key = re.sub(r"\s+", " ", chunk.title.lower()).strip()
            if key and key not in seen:
                seen.add(key)
                all_chunks.append(chunk)

    if not all_chunks:
        return NewsIndex(symbols=symbols)

    matrix = _embed(client, [c.text for c in all_chunks])
    bm25 = BM25([tokenize(c.text) for c in all_chunks])
    aliases = {sym: _aliases_for(sym) for sym in symbols}
    return NewsIndex(chunks=all_chunks, matrix=matrix, bm25=bm25,
                     symbols=symbols, aliases=aliases)


# --- retrieval pipeline ---------------------------------------------------

def _detect_tickers(query: str, index: NewsIndex) -> set[str]:
    """Which indexed tickers does the query mention (by symbol or name word)?"""
    q = query.lower()
    hits: set[str] = set()
    for sym, words in index.aliases.items():
        for w in words:
            if re.search(rf"\b{re.escape(w)}\b", q):
                hits.add(sym)
                break
    return hits


def _rrf(rank_lists: list[list[int]], k: int = RRF_K) -> dict[int, float]:
    """Reciprocal Rank Fusion: combine ranked id lists without score scaling."""
    fused: dict[int, float] = defaultdict(float)
    for ranks in rank_lists:
        for rank, idx in enumerate(ranks):
            fused[idx] += 1.0 / (k + rank)
    return fused


def _recency_weight(published: str, today: date) -> float:
    if not published:
        return 0.85  # slight penalty for undated items
    try:
        age = max((today - date.fromisoformat(published)).days, 0)
    except ValueError:
        return 0.85
    return 0.5 ** (age / RECENCY_HALFLIFE)


def _dedup(cand_idx: list[int], index: NewsIndex) -> list[int]:
    """Drop near-duplicate chunks (same story, different outlet), keep first."""
    kept: list[int] = []
    for i in cand_idx:
        vi = index.matrix[i]
        if all(float(vi @ index.matrix[j]) < NEAR_DUP_SIM for j in kept):
            kept.append(i)
    return kept


def _llm_rerank(client, query: str, cand_idx: list[int], index: NewsIndex, k: int) -> list[int]:
    """Reorder candidates by true relevance to the query with one cheap LLM call."""
    if len(cand_idx) <= 1:
        return cand_idx[:k]
    listing = "\n".join(
        f"{n}. [{index.chunks[i].published or 'n/a'}] {index.chunks[i].title}"
        for n, i in enumerate(cand_idx)
    )
    prompt = (
        f"Query: {query}\n\nCandidate articles:\n{listing}\n\n"
        f"Return the {min(k, len(cand_idx))} most relevant article numbers for the query, "
        f'most relevant first, as JSON: {{"ranking": [numbers]}}. '
        "Only include genuinely relevant ones."
    )
    try:
        resp = client.chat.completions.create(
            model=RERANK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        order = json.loads(resp.choices[0].message.content).get("ranking", [])
        picked = [cand_idx[n] for n in order if isinstance(n, int) and 0 <= n < len(cand_idx)]
        if picked:
            return picked[:k]
    except Exception:  # noqa: BLE001 - fall back to fusion order
        pass
    return cand_idx[:k]


def retrieve(client, index: NewsIndex, query: str, k: int = 5) -> list[NewsChunk]:
    """Hybrid + reranked retrieval. Returns up to k relevant chunks."""
    if index.is_empty():
        return []

    # 1. Dense (cosine) and lexical (BM25) ranked lists.
    qvec = _embed(client, [query])[0]
    cos = index.matrix @ qvec
    cos_rank = list(np.argsort(cos)[::-1][:50])
    bm = np.array(index.bm25.scores(query)) if index.bm25 else np.zeros(len(index.chunks))
    bm_rank = list(np.argsort(bm)[::-1][:50])

    # 2. Fuse with RRF.
    fused = _rrf([cos_rank, bm_rank])

    # 3. Ticker filter: if the query names indexed tickers, keep only those
    #    (fall back to all if that leaves too little).
    wanted = _detect_tickers(query, index)
    if wanted:
        filtered = {i: s for i, s in fused.items() if index.chunks[i].ticker in wanted}
        if len(filtered) >= 3:
            fused = filtered

    # 4. Recency weighting.
    today = datetime.now(tz=timezone.utc).date()
    for i in list(fused):
        fused[i] *= _recency_weight(index.chunks[i].published, today)

    # 5. Top candidates -> near-dup removal.
    ranked = sorted(fused, key=fused.get, reverse=True)[:CANDIDATES]
    # Require a minimum lexical OR dense signal so we can say "no news".
    ranked = [i for i in ranked if cos[i] > 0.15 or bm[i] > 0.0]
    if not ranked:
        return []
    ranked = _dedup(ranked, index)

    # 6. LLM rerank for final relevance.
    final = _llm_rerank(client, query, ranked, index, k)
    return [index.chunks[i] for i in final]


def format_context(chunks: list[NewsChunk]) -> str:
    """Render retrieved chunks as a numbered, citable context block."""
    if not chunks:
        return "No relevant news found."
    lines = []
    for i, c in enumerate(chunks, 1):
        d = f" — {c.published}" if c.published else ""
        tk = f" [{c.ticker}]" if c.ticker else ""
        lines.append(f"[{i}]{d}{tk} {c.title} ({c.publisher})\n{c.text}\nSource: {c.link}")
    return "\n\n".join(lines)
