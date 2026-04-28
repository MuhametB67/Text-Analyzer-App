"""
Five analysis tasks run in parallel on the submitted text:
  1. basic_stats       — chars, words, sentences, paragraphs, reading time
  2. readability       — Flesch Reading Ease, Flesch-Kincaid grade
  3. sentiment         — per-sentence sentiment + overall score
  4. keywords          — top keywords by TF (with stopword filtering)
  5. entities_and_structure — detect emails, URLs, numbers, dates, @mentions, #hashtags

Each task sleeps briefly so progress is visible in the UI.
"""
import re
import time
import math
from collections import Counter
from .celery_app import celery_app


# ---------- Helpers ----------

STOPWORDS = {
    "a","about","above","after","again","against","all","am","an","and","any","are","as","at",
    "be","because","been","before","being","below","between","both","but","by",
    "can","cannot","could",
    "did","do","does","doing","don","down","during",
    "each","else","ever",
    "few","for","from","further",
    "had","has","have","having","he","her","here","hers","herself","him","himself","his","how",
    "i","if","in","into","is","it","its","itself",
    "just",
    "let",
    "me","more","most","my","myself",
    "no","nor","not","now",
    "of","off","on","once","only","or","other","our","ours","ourselves","out","over","own",
    "s","same","she","should","so","some","such",
    "t","than","that","the","their","theirs","them","themselves","then","there","these",
    "they","this","those","through","to","too",
    "under","until","up",
    "very",
    "was","we","were","what","when","where","which","while","who","whom","why","will","with","would",
    "you","your","yours","yourself","yourselves",
    "im","ive","id","ill","dont","doesnt","didnt","cant","wont","isnt","arent","wasnt","werent",
    "has","hasnt","hadnt","youre","youve","youd","youll","theyre","theyve","theyd","theyll",
    "whats","thats","theres","heres","lets",
}

POSITIVE_WORDS = {
    "good","great","excellent","amazing","wonderful","fantastic","love","loved","best","awesome",
    "brilliant","outstanding","perfect","beautiful","happy","joy","pleased","delighted","thrilled",
    "superb","magnificent","marvelous","terrific","fabulous","impressive","remarkable","exceptional",
    "positive","success","successful","achieve","achieved","win","wins","winning","benefit","benefits",
    "effective","efficient","helpful","useful","valuable","worthwhile","enjoy","enjoyed","enjoyable",
    "recommend","recommended","nice","kind","friendly","warm","strong","smart","clever","genius",
    "easy","simple","fast","quick","fresh","new","innovative","clean","clear","safe","secure",
}

NEGATIVE_WORDS = {
    "bad","terrible","awful","horrible","worst","hate","hated","disappointing","poor","sad",
    "angry","frustrated","annoying","broken","failed","failure","fail","problem","problems","issue",
    "issues","bug","bugs","wrong","error","errors","crash","slow","difficult","hard","confusing",
    "useless","worthless","waste","wasted","boring","dull","weak","ugly","dirty","rude","mean",
    "hostile","aggressive","negative","pain","painful","suffer","suffering","cry","crying",
    "dead","die","died","killed","destroyed","damaged","broken","ruined","lost","lose","losing",
    "dangerous","unsafe","risky","scam","fraud","fake","lie","lies","cheat","cheated","stole","stolen",
}


def split_sentences(text: str) -> list:
    """Simple but decent sentence splitter."""
    text = text.strip()
    if not text:
        return []
    # Handle common abbreviations crudely
    text = re.sub(r"\b(Mr|Mrs|Ms|Dr|Prof|Sr|Jr|St|vs|etc|i\.e|e\.g)\.", r"\1<DOT>", text, flags=re.IGNORECASE)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'])", text)
    return [p.replace("<DOT>", ".").strip() for p in parts if p.strip()]


def words_of(text: str) -> list:
    return re.findall(r"\b[\w']+\b", text.lower())


