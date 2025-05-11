from flask import Flask, request, render_template, send_file, session
import os
from pydub import AudioSegment
import numpy as np
from reportlab.pdfgen import canvas
import io

app = Flask(__name__)
app.secret_key = "sicherer-schlüssel"  # nötig für Session

UPLOAD_FOLDER = 'uploads'
REPORT_FOLDER = 'reports'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORT_FOLDER, exist_ok=True)

def calculate_rms(audio):
    rms = audio.rms / (2**15)
    rms_db = 20 * np.log10(rms)
    return round(rms_db, 2)

@app.route("/", methods=["GET", "POST"])
def index():
    report = ""
    if request.method == "POST":
        files = request.files.getlist("files")
        report_lines = []

        for file in files:
            filepath = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(filepath)

            if file.filename.endswith(".mp3"):
                audio = AudioSegment.from_mp3(filepath)
            else:
                audio = AudioSegment.from_wav(filepath)

            rms_db = calculate_rms(audio)

            issues = []
            if rms_db < -24 or rms_db > -18:
                issues.append(f"RMS-Wert außerhalb des zulässigen Bereichs: {rms_db} dB")

            if issues:
                report_lines.append(f"⚠️ Datei: {file.filename}")
                report_lines.extend([f" – {issue}" for issue in issues])
                report_lines.append("")

        report = "\n".join(report_lines)
        session["bericht_text"] = report  # für PDF-Export

        return render_template("index.html", report=report)

    return render_template("index.html", report=None)

@app.route("/download_pdf")
def download_pdf():
    report = session.get("bericht_text", "Kein Bericht vorhanden.")
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)
    p.setFont("Helvetica", 12)

    y = 800
    for line in report.split("\n"):
        p.drawString(50, y, line)
        y -= 20
        if y < 50:
            p.showPage()
            y = 800

    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="bericht.pdf", mimetype="application/pdf")

if __name__ == "__main__":
    app.run(debug=True)
