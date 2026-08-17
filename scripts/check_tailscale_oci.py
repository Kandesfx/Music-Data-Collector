import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.utils.tailscale_controller import TailscaleController
import json

status = TailscaleController.get_status()
print(json.dumps(status, indent=2))