def count_syllables(word: str) -> int:
    """Rough syllable estimator — good enough for readability scoring."""
    word = word.lower()
    if len(word) <= 3:
        return 1
    word = re.sub(r"(?:[^laeiouy]|ed|[^laeiouy]e)$", "", word)
    word = re.sub(r"^y", "", word)
    matches = re.findall(r"[aeiouy]{1,2}", word)
    return max(1, len(matches))


# ---------- Tasks ----------

@celery_app.task(name="basic_stats", bind=True)
def basic_stats(self, text: str) -> dict:
    time.sleep(0.4)
    chars = len(text)
    chars_no_spaces = len(re.sub(r"\s", "", text))
    words = words_of(text)
    word_count = len(words)
    sentences = split_sentences(text)
    sentence_count = len(sentences)
    paragraphs = [p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    avg_word_len = round(sum(len(w) for w in words) / word_count, 2) if word_count else 0
    avg_sentence_len = round(word_count / sentence_count, 2) if sentence_count else 0
    # Average adult reads ~230 wpm
    reading_time_min = round(word_count / 230, 2) if word_count else 0
    speaking_time_min = round(word_count / 140, 2) if word_count else 0
    unique_words = len(set(words))
    lexical_diversity = round(unique_words / word_count, 3) if word_count else 0

    return {
        "task": "basic_stats",
        "characters": chars,
        "characters_no_spaces": chars_no_spaces,
        "words": word_count,
        "unique_words": unique_words,
        "lexical_diversity": lexical_diversity,
        "sentences": sentence_count,
        "paragraphs": len(paragraphs),
        "avg_word_length": avg_word_len,
        "avg_sentence_length": avg_sentence_len,
        "reading_time_minutes": reading_time_min,
        "speaking_time_minutes": speaking_time_min,
        "worker": self.request.hostname,
    }


@celery_app.task(name="readability", bind=True)
def readability(self, text: str) -> dict:
    time.sleep(0.5)
    words = words_of(text)
    sentences = split_sentences(text)
    word_count = len(words)
    sentence_count = len(sentences)

    if word_count == 0 or sentence_count == 0:
        return {
            "task": "readability",
            "flesch_reading_ease": None,
            "flesch_kincaid_grade": None,
            "reading_level": "Not enough text",
            "worker": self.request.hostname,
        }

    total_syllables = sum(count_syllables(w) for w in words)
    words_per_sentence = word_count / sentence_count
    syllables_per_word = total_syllables / word_count

    flesch = 206.835 - 1.015 * words_per_sentence - 84.6 * syllables_per_word
    fk_grade = 0.39 * words_per_sentence + 11.8 * syllables_per_word - 15.59

    flesch = round(flesch, 1)
    fk_grade = round(fk_grade, 1)

    if flesch >= 90:
        level = "Very easy (5th grade)"
    elif flesch >= 80:
        level = "Easy (6th grade)"
    elif flesch >= 70:
        level = "Fairly easy (7th grade)"
    elif flesch >= 60:
        level = "Standard (8-9th grade)"
    elif flesch >= 50:
        level = "Fairly difficult (10-12th grade)"
    elif flesch >= 30:
        level = "Difficult (college)"
    else:
        level = "Very difficult (college graduate)"

    return {
        "task": "readability",
        "flesch_reading_ease": flesch,
        "flesch_kincaid_grade": fk_grade,
        "reading_level": level,
        "avg_syllables_per_word": round(syllables_per_word, 2),
        "worker": self.request.hostname,
    }


@celery_app.task(name="sentiment", bind=True)
def sentiment(self, text: str) -> dict:
    time.sleep(0.6)
    sentences = split_sentences(text)
    per_sentence = []
    total_pos = 0
    total_neg = 0

    for s in sentences:
        s_words = set(words_of(s))
        pos = len(s_words & POSITIVE_WORDS)
        neg = len(s_words & NEGATIVE_WORDS)
        score = pos - neg
        if score > 0:
            label = "positive"
        elif score < 0:
            label = "negative"
        else:
            label = "neutral"
        per_sentence.append({
            "text": s[:200] + ("..." if len(s) > 200 else ""),
            "score": score,
            "label": label,
            "positive_hits": pos,
            "negative_hits": neg,
        })
        total_pos += pos
        total_neg += neg

    overall_score = total_pos - total_neg
    if overall_score > 1:
        overall = "positive"
    elif overall_score < -1:
        overall = "negative"
    else:
        overall = "neutral"

    total_hits = total_pos + total_neg
    polarity = round((total_pos - total_neg) / total_hits, 3) if total_hits else 0.0

    return {
        "task": "sentiment",
        "overall": overall,
        "overall_score": overall_score,
        "polarity": polarity,  # -1.0 to 1.0
        "positive_count": total_pos,
        "negative_count": total_neg,
        "per_sentence": per_sentence,
        "worker": self.request.hostname,
    }


@celery_app.task(name="keywords", bind=True)
def keywords(self, text: str, top_n: int = 15) -> dict:
    time.sleep(0.5)
    all_words = words_of(text)
    filtered = [w for w in all_words if w not in STOPWORDS and len(w) > 2 and not w.isdigit()]
    freq = Counter(filtered)
    top = freq.most_common(top_n)
    max_count = top[0][1] if top else 1

    keywords_list = [
        {"word": w, "count": c, "weight": round(c / max_count, 3)}
        for w, c in top
    ]

    # Bigrams (two-word phrases) — also useful
    bigrams = Counter()
    for i in range(len(filtered) - 1):
        bg = f"{filtered[i]} {filtered[i + 1]}"
        bigrams[bg] += 1
    top_bigrams = [{"phrase": p, "count": c} for p, c in bigrams.most_common(8) if c > 1]

    return {
        "task": "keywords",
        "top_keywords": keywords_list,
        "top_phrases": top_bigrams,
        "total_unique": len(freq),
        "worker": self.request.hostname,
    }


@celery_app.task(name="entities", bind=True)
def entities(self, text: str) -> dict:
    time.sleep(0.4)
    emails = list(set(re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", text)))
    urls = list(set(re.findall(r"https?://[^\s<>\"']+", text)))
    hashtags = list(set(re.findall(r"#\w+", text)))
    mentions = list(set(re.findall(r"(?<!\w)@\w+", text)))
    numbers = re.findall(r"\b\d[\d,]*\.?\d*\b", text)
    dates = list(set(re.findall(
        r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
        r"\d{4}-\d{2}-\d{2}|"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:,?\s+\d{4})?)\b",
        text, flags=re.IGNORECASE,
    )))

    # Capitalized sequences = rough "proper noun" detection (names, places, brands).
    # Skip words that appear right after sentence-ending punctuation to reduce false positives.
    text_for_proper = re.sub(r"[.!?]\s+([A-Z][a-z]+)", lambda m: ". " + m.group(1).lower(), text)
    # Also drop capitalized word if it's the very first token of the whole text.
    text_for_proper = re.sub(r"^([A-Z][a-z]+)", lambda m: m.group(1).lower(), text_for_proper)
    proper_nouns = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text_for_proper)
    # Filter common junk
    COMMON = {"The", "A", "An", "And", "But", "Or", "However", "Also", "Email", "Visit", "Click", "See"}
    proper_counter = Counter(p for p in proper_nouns if p not in COMMON)
    top_proper = [{"name": n, "count": c} for n, c in proper_counter.most_common(10) if c >= 1 and len(n) > 2]

    return {
        "task": "entities",
        "emails": emails,
        "urls": urls,
        "hashtags": hashtags,
        "mentions": mentions,
        "numbers_found": len(numbers),
        "dates": dates,
        "proper_nouns": top_proper,
        "worker": self.request.hostname,
    }


@celery_app.task(name="aggregate_analysis")
def aggregate_analysis(results: list) -> dict:
    """Combine the 5 parallel analyses into one flat response."""
    combined = {}
    for r in results:
        task_name = r.pop("task", "unknown")
        combined[task_name] = r
    return combined
