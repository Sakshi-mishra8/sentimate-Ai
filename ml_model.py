"""
ml_model.py - our own trained machine-learning model (no scikit-learn needed).

Algorithm : Multinomial Naive Bayes on word 1-2 grams, written in pure Python.
Training  : python train_model.py                -> uses the built-in generated dataset
            python train_model.py reviews.csv    -> uses YOUR labelled data (columns: text,label)

NOTE: the built-in dataset is generated from templates, so it is only a starter.
For real accuracy, train on a real review dataset (Amazon / Flipkart / Kaggle reviews).
"""

import csv
import json
import math
import pickle
import random
import re
from collections import Counter
from pathlib import Path

MODEL_PATH = Path(__file__).with_name("model.pkl")
META_PATH = Path(__file__).with_name("model_meta.json")
LABELS = ["Negative", "Neutral", "Positive"]
_TOKEN = re.compile(r"[a-zA-Z']+")
_model = None


def _features(text: str):
    toks = _TOKEN.findall(text.lower())
    return toks + [a + "_" + b for a, b in zip(toks, toks[1:])]


class NaiveBayes:
    """Counts how often each word / word-pair appears in each class, then uses Bayes' rule."""

    def __init__(self, alpha: float = 0.5):
        self.alpha = alpha

    def fit(self, texts, labels):
        self.classes_ = sorted(set(labels))
        self.n_docs = Counter(labels)
        self.counts = {c: Counter() for c in self.classes_}
        self.vocab = set()
        for text, label in zip(texts, labels):
            feats = _features(text)
            self.counts[label].update(feats)
            self.vocab.update(feats)
        self.totals = {c: sum(self.counts[c].values()) for c in self.classes_}
        return self

    def predict_proba(self, texts):
        out, v, n = [], len(self.vocab), sum(self.n_docs.values())
        for text in texts:
            feats = [f for f in _features(text) if f in self.vocab]
            temper = 1 + 0.6 * math.sqrt(len(feats))   # stops long texts from giving 100% certainty
            logs = []
            for c in self.classes_:
                ll = sum(math.log((self.counts[c][f] + self.alpha) / (self.totals[c] + self.alpha * v)) for f in feats)
                logs.append(math.log(self.n_docs[c] / n) + ll / temper)
            m = max(logs)
            exps = [math.exp(x - m) for x in logs]
            total = sum(exps)
            out.append([e / total for e in exps])
        return out


# ---------------------------------------------------------------------------
# starter dataset generator
# ---------------------------------------------------------------------------
_NOUNS = ["product", "item", "order", "delivery", "service", "app", "website", "support team",
          "packaging", "quality", "price", "checkout", "phone", "shirt", "laptop", "headphones"]
_POS = ["love", "amazing", "excellent", "fantastic", "perfect", "great", "wonderful", "brilliant",
        "very happy with", "highly recommend", "impressed by", "satisfied with", "superb", "smooth",
        "reliable", "worth every rupee", "badhiya", "zabardast", "mast"]
_NEG = ["hate", "terrible", "worst", "horrible", "awful", "disappointed with", "useless", "pathetic",
        "very unhappy with", "never buying again", "waste of money", "broken", "defective",
        "unacceptable", "rude", "bakwas", "kharab", "ghatiya", "overpriced", "slow and buggy"]
_NEU = ["okay", "average", "fine", "as described", "nothing special", "acceptable", "decent enough",
        "arrived on time", "does the job", "neither good nor bad", "normal", "so-so", "as expected"]
_POS_T = ["I {w} the {n}.", "The {n} is {w}!", "Honestly {w} the {n}, will buy again.",
          "{w} {n}, five stars.", "The {n} was {w} and the staff were helpful."]
_NEG_T = ["I {w} the {n}.", "The {n} is {w}.", "Honestly {w} the {n}, want a refund.",
          "{w} {n}, one star.", "The {n} was {w} and nobody replied to my emails."]
_NEU_T = ["The {n} is {w}.", "{n} was {w}.", "Got the {n}, it is {w}.", "The {n} is {w}, nothing more to say."]


