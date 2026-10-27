"""guide.py - Ask AI explains the website's pages and AI ideas ("Overview ka kaam kya hai?")."""
import re

# (id, regex that finds the topic in a question, English answer, Hinglish answer)
GUIDE = [
    ("overview", r"overview|ओवरव्यू",
     "Overview shows the big picture of ALL your saved reviews: the AI summary, number of reviews, average score, urgent customers, and graphs by topic, emotion and channel. Use it to see how customers feel overall.",
     "Overview aapke saare saved reviews ki poori tasveer dikhata hai: AI summary, kitne reviews, average score, urgent customers, aur topic, emotion aur channel ke graphs. Isse pata chalta hai ki customers overall kaisa mehsoos kar rahe hain."),
    ("analyze", r"analy[sz]e|analysis|एनालाइज",
     "Analyze checks ONE review. Paste any review and the AI shows positive, neutral or negative, the emotion, topics, churn risk, priority and a suggested reply. Click 'Analyze and save' to keep it in History.",
     "Analyze ek review ko check karta hai. Koi bhi review paste karein, AI positive/neutral/negative, emotion, topics, churn risk, priority aur suggested reply dikhata hai. 'Analyze and save' dabane par wo History mein save ho jaata hai."),
    ("inbox", r"inbox|इनबॉक्स",
     "Inbox is your support to-do list. It is empty at every login. When you upload a CSV it shows that file's messages, urgent customers first. Your older reviews stay in History. You can write an AI reply, send it by email, and mark it Replied or Resolved.",
     "Inbox aapki support to-do list hai. Ye har login par khali hota hai. CSV upload karne par us file ke messages dikhata hai, urgent customers sabse upar. Purane reviews History mein safe rehte hain. Yahan AI reply likh sakte hain, email se bhej sakte hain, aur Replied ya Resolved mark kar sakte hain."),
    ("bulk", r"bulk|upload|अपलोड",
     "Bulk upload analyzes many reviews at once from a CSV file (up to 300 rows). Every file gets its own CSV dashboard and forecast, and the Inbox shows the file you uploaded last.",
     "Bulk upload ek CSV file se ek saath bahut saare reviews (300 tak) analyze karta hai. Har file ka apna CSV dashboard aur forecast banta hai, aur Inbox aakhri uploaded file dikhata hai."),
    ("csv", r"csv dashboard|dashboard|डैशबोर्ड",
     "CSV dashboard shows graphs, the forecast, complaint themes and urgent customers made ONLY from the CSV file you select at the top.",
     "CSV dashboard mein graphs, forecast, complaint themes aur urgent customers dikhte hain, jo sirf aapki selected CSV file se bante hain."),
    ("history", r"history|हिस्ट्री",
     "History lists everything you saved, from every source, with sentiment, emotion and priority. You can download it as a CSV file.",
     "History mein har source se save kiya hua sab kuch dikhta hai, sentiment, emotion aur priority ke saath. Aap ise CSV file mein download kar sakte hain."),
    ("ask", r"ask ?ai|chat ?bot|ask page",
     "Ask AI answers questions about your data, this website and the project in English, Hindi or Hinglish.",
     "Ask AI aapke data, is website aur project ke sawalon ke jawab English, Hindi ya Hinglish mein deta hai."),
    ("feedback", r"feedback (link|form)|customer (link|form)|feedback",
     "The feedback link is a form you share with your customers. Their messages are analyzed by the AI and saved in History (Source: Customer feedback form). The link is at the top of the History page.",
     "Feedback link ek form hai jo aap customers ko bhejti hain. Unke messages AI analyze karta hai aur History mein (Source: Customer feedback form) save hote hain. Link History page ke upar hai."),
    ("reply", r"reply studio|reply",
     "Reply Studio writes a reply for a customer in 4 tones: Professional, Empathetic, Friendly or Short.",
     "Reply Studio customer ke liye reply likhta hai, 4 tone mein: Professional, Empathetic, Friendly ya Short."),
    ("report", r"report|printable",
     "The printable report is a one-page summary. Open it from the summary box and save it as PDF.",
     "Printable report ek page ka summary hai. Isse summary box se kholkar PDF mein save kar sakte hain."),
    ("forecast", r"forecast|predict",
     "Forecast predicts the next 7 sentiment scores by drawing a trend line through the scores of your CSV file. It says improving, stable or declining.",
     "Forecast aapki CSV file ke scores par ek trend line banakar agle 7 scores predict karta hai. Ye batata hai ki sentiment improving, stable ya declining hai."),
    ("churn", r"churn|risk",
     "Churn risk shows how likely a customer is to leave. It uses the negative score, anger and warning words like 'refund' or 'cancel'.",
     "Churn risk batata hai ki customer ke chhod jaane ka kitna khatra hai. Ye negative score, gusse aur 'refund' ya 'cancel' jaise warning words se banta hai."),
    ("priority", r"priority|\bp[123]\b",
     "Priority tells your team who to answer first: P1 = urgent, P2 = high, P3 = normal.",
     "Priority batati hai ki pehle kisko jawab dena hai: P1 = urgent, P2 = high, P3 = normal."),
    ("mixed", r"mixed",
     "A mixed review means the customer likes one thing and dislikes another, like 'product good but delivery late'. The AI shows what is positive and what is negative.",
     "Mixed review ka matlab hai ki customer ko ek cheez pasand hai aur dusri nahi, jaise 'product accha hai lekin delivery late'. AI dikhata hai ki kya positive hai aur kya negative."),
    ("score", r"score",
     "The score goes from 0 to 100. Around 50 is neutral, below about 47 is negative and above about 53 is positive.",
     "Score 0 se 100 tak hota hai. 50 ke aaspaas neutral, lagbhag 47 se kam negative aur 53 se zyada positive hota hai."),
    ("index", r"index",
     "The net sentiment index is the percent of positive reviews minus the percent of negative reviews. +100 means all positive, -100 means all negative.",
     "Net sentiment index = positive reviews ka percent minus negative reviews ka percent. +100 matlab sab positive, -100 matlab sab negative."),
    ("themes", r"theme|cluster|k-?means",
     "Complaint themes group similar negative reviews automatically using K-Means clustering, so you can see the biggest problems.",
     "Complaint themes K-Means clustering se milte-julte negative reviews ko apne aap group karte hain, taaki sabse bade problems dikhein."),
    ("emotion", r"emotion",
     "Emotion finds joy, anger, sadness, fear or surprise from the words a customer used.",
     "Emotion customer ke shabdon se joy, anger, sadness, fear ya surprise pehchanta hai."),
]
GUIDE_TEXT = " ".join(f"{g[0]}: {g[2]}" for g in GUIDE)
CONCEPT_IDS = {"forecast", "churn", "priority", "mixed", "score", "index", "themes", "emotion"}
CUE = (r"kaam|kya hai|kya hota|kya karta|karta hai|matlab|meaning|what is|what does|what's|whats|purpose|used for|"
       r"use of|uses\b|kis liye|kis kaam|kaise use|how to use|how do i use|kaise kaam|how does|explain|samjh|difference|farak|fark|ka kya|क्या है|काम")
DATA_CUE = (r"\bmain\b|common|dominant|\bmere\b|\bmera\b|\bmeri\b|\bmy\b|\bour\b|customers?|reviews?|kitn|average|\bmost\b|zyada|sabse|\btop\b|\bworst\b|"
            r"\bbest\b|highest|lowest|kaun si|konsi|which|how many|total|abhi|current")


def _hits(q):
    q = q.lower()
    return [g for g in GUIDE if re.search(g[1], q)]


def feature_answer(question, prev, hindi, has_data=False):
    """Explain a page/feature when the question asks 'what is / what does / kaam kya hai'."""
    q = question.lower()
    if not re.search(CUE, q):
        return None
    hits = _hits(q)
    if not hits and prev:                       # follow-up like "kaam kya hai simple batao"
        hits = _hits(prev)
    if has_data and re.search(DATA_CUE, q):     # "main emotion kya hai" is a data question, not a definition
        hits = [g for g in hits if g[0] not in CONCEPT_IDS]
    if not hits:
        return None
    return " ".join(g[3] if hindi else g[2] for g in hits[:2])
