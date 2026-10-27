# Customer Sentiment AI

A working customer-feedback tool. Real customers write feedback, the AI analyzes it, your team replies.

## Run (Windows)
Open PowerShell. Replace the path below with the folder that contains `app.py`
(the INNER `customer-sentiment-ai` folder, not the outer one).

### First time only (setup)
    cd C:\Users\acer\Downloads\customer-sentiment-ai\customer-sentiment-ai
    python -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt

### Every time you want to run it
    cd C:\Users\acer\Downloads\customer-sentiment-ai\customer-sentiment-ai
    venv\Scripts\activate
    python app.py

Wait until the window says `Running on http://127.0.0.1:5000`, then open that address in your browser
(press Ctrl+F5 after an update). Keep the window open while you use the site. Press Ctrl+C to stop it.
Your accounts and data are saved in `sentiment.db`, so they are still there next time.

### One command, no activating
    cd C:\Users\acer\Downloads\customer-sentiment-ai\customer-sentiment-ai
    venv\Scripts\python.exe app.py

### Easiest way
Double-click `run.bat` in this folder. It creates the venv if needed, installs the requirements and starts the server.

### Common problems
- `activate` is blocked ("running scripts is disabled"): run once  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
- "can't open file app.py": you are in the outer folder. Run `cd customer-sentiment-ai` and check that `dir` shows `app.py`.
- "Address already in use": close the old window, or use another port:  `$env:PORT="5001"; python app.py`  then open http://127.0.0.1:5001
- "refused to connect" in the browser: the server window was closed. Start it again with the commands above.
- Moved the project to another folder or PC: delete the `venv` folder and repeat the first-time setup.

## Ask AI
Answers about your reviews, the website pages and the project, in English, Hindi and Hinglish. Built in, no key needed.

## What works on what
- Overview, Analyze, History: everything you saved, combined (as always).
- CSV dashboard + forecast, AI insights, complaint themes: ONLY the one CSV file you select.
- Inbox: empty at every login. After you upload a CSV it shows only that file's messages. 'Clear Inbox' empties it again. Nothing is deleted; old reviews stay in History and the CSV dashboard.
- Reviews you save in Analyze, and messages from your feedback link, go to History (and Overview) only.
- Ask AI follows the CSV selected in the CSV dashboard.

## How a business uses it
1. Register. Open **History** and copy your private feedback link.
2. Send the link to customers (WhatsApp, email, website).
3. Each message is analyzed by the AI the moment it arrives and is saved in History (Source: Customer feedback form).
4. Upload a CSV in **Bulk upload**: its messages appear in the **Inbox**, urgent customers first. Write a reply (4 tones), send it by email, mark it Replied or Resolved.
5. Overview, AI insights, Ask AI and the printable Report update from the real data.
Also: Analyze any review by hand in **Analyze**.

## CSV upload rules
- A .csv file, up to 2 MB and 300 reviews. Rows after 300 are not analyzed (the page tells you).
- First row = header. The review column is found automatically: a column called `review`, `text`, `comment`, `feedback`, `message` or `description` is used first. Columns like `reviewer_name`, `title` or `rating` are skipped.
- Commas, semicolons and tabs are accepted. Excel: File > Save As > CSV UTF-8. `.xlsx` files are not accepted.
- You can click anywhere in the dashed box, or drag the file onto the page.

## Let customers outside your computer open the link
- Same Wi-Fi: run  `set HOST=0.0.0.0`  then  `python app.py`, and share  http://YOUR-PC-IP:5000/f/...
- Internet: deploy the project on a web server (PythonAnywhere, Render) and set a strong SECRET_KEY.

## Languages
English, Hinglish (Hindi in English letters) and Hindi script work in the analyzer and in Ask AI.
Mixed reviews ("product good but delivery late") are shown as Mixed review with the reason.

## AI features
3 models vote (VADER, our Naive Bayes ML model, optional DistilBERT) - emotion - topic-by-topic sentiment -
Hinglish support - intent - churn risk and P1/P2/P3 priority - complaint themes (K-Means) -
forecast and alerts - Reply Studio - Ask AI chat.

## Optional upgrade
    pip install transformers torch     -> DistilBERT deep-learning model

## Train the ML model on real data
    python train_model.py reviews.csv      (columns: text,label  with Positive/Neutral/Negative)
The built-in starter data is generated from templates, so its accuracy number is NOT real-world accuracy.

## Files
    app.py  sentiment_engine.py  ml_model.py  insights.py  knowledge.py  guide.py  database.py  train_model.py
    templates/ (landing, auth, dashboard, public feedback form, report)   static/ (css, js)
