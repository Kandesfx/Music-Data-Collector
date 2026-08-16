import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.deploy_to_oci import run_ssh_command

deno_cmd = """
curl -fsSL https://deno.land/install.sh | sh
sudo cp ~/.deno/bin/deno /usr/local/bin/
echo "Deno Version: $(deno --version)"
"""

ok, out = run_ssh_command(deno_cmd, timeout=60)
print("Deno install result:", ok)
