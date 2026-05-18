import sys
import os

# GANTI 'UsernameAnda' dengan username PythonAnywhere Anda!
path = '/home/UsernameAnda/algoritma-SHORTEST-PATH-ADAPTIF_Dynamic-A-with-Scenario-Engine-untuk-daerah-kampus'

if path not in sys.path:
    sys.path.append(path)

# Mengimpor variabel 'app' dari web_server.py agar dikenali oleh server
from web_server import app as application
