"""
sentiment_engine.py  -  the AI brain of the project.

What happens to every review
----------------------------
1. normalize()      fix typos, emojis, Hindi/Hinglish negation ("accha nahi" -> "not accha")
2. 3 models vote    VADER (NLP rules) + our own ML model + optional DistilBERT
3. sarcasm check    "Oh great, another delay" is negative, not positive
4. mixed check      "product is good BUT delivery is late" -> Mixed review, explained clearly
5. emotion, topics (aspects), risk, intent, priority, suggested reply
Works in English, Hinglish (Hindi in English letters) and Hindi script.
"""

import importlib.util
import re
import unicodedata
from collections import Counter

import vaderSentiment.vaderSentiment as _vs
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

import ml_model

# ----------------------------------------------------------------------------
# 1. Base model: VADER + our own vocabulary (English, Hinglish, Hindi)
# ----------------------------------------------------------------------------
_vader = SentimentIntensityAnalyzer()


def _nfc(word: str) -> str:
    return unicodedata.normalize("NFC", word.lower())


ENGLISH = {
    # negative
    "refund": -1.2, "scam": -3.0, "fraud": -3.0, "worst": -3.0, "delayed": -1.8, "late": -1.8, "delay": -1.6,
    "broken": -2.2, "damaged": -2.2, "defective": -2.5, "overpriced": -2.0, "crash": -2.0, "crashing": -2.0,
    "crashed": -2.0, "crashes": -2.0, "freezes": -1.8, "glitch": -1.5, "rude": -2.5, "unresponsive": -2.2,
    "useless": -2.5, "pathetic": -2.8, "laggy": -1.8, "lag": -1.5, "slow": -1.5, "hassle": -1.5,
    "disappointing": -2.2, "disappointed": -2.2, "waste": -2.0, "poor": -1.8, "junk": -2.5, "fake": -2.5,
    "missing": -1.8, "torn": -1.8, "cracked": -2.0, "leaking": -2.0, "ignored": -2.0, "ignoring": -2.0,
    "unprofessional": -2.5, "careless": -2.0, "overcharged": -2.3, "complicated": -1.3, "confusing": -1.5,
    "buggy": -2.0, "cancelled": -1.8, "canceled": -1.8, "regret": -2.0, "ruining": -2.5, "ruined": -2.5,
    "ruin": -2.2, "dies": -1.8, "died": -1.8, "dead": -1.5, "drains": -1.5, "drain": -1.3, "heats": -1.5,
    "overheating": -2.0, "faded": -1.5, "cheaply": -1.5, "flimsy": -2.0, "fragile": -1.5, "shoddy": -2.3,
    "lousy": -2.3, "awful": -3.0, "horrible": -3.0, "terrible": -3.0, "dirty": -1.8, "stale": -1.8,
    "expired": -2.3, "wrong": -1.8, "mistake": -1.5, "unacceptable": -2.5, "frustrating": -2.2,
    "irritating": -2.0, "joke": -1.8, "nightmare": -2.8, "rubbish": -2.5, "garbage": -2.5, "trash": -2.3,
    "stopped": -1.2, "fails": -1.8, "failed": -1.8, "failure": -2.0, "unreliable": -2.2, "overrated": -1.8,
    # positive
    "recommend": 1.6, "flawless": 2.5, "lifesaver": 2.5, "worthwhile": 1.8, "affordable": 1.5, "prompt": 1.4,
    "smooth": 1.5, "reliable": 1.8, "impressed": 2.2, "satisfied": 1.8, "hassle-free": 2.0, "legit": 1.0,
    "decent": 1.2, "polite": 1.8, "quick": 1.5, "fast": 1.5, "sturdy": 1.8, "premium": 1.5, "stunning": 2.5,
    "tasty": 2.0, "delicious": 2.6, "comfortable": 1.8, "spacious": 1.5, "durable": 1.8, "responsive": 1.6,
    "professional": 1.6, "efficient": 1.8, "seamless": 2.0, "superb": 2.8, "brilliant": 2.8, "worth": 1.5,
    "timely": 1.5, "neat": 1.3, "perfectly": 2.0, "recommended": 1.8, "trustworthy": 2.2, "genuine": 1.5,
}
HINGLISH = {   # Hindi written in English letters
    "bakwas": -2.5, "bekar": -2.3, "bekaar": -2.3, "ghatiya": -2.7, "kharab": -2.2, "kharaab": -2.2,
    "faltu": -2.2, "dhokha": -3.0, "dhoka": -3.0, "pareshan": -1.8, "pareshani": -1.8, "dikkat": -1.5,
    "toota": -2.0, "tuta": -2.0, "nakli": -2.5, "chor": -2.5, "ganda": -2.0, "gandi": -2.0, "barbaad": -2.5,
    "barbad": -2.5, "jhoota": -2.0, "jhuta": -2.0, "gussa": -1.8, "dukhi": -1.5, "nirash": -2.0,
    "mehnga": -1.2, "mehenga": -1.2, "bura": -2.0, "buri": -2.0, "kamzor": -1.5, "tang": -1.5,
    "achha": 1.8, "accha": 1.8, "acha": 1.8, "achchha": 1.8, "badhiya": 2.3, "mast": 2.2, "zabardast": 2.8,
    "shandar": 2.6, "behtareen": 2.5, "behtar": 1.8, "pasand": 1.5, "kamaal": 2.4, "vasool": 1.5,
    "lajawab": 2.8, "khush": 2.0, "shukriya": 1.8, "dhanyawad": 1.8, "dhanyavaad": 1.8, "sahi": 1.2,
    "sasta": 0.8, "der": -0.8, "majboot": 1.6, "sundar": 1.8, "theek": 0.4, "thik": 0.4,
}
HINDI = {      # Devanagari script
    "अच्छा": 1.8, "अच्छी": 1.8, "अच्छे": 1.8, "बढ़िया": 2.3, "शानदार": 2.6, "बेहतरीन": 2.5, "बेहतर": 1.8,
    "कमाल": 2.4, "पसंद": 1.5, "खुश": 2.0, "धन्यवाद": 1.8, "शुक्रिया": 1.8, "लाजवाब": 2.8, "सुंदर": 1.8,
    "मजबूत": 1.6, "बेकार": -2.3, "खराब": -2.2, "बकवास": -2.5, "घटिया": -2.7, "धोखा": -3.0, "नकली": -2.5,
    "परेशान": -1.8, "परेशानी": -1.8, "गुस्सा": -1.8, "दुखी": -1.5, "निराश": -2.0, "टूटा": -2.0, "टूट": -1.5,
    "देर": -1.2, "महंगा": -1.2, "गंदा": -2.0, "झूठ": -2.0, "बर्बाद": -2.5, "बुरा": -2.0, "कमजोर": -1.5,
    "दिक्कत": -1.5, "शिकायत": -1.2,
}
for _group in (ENGLISH, HINGLISH, HINDI):
    _vader.lexicon.update({_nfc(k): v for k, v in _group.items()})
