from app.ml.skills import SkillTaxonomy, get_taxonomy, tokenize


def test_taxonomy_size_and_unique_names():
    tax = get_taxonomy()
    assert len(tax) >= 280
    names = [s.name.lower() for s in tax.skills.values()]
    assert len(names) == len(set(names))


def test_tokenizer_keeps_programming_punctuation():
    assert tokenize("C++, C#, Node.js and ASP.NET.") == ["C++", "C#", "Node.js", "and", "ASP.NET"]
    assert tokenize("CI/CD") == ["CI", "CD"]
    assert tokenize(".NET Core") == ["dotnet", "Core"]


def test_aliases_map_to_canonical_names():
    tax = get_taxonomy()
    text = "Worked with JS, Postgres, k8s, sklearn, GCP and ReactJS."
    assert tax.extract(text) == [
        "JavaScript",
        "PostgreSQL",
        "Kubernetes",
        "scikit-learn",
        "Google Cloud",
        "React",
    ]


def test_longest_match_wins():
    tax = get_taxonomy()
    assert tax.extract("React Native and Spring Boot") == ["React Native", "Spring Boot"]
    assert tax.extract("Apache Kafka") == ["Apache Kafka"]


def test_case_sensitive_skills_ignore_english_words():
    tax = get_taxonomy()
    assert tax.extract("Ready to go in spring, swift delivery") == []
    assert tax.extract("Built services in Go and Swift") == ["Go", "Swift"]


def test_multi_token_aliases():
    tax = get_taxonomy()
    assert "CI/CD" in tax.extract("Set up CI/CD with GitHub Actions")
    assert ".NET" in tax.extract("Migrated to .NET Core 6")
    assert "A/B Testing" in tax.extract("Ran A/B testing on checkout")


def test_extract_deduplicates_in_order():
    tax = get_taxonomy()
    assert tax.extract("Python, python3, Docker, Python") == ["Python", "Docker"]


def test_normalise_user_entered_skills():
    tax = get_taxonomy()
    assert tax.normalise(["js", "go", "Postgres", "My Custom Tool", "javascript"]) == [
        "JavaScript",
        "Go",
        "PostgreSQL",
        "My Custom Tool",
    ]
    assert tax.canonical("   ") is None


def test_search_prefers_prefix_matches():
    tax = get_taxonomy()
    res = tax.search("reac")
    assert res[0] == "React"
    assert "React Native" in res
    assert tax.search("") == []


def test_category_lookup():
    tax = get_taxonomy()
    assert tax.category_of("Flutter") == "mobile"
    assert tax.category_of("Unknown") is None


def test_small_custom_taxonomy():
    tax = SkillTaxonomy([{"name": "Foo", "category": "x", "aliases": ["Foo Bar", ""]}])
    assert tax.extract("foo bar baz foo") == ["Foo"]
