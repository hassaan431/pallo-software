import os
import sys
import webbrowser
import threading
import time

# Set the working directory to the app folder
if getattr(sys, 'frozen', False):
    # Running as PyInstaller bundle
    bundle_dir = os.path.dirname(sys.executable)
    # Check for templates in Resources folder (macOS .app)
    resources_dir = os.path.join(
        os.path.dirname(bundle_dir), 'Resources')
    if os.path.exists(os.path.join(
            resources_dir, 'templates')):
        bundle_dir = resources_dir
    elif os.path.exists(os.path.join(
            os.path.dirname(bundle_dir), 
            'Frameworks', 'templates')):
        bundle_dir = os.path.join(
            os.path.dirname(bundle_dir), 'Frameworks')
    os.chdir(bundle_dir)
else:
    bundle_dir = os.path.dirname(
        os.path.abspath(__file__))
    os.chdir(bundle_dir)

# Add bundle dir to path
sys.path.insert(0, bundle_dir)

def open_browser():
    time.sleep(2.5)
    webbrowser.open('http://127.0.0.1:5000')

# Open browser after short delay
threading.Thread(
    target=open_browser, 
    daemon=True
).start()

# Import and run the app
from app import app
from database import init_db

init_db()

app.run(
    host='127.0.0.1',
    port=5000,
    debug=False,
    use_reloader=False
)
