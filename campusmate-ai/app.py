"""CampusMate AI - smart college helpdesk (AZ-900 + AI-900 project)."""
import os, sqlite3, requests
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
EP = os.getenv("AZURE_LANGUAGE_ENDPOINT", "").rstrip("/")
KEY = os.getenv("AZURE_LANGUAGE_KEY", "")
REGION = os.getenv("AI_REGION", "centralindia")
DEMO = not (EP and KEY)
# /home is persistent storage on Azure App Service
DB = "/tmp/campusmate.db" if os.getenv("VERCEL") or os.path.exists("/var/task") else "campusmate.db"
H = {"Ocp-Apim-Subscription-Key": KEY}


def db():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS feedback(
        id INTEGER PRIMARY KEY, text TEXT, sentiment TEXT, phrases TEXT,
        ts DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    return c



def language(kind, text):
    url = f"{EP}/language/:analyze-text"
    params = {"api-version": "2023-04-01"}

    payload = {
        "kind": kind,
        "analysisInput": {
            "documents": [
                {"id": "1", "text": text}
            ]
        }
    }

    r = requests.post(
        url,
        params=params,
        headers=H,
        json=payload,
        timeout=20
    )
    r.raise_for_status()
    return r.json()["results"]["documents"][0]



@app.get("/")
def home():
    return render_template("index.html", demo=DEMO)


@app.post("/api/feedback")  # AI-900: NLP -> sentiment + key phrases
def feedback():
    text = (request.json or {}).get("text", "").strip()
    if not text:
        return jsonify(error="Empty feedback"), 400
    if DEMO:
        bad = any(w in text.lower() for w in ["bad", "worst", "slow", "dirty", "late", "problem"])
        good = any(w in text.lower() for w in ["good", "great", "best", "clean", "helpful", "thanks"])
        sent = "negative" if bad else "positive" if good else "neutral"
        phrases = [w for w in text.split() if len(w) > 5][:4]
    else:
        sent = language("SentimentAnalysis", text)["sentiment"]
        phrases = language("KeyPhraseExtraction", text)["keyPhrases"]
    with db() as c:
        c.execute("INSERT INTO feedback(text,sentiment,phrases) VALUES(?,?,?)", (text, sent, ", ".join(phrases)))
    return jsonify(sentiment=sent, phrases=phrases)


@app.get("/api/dashboard")  # admin view
def dashboard():
    with db() as c:
        counts = dict(c.execute("SELECT sentiment, COUNT(*) FROM feedback GROUP BY sentiment"))
        rows = c.execute("SELECT text,sentiment,phrases,ts FROM feedback ORDER BY id DESC LIMIT 10").fetchall()
    return jsonify(counts=counts, recent=rows)


@app.post("/api/ocr")  # AI-900: Computer Vision -> read text from notice image
def ocr():
    f = request.files.get("image")
    if not f:
        return jsonify(error="No image"), 400
    if DEMO:
        return jsonify(text="[Demo Mode] Add AI_KEY to read real text from your notice image.")
    r = requests.post(f"{EP}/computervision/imageanalysis:analyze?api-version=2023-10-01&features=read",
        headers={**H, "Content-Type": "application/octet-stream"}, data=f.read(), timeout=30)
    r.raise_for_status()
    lines = [l["text"] for b in r.json().get("readResult", {}).get("blocks", []) for l in b["lines"]]
    return jsonify(text="\n".join(lines) or "No text found")


@app.post("/api/translate")  # AI-900: Translator (English <-> Hindi)
def translate():
    d = request.json or {}
    text, to = d.get("text", ""), d.get("to", "hi")
    if DEMO:
        return jsonify(text=f"[Demo Mode] ({to}) {text}")
    r = requests.post(f"https://api.cognitive.microsofttranslator.com/translate?api-version=3.0&to={to}",
        headers={**H, "Ocp-Apim-Subscription-Region": REGION, "Content-Type": "application/json"},
        json=[{"Text": text}], timeout=20)
    r.raise_for_status()
    return jsonify(text=r.json()[0]["translations"][0]["text"])


@app.get("/health")  # used by Azure health checks / monitoring
def health():
    return jsonify(status="ok", demo=DEMO)


if __name__ == "__main__":
    app.run(debug=True)
