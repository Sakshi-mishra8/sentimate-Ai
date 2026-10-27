"""
insights.py - the "high level" AI: finds patterns across ALL reviews.

* Complaint themes     -> unsupervised learning (TF-IDF + K-Means clustering)
* Word clouds          -> what customers praise / complain about
* Forecast             -> linear-regression trend of the sentiment score
* Smart alerts         -> anomaly detection (sudden drops, weak topics, churn spikes)
* Executive summary    -> auto-written report
* Ask AI (chat)        -> answers questions about your own data
"""
import json
import math
import re
from collections import Counter

import numpy as np

import database
from guide import feature_answer
from knowledge import kb_answer

STOP = set("""a an the and or but if so to of in on at for with is are was were be been it its this that
these those i me my we our you your they them their he she his her as by from not no very just have has had do
did does will would can could get got also really one all too than then there when what which who how why
product item order bought buy buying thing things hai hain hu aur bhi ka ki ke ko se mein bahut nahi""".split())


def _words(texts, n=18):
    c = Counter(w for t in texts for w in re.findall(r"[a-zA-Z']{3,}", t.lower()) if w not in STOP)
    return [{"word": w, "count": k} for w, k in c.most_common(n)]


def _terms(text):
    toks = [w for w in re.findall(r"[a-zA-Z']{3,}", text.lower()) if w not in STOP]
    return toks + [x + " " + y for x, y in zip(toks, toks[1:])]


def _kmeans(x, k, n_init=8, iters=30, seed=1):
    """Plain NumPy K-Means. Returns (labels, centers, distance-matrix) of the best of n_init runs."""
    rng = np.random.default_rng(seed)
    best = None
    for _ in range(n_init):
        centers = x[rng.choice(len(x), k, replace=False)].copy()
        for _ in range(iters):
            dist = (x ** 2).sum(1)[:, None] - 2 * x @ centers.T + (centers ** 2).sum(1)[None, :]
            labels = dist.argmin(1)
            for i in range(k):
                members = x[labels == i]
                centers[i] = members.mean(0) if len(members) else x[rng.integers(len(x))]
        dist = (x ** 2).sum(1)[:, None] - 2 * x @ centers.T + (centers ** 2).sum(1)[None, :]
        inertia = float(dist.min(1).sum())
        if best is None or inertia < best[0]:
            best = (inertia, dist.argmin(1), centers, dist)
    return best[1], best[2], best[3]


