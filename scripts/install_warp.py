import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.deploy_to_oci import run_ssh_command

INSTALL_SCRIPT = """
set -e
echo "🚀 [1/5] Adding Cloudflare WARP official repository..."
sudo apt-get update -y
sudo apt-get install -y curl gpg lsb-release

curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | sudo gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflare-client.list

echo "📦 [2/5] Installing cloudflare-warp package..."
sudo apt-get update -y
sudo apt-get install -y cloudflare-warp

echo "⚙️ [3/5] Registering WARP client & setting SOCKS5 Proxy Mode..."
warp-cli --accept-tos registration new || warp-cli registration new || true
warp-cli mode proxy
warp-cli proxy port 40000

echo "🌐 [4/5] Connecting to Cloudflare Anycast Network..."
warp-cli connect
sleep 3
warp-cli status

echo "🔍 [5/5] Testing Egress IP through SOCKS5 Gateway (127.0.0.1:40000)..."
echo "--- Direct IP ---"
curl -s --max-time 5 https://api.ipify.org || true
echo ""
echo "--- Masked Cloudflare Egress IP ---"
curl -s --max-time 8 --socks5 127.0.0.1:40000 https://ipinfo.io/json || true
echo ""
echo "✅ Cloudflare WARP SOCKS5 Gateway (127.0.0.1:40000) Installed & Connected Successfully!"
"""

def main():
    print("🚀 Starting Remote Cloudflare WARP Gateway Installation on OCI Server...")
    run_ssh_command(INSTALL_SCRIPT)

if __name__ == "__main__":
    main()
