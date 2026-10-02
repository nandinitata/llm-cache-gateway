"""Semantic cache logic, tested with hand-made vectors so no model is needed."""
import store


def _vec(*parts):
    """A tiny normalized-ish vector for predictable similarity."""
    return list(parts)


def test_exact_vector_is_a_hit(r):
    cache = store.SemanticCache(r, threshold=0.9)
    v = _vec(1, 0, 0, 0)
    cache.store("capital of France?", v, "Paris", "test")
    hit = cache.lookup(_vec(1, 0, 0, 0))
    assert hit is not None
    assert hit["answer"] == "Paris"
    assert hit["similarity"] > 0.99


def test_near_vector_is_a_hit(r):
    cache = store.SemanticCache(r, threshold=0.9)
    cache.store("q", _vec(1, 0, 0, 0), "A", "test")
    hit = cache.lookup(_vec(0.98, 0.02, 0, 0))
    assert hit is not None
    assert hit["answer"] == "A"


def test_far_vector_is_a_miss(r):
    cache = store.SemanticCache(r, threshold=0.9)
    cache.store("q", _vec(1, 0, 0, 0), "A", "test")
    assert cache.lookup(_vec(0, 1, 0, 0)) is None


def test_empty_cache_is_a_miss(r):
    cache = store.SemanticCache(r, threshold=0.9)
    assert cache.lookup(_vec(1, 0, 0, 0)) is None


def test_stats_track_hits_and_misses(r):
    cache = store.SemanticCache(r, threshold=0.9)
    cache.store("q", _vec(1, 0, 0, 0), "A", "test")
    cache.lookup(_vec(1, 0, 0, 0))   # hit
    cache.lookup(_vec(0, 1, 0, 0))   # miss
    s = cache.stats()
    assert s["hits"] == 1 and s["misses"] == 1
    assert abs(s["hit_rate"] - 0.5) < 1e-9
    assert s["entries"] == 1


def test_clear_empties_everything(r):
    cache = store.SemanticCache(r, threshold=0.9)
    cache.store("q", _vec(1, 0, 0, 0), "A", "test")
    cache.clear()
    assert cache.stats()["entries"] == 0
    assert cache.lookup(_vec(1, 0, 0, 0)) is None
