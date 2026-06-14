"""The internal, dependency-free plagiarism engine.

Pure-Python TF-IDF cosine + word-shingle Jaccard, blended into a per-source
similarity, with stdlib ``difflib`` used only on the top-K candidates to pull
out the verbatim passages an instructor can eyeball. No numpy / scikit-learn.

Scale: vectorizing the corpus and scoring target-vs-each is linear in corpus
size; difflib (the only O(n·m) step) is fenced to ``TOP_K_DIFFLIB`` sources, so
hundreds of cross-term submissions stay cheap.
"""

import difflib
import math
from collections import Counter

from .base import (
    STATUS_COMPLETED,
    STATUS_SKIPPED,
    MatchedSource,
    PlagiarismAdapter,
    PlagiarismReport,
)
from .fingerprint import STOPWORDS, shingles, tokenize

# Blend weights: cosine catches paraphrase / vocabulary overlap, Jaccard catches
# verbatim phrase copying. Together they damp both boilerplate false-positives
# and reordering false-negatives.
W_COSINE = 0.6
W_JACCARD = 0.4

KEEP_FLOOR = 5.0  # drop near-zero sources from the stored list (noise)
MAX_SOURCES = 25  # cap rows persisted per result
TOP_K_DIFFLIB = 5  # only the strongest few get passage-level extraction
MAX_PASSAGES = 10  # longest matching blocks kept per source


def _tf(tokens, drop_stopwords=True):
    """Term-frequency Counter; stopwords dropped so shared function words don't
    inflate the cosine."""
    if drop_stopwords:
        return Counter(t for t in tokens if t not in STOPWORDS)
    return Counter(tokens)


def _tfidf_vector(tf, idf):
    """Sparse tf-idf dict for one document given a shared idf table."""
    return {term: freq * idf.get(term, 0.0) for term, freq in tf.items()}


def _l2(vec):
    return math.sqrt(sum(v * v for v in vec.values())) or 1.0


def _cosine(a, b, a_norm, b_norm):
    """Cosine over two sparse tf-idf dicts (iterate the smaller one)."""
    if len(a) > len(b):
        a, b = b, a
    dot = sum(weight * b.get(term, 0.0) for term, weight in a.items())
    return dot / (a_norm * b_norm)


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if not inter:
        return 0.0
    return inter / len(a | b)


def _passages(target_tokens, source_tokens, min_len):
    """Verbatim overlapping passages via difflib, longest first. Each block is a
    contiguous identical token run >= min_len words."""
    sm = difflib.SequenceMatcher(None, target_tokens, source_tokens, autojunk=False)
    blocks = [b for b in sm.get_matching_blocks() if b.size >= min_len]
    blocks.sort(key=lambda b: b.size, reverse=True)
    out = []
    denom = len(target_tokens) or 1
    for b in blocks[:MAX_PASSAGES]:
        out.append(
            {
                "text": " ".join(target_tokens[b.a : b.a + b.size]),
                "ratio": round(b.size / denom, 4),
            }
        )
    return out


class InternalPlagiarismAdapter(PlagiarismAdapter):
    """Compares the target submission against the supplied corpus (all other
    submissions for the same assignment, across every term)."""

    provider_key = "internal"
    requires_account = False

    def check(self, target: dict, corpus: list, config: dict) -> PlagiarismReport:
        ngram = int(config.get("ngram_size") or 5)
        min_len = int(config.get("min_document_length") or 200)
        exclude_same_student = bool(config.get("exclude_same_student", True))
        question_text = config.get("question_text") or ""

        target_text = target.get("text") or ""
        target_tokens = tokenize(target_text)

        # Strip the echoed assignment question so the prompt every student pastes
        # doesn't read as plagiarism (the highest-impact false-positive source).
        question_tokens = set(tokenize(question_text)) if question_text else set()
        if question_tokens:
            target_tokens = [t for t in target_tokens if t not in question_tokens]

        report = PlagiarismReport()
        report.checked_chars = len(target_text)
        report.source_count = len(corpus)
        report.engine_meta = {
            "ngram_size": ngram,
            "weights": [W_COSINE, W_JACCARD],
            "corpus_size": len(corpus),
            "question_stripped": bool(question_tokens),
        }

        if len(target_text) < min_len or not target_tokens:
            report.status = STATUS_SKIPPED
            report.error = "Submission text too short to check."
            return report

        # Tokenize the corpus once; drop empties up front.
        sources = []
        for item in corpus:
            tokens = tokenize(item.get("text") or "")
            if question_tokens:
                tokens = [t for t in tokens if t not in question_tokens]
            if not tokens:
                continue
            sources.append((item, tokens))

        if not sources:
            report.status = STATUS_COMPLETED
            return report

        # --- IDF over target + corpus -------------------------------------
        target_tf = _tf(target_tokens)
        source_tfs = [_tf(toks) for _, toks in sources]
        n_docs = len(sources) + 1
        df = Counter()
        for tf in source_tfs + [target_tf]:
            df.update(tf.keys())
        idf = {term: math.log((1 + n_docs) / (1 + d)) + 1.0 for term, d in df.items()}

        target_vec = _tfidf_vector(target_tf, idf)
        target_norm = _l2(target_vec)
        target_shingles = shingles(target_tokens, ngram)

        # --- score every source (linear) ---------------------------------
        scored = []
        for (item, toks), src_tf in zip(sources, source_tfs):
            src_vec = _tfidf_vector(src_tf, idf)
            cos = _cosine(target_vec, src_vec, target_norm, _l2(src_vec))
            jac = _jaccard(target_shingles, shingles(toks, ngram))
            score = 100.0 * (W_COSINE * cos + W_JACCARD * jac)
            if score < KEEP_FLOOR:
                continue
            same_student = bool(
                target.get("student")
                and item.get("student")
                and target["student"] == item["student"]
            )
            scored.append(
                {
                    "item": item,
                    "tokens": toks,
                    "score": round(score, 2),
                    "same_student": same_student,
                }
            )

        scored.sort(key=lambda s: s["score"], reverse=True)
        scored = scored[:MAX_SOURCES]

        # --- difflib passages for the top-K only --------------------------
        for s in scored[:TOP_K_DIFFLIB]:
            s["passages"] = _passages(target_tokens, s["tokens"], ngram)

        # --- headline score -----------------------------------------------
        relevant = [
            s for s in scored if not (exclude_same_student and s["same_student"])
        ]
        report.overall_score = relevant[0]["score"] if relevant else 0.0

        for s in scored:
            item = s["item"]
            report.matched_sources.append(
                MatchedSource(
                    source_submission=item.get("name"),
                    similarity=s["score"],
                    source_student=item.get("student"),
                    source_student_name=item.get("member_name"),
                    source_course=item.get("course"),
                    same_student=s["same_student"],
                    matched_passages=s.get("passages", []),
                )
            )

        report.status = STATUS_COMPLETED
        return report