_vs.BOOSTER_DICT.update({k: 0.293 for k in ("bahut", "bohot", "bilkul", "ekdum", "बहुत", "बिल्कुल", "एकदम", "kaafi")})

# ----------------------------------------------------------------------------
# 2. Optional deep-learning model (Hugging Face transformers)
# ----------------------------------------------------------------------------
_transformer = None
TRANSFORMER_MODEL = "distilbert-base-uncased-finetuned-sst-2-english"


def transformer_available() -> bool:
    return importlib.util.find_spec("transformers") is not None


def _load_transformer():
    global _transformer
    if _transformer is None:
        from transformers import pipeline  # imported lazily (heavy)
        _transformer = pipeline("sentiment-analysis", model=TRANSFORMER_MODEL)
    return _transformer


def _transformer_compound(text: str) -> float:
    out = _load_transformer()(text[:1500], truncation=True)[0]
    value = float(out["score"])
    return value if out["label"].upper().startswith("POS") else -value


# ----------------------------------------------------------------------------
# 3. Text clean-up: typos, emojis, Hindi / Hinglish negation, sarcasm
# ----------------------------------------------------------------------------
TYPOS = {
    "wrost": "worst", "worse": "worse", "servise": "service", "sevice": "service", "servce": "service",
    "gud": "good", "gd": "good", "bt": "but", "evr": "ever", "gr8": "great", "delivry": "delivery",
    "dilivery": "delivery", "delievery": "delivery", "deliverd": "delivered", "definately": "definitely",
    "defintely": "definitely", "agin": "again", "dont": "don't", "cant": "can't", "wont": "won't",
    "doesnt": "doesn't", "didnt": "didn't", "isnt": "isn't", "wasnt": "wasn't", "pls": "please",
    "plz": "please", "thx": "thanks", "awsome": "awesome", "awesom": "awesome", "terrable": "terrible",
    "horible": "horrible", "recomend": "recommend", "recommed": "recommend", "qualty": "quality",
    "qualiti": "quality", "prodct": "product", "produt": "product", "excelent": "excellent",
    "experiance": "experience", "disapointed": "disappointed", "dissapointed": "disappointed",
    "usless": "useless", "worthless": "worthless", "amazin": "amazing", "amzing": "amazing",
    "bad": "bad", "nyc": "nice", "luv": "love", "lov": "love", "fkn": "very", "v": "very",
}
EMOJI = {"😡": " angry ", "😠": " angry ", "🤬": " angry ", "😤": " angry ", "😍": " love ", "🥰": " love ",
         "😊": " happy ", "😀": " happy ", "😁": " happy ", "😃": " happy ", "👍": " good ", "👎": " bad ",
         "😢": " sad ", "😭": " sad ", "😞": " disappointed ", "💔": " disappointed ", "❤️": " love ",
         "❤": " love ", "🙏": " thanks ", "👌": " good ", "🔥": " great ", "🤮": " disgusting ", "😒": " annoyed "}
