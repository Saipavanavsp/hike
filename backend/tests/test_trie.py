from app.services.trie import Trie


def build(*terms):
    t = Trie()
    for term in terms:
        if isinstance(term, tuple):
            t.insert(*term)
        else:
            t.insert(term)
    return t


def test_prefix_match_is_case_insensitive():
    t = build("React", "Redux", "Python")
    assert t.suggest("re") == ["React", "Redux"]
    assert t.suggest("RE") == ["React", "Redux"]
    assert t.suggest("py") == ["Python"]


def test_matches_any_word_start():
    t = build("Senior Backend Engineer")
    assert t.suggest("back") == ["Senior Backend Engineer"]
    assert t.suggest("eng") == ["Senior Backend Engineer"]
    assert t.suggest("backend eng") == ["Senior Backend Engineer"]
    assert t.suggest("ackend") == []  # mid-word is not a prefix


def test_weight_orders_suggestions_then_alphabetical():
    t = build(("Java", 2), ("JavaScript", 9), ("Jenkins", 2))
    assert t.suggest("j") == ["JavaScript", "Java", "Jenkins"]


def test_repeated_insert_accumulates_weight():
    t = build("Go", "Docker", "Docker")
    t.insert("Go")
    t.insert("Go")
    assert t.suggest("d") == ["Docker"]
    assert t.suggest("go") == ["Go"]


def test_limit_and_empty_inputs():
    t = build(*[f"Skill{i}" for i in range(20)])
    assert len(t.suggest("skill", limit=5)) == 5
    assert t.suggest("") == []
    assert t.suggest("zzz") == []
    t.insert("   ")
    assert len(t) == 20


def test_contains_and_whitespace_normalisation():
    t = build("Machine   Learning")
    assert "machine learning" in t
    assert "machine" not in t
    assert t.suggest("learn") == ["Machine Learning"]


def test_no_duplicate_when_term_has_repeated_words():
    t = build("Data Data Engineer")
    assert t.suggest("data") == ["Data Data Engineer"]
