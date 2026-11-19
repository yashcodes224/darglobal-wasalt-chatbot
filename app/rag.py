"""
Hybrid retriever combining:
1. BM25 keyword search
2. SentenceTransformer semantic search
3. Reciprocal Rank Fusion (RRF)

Input: data/processed/chunks.jsonl
"""

import json
import math
import re
from collections import Counter
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

BM25_WEIGHT = 0.45
VECTOR_WEIGHT = 0.55
RRF_K = 60

CANDIDATE_MULTIPLIER = 4
MIN_CANDIDATES = 20


# ---------------------------------------------------------
# Text processing
# ---------------------------------------------------------

STOP = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on",
    "for", "is", "are", "was", "were", "be", "been", "it",
    "its", "this", "that", "with", "as", "at", "by", "from",
    "do", "does", "did", "i", "you", "me", "my", "we", "our",
    "can", "could", "would", "should", "what", "which", "who",
    "whom", "how", "tell", "about", "please", "any", "there",
    "have", "has", "had", "show", "give", "list", "all", "me",
}

LISTING_INTENT = re.compile(
    r"\b(all|list|every|which|how many|show|projects? in|"
    r"properties in|available|property|properties|villa|"
    r"villas|apartment|apartments|bedroom|bedrooms|"
    r"for sale|for rent|price|budget)\b",
    re.I,
)

MONTHS = {
    "january": "jan",
    "february": "feb",
    "march": "mar",
    "april": "apr",
    "june": "jun",
    "july": "jul",
    "august": "aug",
    "september": "sep",
    "october": "oct",
    "november": "nov",
    "december": "dec",
}

# Query-side vocabulary expansion
EXPAND = {
    "own": ["joint", "venture", "arkan", "quara"],
    "owner": ["joint", "venture", "arkan", "quara"],
    "ownership": ["joint", "venture", "arkan", "quara"],
    "found": ["joint", "venture"],
    "news": ["press"],
    "announc": ["press"],
    "announcement": ["press"],
    "latest": ["press"],
    "recent": ["press"],
    "partner": ["collaboration", "brand"],
    "contact": ["support", "phone"],
    "price": ["cost", "sar"],
    "cost": ["price"],
    "invest": ["investor", "investment"],
}


def stem(token):
    """Lightweight English suffix normalization."""

    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        token = token[:-1]

    for suffix in ("ing", "ed"):
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            token = token[:-len(suffix)]
            break

    if len(token) > 4 and token.endswith("e"):
        token = token[:-1]

    return token


def tokenize(text):
    """Tokenize English and Arabic text."""

    text = str(text or "").lower()

    tokens = re.findall(
        r"[a-z0-9]+|[\u0600-\u06ff]+",
        text,
    )

    output = []

    for token in tokens:
        if token in STOP:
            continue

        token = MONTHS.get(token, token)
        output.append(stem(token))

    return output


def expand_tokens(tokens):
    """Add related terms to improve keyword matching."""

    extra = []

    for token in tokens:
        extra.extend(EXPAND.get(token, []))

    return tokens + [stem(token) for token in extra]


# ---------------------------------------------------------
# Listing intent
# ---------------------------------------------------------

def wants_listing(query):
    return bool(LISTING_INTENT.search(str(query or "")))


# ---------------------------------------------------------
# Hybrid index
# ---------------------------------------------------------

