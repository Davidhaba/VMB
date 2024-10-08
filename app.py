from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
from translations import translations
import os, subprocess, socket

app = Flask(__name__)
available_languages = ['en', 'uk', 'es', 'de']
not_found_language = 'The requested language was not found on the server. If you entered the URL manually please check your spelling and try again.'
not_found_url = 'The requested URL was not found on the server. If you entered the URL manually please check your spelling and try again.'

UPLOAD_FOLDER = './OS-fromUsers'
FILES_FOLDER = './Windows'
disks_dir = './Disks'
os.makedirs(disks_dir, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def find_free_port(start_port=5900):
    """Find a free VNC port starting from start_port."""
    port = start_port
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', port)) != 0:
                return port
            port += 1

def start_novnc(vnc_port):
    script_dir = os.path.dirname(__file__)
    novnc_path = os.path.join(script_dir, 'novnc.exe')
    os.environ["PATH"] += os.pathsep + script_dir
    subprocess.Popen([novnc_path, '--target', f'localhost:{vnc_port}', '--listen', f'0.0.0.0:{vnc_port + 10}'], shell=True)

def get_language():
    return request.args.get('lang', 'en')

@app.errorhandler(404)
def page_not_found(e):
    return render_template('not_found.html', message=not_found_url, code=404), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('not_found.html', message="Internal server error", code=500), 500

@app.errorhandler(403)
def forbidden_error(e):
    return render_template('not_found.html', message="Forbidden", code=403), 403

@app.errorhandler(400)
def bad_request(e):
    return render_template('not_found.html', message="Bad Request", code=400), 400

@app.errorhandler(408)
def request_timeout(e):
    return render_template('not_found.html', message="Request Timeout", code=408), 408

@app.route('/')
def index():
    lang = get_language()
    if lang in available_languages:
        return render_template('index.html', translations=translations[lang])
    else:
        return render_template('not_found.html', message=not_found_language, code=404), 404

@app.route('/create-vm-page', methods=['GET'])
def create_vm_page():
    os_images = [f for f in os.listdir(FILES_FOLDER) if f.endswith('.iso')]
    lang = get_language()
    if lang in available_languages:
        return render_template('create_vm.html', os_images=os_images, translations=translations[lang])
    else:
        return render_template('not_found.html', message=not_found_language, code=404), 404

@app.route('/create-vm', methods=['POST'])
def create_vm():
    try:
        data = request.form
        os_image = data.get('os')
        cpu_cores = data.get('cpu')
        ram_size = data.get('ram')
        boot_device = data.get('boot_device')

        vnc_port = find_free_port()
        vnc_display = vnc_port - 5900

        os_image_path = os.path.join(UPLOAD_FOLDER, os_image) if os_image.startswith('(uploaded)') else os.path.join(FILES_FOLDER, os_image)

        qemu_command = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'qemu', 'qemu-system-x86_64.exe'),
            '-m', str(ram_size),
            '-smp', str(cpu_cores),
            '-vnc', f'localhost:{vnc_display}',
        ]
        if os_image_path:
            qemu_command.extend(['-cdrom', os_image_path])

        index = 0
        disk_count = 0
        while True:
            device_type = data.get(f'device_{index}_type')
            if not device_type:
                break
            
            if device_type == 'harddrive':
                disk_size = data.get(f'device_{index}_disk_size')
                if disk_size:
                    disk_image = os.path.join(disks_dir, f'disk_image_{vnc_port}_{disk_count}.qcow2')
                    try:
                        subprocess.run(['qemu-img', 'create', '-f', 'qcow2', disk_image, f'{disk_size}G'], check=True)
                        disk_device = f'-hd{chr(97 + disk_count)}'
                        if disk_count < 2:
                            qemu_command.extend([disk_device, disk_image])
                        disk_count += 1
                    except subprocess.CalledProcessError as e:
                        return jsonify({'success': False, 'error': f'Failed to create hard disk: {str(e)}'})

            device_file = request.files.get(f'device_{index}_file')
            if device_file:
                device_file_path = os.path.join(UPLOAD_FOLDER, device_file.filename)
                device_file.save(device_file_path)
                if device_type == 'cdrom':
                    qemu_command.extend(['-cdrom', device_file_path])
                elif device_type == 'floppydisk':
                    qemu_command.extend(['-fda', device_file_path])

            index += 1

        if boot_device == 'cdrom':
            qemu_command.extend(['-boot', 'd'])  # Boot from CD-ROM
        elif boot_device == 'floppydisk':
            qemu_command.extend(['-boot', 'f'])  # Boot from floppy
        else:
            qemu_command.extend(['-boot', 'c'])  # Boot from Hard Disk
        subprocess.Popen(qemu_command, shell=True)
        start_novnc(vnc_port)
        return jsonify({'success': True, 'novnc_url': f'https://vmb-30i9.onrender.com:{vnc_port + 10}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/upload', methods=['POST'])
def upload():
    uploaded_file = request.files.get('file')
    if uploaded_file and uploaded_file.filename.lower().endswith(('.iso', '.qcow2', '.vmdk')):
        upload_path = os.path.join(UPLOAD_FOLDER, "(uploaded) " + uploaded_file.filename)
        uploaded_file.save(upload_path)
        if uploaded_file.filename.lower().endswith(('.qcow2', '.vmdk')):
            return jsonify({'success': True, 'iso': False})
        return jsonify({'success': True, 'iso': True})
    return jsonify({'success': False})

if __name__ == '__main__':
    SocketIO(app).run(app, host='0.0.0.0', port=5000, debug=True)
