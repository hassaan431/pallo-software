import os
import sys
import webbrowser
import threading
import time

# Set the working directory to the app folder
if getattr(sys, 'frozen', False):
    # Running as PyInstaller bundle
    bundle_dir = os.path.dirname(sys.executable)
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
