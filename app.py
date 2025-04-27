from flask import Flask, render_template, request, send_file
import os
import re
import subprocess
import io
import csv

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Globale Variable für Ergebnisse
reports_global = []

# Dateiname-Muster: z.B. 001_Titel.mp3
FILENAME_PATTERN = re.compile(r'^\d{3}_.*\.mp3$')


def analyze_audio(filepath):
    try:
        cmd = [
            'ffmpeg', '-hide_banner', '-nostats', '-i', filepath,
            '-af', 'volumedetect',
            '-f', 'null', '-'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        output = result.stderr

        mean_volume = None
        for line in output.splitlines():
            if "mean_volume:" in line:
                parts = line.split('mean_volume:')[-1].strip()
                mean_volume = float(parts.split(' ')[0].replace('dB', ''))

        return mean_volume

    except Exception as e:
        print(f"Fehler bei Analyse: {e}")
        return None


def generate_report(filename, rms_value):
    # Bookwire-RMS-Toleranzbereich: -24 dB bis -18 dB
    if rms_value is None:
        status = "Fehler bei Analyse"
        deviation = "--"
        within_range = False
    elif -24 <= rms_value <= -18:
        status = "passt"
        deviation = "innerhalb der Toleranz"
        within_range = True
    elif rms_value > -18:
        deviation = f"{rms_value - (-18):.2f} dB zu laut"
        status = "außerhalb der Vorgaben"
        within_range = False
    else:
        deviation = f"{(-24) - rms_value:.2f} dB zu leise"
        status = "außerhalb der Vorgaben"
        within_range = False

    return {
        'Datei': filename,
        'RMS': f"{rms_value:.2f} dB" if rms_value is not None else "Fehler",
        'Abweichung': deviation,
        'Status': status,
        'Innerhalb Toleranz': within_range
    }


@app.route('/', methods=['GET', 'POST'])
def index():
    global reports_global
    reports_global = []

    if request.method == 'POST':
        files = request.files.getlist('files')
        for file in files:
            if file and file.filename.endswith('.mp3'):
                filename = file.filename
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)

                rms = analyze_audio(filepath)
                report = generate_report(filename, rms)
                reports_global.append(report)

                os.remove(filepath)  # Dateileichen vermeiden

    return render_template('index.html', reports=reports_global)


@app.route('/download', methods=['GET'])
def download_csv():
    global reports_global
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['Datei', 'RMS', 'Abweichung', 'Status'])
    writer.writeheader()
    for report in reports_global:
        writer.writerow({
            'Datei': report['Datei'],
            'RMS': report['RMS'],
            'Abweichung': report['Abweichung'],
            'Status': report['Status']
        })
    output.seek(0)

    return send_file(io.BytesIO(output.getvalue().encode()), mimetype='text/csv', as_attachment=True, download_name='Ergebnisse.csv')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