class HybridIndex:

    def __init__(
        self,
        chunks,
        model_name=EMBEDDING_MODEL,
        bm25_weight=BM25_WEIGHT,
        vector_weight=VECTOR_WEIGHT,
        rrf_k=RRF_K,
    ):
        self.chunks = chunks

        self.bm25_weight = bm25_weight
        self.vector_weight = vector_weight
        self.rrf_k = rrf_k

        if not chunks:
            self.documents = []
            self.bm25 = None
            self.model = None
            self.embeddings = None
            return

        # Build searchable text for every chunk.
        self.documents = [
            self._document_text(chunk)
            for chunk in chunks
        ]

        # Build BM25 index.
        tokenized_documents = [
            tokenize(document)
            for document in self.documents
        ]

        self.bm25 = BM25Okapi(tokenized_documents)

        # Load embedding model.
        print(f"Loading embedding model: {model_name}")

        self.model = SentenceTransformer(model_name)

        # Create normalized document embeddings.
        print("Creating document embeddings...")

        self.embeddings = self.model.encode(
            self.documents,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=True,
        )

        self.embeddings = np.asarray(
            self.embeddings,
            dtype=np.float32,
        )

        print(f"Hybrid index ready: {len(chunks)} chunks")

    @staticmethod
    def _document_text(chunk):
        """
        Include metadata in the searchable text so that
        property questions can match listing information.
        """

        fields = [
            chunk.get("title", ""),
            chunk.get("source", ""),
            chunk.get("listing_type", ""),
            chunk.get("location", ""),
            chunk.get("country", ""),
            chunk.get("property_type", ""),
            str(chunk.get("price", "")),
            str(chunk.get("bedrooms", "")),
            str(chunk.get("area_sqm", "")),
            chunk.get("chunk_text", ""),
        ]

        return " ".join(
            str(field)
            for field in fields
            if field not in (None, "")
        )

    def search(self, query, k=6):
        """
        Return the top-k chunks using hybrid retrieval.

        The returned dictionaries preserve the original chunk
        fields and include a combined retrieval score.
        """

        if not self.chunks or self.bm25 is None:
            return []

        query = str(query or "").strip()

        if not query:
            return []

        query_tokens = expand_tokens(tokenize(query))

        if not query_tokens:
            return []

        total_docs = len(self.chunks)

        candidate_count = min(
            total_docs,
            max(k * CANDIDATE_MULTIPLIER, MIN_CANDIDATES),
        )

        # ---------------------------------------------
        # 1. BM25 keyword retrieval
        # ---------------------------------------------

        bm25_scores = self.bm25.get_scores(query_tokens)

        bm25_indices = np.argsort(bm25_scores)[::-1][
            :candidate_count
        ]

        bm25_ranks = {}

        for rank, index in enumerate(bm25_indices, start=1):
            if bm25_scores[index] > 0:
                bm25_ranks[int(index)] = rank

        # ---------------------------------------------
        # 2. Semantic vector retrieval
        # ---------------------------------------------

        query_embedding = self.model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        query_embedding = np.asarray(
            query_embedding[0],
            dtype=np.float32,
        )

        similarities = self.embeddings @ query_embedding

        vector_indices = np.argsort(similarities)[::-1][
            :candidate_count
        ]

        vector_ranks = {
            int(index): rank
            for rank, index in enumerate(vector_indices, start=1)
        }

        # ---------------------------------------------
        # 3. Reciprocal Rank Fusion
        # ---------------------------------------------

        candidate_indices = (
            set(bm25_ranks.keys())
            | set(vector_ranks.keys())
        )

        fused_scores = {}

        for index in candidate_indices:

            score = 0.0

            if index in bm25_ranks:
                score += (
                    self.bm25_weight
                    / (self.rrf_k + bm25_ranks[index])
                )

            if index in vector_ranks:
                score += (
                    self.vector_weight
                    / (self.rrf_k + vector_ranks[index])
                )

            fused_scores[index] = score

        ranked_indices = sorted(
            fused_scores,
            key=lambda index: fused_scores[index],
            reverse=True,
        )

        results = []

        for index in ranked_indices[:k]:
            chunk = dict(self.chunks[index])

            chunk["score"] = round(
                fused_scores[index],
                6,
            )

            chunk["bm25_rank"] = bm25_ranks.get(index)
            chunk["vector_rank"] = vector_ranks.get(index)

            results.append(chunk)

        return results


# ---------------------------------------------------------
# Load JSONL and create index
# ---------------------------------------------------------

def load_chunks(path="data/processed/chunks.jsonl"):

    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run: python process_data.py"
        )

    chunks = []

    with file_path.open("r", encoding="utf-8") as file:

        for line_number, line in enumerate(file, start=1):

            if not line.strip():
                continue

            try:
                chunk = json.loads(line)

            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON on line {line_number} "
                    f"of {path}: {error}"
                ) from error

            if not isinstance(chunk, dict):
                continue

            chunk.setdefault("title", "")
            chunk.setdefault("source", "unknown")
            chunk.setdefault("url", "")
            chunk.setdefault("chunk_text", "")

            chunks.append(chunk)

    return chunks


def load_index(path="data/processed/chunks.jsonl"):

    chunks = load_chunks(path)

    if not chunks:
        raise ValueError(
            f"No chunks found in {path}. "
            "Check your raw data and run process_data.py."
        )

    return HybridIndex(chunks)