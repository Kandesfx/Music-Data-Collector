"""
Music Data Collector - Tailscale Mesh Exit Node Controller Module
Manages the Tailscale daemon (tailscaled/tailscale CLI) on the host machine to route egress traffic
through a self-hosted residential exit node (e.g. home PC / private server) via SOCKS5 (port 1055)
or direct interface routing.
"""

import json
import shutil
import subprocess
import time
from typing import Dict, Any, List, Optional
from src.utils.lock_manager import lock_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TailscaleController:
    """Manages the Tailscale daemon and SOCKS5 proxy server for Exit Node egress routing."""

    DEFAULT_SOCKS5_PORT = 1055
    DEFAULT_PROXY_URL = f"socks5://127.0.0.1:{DEFAULT_SOCKS5_PORT}"

    @classmethod
    def is_installed(cls) -> bool:
        """Check if tailscale is installed on the host system."""
        return shutil.which("tailscale") is not None

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        """
        Get current Tailscale connection status, local node IPs, and available Exit Nodes.
        """
        if not cls.is_installed():
            return {
                "installed": False,
                "status": "NOT_INSTALLED",
                "is_connected": False,
                "tailscale_ips": [],
                "hostname": "",
                "active_exit_node": None,
                "available_exit_nodes": [],
                "socks5_port": cls.DEFAULT_SOCKS5_PORT,
                "proxy_url": cls.DEFAULT_PROXY_URL,
                "message": "Tailscale chưa được cài đặt trên máy chủ.",
            }

        try:
            res = subprocess.run(
                ["tailscale", "status", "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
            if res.returncode != 0:
                return {
                    "installed": True,
                    "status": "OFFLINE",
                    "is_connected": False,
                    "tailscale_ips": [],
                    "hostname": "",
                    "active_exit_node": None,
                    "available_exit_nodes": [],
                    "socks5_port": cls.DEFAULT_SOCKS5_PORT,
                    "proxy_url": cls.DEFAULT_PROXY_URL,
                    "message": "Tailscale đang ở trạng thái dừng hoặc chưa đăng nhập.",
                }

            data = json.loads(res.stdout) if res.stdout else {}
            backend_state = data.get("BackendState", "Unknown")
            is_connected = backend_state == "Running"
            
            self_node = data.get("Self") or {}
            tailscale_ips = self_node.get("TailscaleIPs") or []
            hostname = self_node.get("HostName", "")
            
            # Find available exit nodes from peers
            peers = data.get("Peer") or {}
            available_exit_nodes: List[Dict[str, Any]] = []
            active_exit_node: Optional[Dict[str, Any]] = None

            for peer_id, peer in peers.items():
                is_exit_node = peer.get("ExitNodeOption", False) or peer.get("ExitNode", False)
                node_info = {
                    "id": peer_id,
                    "hostname": peer.get("HostName", "Unknown"),
                    "dns_name": peer.get("DNSName", "").rstrip("."),
                    "ip": peer.get("TailscaleIPs", [""])[0] if peer.get("TailscaleIPs") else "",
                    "online": peer.get("Online", False),
                    "is_exit_node": is_exit_node,
                    "is_active_exit": peer.get("ExitNode", False),
                    "os": peer.get("OS", "Unknown"),
                }
                if is_exit_node:
                    available_exit_nodes.append(node_info)
                if peer.get("ExitNode", False):
                    active_exit_node = node_info

            return {
                "installed": True,
                "status": "CONNECTED" if is_connected else backend_state.upper(),
                "is_connected": is_connected,
                "tailscale_ips": tailscale_ips,
                "primary_ip": tailscale_ips[0] if tailscale_ips else "",
                "hostname": hostname,
                "backend_state": backend_state,
                "active_exit_node": active_exit_node,
                "available_exit_nodes": available_exit_nodes,
                "socks5_port": cls.DEFAULT_SOCKS5_PORT,
                "proxy_url": cls.DEFAULT_PROXY_URL,
                "message": (
                    f"Tailscale đang kết nối ({tailscale_ips[0] if tailscale_ips else ''})"
                    if is_connected
                    else f"Trạng thái Tailscale: {backend_state}"
                ),
            }
        except Exception as e:
            return {
                "installed": True,
                "status": "ERROR",
                "is_connected": False,
                "tailscale_ips": [],
                "hostname": "",
                "active_exit_node": None,
                "available_exit_nodes": [],
                "socks5_port": cls.DEFAULT_SOCKS5_PORT,
                "proxy_url": cls.DEFAULT_PROXY_URL,
                "message": f"Lỗi truy vấn trạng thái Tailscale: {e}",
            }

    @classmethod
    def _do_connect(cls, auth_key: str, exit_node: Optional[str], socks5_port: int) -> Dict[str, Any]:
        clean_key = auth_key.strip()
        cmd = [
            "tailscale",
            "up",
            f"--authkey={clean_key}",
            f"--socks5-server=127.0.0.1:{socks5_port}",
            "--accept-routes",
            "--reset",
        ]
        if exit_node and exit_node.strip():
            cmd.append(f"--exit-node={exit_node.strip()}")
            cmd.append("--exit-node-allow-lan-access=true")

        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=25)
        if res.returncode != 0:
            err_msg = (res.stderr or res.stdout).strip()
            logger.error(f"Tailscale up failed: {err_msg}")
            return {"success": False, "error": err_msg or "Lỗi kích hoạt Tailscale"}

        time.sleep(2)
        status = cls.get_status()
        logger.info(f"Tailscale connect success: {status.get('status')} IP: {status.get('primary_ip')}")
        return {"success": True, "status": status}

    @classmethod
    def connect_with_auth_key(
        cls,
        auth_key: str,
        exit_node: Optional[str] = None,
        socks5_port: int = DEFAULT_SOCKS5_PORT,
    ) -> Dict[str, Any]:
        """Authenticate Tailscale with CLI mutex lock."""
        if not cls.is_installed():
            return {"success": False, "error": "Tailscale chưa được cài đặt trên máy chủ"}
        if not auth_key.strip():
            return {"success": False, "error": "Auth Key không được để trống!"}

        try:
            return lock_manager.execute_with_cli_mutex(
                "tailscale_cli_mutex",
                cls._do_connect,
                auth_key,
                exit_node,
                socks5_port,
                timeout_sec=30,
            )
        except Exception as e:
            return {"success": False, "error": str(e)}

    # Alias for backward compatibility
    connect = connect_with_auth_key

    @classmethod
    def _do_set_exit_node(cls, exit_node_name_or_ip: str) -> Dict[str, Any]:
        clean_node = exit_node_name_or_ip.strip()
        cmd = ["tailscale", "set"]
        if clean_node:
            cmd.append(f"--exit-node={clean_node}")
            cmd.append("--exit-node-allow-lan-access=true")
        else:
            cmd.append("--exit-node=")

        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
        if res.returncode != 0:
            err_msg = (res.stderr or res.stdout).strip()
            return {"success": False, "error": err_msg}

        time.sleep(1)
        status = cls.get_status()
        return {"success": True, "status": status}

    @classmethod
    def set_exit_node(cls, exit_node_name_or_ip: str) -> Dict[str, Any]:
        """Dynamically change active exit node with CLI mutex lock."""
        if not cls.is_installed():
            return {"success": False, "error": "Tailscale chưa được cài đặt trên máy chủ"}
        try:
            return lock_manager.execute_with_cli_mutex(
                "tailscale_cli_mutex",
                cls._do_set_exit_node,
                exit_node_name_or_ip,
                timeout_sec=20,
            )
        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def _do_disconnect(cls) -> bool:
        subprocess.run(["tailscale", "down"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        time.sleep(1)
        status = cls.get_status()
        return not status["is_connected"]

    @classmethod
    def disconnect(cls) -> bool:
        """Disconnect Tailscale with CLI mutex lock."""
        if not cls.is_installed():
            return False
        try:
            return lock_manager.execute_with_cli_mutex("tailscale_cli_mutex", cls._do_disconnect, timeout_sec=15)
        except Exception as e:
            logger.error(f"Tailscale disconnect failed: {e}")
            return False
