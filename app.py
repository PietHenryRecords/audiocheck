from flask import Flask, request, render_template, send_file, session
import os
import numpy as np
import subprocess
from scipy.io import wavfile
from reportlab.pdfgen import canvas
import io

app = Flask(__name__)
app.secret_key = "sicherer-schlüssel"

UPLOAD_FOLDER = 'uploads'
REPORT_FOLDER = 'reports'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORT_FOLDER, exist_ok=True)

def convert_mp3_to_wav(mp3_path, wav_path):
    subprocess.run(["ffmpeg", "-y", "-i", mp3_path, wav_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def calculate_rms(wav_path):
    samplerate, data = wavfile.read(wav_path)
    if data.ndim > 1:
        data = data.mean(axis=1)
    rms = np.sqrt(np.mean(np.square(data / 32768.0)))
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
                wav_path = filepath.replace(".mp3", ".wav")
                convert_mp3_to_wav(filepath, wav_path)
            else:
                wav_path = filepath

            try:
                rms_db = calculate_rms(wav_path)
            except Exception as e:
                report_lines.append(f"❌ Fehler bei {file.filename}: {str(e)}")
                continue

            if rms_db < -24 or rms_db > -18:
                report_lines.append(f"⚠️ Datei: {file.filename}")
                report_lines.append(f" – RMS-Wert außerhalb des Bereichs: {rms_db} dB\n")

        report = "\n".join(report_lines)
        session["bericht_text"] = report
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