SARCASM = [
    r"\boh,? (great|wow|wonderful|nice|perfect|fantastic|brilliant)\b", r"\bthanks for nothing\b",
    r"\byeah,? right\b", r"\bjust what i (needed|wanted)\b", r"\bexactly what i needed\b",
    r"\bthanks (a lot|so much) for (ruining|nothing|breaking|losing|ignoring)\b", r"\bsure,? because\b",
    r"\bto my enemies\b", r"\bwow,?[^.!?]*\b(only|took)\b[^.!?]*\b(weeks?|months?|days?|hours?)\b",
    r"\bbest [a-z ]+ ever\b[^.!?]*\bif you (like|enjoy|love)\b", r"\bgreat,? (another|more|now)\b",
    r"\bwhat a (joke|surprise|waste)\b", r"\btruly impressive\b[^.!?]*\b(weeks?|months?)\b",
]
_SARCASM_RE = [re.compile(p, re.I) for p in SARCASM]
_NEG_WORDS = r"(nahi|nahin|nhi|nahee|nai|नहीं|नही)"


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFC", text).replace("।", " . ")
    for emo, word in EMOJI.items():
        t = t.replace(emo, word)
    t = re.sub(r"\btime par " + _NEG_WORDS + r" (aa\w*|pahunch\w*)", " late ", t, flags=re.I)
    t = re.sub(r"\b(kaam|work) " + _NEG_WORDS + r" kar\w*", " not working ", t, flags=re.I)
    t = re.sub(r"\bpais[ae] wapas\b|\brefund chahiye\b", " refund ", t, flags=re.I)
    # Hindi/Hinglish negation comes AFTER the word: "accha nahi" -> "not accha"
    t = re.sub(r"(\S+?)(?:\s+(?:par|ko|se|mein|me|ka|ki|ke|bhi|to|में|का|की|के|को|से))?\s+" + _NEG_WORDS + r"(?=\s|[.,!?;]|$)",
               r"not \1", t, flags=re.I)
    t = re.sub(r"[A-Za-z0-9']+", lambda m: TYPOS.get(m.group(0).lower(), m.group(0)), t)
    return re.sub(r"\s+", " ", t).strip()


def is_sarcastic(text: str) -> bool:
    return any(p.search(text) for p in _SARCASM_RE)


