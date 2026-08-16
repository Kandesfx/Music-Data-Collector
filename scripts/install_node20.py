import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.deploy_to_oci import run_ssh_command

node_cmd = """
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
echo "NodeJS Version: $(node -v)"
"""

ok, out = run_ssh_command(node_cmd, timeout=120)
print("Node install result:", ok)