def generate_dataset(n_per_class: int = 600, seed: int = 7):
    rnd = random.Random(seed)
    rows = []
    for words, temps, label in ((_POS, _POS_T, "Positive"), (_NEG, _NEG_T, "Negative"), (_NEU, _NEU_T, "Neutral")):
        for _ in range(n_per_class):
            text = rnd.choice(temps).format(w=rnd.choice(words), n=rnd.choice(_NOUNS))
            if rnd.random() < 0.3:  # mixed sentence: add a second clause
                extra_words, extra_label = rnd.choice(((_POS, "p"), (_NEG, "n"), (_NEU, "u")))
                if (label == "Positive" and extra_label == "p") or (label == "Negative" and extra_label == "n") \
                        or (label == "Neutral" and extra_label == "u"):
                    text += " " + rnd.choice(temps).format(w=rnd.choice(extra_words), n=rnd.choice(_NOUNS))
            rows.append((text, label))
    for _ in range(n_per_class // 2):   # mixed reviews (one good point + one bad point) -> Neutral overall
        a, b = rnd.sample(_NOUNS, 2)
        good, bad = rnd.choice(_POS), rnd.choice(_NEG)
        pattern = rnd.choice(["The {a} is {g}, but the {b} is {x}.", "{g} {a}, however the {b} was {x}.",
                              "I {g} the {a} but the {b} was {x}.", "The {a} was {g} but {x} {b}."])
        rows.append((pattern.format(a=a, b=b, g=good, x=bad), "Neutral"))
    rnd.shuffle(rows)
    return rows


def load_csv(path: str):
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            text, label = (r.get("text") or "").strip(), (r.get("label") or "").strip().capitalize()
            if text and label in LABELS:
                rows.append((text, label))
    if len(rows) < 30:
        raise ValueError("Need a CSV with columns text,label (Positive/Neutral/Negative) and at least 30 rows.")
    return rows


# ---------------------------------------------------------------------------
# train / load / predict
# ---------------------------------------------------------------------------
def train(rows=None, source="built-in generated dataset"):
    rows = list(rows or generate_dataset())
    rnd = random.Random(42)
    rnd.shuffle(rows)
    cut = int(len(rows) * 0.8)
    train_rows, test_rows = rows[:cut], rows[cut:]

    check = NaiveBayes().fit(*zip(*train_rows))          # 1) train on 80%, test on the other 20%
    truth = [l for _, l in test_rows]
    pred = []
    for probs in check.predict_proba([t for t, _ in test_rows]):
        pred.append(check.classes_[probs.index(max(probs))])
    acc = sum(1 for a, b in zip(truth, pred) if a == b) / len(truth)
    f1 = {}
    for c in LABELS:
        tp = sum(1 for a, b in zip(truth, pred) if a == b == c)
        fp = sum(1 for a, b in zip(truth, pred) if b == c and a != c)
        fn = sum(1 for a, b in zip(truth, pred) if a == c and b != c)
        f1[c] = round(100 * 2 * tp / (2 * tp + fp + fn), 1) if (2 * tp + fp + fn) else 0.0

    model = NaiveBayes().fit(*zip(*rows))                # 2) final model learns from everything
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    meta = {"source": source, "samples": len(rows), "test_accuracy": round(acc * 100, 1), "f1": f1,
            "algorithm": "Naive Bayes (word 1-2 grams)"}
    META_PATH.write_text(json.dumps(meta, indent=2))
    global _model
    _model = model
    return meta


def get_model():
    global _model
    if _model is None:
        if not MODEL_PATH.exists():
            train()
        try:
            with open(MODEL_PATH, "rb") as f:
                _model = pickle.load(f)
        except Exception:                                # corrupted or old file: train again
            train()
    return _model


def model_info() -> dict:
    get_model()
    return json.loads(META_PATH.read_text()) if META_PATH.exists() else {}


def predict(text: str) -> dict:
    """Return label probabilities (%) and a compound-style value in [-1, 1]."""
    model = get_model()
    probs = dict(zip(model.classes_, model.predict_proba([text])[0]))
    return {"probs": {k: round(v * 100) for k, v in probs.items()},
            "compound": round(probs.get("Positive", 0) - probs.get("Negative", 0), 3)}
