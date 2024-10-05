from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit
import os
import subprocess

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysecret'
socketio = SocketIO(app)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)
    if file:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)
        
        # Get emulator parameters
        cpu = 'qemu64'
        cores = request.form['cores']
        ram = request.form['ram']
        
        # Run QEMU with the provided parameters
        qemu_command = [
            'qemu-system-x86_64',
            '-cpu', cpu,
            '-smp', cores,
            '-m', ram,
            '-cdrom', file_path,
            '-boot', 'd',
            '-vga', 'std',
            '-vnc', ':4'
        ]
        with open('qemu.log', 'w') as f:
            f.write("Running QEMU command: " + " ".join(qemu_command) + "\n")
            subprocess.Popen(qemu_command, stdout=f, stderr=f)
        
        # Run NoVNC on port 6084
        novnc_command = [
            'websockify',
            '--web', './noVNC',
            '6084', 'localhost:5904'
        ]
        with open('novnc.log', 'w') as f:
            f.write("Running NoVNC command: " + " ".join(novnc_command) + "\n")
            subprocess.Popen(novnc_command, stdout=f, stderr=f)
        
        return redirect(url_for('vnc'))

@app.route('/vnc')
def vnc():
    return redirect("https://vmb-z22j.onrender.com:6084/vnc.html")

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