# ----------------------------------------------------------------------------
# 4. Emotion lexicon (English + Hinglish + Hindi)
# ----------------------------------------------------------------------------
EMOTIONS = {
    "joy": {"love", "loved", "great", "happy", "amazing", "awesome", "excellent", "perfect", "delighted",
            "wonderful", "fantastic", "pleased", "enjoy", "enjoyed", "best", "thrilled", "glad", "satisfied",
            "impressed", "brilliant", "superb", "thanks", "thank", "mast", "badhiya", "zabardast", "shandar",
            "khush", "shukriya", "dhanyawad", "kamaal", "lajawab", "खुश", "शानदार", "बढ़िया", "धन्यवाद", "शुक्रिया"},
    "anger": {"angry", "furious", "worst", "terrible", "horrible", "rude", "scam", "fraud", "unacceptable",
              "ridiculous", "pathetic", "useless", "hate", "hated", "annoyed", "annoying", "irritated",
              "outrageous", "disgusting", "waste", "bakwas", "ghatiya", "chor", "dhokha", "gussa", "bekar",
              "बकवास", "गुस्सा", "धोखा", "घटिया", "बेकार"},
    "sadness": {"sad", "disappointed", "disappointing", "unhappy", "upset", "regret", "sorry", "unfortunately",
                "poor", "miss", "missed", "hurt", "dukhi", "nirash", "दुखी", "निराश"},
    "fear": {"worried", "worry", "afraid", "scared", "unsafe", "risk", "risky", "doubt", "concerned", "anxious",
             "nervous", "suspicious", "fake", "stolen", "chinta", "डर", "चिंता"},
    "surprise": {"surprised", "surprising", "wow", "unexpected", "unexpectedly", "shocked", "suddenly",
                 "unbelievable", "astonished"},
}

# ----------------------------------------------------------------------------
# 5. Topics (aspects): English + Hinglish + Hindi keywords
# ----------------------------------------------------------------------------
ASPECTS = {
    "Product quality": ["quality", "product", "material", "build", "durable", "durability", "sturdy", "broken",
                        "defective", "damaged item", "fabric", "stitching", "size", "fit", "fitting", "works",
                        "working", "stopped working", "screen", "battery", "sound", "camera", "performance",
                        "colour", "color", "taste", "design", "item", "maal", "क्वालिटी", "प्रोडक्ट", "सामान", "माल"],
    "Delivery": ["delivery", "delivered", "deliver", "shipping", "shipped", "shipment", "courier", "arrived",
                 "arrive", "late", "delay", "delayed", "dispatch", "tracking", "parcel", "dilivery", "delivry",
                 "डिलीवरी", "देर", "कूरियर", "पार्सल"],
    "Price": ["price", "prices", "expensive", "cheap", "cost", "costly", "value", "money", "overpriced", "worth",
              "discount", "affordable", "pricing", "charges", "fee", "budget", "offer", "daam", "kimat", "paisa",
              "paise", "mehnga", "sasta", "rupee", "rupees", "पैसा", "पैसे", "दाम", "कीमत", "महंगा", "सस्ता"],
    "Customer support": ["support", "service", "staff", "agent", "representative", "customer care", "customer service",
                         "helpline", "response", "responded", "refund", "replacement", "exchange", "rude",
                         "helpful", "complaint", "resolved", "manager", "warranty", "madad", "jawab", "reply",
                         "सपोर्ट", "सर्विस", "मदद", "जवाब", "स्टाफ"],
    "App / Website": ["app", "website", "site", "checkout", "login", "interface", "crash", "crashes", "crashing",
                      "lag", "laggy", "payment", "bug", "bugs", "slow", "loading", "page", "search", "otp",
                      "notification", "notifications", "update", "freezes", "ऐप", "वेबसाइट"],
    "Packaging": ["packaging", "packed", "packing", "package", "box", "wrapped", "wrapping", "seal", "sealed",
                  "पैकिंग", "डिब्बा"],
}


