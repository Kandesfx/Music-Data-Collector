import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.deploy_to_oci import run_ssh_command

fix_dpkg = """
sudo dpkg --remove --force-all libnode-dev libnode72 || true
sudo dpkg -i --force-overwrite /var/cache/apt/archives/nodejs_20.20.2-1nodesource1_amd64.deb || true
sudo apt-get install -f -y
echo "Fixed NodeJS Version: $(node -v)"
"""

ok, out = run_ssh_command(fix_dpkg, timeout=60)
print("Node fix result:", ok)
