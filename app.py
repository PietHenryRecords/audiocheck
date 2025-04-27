from flask import Flask, render_template, request, send_file, redirect, url_for
import os
import subprocess
import io
import csv

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

reports_global = []

@app.route('/', methods=['GET', 'POST'])
def index():
    global reports_global

    if request.method == 'POST':
        reports_global = []  # Reset beim neuen Upload

        uploaded_files = request.files.getlist('files')

        for file in uploaded_files:
            if file:
                filename = file.filename
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)

                report = {'Datei': filename, 'Fehler': []}

                audio_info = get_audio_info(filepath)

                if audio_info:
                    if audio_info['sample_rate'] != 44100:
                        report['Fehler'].append(f"Sample Rate falsch: {audio_info['sample_rate']} Hz (erwartet: 44100 Hz)")
                    if audio_info['bit_depth'] != 16:
                        report['Fehler'].append(f"Bit-Tiefe falsch: {audio_info['bit_depth']} Bit (erwartet: 16 Bit)")
                    if audio_info['channels'] != 2:
                        report['Fehler'].append(f"Nicht Stereo: {audio_info['channels']} Kanal(e) gefunden")
                    if not (-24 <= audio_info['rms'] <= -18):
                        report['Fehler'].append(f"RMS falsch: {audio_info['rms']} dB (erwartet zwischen -24 dB und -18 dB)")
                else:
                    report['Fehler'].append("Datei konnte nicht analysiert werden.")

                reports_global.append(report)

        # Nach POST direkt Redirect auf die Indexseite
        return redirect(url_for('index'))

    else:
        # GET: Seite neu laden, Reports anzeigen
        return render_template('index.html', reports=reports_global)

def get_audio_info(filepath):
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'a:0',
            '-show_entries', 'stream=sample_rate,channels,bit_rate',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            filepath
        ]
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().splitlines()

        sample_rate = int(output[0])
        channels = int(output[1])
        bit_rate = int(output[2]) if len(output) > 2 else 0
        bit_depth = round(bit_rate / sample_rate / channels) if bit_rate and sample_rate and channels else 16
        rms = get_rms(filepath)

        return {
            'sample_rate': sample_rate,
            'channels': channels,
            'bit_depth': bit_depth,
            'rms': rms
        }
    except Exception as e:
        print(f"Fehler bei der Analyse: {e}")
        return None

def get_rms(filepath):
    try:
        cmd = [
            'ffmpeg', '-i', filepath, '-af', 'volumedetect',
            '-f', 'null', '-'
        ]
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode()

        for line in output.splitlines():
            if 'mean_volume' in line:
                parts = line.split(':')
                return float(parts[-1].strip().replace('dB', ''))
    except Exception as e:
        print(f"Fehler beim RMS-Check: {e}")
    return 0

@app.route('/download', methods=['GET'])
def download():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Datei', 'Status', 'Fehler'])

    for report in reports_global:
        status = 'OK' if not report['Fehler'] else 'Fehler'
        fehler_text = '; '.join(report['Fehler']) if report['Fehler'] else ''
        writer.writerow([report['Datei'], status, fehler_text])

    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype='text/csv', as_attachment=True, download_name='ergebnisse.csv')

if __name__ == '__main__':
    app.run(debug=True)