def _aspect_pattern(words):
    ascii_w = [re.escape(w) for w in words if w.isascii()]
    other_w = [re.escape(_nfc(w)) for w in words if not w.isascii()]
    parts = []
    if ascii_w:
        parts.append(r"\b(?:" + "|".join(ascii_w) + r")\b")
    if other_w:
        parts.append("(?:" + "|".join(other_w) + ")")
    return re.compile("|".join(parts), re.I)


_ASPECT_PATTERNS = {name: _aspect_pattern(words) for name, words in ASPECTS.items()}

RISK_TRIGGERS = ["refund", "cancel", "cancelling", "canceling", "unsubscribe", "legal", "lawyer", "consumer court",
                 "complaint", "scam", "fraud", "never again", "worst", "switch", "switching", "competitor",
                 "chargeback", "report", "stop using", "last time", "dhokha", "बंद", "धोखा"]


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def _label(compound: float) -> str:
    if compound >= 0.05:
        return "Positive"
    if compound <= -0.05:
        return "Negative"
    return "Neutral"


_CONTRAST = r"\s+(?:but|however|although|though|while|yet|lekin|magar|parantu|kintu|लेकिन|मगर|परंतु|किंतु|जबकि)\s+"


def _clauses(text: str):
    """Split into small opinions: sentences, commas and contrast words (but / lekin / however)."""
    parts = [p.strip() for p in re.split(r"(?<=[.!?;])\s+|\s*,\s+|" + _CONTRAST, text.strip(), flags=re.I) if p and p.strip()]
    merged = []
    carry = ""
    for p in parts:                       # a 1-word piece ("Honestly,") joins the next piece
        p = (carry + " " + p).strip()
        carry = ""
        if len(p.split()) < 2 and p is not parts[-1]:
            carry = p
            continue
        merged.append(p)
    if carry:
        if merged:
            merged[-1] += " " + carry
        else:
            merged.append(carry)
    return merged


def _tokens(text: str):
    return [t.lower().strip("'’\"“”") for t in re.findall(r"[^\s.,!?;:()\"“”]+", text) if t.strip("'’\"“”")]


def detect_emotions(text: str, compound: float) -> dict:
    counts = Counter()
    toks = _tokens(text)
    for emotion, words in EMOTIONS.items():
        counts[emotion] = sum(1 for t in toks if _nfc(t) in {_nfc(w) for w in words})
    total = sum(counts.values())
    if total == 0:
        dominant = "satisfaction" if compound >= 0.05 else "dissatisfaction" if compound <= -0.05 else "neutral"
        return {"dominant": dominant, "scores": {e: 0 for e in EMOTIONS}}
    scores = {e: round(100 * c / total) for e, c in counts.items()}
    negative = {"anger", "sadness", "fear"}

    def rank(e):  # on ties, prefer the emotion that matches the overall mood
        return (counts[e], (e in negative) == (compound < 0))
    return {"dominant": max(counts, key=rank), "scores": scores}


def aspect_sentiment(clauses, clause_scores) -> list:
    found = {}
    for clause, comp in zip(clauses, clause_scores):
        for name, pattern in _ASPECT_PATTERNS.items():
            if pattern.search(clause.lower()):
                found.setdefault(name, []).append(comp)
    result = []
    for name, vals in found.items():
        avg = sum(vals) / len(vals)
        result.append({"name": name, "compound": round(avg, 3), "label": _label(avg), "mentions": len(vals)})
    return sorted(result, key=lambda a: a["compound"])


def explain_words(text: str, limit: int = 8) -> list:
    """Words from the model vocabulary that influenced the score (explainable AI). Negated words flip sign."""
    seen, words = set(), []
    toks = _tokens(text)
    for i, tok in enumerate(toks):
        val = _vader.lexicon.get(_nfc(tok))
        if val is None or abs(val) < 1.0 or tok in seen:
            continue
        if i and toks[i - 1] in ("not", "no", "never", "isn't", "wasn't", "don't", "didn't", "doesn't", "wouldn't"):
            val = -val
        seen.add(tok)
        words.append({"word": tok, "value": round(val, 1)})
    words.sort(key=lambda w: abs(w["value"]), reverse=True)
    return words[:limit]


