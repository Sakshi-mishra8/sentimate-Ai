"""
knowledge.py - everything Ask AI knows about THIS project (works without any API key).

Each entry has keywords, a title, and an answer in English and Hinglish.
kb_answer() scores the question against all keywords and returns the best match.
"""
import re

KB = [
    {"id": "run", "title": "How to run the project",
     "kw": ["run.bat", "start project", "project start", "how to run", "kaise chalau", "kaise chalaye", "kaise chalana",
            "chalu kaise", "project chalu", "server start", "python app.py", "open website", "website kholni", "127.0.0.1", "localhost"],
     "en": "Double-click run.bat in the project folder. Wait until the black window says 'Running on http://127.0.0.1:5000', then open that address in your browser. Keep the black window open while you use the site.",
     "hi": "Project folder mein run.bat par double-click karein. Black window mein 'Running on http://127.0.0.1:5000' aane tak rukein, phir wo address browser mein kholein. Site use karte waqt black window khuli rakhein."},
    {"id": "csvfmt", "title": "What a CSV file must look like",
     "kw": ["csv format", "csv kaisi", "csv kaise", "csv banana", "csv template", "csv ka format", "review column", "header row",
            "excel se csv", "save as csv", "csv me kya", "file format", "kaisi file", "csv file kaisi", "csv kya chahiye"],
     "en": "Use a .csv file whose first row is a header, for example 'review', with one customer review in each row. Column names like text, comment or feedback also work, and commas, semicolons and tabs are all accepted. In Excel use Save As and choose CSV. A template is on the Bulk upload page.",
     "hi": "Aisi .csv file banayein jiski pehli row header ho, jaise 'review', aur har row mein ek customer review. text, comment ya feedback naam bhi chalte hain, aur comma, semicolon ya tab sab chalte hain. Excel mein Save As karke CSV chunein. Template Bulk upload page par hai."},
    {"id": "limits", "title": "Upload limits",
     "kw": ["limit", "max rows", "kitne rows", "kitni rows", "2 mb", "300 rows", "size limit", "how many rows", "upload limit", "kitne reviews upload"],
     "en": "One upload can have up to 300 reviews, and the file can be up to 2 MB. Rows after 300 are ignored, so split bigger files.",
     "hi": "Ek upload mein 300 reviews tak aur file 2 MB tak ho sakti hai. 300 ke baad ki rows chhod di jaati hain, isliye badi file ko tod kar upload karein."},
    {"id": "howai", "title": "How the AI works",
     "kw": ["ai kaise", "how does the ai", "how ai works", "how it works", "kaise kaam karta", "kaise analyze", "kaise pata", "algorithm",
            "kaunsa model", "which model", "models vote", "3 models", "pipeline", "kaise samajhta", "working of ai", "kaise kaam"],
     "en": "Each review is cleaned first (typos, emojis, Hinglish negation). Then three models vote: VADER (language rules), our own Naive Bayes ML model, and optionally DistilBERT (deep learning). The AI then checks sarcasm and mixed opinions, finds the emotion and topics, predicts churn risk and priority, and writes a reply.",
     "hi": "Pehle review saaf hota hai (typos, emojis, Hinglish negation). Phir teen models vote karte hain: VADER (language rules), hamara apna Naive Bayes ML model, aur optional DistilBERT (deep learning). Uske baad AI sarcasm aur mixed opinion check karta hai, emotion aur topics nikalta hai, churn risk aur priority batata hai, aur reply likhta hai."},
    {"id": "vader", "title": "What VADER is",
     "kw": ["vader", "lexicon", "rule based", "rules wala"],
     "en": "VADER is a ready-made NLP model. It gives every word a positive or negative weight and understands negation, CAPITALS and words like 'very'. We added customer-service, Hinglish and Hindi words to it.",
     "hi": "VADER ek ready-made NLP model hai. Ye har shabd ko positive ya negative weight deta hai aur negation, CAPITAL letters aur 'very' jaise shabd samajhta hai. Humne ismein customer-service, Hinglish aur Hindi ke shabd jode hain."},
    {"id": "nb", "title": "Our own ML model",
     "kw": ["naive bayes", "ml model", "our model", "apna model", "machine learning model", "trained model", "train kaise", "train model", "dataset", "training data"],
     "en": "Our ML model is Naive Bayes on words and word pairs, written in pure Python. It is trained on a generated starter dataset, so its accuracy number is optimistic. To train it on real reviews run: python train_model.py your_reviews.csv (columns: text,label).",
     "hi": "Hamara ML model words aur word-pairs par Naive Bayes hai, jo pure Python mein likha hai. Ye ek generated starter dataset par trained hai, isliye iski accuracy zyada dikhti hai. Asli reviews par train karne ke liye chalayein: python train_model.py your_reviews.csv (columns: text,label)."},
    {"id": "bert", "title": "DistilBERT (deep learning)",
     "kw": ["distilbert", "transformer", "deep learning", "bert", "neural"],
     "en": "DistilBERT is a deep-learning model that understands context better. It is optional: run pip install transformers torch, then choose DistilBERT or Ensemble in Analyze. The first download is large.",
     "hi": "DistilBERT ek deep-learning model hai jo context behtar samajhta hai. Ye optional hai: pip install transformers torch chalayein, phir Analyze mein DistilBERT ya Ensemble chunein. Pehli baar download bada hota hai."},
    {"id": "kmeans", "title": "How complaint themes are found",
     "kw": ["k-means", "kmeans", "clustering", "cluster", "themes kaise", "theme kaise"],
     "en": "K-Means is an unsupervised learning method. It turns negative reviews into numbers (TF-IDF) and groups the ones that talk about similar things, without any labels. Each group becomes a complaint theme.",
     "hi": "K-Means ek unsupervised learning method hai. Ye negative reviews ko numbers (TF-IDF) mein badalta hai aur milte-julte reviews ko bina kisi label ke group karta hai. Har group ek complaint theme banta hai."},
    {"id": "defs", "title": "What sentiment analysis, NLP and AI mean",
     "kw": ["sentiment analysis kya", "what is sentiment analysis", "sentiment kya hota", "nlp kya", "what is nlp", "machine learning kya",
            "what is machine learning", "ai kya hai", "what is ai", "sentiment kya hai", "sentiment analysis"],
     "en": "Sentiment analysis means a computer reads text and decides if the writer feels positive, negative or neutral. It uses NLP (Natural Language Processing), which teaches computers to read human language, and machine learning, where the computer learns patterns from examples.",
     "hi": "Sentiment analysis ka matlab hai ki computer text padhkar batata hai ki likhne wala positive, negative ya neutral mehsoos kar raha hai. Ismein NLP (Natural Language Processing) use hota hai, jo computer ko insaani bhasha padhna sikhata hai, aur machine learning, jisme computer examples se patterns seekhta hai."},
    {"id": "accuracy", "title": "How accurate the AI is",
     "kw": ["accuracy", "kitna sahi", "how accurate", "kitni sahi", "wrong result", "sahi nahi", "reliable", "trust", "bharosa", "galat result", "galat answer"],
     "en": "On new sentences I tested it was about 79 percent correct, and about 65 percent on a deliberately tricky file. It is weaker with subtle sarcasm and mild mixed opinions. Training on real data and turning on DistilBERT makes it better. The 94 percent on the model card is measured on generated data, so it is optimistic.",
     "hi": "Naye sentences par test karne par ye lagbhag 79 percent sahi tha, aur jaanbujhkar mushkil file par lagbhag 65 percent. Ye subtle sarcasm aur halke mixed opinions mein kamzor hai. Asli data par training aur DistilBERT on karne se behtar hota hai. Model card par dikhne wala 94 percent generated data par hai, isliye zyada dikhta hai."},
    {"id": "langs", "title": "Languages supported",
     "kw": ["language", "bhasha", "hindi me", "hinglish", "english only", "kaun si language", "devanagari", "hindi script", "languages"],
     "en": "The AI works in English, Hinglish (Hindi in English letters) and Hindi script. Ask AI also answers in Hinglish when you ask in Hindi or Hinglish.",
     "hi": "AI English, Hinglish (English letters mein Hindi) aur Hindi script mein kaam karta hai. Hindi ya Hinglish mein poochne par Ask AI Hinglish mein jawab deta hai."},
    {"id": "sarcasm", "title": "Sarcasm",
     "kw": ["sarcasm", "taana", "vyang", "mazak", "sarcastic"],
     "en": "The AI catches simple sarcasm like 'Oh great, another delay' and marks it negative. Subtle sarcasm can still be missed.",
     "hi": "AI 'Oh great, another delay' jaisa simple sarcasm pakad leta hai aur use negative maanta hai. Bahut halka sarcasm abhi bhi chhoot sakta hai."},
    {"id": "share", "title": "How to share the feedback link",
     "kw": ["link share", "link kaise", "link bhej", "share link", "same wifi", "ngrok", "public link", "link kaam nahi", "doosre device",
            "other device", "mobile se", "dost ko link", "friend ko link", "link friend"],
     "en": "The feedback link starts with 127.0.0.1, which opens only on your own computer. For friends on your Wi-Fi run $env:HOST=\"0.0.0.0\" and then python app.py, and share http://YOUR-PC-IP:5000/f/... (find the IP with ipconfig). For anyone on the internet, deploy the project (for example on PythonAnywhere) or use a tunnel like ngrok.",
     "hi": "Feedback link 127.0.0.1 se shuru hota hai, jo sirf aapke computer par khulta hai. Wi-Fi par dosto ke liye $env:HOST=\"0.0.0.0\" chalayein, phir python app.py, aur http://YOUR-PC-IP:5000/f/... bhejein (IP ipconfig se milta hai). Internet par kisi ko bhi dene ke liye project deploy karein (jaise PythonAnywhere par) ya ngrok jaisa tunnel use karein."},
    {"id": "deploy", "title": "How to put the project live",
     "kw": ["deploy", "github", "live kaise", "go live", "pythonanywhere", "render", "hosting", "website live", "internet par", "online kaise"],
     "en": "GitHub only stores code; it cannot run Flask. Push the code to GitHub, then run it live on a host such as PythonAnywhere (free): clone the repository, create a venv, pip install -r requirements.txt, set the Source code and Virtualenv paths on the Web tab, edit the WSGI file, and click Reload. Also set a strong SECRET_KEY.",
     "hi": "GitHub sirf code rakhta hai, Flask nahi chala sakta. Code GitHub par daalein, phir PythonAnywhere (free) jaise host par live karein: repository clone karein, venv banayein, pip install -r requirements.txt chalayein, Web tab par Source code aur Virtualenv path set karein, WSGI file edit karein aur Reload dabayein. Ek majboot SECRET_KEY bhi set karein."},
    {"id": "privacy", "title": "Privacy and security",
     "kw": ["privacy", "secure", "security", "data safe", "kaun dekh", "private", "surakshit", "safe hai", "password safe"],
     "en": "Each account sees only its own reviews. Passwords are stored hashed, not as plain text. Nothing is sent to any outside AI service; the analysis runs on your own computer.",
     "hi": "Har account sirf apne reviews dekhta hai. Passwords hash karke store hote hain, plain text mein nahi. Koi data kisi bahari AI service ko nahi bheja jaata; analysis aapke apne computer par hota hai."},
    {"id": "delete", "title": "How to delete data",
     "kw": ["delete", "remove data", "data hatao", "data delete", "clear data", "mitana", "hatana", "data kaise hataye"],
     "en": "In CSV dashboard, 'Delete this file's data' removes one uploaded file. In History, 'Delete all my data' removes everything.",
     "hi": "CSV dashboard mein 'Delete this file's data' ek uploaded file hatata hai. History mein 'Delete all my data' sab kuch hata deta hai."},
    {"id": "export", "title": "Download and print",
     "kw": ["download", "export", "pdf", "report save", "save report", "print", "csv download"],
     "en": "History has 'Download CSV' for your saved reviews. The report page can be printed or saved as PDF with the Print button.",
     "hi": "History mein 'Download CSV' se saved reviews download hote hain. Report page ko Print button se print ya PDF mein save kar sakte hain."},
    {"id": "account", "title": "Login and account",
     "kw": ["login", "register", "account", "forgot password", "password bhool", "reset password", "sign up", "logout", "password reset"],
     "en": "Create an account with Register, then log in. Password reset is not built yet, so remember your password; you can always register another account with a different email.",
     "hi": "Register se account banayein, phir login karein. Password reset abhi nahi bana hai, isliye password yaad rakhein; aap hamesha dusre email se naya account bana sakti hain."},
    {"id": "tech", "title": "Technology used",
     "kw": ["tech stack", "technology", "technologies", "kis language", "kaun si language me bana", "python", "flask", "sqlite", "database", "frontend", "backend", "tools used", "libraries"],
     "en": "Backend: Python and Flask with a SQLite database. AI: VADER, our Naive Bayes model, NumPy K-Means and regression, and optional DistilBERT. Frontend: HTML, CSS, JavaScript and Chart.js.",
     "hi": "Backend: Python aur Flask, database SQLite. AI: VADER, hamara Naive Bayes model, NumPy K-Means aur regression, aur optional DistilBERT. Frontend: HTML, CSS, JavaScript aur Chart.js."},
    {"id": "files", "title": "Project files",
     "kw": ["files", "structure", "folder", "kaun si file", "code kahan", "project structure", "source code", "file kya karti"],
     "en": "app.py is the server and API. sentiment_engine.py does the AI analysis. ml_model.py is our trained model. insights.py has clustering, forecast and Ask AI. knowledge.py and guide.py hold Ask AI's project knowledge. database.py stores data. templates/ and static/ hold the pages.",
     "hi": "app.py server aur API hai. sentiment_engine.py AI analysis karta hai. ml_model.py hamara trained model hai. insights.py mein clustering, forecast aur Ask AI hai. knowledge.py aur guide.py mein Ask AI ka project knowledge hai. database.py data store karta hai. templates/ aur static/ mein pages hain."},
    {"id": "features", "title": "All features",
     "kw": ["features", "kya kya", "sab kuch", "what can", "capabilities", "kya kar sakta", "list of features", "sare features", "all features", "feature list"],
     "en": "Analyze one review; upload CSV files; a CSV dashboard with forecast, themes and urgent customers; an Inbox that shows the CSV you just uploaded, with AI replies; a customer feedback link whose messages go to History; Overview and History of everything saved; Hinglish and Hindi support; sarcasm and mixed-review detection; churn risk and priority; a printable report; and this Ask AI.",
     "hi": "Ek review analyze karna; CSV upload; forecast, themes aur urgent customers wala CSV dashboard; abhi upload ki hui CSV ka Inbox AI reply ke saath; customer feedback link jiske messages History mein jaate hain; sab saved ka Overview aur History; Hinglish aur Hindi support; sarcasm aur mixed-review detection; churn risk aur priority; printable report; aur ye Ask AI."},
    {"id": "future", "title": "Limitations and future work",
     "kw": ["limitation", "kamiyan", "kamzori", "weakness", "future scope", "improvement", "aage kya", "future work", "aur kya add", "drawback"],
     "en": "Limits: the ML model is trained on generated data, subtle sarcasm is missed, and there is no password reset or email sending. Future work: train on a real review dataset, add DistilBERT by default, connect real review sources through APIs, and deploy online.",
     "hi": "Kamiyan: ML model generated data par trained hai, halka sarcasm chhoot jaata hai, aur password reset ya email bhejna nahi hai. Aage ka kaam: asli review dataset par training, DistilBERT default karna, API se asli review sources jodna, aur online deploy karna."},
    {"id": "viva", "title": "How to explain the project",
     "kw": ["viva", "presentation", "explain project", "project samjha", "interview", "teacher", "professor", "sir ko kya", "project kaise samjhau"],
     "en": "You can say: 'It is a web app where a business collects customer feedback. The AI reads each message for sentiment, emotion, topics, churn risk and intent, shows a dashboard and a forecast for each uploaded CSV, and helps the team reply.' Be honest that the starter ML model is trained on generated data.",
     "hi": "Aap keh sakti hain: 'Ye ek web app hai jahan business customer feedback ikattha karta hai. AI har message ka sentiment, emotion, topics, churn risk aur intent padhta hai, har uploaded CSV ka dashboard aur forecast dikhata hai, aur team ko reply likhne mein madad karta hai.' Imaandari se batayein ki starter ML model generated data par trained hai."},
    {"id": "status", "title": "What New, Replied and Resolved mean",
     "kw": ["replied", "resolved", "new status", "mark replied", "mark resolved", "status kya"],
     "en": "New means nobody handled it yet. Replied means you answered. Resolved means the problem is fixed. 'Needs action' shows New messages that need an answer, and 'Done' shows Replied and Resolved ones.",
     "hi": "New ka matlab hai abhi kisi ne dekha nahi. Replied ka matlab aapne jawab diya. Resolved ka matlab problem theek ho gayi. 'Needs action' mein wo New messages aate hain jinhe jawab chahiye, aur 'Done' mein Replied aur Resolved wale."},
    {"id": "live", "title": "Real-time messages",
     "kw": ["live monitor", "real time", "realtime", "live feed", "live reviews"],
     "en": "The simulated Live monitor was removed. Customers can now send real messages through your feedback link; they are saved in History. The Inbox refreshes every 15 seconds.",
     "hi": "Nakli Live monitor hata diya gaya hai. Ab customers aapke feedback link se asli messages bhej sakte hain; wo History mein save hote hain. Inbox har 15 second mein refresh hota hai."},
    {"id": "trouble", "title": "Fixing errors",
     "kw": ["error", "not working", "kaam nahi", "install", "pip", "dll", "blocked", "port", "refused", "nahi chal", "problem aa", "crash"],
     "en": "Common fixes: 'refused to connect' means the black window is not running, so start run.bat again. A pip error means the internet is off or you are in the wrong folder; the folder must contain app.py. A 'DLL blocked' error is a Windows policy; this project avoids scikit-learn for that reason. After an update press Ctrl+F5 in the browser.",
     "hi": "Aam solutions: 'refused to connect' ka matlab black window band hai, run.bat dobara chalayein. pip error ka matlab internet band hai ya galat folder mein hain; folder mein app.py hona chahiye. 'DLL blocked' Windows policy ki wajah se aata hai; isiliye ye project scikit-learn use nahi karta. Update ke baad browser mein Ctrl+F5 dabayein."},
    {"id": "update", "title": "Updating to a new version",
     "kw": ["new version", "naya zip", "extract", "purana", "old version", "version", "update kaise"],
     "en": "Extract the new zip into a fresh folder, double-click run.bat, then press Ctrl+F5 in the browser. The version name is shown at the bottom of the left menu, so you can check that you run the new one.",
     "hi": "Naya zip nayi khali folder mein extract karein, run.bat double-click karein, phir browser mein Ctrl+F5 dabayein. Left menu ke neeche version ka naam dikhta hai, isse check kar sakti hain ki naya version chal raha hai."},
    {"id": "cost", "title": "Cost",
     "kw": ["free", "paid", "cost", "kitna paisa", "charges", "subscription", "paisa lagega", "api key"],
     "en": "The project is completely free to run. It needs no paid service or API key.",
     "hi": "Project chalana bilkul free hai. Ismein koi paid service ya API key nahi lagti."},
    {"id": "channels", "title": "What channels mean",
     "kw": ["channel kya", "channels kya", "source kya", "channel ka matlab"],
     "en": "A channel is where the review came from, such as Website, Amazon, Play Store, Social media, Email or the Feedback form. It helps you see which source has unhappy customers.",
     "hi": "Channel ka matlab hai review kahan se aaya, jaise Website, Amazon, Play Store, Social media, Email ya Feedback form. Isse pata chalta hai ki kis source par customers naraz hain."},
    {"id": "about", "title": "Who built it",
     "kw": ["who made", "kisne banaya", "creator", "developer", "made by", "author", "kisne bnaya"],
     "en": "This is the Customer Sentiment AI project, a BCA project built with Python and Flask.",
     "hi": "Ye Customer Sentiment AI project hai, ek BCA project jo Python aur Flask mein bana hai."},
]

KB_TEXT = " ".join(f"{e['title']}: {e['en']}" for e in KB)


def _score(q: str, entry) -> int:
    pts = 0
    for kw in entry["kw"]:
        if kw in q:
            pts += 2 if len(kw) >= 8 else 1
    return pts


def kb_answer(question: str, hindi: bool, min_points: int = 2):
    """Return (answer or None, [titles of the 3 closest topics])."""
    q = re.sub(r"\s+", " ", question.lower())
    scored = sorted(((_score(q, e), e) for e in KB), key=lambda t: -t[0])
    best_pts, best = scored[0]
    near = [e["title"] for pts, e in scored[:3] if pts > 0]
    if best_pts >= min_points:
        return best["hi" if hindi else "en"], near
    return None, near
