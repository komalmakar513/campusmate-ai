"""CampusMate AI - smart college helpdesk (AZ-900 + AI-900 project)."""
import os, sqlite3, requests
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
EP = os.getenv("AZURE_LANGUAGE_ENDPOINT", "").rstrip("/")
KEY = os.getenv("AZURE_LANGUAGE_KEY", "")
VISION_EP = os.getenv("AZURE_VISION_ENDPOINT", "").rstrip("/")
VISION_KEY = os.getenv("AZURE_VISION_KEY", "")
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




def format_timetable(text, ocr_lines=None):
    import re

    days = ["Monday", "Tuesday", "Wednesday",
            "Thursday", "Friday", "Saturday", "Sunday"]
    result = {"days": days, "rows": [], "valid": False, "message": ""}
    time_pattern = re.compile(
        r"^\s*\d{1,2}(?::\d{2})?\s*(?:AM|PM)?"
        r"(?:\s*(?:-|–|—|to)\s*\d{1,2}(?::\d{2})?\s*(?:AM|PM)?)?\s*$",
        re.I
    )
    day_aliases = {
        alias: day for day in days
        for alias in (day.lower(), day[:3].lower())
    }

    def line_geometry(line):
        bounds = line.get("boundingBox") or line.get("boundingPolygon")
        if isinstance(bounds, dict):
            if all(key in bounds for key in ("x", "y", "width", "height")):
                try:
                    x, y = float(bounds["x"]), float(bounds["y"])
                    return x + float(bounds["width"]) / 2, y + float(bounds["height"]) / 2
                except (TypeError, ValueError):
                    return None
            bounds = bounds.get("points", [])

        try:
            if bounds and isinstance(bounds[0], dict):
                xs = [float(point["x"]) for point in bounds]
                ys = [float(point["y"]) for point in bounds]
            else:
                values = [float(value) for value in bounds]
                if len(values) == 4:
                    x, y, width, height = values
                    return x + width / 2, y + height / 2
                else:
                    xs, ys = values[0::2], values[1::2]
            if not xs or not ys:
                return None
            return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        except (TypeError, ValueError, KeyError, IndexError):
            return None

    positioned = []
    for line in ocr_lines or []:
        if not isinstance(line, dict):
            continue
        value = line.get("text", "").strip()
        center = line_geometry(line)
        if value and center is not None:
            positioned.append({"text": value, "x": center[0], "y": center[1]})

    if not positioned:
        result["message"] = "Timetable layout could not be detected from OCR coordinates."
        return result

    day_positions = {}
    for line in positioned:
        normalized = re.sub(r"[^a-z]", "", line["text"].lower())
        day = day_aliases.get(normalized)
        if day:
            day_positions.setdefault(day, []).append(line["x"])

    day_centers = sorted(
        (sum(xs) / len(xs), day) for day, xs in day_positions.items()
    )
    time_lines = sorted(
        (line["y"], line["text"], line["x"])
        for line in positioned
        if time_pattern.fullmatch(line["text"])
    )
    if len(day_centers) < 2 or not time_lines:
        result["message"] = "Could not reliably identify timetable day columns and time slots."
        return result

    # Time labels belong to the time column to the left of the first day header.
    time_lines = [entry for entry in time_lines if entry[2] < day_centers[0][0]]
    if not time_lines:
        result["message"] = "No time slots were found to the left of the weekday columns."
        return result

    rows = [{
        "time": label,
        "cells": {
            day: {"subject": "", "teacher": "", "room": ""}
            for day in days
        }
    } for _, label, _ in time_lines]
    cell_lines = [[[] for _ in days] for _ in rows]
    day_indices = {day: index for index, day in enumerate(days)}

    for line in positioned:
        normalized = re.sub(r"[^a-z]", "", line["text"].lower())
        if normalized in day_aliases or time_pattern.fullmatch(line["text"]):
            continue

        day_spacing = day_centers[1][0] - day_centers[0][0]
        left_edge = day_centers[0][0] - day_spacing / 2
        right_edge = day_centers[-1][0] + (
            day_centers[-1][0] - day_centers[-2][0]
        ) / 2
        if not left_edge <= line["x"] <= right_edge:
            continue

        day_index = min(
            range(len(day_centers)),
            key=lambda index: abs(day_centers[index][0] - line["x"])
        )

        row_index = min(
            range(len(time_lines)),
            key=lambda index: abs(time_lines[index][0] - line["y"])
        )
        if len(time_lines) > 1:
            lower = (
                (time_lines[0][0] - (time_lines[1][0] - time_lines[0][0]) / 2)
                if row_index == 0 else
                (time_lines[row_index - 1][0] + time_lines[row_index][0]) / 2
            )
            upper = (
                (time_lines[-1][0] + (time_lines[-1][0] - time_lines[-2][0]) / 2)
                if row_index == len(time_lines) - 1 else
                (time_lines[row_index][0] + time_lines[row_index + 1][0]) / 2
            )
            if not lower <= line["y"] <= upper:
                continue

        day = day_centers[day_index][1]
        cell_lines[row_index][day_indices[day]].append(line)

    room_pattern = re.compile(
        r"\b(?:(?:room|rm|lab|block)\s*(?:no\.?|#)?\s*"
        r"[A-Z]?\s*[-–]?\s*\d+[A-Z]?|[A-Z][-– ]?\d{2,4}[A-Z]?)\b",
        re.I
    )
    teacher_pattern = re.compile(
        r"\b(?:Dr\.?|Prof(?:essor)?\.?|Mr\.?|Mrs\.?|Ms\.?|Er\.?)\s+"
        r"[A-Z][\w.'-]*(?:\s+[A-Z][\w.'-]*){0,3}",
        re.I
    )

    def format_cell(lines):
        content = " ".join(line["text"] for line in sorted(lines, key=lambda item: item["y"]))
        room_match = room_pattern.search(content)
        room = room_match.group().strip() if room_match else ""
        if room_match:
            content = content[:room_match.start()] + " " + content[room_match.end():]

        teacher_match = re.search(
            r"\b(?:by|teacher|instructor)\s*[:\-]?\s*(.+?)(?=$)",
            content, re.I
        )
        if teacher_match:
            teacher = teacher_match.group(1).strip()
            content = content[:teacher_match.start()]
        else:
            teacher_match = teacher_pattern.search(content)
            teacher = teacher_match.group().strip() if teacher_match else ""
            if teacher_match:
                content = content[:teacher_match.start()] + " " + content[teacher_match.end():]

        subject = re.sub(r"\s+", " ", content).strip(" \t,;:-")
        return {"subject": subject, "teacher": teacher, "room": room}

    for row_index, row in enumerate(rows):
        for day_index, day in enumerate(days):
            row["cells"][day] = format_cell(cell_lines[row_index][day_index])

    result["rows"] = rows
    result["valid"] = True
    return result



@app.post("/api/ocr")
def ocr():
    f = request.files.get("image")

    if not f:
        return jsonify(error="No image uploaded"), 400

    if DEMO:
        return jsonify(
            text="[Demo Mode] Add Azure AI credentials."
        )

    try:
        url = f"{VISION_EP}/computervision/imageanalysis:analyze"

        params = {
            "api-version": "2024-02-01",
            "features": "read"
        }

        headers = {
            "Ocp-Apim-Subscription-Key": VISION_KEY,
            "Content-Type": "application/octet-stream"
        }

        r = requests.post(
            url,
            params=params,
            headers=headers,
            data=f.read(),
            timeout=30
        )

        if not r.ok:
            return jsonify(
                error="Azure OCR error",
                details=r.text[:500]
            ), 502

        result = r.json()

        ocr_lines = [
            line
            for block in result.get("readResult", {}).get("blocks", [])
            for line in block.get("lines", [])
        ]

        text = "\n".join(
            line.get("text", "") for line in ocr_lines
            if isinstance(line, dict) and line.get("text")
        ) or "No text found"

        return jsonify(
            text=text,
            timetable=format_timetable(text, ocr_lines)
        )


    except requests.RequestException as e:
        return jsonify(error=str(e)), 502



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
