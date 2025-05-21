import wave
import struct
import numpy as np
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
import subprocess
import tempfile
import os

class AudioChecker:
    """
    Analyze audio files (.wav and .mp3) and generate PDF reports.
    Requires ffmpeg installed and accessible in PATH for MP3 support.
    """
    def __init__(self, filepath: str):
        ext = os.path.splitext(filepath)[1].lower()
        if ext not in ('.wav', '.mp3'):
            raise ValueError("Only .wav and .mp3 files are supported.")
        self.filepath = filepath
        self.params = None
        self.frames = None
        self.signal = None

    def load_wav(self):
        """
        Load audio, converting MP3 to WAV via ffmpeg if necessary.
        """
        # Determine working WAV path
        filepath = self.filepath
        temp_wav = None
        if filepath.lower().endswith('.mp3'):
            # Convert MP3 to WAV using ffmpeg
            tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_wav = tmp.name
            tmp.close()
            subprocess.run([
                'ffmpeg', '-y', '-i', filepath,
                '-ar', '44100', '-ac', '2', temp_wav
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            filepath = temp_wav

        # Read WAV
        with wave.open(filepath, 'rb') as wf:
            self.params = wf.getparams()
            raw = wf.readframes(self.params.nframes)

        # Clean up temporary file
        if temp_wav:
            try:
                os.remove(temp_wav)
            except OSError:
                pass

        # Unpack to numpy signal
        fmt = '<' + 'h' * (self.params.nframes * self.params.nchannels)
        data = struct.unpack(fmt, raw)
        signal = np.array(data)
        if self.params.nchannels > 1:
            signal = signal.reshape(-1, self.params.nchannels)
        self.frames = self.params.nframes
        self.signal = signal

    def analyze(self):
        if self.signal is None:
            raise RuntimeError("Audio not loaded. Call load_wav() first.")
        duration = self.frames / self.params.framerate
        peak = np.max(np.abs(self.signal))
        mean_amp = np.mean(np.abs(self.signal))
        return {
            'channels': self.params.nchannels,
            'sample_width': self.params.sampwidth,
            'framerate': self.params.framerate,
            'frames': self.frames,
            'duration_s': duration,
            'peak_amplitude': int(peak),
            'mean_amplitude': float(mean_amp)
        }

    def plot_waveform(self):
        if self.signal is None:
            raise RuntimeError("Audio not loaded. Call load_wav() first.")
        plt.figure()
        if self.params.nchannels > 1:
            plt.plot(self.signal[:, 0], label='Left')
            plt.plot(self.signal[:, 1], label='Right')
            plt.legend()
        else:
            plt.plot(self.signal)
        plt.title('Waveform')
        plt.xlabel('Samples')
        plt.ylabel('Amplitude')
        buf = BytesIO()
        plt.savefig(buf, format='PNG')
        plt.close()
        buf.seek(0)
        return buf

    def export_pdf_report(self, output_pdf: str):
        analysis = self.analyze()
        waveform_img = self.plot_waveform()

        c = canvas.Canvas(output_pdf, pagesize=A4)
        width, height = A4
        c.setFont('Helvetica-Bold', 14)
        c.drawString(30, height - 50, 'AudioChecker Report')
        c.setFont('Helvetica', 12)
        y = height - 80
        for key, value in analysis.items():
            c.drawString(30, y, f"{key.replace('_', ' ').title()}: {value}")
            y -= 20
        c.drawImage(waveform_img, 30, y - 300, width=500, preserveAspectRatio=True)
        c.showPage()
        c.save()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description='AudioChecker: Analyze .wav and .mp3 files and generate PDF reports'
    )
    parser.add_argument('input', help='Path to input audio file (.wav or .mp3)')
    parser.add_argument('-o', '--output', default='report.pdf', help='Path to output PDF report')
    args = parser.parse_args()

    checker = AudioChecker(args.input)
    checker.load_wav()
    checker.export_pdf_report(args.output)
    print(f"PDF report saved to {args.output}")
