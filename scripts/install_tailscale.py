"""
Scripts - Auto Installer for Tailscale Mesh Client on Ubuntu 22.04 (OCI)
Installs Tailscale daemon (tailscaled) to enable Self-Hosted Exit Node routing.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.deploy_to_oci import run_ssh_command

INSTALL_SCRIPT = """
set -e
echo "🚀 [1/3] Adding Tailscale official repository & package..."
curl -fsSL https://tailscale.com/install.sh | sudo sh

echo "⚙️ [2/3] Enabling & Starting tailscaled system service..."
sudo systemctl enable --now tailscaled
sudo systemctl status tailscaled --no-pager

echo "🔍 [3/3] Verifying Tailscale CLI installation..."
tailscale version
echo "✅ Tailscale Daemon Installed Successfully on OCI Server!"
"""

def main():
    print("🚀 Installing Tailscale on OCI Server...")
    run_ssh_command(INSTALL_SCRIPT)

if __name__ == "__main__":
    main()