def themes(neg_texts):
    """Group negative reviews into complaint themes (TF-IDF + K-Means, written with NumPy)."""
    n = len(neg_texts)
    if n < 6:
        return []
    k = min(4, max(2, n // 5))
    docs = [_terms(t) for t in neg_texts]
    df = Counter()
    for d in docs:
        df.update(set(d))
    vocab = [w for w, c in df.items() if c <= 0.9 * n]
    if len(vocab) < k:
        return []
    index = {w: i for i, w in enumerate(vocab)}
    idf = np.array([math.log((1 + n) / (1 + df[w])) + 1 for w in vocab])
    x = np.zeros((n, len(vocab)))
    for i, d in enumerate(docs):
        for w, c in Counter(d).items():
            if w in index:
                x[i, index[w]] = (1 + math.log(c)) * idf[index[w]]
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    x = x / np.where(norms == 0, 1, norms)

    labels, centers, dist = _kmeans(x, k)
    terms = np.array(vocab)
    out = []
    for i in range(k):
        idx = np.where(labels == i)[0]
        if len(idx) == 0:
            continue
        top = terms[np.argsort(centers[i])[::-1][:4]].tolist()
        examples = []
        for j in idx[np.argsort(dist[idx, i])]:        # closest reviews first, no duplicates
            if neg_texts[j][:140] not in examples:
                examples.append(neg_texts[j][:140])
            if len(examples) == 2:
                break
        out.append({"name": " / ".join(top[:2]), "keywords": top, "count": int(len(idx)), "examples": examples})
    return sorted(out, key=lambda t: -t["count"])


def forecast(scores):
    """scores in time order (oldest first)."""
    if len(scores) < 8:
        return None
    y = np.array(scores[-40:], dtype=float)
    x = np.arange(len(y))
    slope, intercept = np.polyfit(x, y, 1)
    nxt = [round(float(np.clip(intercept + slope * (len(y) + i), 0, 100))) for i in range(7)]
    trend = "improving" if slope > 0.4 else "declining" if slope < -0.4 else "stable"
    return {"trend": trend, "slope": round(float(slope), 2), "next": nxt, "history": [int(v) for v in y]}


def alerts(st, data, fc):
    out = []
    recent = [r["score"] for r in data[:10]]
    before = [r["score"] for r in data[10:20]]
    if len(recent) >= 5 and len(before) >= 5:
        diff = round(sum(recent) / len(recent) - sum(before) / len(before))
        if diff <= -8:
            out.append({"level": "danger", "text": f"Sentiment fell {abs(diff)} points in the last 10 reviews."})
        elif diff >= 8:
            out.append({"level": "good", "text": f"Sentiment rose {diff} points in the last 10 reviews."})
    for a in st.get("aspects", []):
        if a["mentions"] >= 3 and a["score"] <= 40:
            out.append({"level": "warning", "text": f"{a['name']} is a weak area: score {a['score']}/100 over {a['mentions']} mentions."})
            break
    hr = sum(1 for r in data[:20] if r["risk_level"] == "High")
    if hr >= 3:
        out.append({"level": "danger", "text": f"{hr} of the last 20 customers are at high churn risk."})
    if fc and fc["trend"] == "declining":
        out.append({"level": "warning", "text": "Forecast: sentiment is trending down. Act before it falls further."})
    if not out:
        out.append({"level": "good", "text": "No problems detected. Sentiment looks healthy."})
    return out


def compute(user_id, channel=None, ds=None):
    data = database.rows(user_id, 1000, channel, ds)
    st = database.stats(user_id, channel, ds)
    if not data:
        return {"total": 0}
    chrono = [r["score"] for r in reversed(data)]
    fc = forecast(chrono) if ds and ds > 0 else None      # predictions are made ONLY for one uploaded CSV file
    pos = [r["text"] for r in data if r["label"] == "Positive"]
    neg = [r["text"] for r in data if r["label"] == "Negative"]
    at_risk = [{"text": r["text"][:160], "points": r["risk_points"], "intent": r["intent"], "channel": r["channel"]}
               for r in data if r["priority"].startswith("P1")][:6]
    return {"total": st["total"], "positive_words": _words(pos), "negative_words": _words(neg),
            "themes": themes(neg), "forecast": fc, "alerts": alerts(st, data, fc), "at_risk": at_risk}


# ---------------------------------------------------------------- summary
def summary(user_id, channel=None, ds=None):
    st = database.stats(user_id, channel, ds)
    if not st["total"]:
        return {"text": "No data yet. Analyze some reviews first.", "actions": [], "source": "rule-based"}
    ins = compute(user_id, channel, ds)
    t = st["total"]
    pos = round(100 * st["positive"] / t)
    neg = round(100 * st["negative"] / t)
    best = max(st["aspects"], key=lambda a: a["score"]) if st["aspects"] else None
    worst = st["aspects"][0] if st["aspects"] else None
    parts = [f"Out of {t} customer reviews, {pos}% are positive and {neg}% are negative. "
             f"The average sentiment score is {st['average']}/100 and the net sentiment index is {st['index']:+d}."]
    if best and worst and best["name"] != worst["name"]:
        parts.append(f"Customers are happiest with {best['name'].lower()} ({best['score']}/100) "
                     f"and least happy with {worst['name'].lower()} ({worst['score']}/100).")
    parts.append(f"The most common emotion is {st['top_emotion']}. {st['urgent']} review(s) need urgent attention.")
    if ins["forecast"]:
        parts.append(f"The forecast says sentiment is {ins['forecast']['trend']}.")
    actions = []
    if worst and worst["score"] < 50:
        actions.append(f"Fix {worst['name'].lower()} first. It has the lowest score.")
    if st["urgent"]:
        actions.append(f"Contact the {st['urgent']} urgent customers within 24 hours.")
    if ins["themes"]:
        actions.append(f"Investigate the biggest complaint theme: \"{ins['themes'][0]['name']}\".")
    if best:
        actions.append(f"Promote your strength: {best['name'].lower()}.")
    text = " ".join(parts)
    return {"text": text, "actions": actions, "source": "rule-based"}


# ---------------------------------------------------------------- chat (English, Hinglish, Hindi)
HINGLISH_WORDS = set("""kya kitne kitna hai hain mere mera meri mujhe batao bataiye bataye sabse kaun kaise kab kahan shikayat
dikkat pareshani samasya kharab bura galat kamzor sudhar accha acha achha pasand khush tareef badhiya behtar
kul sankhya ginti jaldi zaruri khatra chhod saransh vivaran kaisa kaisi konsa konsi hota sakta sakte chahiye aap kyu kyun
wala wali karo karna hoga ka ki ko mein samjhao dikhao namaste namaskar""".split())
PATTERNS = {
    "summary": r"summary|report|overview|overall|saransh|vivaran|poora hisab|kul mila ke|सारांश|रिपोर्ट|कुल मिलाकर|ओवरऑल",
    "percent": r"percent|percentage|%|प्रतिशत",
    "average": r"average|avg|औसत|score kitna|kitna score|mean score",
    "count": r"how many|total|count|number|kitne|kitna|kul reviews|sankhya|ginti|कितने|कुल|संख्या|गिनती",
    "channel": r"channel|amazon|website|play store|social|email|source|kahan se|चैनल|कहाँ से|कहां से",
    "risk": r"risk|churn|leave|leaving|urgent|angry|priority|jaa sakta|chhod|khatra|jaldi|zaruri|gussa|जोखिम|खतरा|छोड़|जरूरी|गुस्सा|नाराज",
    "trend": r"trend|forecast|improv|declin|future|predict|sudhar raha|sudhra|badh raha|gir raha|girawat|bhavishya|anuman|ट्रेंड|सुधर|बढ़ रहा|गिर रहा|भविष्य|अनुमान",
    "emotion": r"emotion|feeling|mood|bhavna|भावना",
    "intents": r"refund|suggestion|suggest|sujhav|\bbug\b|bugs|crash|cancel|request",
    "examples": r"example|udaharan|dikhao|show me|kuch reviews|sample review|उदाहरण",
    "complaints": r"complain|problem|issue|worst|\bbad\b|negative|weak|\bfix\b|shikayat|dikkat|pareshani|samasya|kharab|bura|galat|kamzor|sudhar|शिकायत|समस्या|दिक्कत|परेशानी|खराब|बुरा|गलत|कमजोर|कमज़ोर|सुधार",
    "strengths": r"best|praise|like|love|strength|good|positive|accha|acha|achha|pasand|khushi|khush|tareef|badhiya|behtar|अच्छा|अच्छी|पसंद|खुश|तारीफ|बढ़िया|बेहतर|ताकत",
}
TOPIC_WORDS = {
    "Delivery": r"deliver|dilivery|shipping|courier|डिलीवरी",
    "Price": r"price|daam|kimat|paisa|paise|mehnga|sasta|pricing|cost|पैसे|दाम|कीमत",
    "Customer support": r"support|service|staff|helpline|सपोर्ट|सर्विस",
    "Product quality": r"quality|product|maal|क्वालिटी|प्रोडक्ट",
    "App / Website": r"\bapp\b|website|checkout|ऐप",
    "Packaging": r"packag|packing|पैकिंग",
}


def _is_hindi(q):
    return bool(re.search(r"[\u0900-\u097F]", q)) or bool(set(re.findall(r"[a-z]+", q.lower())) & HINGLISH_WORDS)


def _rule_data_answer(user_id, q, hi, st, ins, channel, ds):
    """Answer a question about the user's own reviews. Returns text or None."""
    aspects = st["aspects"]
    hit = lambda key: re.search(PATTERNS[key], q)
    if hit("summary"):
        return summary(user_id, channel, ds)["text"]
    if hit("percent"):
        t = st["total"]
        p = lambda n: round(100 * n / t)
        return (f"{p(st['positive'])}% positive, {p(st['neutral'])}% neutral aur {p(st['negative'])}% negative reviews hain." if hi else
                f"{p(st['positive'])}% positive, {p(st['neutral'])}% neutral and {p(st['negative'])}% negative.")
    if hit("average"):
        return (f"Average score {st['average']}/100 hai aur net sentiment index {st['index']:+d} hai." if hi else
                f"The average score is {st['average']}/100 and the net sentiment index is {st['index']:+d}.")
    if hit("intents") and not hit("trend"):
        wanted = [name for name, pat in (("Refund request", r"refund"), ("Suggestion", r"suggest|sujhav"), ("Bug report", r"bug|crash"),
                                         ("Cancellation threat", r"cancel")) if re.search(pat, q)]
        if wanted:
            n = st["intents"].get(wanted[0], 0)
            return f"{wanted[0]}: {n} reviews mein." if hi else f"{wanted[0]}: {n} review(s)."
        it = ", ".join(f"{k}: {v}" for k, v in sorted(st["intents"].items(), key=lambda kv: -kv[1]))
        return f"Customers kya chahte hain (intent): {it}." if hi else f"What customers want (intent): {it}."
    if hit("count"):
        return (f"Kul {st['total']} reviews hain: {st['positive']} positive, {st['neutral']} neutral, {st['negative']} negative." if hi else
                f"{st['total']} reviews: {st['positive']} positive, {st['neutral']} neutral, {st['negative']} negative.")
    if hit("channel"):
        pairs = ", ".join(f"{c['name']} {c['score']}" for c in st["channels"])
        return f"Channel ke hisaab se average score: {pairs}." if hi else f"Average score by channel: {pairs}."
    if hit("risk"):
        ex = f" \"{ins['at_risk'][0]['text']}\"" if ins["at_risk"] else ""
        return (f"{st['high_risk']} customers ka churn risk high hai aur {st['urgent']} urgent (P1) hain. Example:{ex}" if hi else
                f"{st['high_risk']} customers have high churn risk and {st['urgent']} are urgent (P1)." + (f" Example:{ex}" if ex else ""))
    if hit("trend"):
        f = ins["forecast"]
        if not f:
            return ("Forecast sirf CSV file par banta hai. CSV dashboard mein file chunein (kam se kam 8 reviews)." if hi else
                    "Forecasts are made on an uploaded CSV file. Choose a file in the CSV dashboard (at least 8 reviews).")
        nxt = ", ".join(map(str, f["next"]))
        word = {"improving": "sudhar raha", "declining": "gir raha", "stable": "sthir"}[f["trend"]]
        return (f"Sentiment abhi {word} hai (slope {f['slope']} points per review). Agle 7 predicted scores: {nxt}." if hi else
                f"Sentiment is {f['trend']} (slope {f['slope']} points per review). Next 7 predicted scores: {nxt}.")
    for name, pat in TOPIC_WORDS.items():                                   # "delivery kaisi hai?"
        if re.search(pat, q):
            a = next((x for x in aspects if x["name"] == name), None)
            if not a:
                return f"Abhi kisi review mein {name} ka zikr nahi hai." if hi else f"No review mentions {name} yet."
            ex = ""
            for r in database.rows(user_id, 500, channel, ds):
                if any(x["name"] == name and x["label"] == "Negative" for x in json.loads(r["aspects"])):
                    ex = r["text"][:140]
                    break
            core = (f"{name}: score {a['score']}/100, {a['mentions']} baar zikr ({a['negative']} negative, {a['positive']} positive)." if hi else
                    f"{name}: score {a['score']}/100 from {a['mentions']} mentions ({a['negative']} negative, {a['positive']} positive).")
            return core + (f" Example: \"{ex}\"" if ex else "")
    if hit("emotion"):
        em = sorted(st["emotions"].items(), key=lambda kv: -kv[1])[:3]
        txt = ", ".join(f"{k} ({v})" for k, v in em)
        return f"Sabse zyada emotions: {txt}." if hi else f"Most common emotions: {txt}."
    if hit("intents"):
        it = ", ".join(f"{k}: {v}" for k, v in sorted(st["intents"].items(), key=lambda kv: -kv[1]))
        return f"Customers kya chahte hain (intent): {it}." if hi else f"What customers want (intent): {it}."
    if hit("examples"):
        rows = [r for r in database.rows(user_id, 300, channel, ds) if r["label"] == "Negative"][:3]
        if not rows:
            return "Koi negative review nahi mila." if hi else "No negative reviews found."
        return ("Kuch negative reviews: " if hi else "Some negative reviews: ") + " | ".join(f"\"{r['text'][:110]}\"" for r in rows)
    if hit("complaints"):
        weak = ", ".join(f"{a['name']} ({a['score']}/100)" for a in aspects[:2])
        th = f"{ins['themes'][0]['name']} ({ins['themes'][0]['count']} reviews)" if ins["themes"] else ""
        if not weak:                                    # no topic words (delivery, price...) found in these reviews
            words = ", ".join(w["word"] for w in ins["negative_words"][:5])
            if not words:
                return ("Abhi koi khaas shikayat nahi mili." if hi else "No specific complaints stand out in this data.")
            return (f"Kisi topic ka zikr nahi, par customers aksar kehte hain: {words}." if hi else
                    f"No specific topic is mentioned, but customers often write: {words}.")
        if hi:
            return f"Sabse kamzor topics: {weak}." + (f" Sabse badi shikayat ka theme: {th}." if th else "")
        return f"Weakest topics: {weak}." + (f" Biggest complaint theme: {th}." if th else "")
    if hit("strengths"):
        best = ", ".join(f"{a['name']} ({a['score']}/100)" for a in aspects[::-1][:2])
        words = ", ".join(w["word"] for w in ins["positive_words"][:5])
        if not best:
            if not words:
                return ("Abhi koi khaas taareef nahi mili." if hi else "No specific praise stands out in this data.")
            return (f"Kisi topic ka zikr nahi, par customers aksar kehte hain: {words}." if hi else
                    f"No specific topic is mentioned, but customers often write: {words}.")
        if hi:
            return f"Sabse majboot topics: {best}." + (f" Customers aksar kehte hain: {words}." if words else "")
        return f"Strongest topics: {best}." + (f" Customers often say: {words}." if words else "")
    return None


def _looks_like_data_question(q):
    return any(re.search(p, q) for p in PATTERNS.values()) or any(re.search(p, q) for p in TOPIC_WORDS.values())


def chat(user_id, question, channel=None, ds=None, prev=""):
    """Answer order: page guide -> project knowledge -> your review data -> suggestions."""
    hi = _is_hindi(question)
    q = question.lower()
    st = database.stats(user_id, channel, ds)
    has = st.get("total", 0) > 0

    guide = feature_answer(question, prev, hi, has)
    if guide:
        return {"answer": guide, "source": "built-in guide", "note": ""}

    note = ""

    if re.fullmatch(r"\s*(hi|hello|hey|namaste|namaskar|hii+|helo)[ !.?]*", q):
        return {"answer": ("Namaste! Mujhse apne reviews, website ke pages ya project ke baare mein kuch bhi poochiye, jaise 'Inbox ka kaam kya hai?' ya 'Sabse badi shikayat kya hai?'." if hi else
                           "Hello! Ask me about your reviews, the website pages or the project, for example 'What is the Inbox for?' or 'What is the biggest complaint?'."),
                "source": "built-in guide", "note": note}
    kb, near = kb_answer(question, hi)
    if kb:
        return {"answer": kb, "source": "built-in guide", "note": note}

    if has:
        ans = _rule_data_answer(user_id, q, hi, st, compute(user_id, channel, ds), channel, ds)
        if ans:
            return {"answer": ans, "source": "rule-based", "note": note}
    elif _looks_like_data_question(q):
        return {"answer": ("Is file ka koi data nahi hai. Pehle reviews analyze karein ya CSV upload karein." if hi else
                           "There is no data here yet. Analyze some reviews or upload a CSV first."), "source": "rule-based", "note": note}

    _, near = kb_answer(question, hi, min_points=1)
    hint = (" Shayad aap ye puchna chahte the: " if hi else " Maybe you wanted to ask about: ") + "; ".join(near) + "." if near else ""
    return {"answer": (("Ye sawal mujhe poori tarah samajh nahi aaya." + hint + " Main aapke reviews, website ke pages aur is project ke sawalon ke jawab de sakta hoon.") if hi else
                       ("I did not fully understand that." + hint + " I can answer questions about your reviews, the website pages and this project.")),
            "source": "built-in guide", "note": note}


# ---------------------------------------------------------------- reply studio
TONES = {
    "Empathetic": ("I'm truly sorry you had this experience{topic}. I understand how frustrating it must be. {fix}",
                   "Thank you for such kind words{topic}! We're so happy this made your day. {fix}"),
    "Professional": ("Thank you for your feedback. We apologise for the inconvenience{topic}. {fix}",
                     "Thank you for your positive feedback{topic}. We appreciate your support. {fix}"),
    "Friendly": ("Oh no, that's not what we want for you{topic}! Let's put it right. {fix}",
                 "Yay, thank you{topic}! You just made our team smile. {fix}"),
    "Short": ("Sorry about that{topic}. {fix}", "Thanks a lot{topic}! {fix}"),
}


def reply_studio(analysis, tone="Professional"):
    tone = tone if tone in TONES else "Professional"
    neg_aspect = next((a["name"].lower() for a in analysis["aspects"] if a["label"] == "Negative"), None)
    pos_aspect = next((a["name"].lower() for a in reversed(analysis["aspects"]) if a["label"] == "Positive"), None)
    if analysis.get("mixed") and neg_aspect and pos_aspect:
        mixed = {"Professional": "Thank you for your feedback. We're glad you liked our {p}, and we apologise for the issue with our {n}. Please share your order number so we can resolve it.",
                 "Empathetic": "Thank you for being honest. We're happy you enjoyed our {p}, and truly sorry our {n} let you down. We want to make this right.",
                 "Friendly": "Thanks for telling us! So glad you liked our {p}. Sorry about our {n}, we're on it!",
                 "Short": "Thanks! Glad you liked our {p}. Sorry about our {n}."}
        return {"reply": mixed[tone].format(p=pos_aspect, n=neg_aspect), "source": "template"}
    negative = analysis["label"] == "Negative"
    topic = f" with our {neg_aspect}" if negative and neg_aspect else f" about our {pos_aspect}" if pos_aspect and not negative else ""
    if analysis["label"] == "Neutral":
        return {"reply": "Thanks for your feedback. Could you tell us one thing we can improve?", "source": "template"}
    fix = ("Please share your order number and a senior agent will contact you within 24 hours."
           if negative and analysis["priority"].startswith("P1") else
           "Please send us your order number so we can fix this quickly." if negative else
           "We look forward to serving you again.")
    return {"reply": TONES[tone][0 if negative else 1].format(topic=topic, fix=fix), "source": "template"}