def churn_risk(text: str, raw_compound: float, emotions: dict) -> dict:
    low = text.lower()
    triggers = [t for t in RISK_TRIGGERS if t in low]
    points = 0
    if raw_compound < -0.05:
        points += int(-raw_compound * 60)
    points += int(emotions["scores"].get("anger", 0) * 0.2)
    points += min(len(triggers) * 15, 35)
    points = max(0, min(100, points))
    level = "High" if points >= 60 else "Medium" if points >= 30 else "Low"
    return {"level": level, "points": points, "triggers": triggers}


def suggest_reply(label: str, aspects: list, risk: dict, mixed: bool = False) -> str:
    worst = next((a["name"].lower() for a in aspects if a["label"] == "Negative"), None)
    best = next((a["name"].lower() for a in reversed(aspects) if a["label"] == "Positive"), None)
    if mixed and worst and best:
        return (f"Thank you for your feedback. We're glad you liked our {best}, and we're sorry about our {worst}. "
                "Please share your order number so we can make it right.")
    if label == "Positive":
        extra = f" We're especially glad you liked our {best}." if best else ""
        return ("Thank you so much for your kind feedback!" + extra +
                " It means a lot to our team. We'd love to see you again soon.")
    if label == "Negative":
        topic = f" with our {worst}" if worst else ""
        urgent = (" A senior member of our team will contact you within 24 hours to make this right."
                  if risk["level"] == "High" else " Please share your order number so we can fix this quickly.")
        return f"We're really sorry about your experience{topic}. This is not the standard we aim for." + urgent
    return ("Thank you for your feedback. We'd like to understand your experience better - "
            "could you tell us what we can do to improve?")


# ----------------------------------------------------------------------------
# intent, language, priority
# ----------------------------------------------------------------------------
INTENTS = [
    ("Cancellation threat", r"\b(cancel (my|the|this)|cancelling|unsubscribe|switch(ing)? to|stop using|never (again|buy|use)|will not shop|won't shop)\b"),
    ("Refund request", r"\b(refund|money back|return (it|this)|chargeback|replace(ment)?)\b"),
    ("Question", r"\?|\b(how do|how can|when will|where is|can you|could you|can i|why is|why does)\b"),
    ("Suggestion", r"\b(please add|should add|would love|wish (you|it)|it would be (nice|great)|suggest|add a)\b"),
    ("Bug report", r"\b(crash|crashes|crashing|bug|error|not working|stopped working|fails?|failed|glitch)\b"),
]


def detect_intent(text: str, label: str, mixed: bool = False) -> str:
    low = text.lower()
    for name, pattern in INTENTS:
        if re.search(pattern, low):
            return name
    if mixed:
        return "Mixed feedback"
    if label == "Positive":
        return "Praise"
    if label == "Negative":
        return "Complaint"
    return "General feedback"


_HINGLISH_FUNCTION = {"hai", "hain", "nahi", "nahin", "nhi", "bahut", "hu", "hoon", "aur", "bhi", "ka", "ki", "ke",
                      "ko", "se", "mein", "par", "tha", "thi", "kya", "mujhe", "mera", "meri", "lekin", "magar"}


def detect_language(text: str) -> str:
    if re.search(r"[\u0900-\u097F]", text):
        return "Hindi script"
    toks = set(_tokens(text))
    if toks & set(HINGLISH) or len(toks & _HINGLISH_FUNCTION) >= 2:
        return "Hinglish"
    return "English"


def priority(risk: dict, intent: str, mixed: bool, has_negative: bool) -> str:
    if risk["level"] == "High" or intent == "Cancellation threat":
        return "P1 - Urgent"
    if risk["level"] == "Medium" or intent in ("Refund request", "Bug report") or (mixed and has_negative):
        return "P2 - High"
    return "P3 - Normal"


def _model_vote(name: str, compound: float) -> dict:
    return {"name": name, "label": _label(compound), "compound": round(compound, 3)}


# ----------------------------------------------------------------------------
# main entry point
# ----------------------------------------------------------------------------
ENGINES = ("vader", "ml", "transformer", "ensemble")


