import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.utils.tailscale_controller import TailscaleController

st = TailscaleController.get_status()
print(f"Tailscale Installed: {st.get('installed')}")
print(f"Tailscale Connected: {st.get('is_connected')}")
print(f"Tailscale IP: {st.get('primary_ip')}")
print(f"Status Message: {st.get('message')}")
