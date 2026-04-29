"""Unit tests for each individual analysis task.

These run the Celery tasks as plain functions (via `.run()`), so they don't
need a running Redis or worker. They verify:
  - output shape (all expected keys present)
  - value ranges and types
  - known-correct outputs for fixed inputs

Run with:
    pytest tests/test_tasks.py -v
"""
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.tasks import (  # noqa: E402
    basic_stats,
    readability,
    sentiment,
    keywords,
    entities,
    aggregate_analysis,
)




def test_basic_stats_counts_words_and_sentences():
    text = "The cat sat. The dog ran. The bird flew."
    result = basic_stats.run(text)

    assert result["task"] == "basic_stats"
    assert result["words"] == 9
    assert result["sentences"] == 3
    assert result["characters"] == len(text)
    assert result["unique_words"] == 7  
    assert 0 < result["lexical_diversity"] <= 1.0


def test_basic_stats_handles_empty_string():
    result = basic_stats.run("")
    assert result["words"] == 0
    assert result["sentences"] == 0
    assert result["lexical_diversity"] == 0




def test_readability_returns_score_in_valid_range():
    text = "The cat sat on the mat. The dog ran fast. The bird flew high."
    result = readability.run(text)

    assert result["task"] == "readability"
    
    
    assert -50 <= result["flesch_reading_ease"] <= 121
    assert result["flesch_kincaid_grade"] is not None
    assert isinstance(result["reading_level"], str)
    assert result["reading_level"]  


def test_readability_simple_text_scores_easy():
    
    text = "The cat sat. The dog ran. The bird flew. The fish swam."
    result = readability.run(text)
    
    assert result["flesch_reading_ease"] >= 70


def test_readability_handles_empty_text():
    result = readability.run("")
    assert result["flesch_reading_ease"] is None
    assert result["reading_level"] == "Not enough text"




def test_sentiment_classifies_positive_text():
    text = "I love this. It is amazing and wonderful. Best day ever."
    result = sentiment.run(text)

    assert result["task"] == "sentiment"
    assert result["overall"] == "positive"
    assert result["polarity"] > 0
    assert result["positive_count"] > result["negative_count"]


def test_sentiment_classifies_negative_text():
    text = "This is terrible. I hate it. Worst experience ever, awful."
    result = sentiment.run(text)

    assert result["overall"] == "negative"
    assert result["polarity"] < 0
    assert result["negative_count"] > result["positive_count"]


def test_sentiment_neutral_text():
    text = "The book has 200 pages. It was published last year."
    result = sentiment.run(text)
    assert result["overall"] == "neutral"


def test_sentiment_polarity_in_valid_range():
    result = sentiment.run("Good and bad things happen.")
    assert -1.0 <= result["polarity"] <= 1.0


def test_sentiment_per_sentence_breakdown():
    text = "I love this product. But the delivery was terrible."
    result = sentiment.run(text)

    assert isinstance(result["per_sentence"], list)
    assert len(result["per_sentence"]) == 2
    labels = [s["label"] for s in result["per_sentence"]]
    assert "positive" in labels
    assert "negative" in labels




def test_keywords_finds_repeated_words():
    text = "Python is great. Python is powerful. I love Python programming."
    result = keywords.run(text)

    assert result["task"] == "keywords"
    top_words = [k["word"] for k in result["top_keywords"]]
    assert "python" in top_words
    # "python" appears 3 times so it should be on top
    assert result["top_keywords"][0]["word"] == "python"
    assert result["top_keywords"][0]["count"] == 3


def test_keywords_filters_stopwords():
    text = "The cat and the dog are in the house with the bird."
    result = keywords.run(text)
    top_words = [k["word"] for k in result["top_keywords"]]
    # "the", "and", "are", "in", "with" are all stopwords
    assert "the" not in top_words
    assert "and" not in top_words
    assert "with" not in top_words


def test_keywords_weights_normalized():
    text = "alpha alpha alpha beta beta gamma"
    result = keywords.run(text)
    weights = [k["weight"] for k in result["top_keywords"]]
    
    assert max(weights) == 1.0
    assert all(0 < w <= 1.0 for w in weights)




def test_entities_extracts_email():
    text = "Contact me at hello@example.com for details."
    result = entities.run(text)

    assert result["task"] == "entities"
    assert "hello@example.com" in result["emails"]


def test_entities_extracts_url():
    text = "Visit https://example.com/page or http://site.org for more info."
    result = entities.run(text)
    urls = result["urls"]
    assert any("example.com" in u for u in urls)
    assert any("site.org" in u for u in urls)


def test_entities_extracts_hashtags_and_mentions():
    text = "Big news! #python @alice and @bob are #coding tonight."
    result = entities.run(text)

    assert "#python" in result["hashtags"]
    assert "#coding" in result["hashtags"]
    assert "@alice" in result["mentions"]
    assert "@bob" in result["mentions"]


def test_entities_extracts_dates():
    text = "Meeting on March 15, 2024 and another on 12/25/2023."
    result = entities.run(text)
    dates = result["dates"]
    
    assert len(dates) >= 1
    assert any("2024" in d or "2023" in d for d in dates)


def test_entities_extracts_proper_noun():
    text = "I went to Paris with Maria Gonzalez last week."
    result = entities.run(text)
    proper = [p["name"] for p in result["proper_nouns"]]
    assert any("Paris" in name or "Maria" in name for name in proper)


def test_entities_handles_text_with_no_entities():
    text = "the cat sat on the mat without doing anything special"
    result = entities.run(text)

    assert result["emails"] == []
    assert result["urls"] == []
    assert result["hashtags"] == []
    assert result["mentions"] == []




def test_aggregate_analysis_combines_results():
    fake_results = [
        {"task": "basic_stats", "words": 10},
        {"task": "readability", "flesch_reading_ease": 70.0},
        {"task": "sentiment", "overall": "positive"},
        {"task": "keywords", "top_keywords": []},
        {"task": "entities", "emails": []},
    ]
    combined = aggregate_analysis.run(fake_results)

    assert set(combined.keys()) == {
        "basic_stats", "readability", "sentiment", "keywords", "entities"
    }
    assert combined["basic_stats"]["words"] == 10
    assert combined["sentiment"]["overall"] == "positive"
    
    assert "task" not in combined["basic_stats"]