def analyze(text: str, engine: str = "ensemble") -> dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("Text is empty")
    if engine not in ENGINES:
        engine = "ensemble"

    clean = normalize(text)
    warning = None
    vader_scores = _vader.polarity_scores(clean)
    votes = [_model_vote("VADER (NLP rules)", vader_scores["compound"])]

    if engine in ("ml", "ensemble"):
        votes.append(_model_vote("Our ML model", ml_model.predict(clean)["compound"]))
    if engine in ("transformer", "ensemble"):
        if transformer_available():
            try:
                votes.append(_model_vote("DistilBERT (deep learning)", _transformer_compound(clean)))
            except Exception as exc:
                warning = f"Deep model failed ({exc.__class__.__name__}); other models were used."
        elif engine == "transformer":
            warning = "DistilBERT is not installed (pip install transformers torch); VADER was used."
    if engine == "ml":
        votes = [v for v in votes if v["name"] == "Our ML model"]
    elif engine == "transformer" and len(votes) > 1:
        votes = [v for v in votes if v["name"].startswith("DistilBERT")]

    # VADER and DistilBERT understand negation and context better than our small starter model, so they count double
    weights = [1.0 if v["name"] == "Our ML model" else 2.0 for v in votes]
    raw = sum(v["compound"] * w for v, w in zip(votes, weights)) / sum(weights)

    # --- clause by clause: topics and mixed opinions ---
    clauses = _clauses(clean)
    clause_scores = [_vader.polarity_scores(c)["compound"] for c in clauses]
    aspects = aspect_sentiment(clauses, clause_scores)
    mixed = len(clauses) > 1 and max(clause_scores) >= 0.15 and min(clause_scores) <= -0.25
    sarcasm = is_sarcastic(clean)

    compound = raw
    if sarcasm:
        compound = -max(abs(raw), 0.55)            # positive words, negative meaning
        mixed = False
    elif mixed:
        compound = raw * 0.35                      # good AND bad: pull the score to the middle
        if abs(compound) < 0.25:                   # balanced mix = Neutral overall, shown as "Mixed review"
            compound *= 0.2
    elif "?" in text and abs(vader_scores["compound"]) < 0.3:
        compound = raw * 0.15                      # a plain question is not an opinion

    label = _label(compound)
    agree = sum(1 for v in votes if v["label"] == label)
    emotions = detect_emotions(clean, raw)
    risk = churn_risk(clean, min(raw, compound), emotions)
    intent = detect_intent(clean, label, mixed)
    has_negative = any(a["label"] == "Negative" for a in aspects) or min(clause_scores) <= -0.25

    pos_names = [a["name"].lower() for a in aspects if a["label"] == "Positive"]
    neg_names = [a["name"].lower() for a in aspects if a["label"] == "Negative"]
    explain = ""
    if sarcasm:
        explain = "Sarcasm detected: the words sound positive, but the meaning is negative."
    elif mixed:
        explain = "Mixed review. " + (f"Positive about: {', '.join(pos_names)}. " if pos_names else "") + \
                  (f"Negative about: {', '.join(neg_names)}." if neg_names else "") if (pos_names or neg_names) else \
                  "Mixed review: some parts are positive and some are negative."

    return {
        "text": text,
        "label": label,
        "compound": round(compound, 3),
        "score": round((compound + 1) / 2 * 100),
        "confidence": min(99, round(50 + abs(compound) * 50)),
        "engine": engine,
        "models": votes,
        "agreement": f"{agree} of {len(votes)} models agree",
        "breakdown": {"positive": round(vader_scores["pos"] * 100), "neutral": round(vader_scores["neu"] * 100),
                      "negative": round(vader_scores["neg"] * 100)},
        "emotion": emotions,
        "aspects": aspects,
        "words": explain_words(clean),
        "risk": risk,
        "intent": intent,
        "language": detect_language(text),
        "priority": priority(risk, intent, mixed, has_negative),
        "mixed": mixed,
        "sarcasm": sarcasm,
        "explain": explain,
        "reply": suggest_reply(label, aspects, risk, mixed),
        "warning": warning,
    }
