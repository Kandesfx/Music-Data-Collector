"""
Music Data Collector - Authentication, Team Auditing & Shared Config Profiles Module
Manages user accounts, password hashing (PBKDF2-HMAC-SHA256), per-user activity analytics,
and shared team profiles (Spotify credentials & Proxy pools).
"""

import os
import hashlib
import binascii
from datetime import datetime
from typing import Dict, List, Any, Optional

from src.storage.db_manager import DBManager
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AuthManager:
    """Manages user authentication, team analytics, and shared team profiles in MongoDB."""

    def __init__(self, db_manager: Optional[DBManager] = None):
        self.db = db_manager or DBManager()
        self._ensure_default_admin()
        self._ensure_default_team_profiles()

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password with salt using PBKDF2-HMAC-SHA256."""
        salt = os.urandom(16)
        pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
        return f"{binascii.hexlify(salt).decode('ascii')}${binascii.hexlify(pwd_hash).decode('ascii')}"

    @staticmethod
    def verify_password(stored_password: str, provided_password: str) -> bool:
        """Verify a stored password against one provided by user."""
        if not stored_password or "$" not in stored_password:
            return False
        try:
            salt_hex, hash_hex = stored_password.split("$", 1)
            salt = binascii.unhexlify(salt_hex.encode("ascii"))
            pwd_hash = hashlib.pbkdf2_hmac("sha256", provided_password.encode("utf-8"), salt, 100000)
            return binascii.hexlify(pwd_hash).decode("ascii") == hash_hex
        except Exception:
            return False

    def _ensure_default_admin(self):
        """Create a default admin user if the users collection is empty."""
        if not self.db.is_connected():
            return
        try:
            count = self.db.db.users.count_documents({})
            if count == 0:
                self.create_user(
                    username="admin",
                    password="adminpassword123",
                    email="admin@datn.local",
                    role="admin",
                    display_name="Trưởng Nhóm (Admin)",
                )
                logger.info("Initialized default administrator account: username='admin'")
        except Exception as e:
            logger.debug(f"Default admin init note: {e}")

    def _ensure_default_team_profiles(self):
        """Create default shared Spotify & Proxy profiles if none exist."""
        if not self.db.is_connected():
            return
        try:
            count = self.db.db.team_configs.count_documents({})
            if count == 0:
                default_profiles = [
                    {
                        "profile_id": "spotify_default",
                        "type": "spotify",
                        "name": "Spotify Default Pool (Free & High-Speed Search)",
                        "client_id": os.getenv("SPOTIFY_CLIENT_ID", ""),
                        "client_secret": os.getenv("SPOTIFY_CLIENT_SECRET", ""),
                        "is_active": True,
                        "description": "Cấu hình Spotify API chính của nhóm",
                    },
                    {
                        "profile_id": "proxy_none",
                        "type": "proxy",
                        "name": "Direct Connection (No Proxy)",
                        "proxies": [],
                        "is_active": True,
                        "description": "Kết nối trực tiếp tốc độ cao",
                    },
                ]
                self.db.db.team_configs.insert_many(default_profiles)
        except Exception as e:
            logger.debug(f"Default team profiles note: {e}")

    def create_user(
        self,
        username: str,
        password: str,
        email: str = "",
        role: str = "collector",
        display_name: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Create a new user account with initial activity metrics."""
        if not self.db.is_connected():
            return None
        username = username.strip().lower()
        if not username or not password:
            return None

        # Check existing user
        if self.db.db.users.find_one({"username": username}):
            logger.warning(f"User '{username}' already exists.")
            return None

        user_doc = {
            "username": username,
            "display_name": display_name.strip() or username,
            "password_hash": self.hash_password(password),
            "email": email.strip().lower(),
            "role": role if role in ["admin", "collector", "viewer"] else "collector",
            "is_active": True,
            "created_at": datetime.utcnow(),
            "last_login": None,
            "stats": {
                "crawled_tracks_count": 0,
                "downloaded_tracks_count": 0,
                "direct_links_count": 0,
                "last_action": "Tài khoản vừa được tạo",
                "last_active_at": datetime.utcnow(),
            },
        }

        self.db.db.users.insert_one(user_doc)
        logger.info(f"Created new user account: {username} (Role: {user_doc['role']})")
        user_doc.pop("password_hash", None)
        return user_doc

    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user credentials and return user info dict."""
        if not self.db.is_connected():
            return None
        username = username.strip().lower()
        user = self.db.db.users.find_one({"username": username})
        if not user:
            return None

        if not user.get("is_active", True):
            logger.warning(f"Account '{username}' is disabled.")
            return None

        if self.verify_password(user.get("password_hash", ""), password):
            # Update last login
            self.db.db.users.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "last_login": datetime.utcnow(),
                        "stats.last_active_at": datetime.utcnow(),
                    }
                },
            )
            user_info = {
                "username": user["username"],
                "display_name": user.get("display_name", user["username"]),
                "email": user.get("email", ""),
                "role": user.get("role", "collector"),
                "created_at": user.get("created_at"),
                "stats": user.get("stats", {}),
            }
            return user_info
        return None

    def record_user_action(
        self,
        username: str,
        action_type: str,
        count: int = 1,
        details: str = "",
    ):
        """
        Record a team member's action and update their personal metrics.
        action_type: 'crawl_metadata' | 'download_audio' | 'direct_url' | 'export_data'
        """
        if not self.db.is_connected() or not username:
            return

        now = datetime.utcnow()
        inc_field = None
        if action_type == "crawl_metadata":
            inc_field = "stats.crawled_tracks_count"
        elif action_type == "download_audio":
            inc_field = "stats.downloaded_tracks_count"
        elif action_type == "direct_url":
            inc_field = "stats.direct_links_count"

        update_doc: Dict[str, Any] = {
            "$set": {
                "stats.last_action": details or f"Executed {action_type} ({count} items)",
                "stats.last_active_at": now,
            }
        }
        if inc_field:
            update_doc["$inc"] = {inc_field: count}

        try:
            self.db.db.users.update_one({"username": username.lower()}, update_doc)
            # Log into activity_logs collection
            self.db.db.activity_logs.insert_one(
                {
                    "username": username.lower(),
                    "action_type": action_type,
                    "count": count,
                    "details": details,
                    "timestamp": now,
                }
            )
        except Exception as e:
            logger.debug(f"User activity recording note: {e}")

    @staticmethod
    def _sanitize_doc(doc: Any) -> Any:
        """Recursively convert datetime objects, ObjectIds, etc. to JSON-safe primitives."""
        if isinstance(doc, dict):
            return {k: AuthManager._sanitize_doc(v) for k, v in doc.items()}
        elif isinstance(doc, list):
            return [AuthManager._sanitize_doc(item) for item in doc]
        elif isinstance(doc, datetime):
            return doc.isoformat()
        elif hasattr(doc, "__str__") and type(doc).__name__ == "ObjectId":
            return str(doc)
        return doc

    def get_team_leaderboard(self) -> List[Dict[str, Any]]:
        """Get all team members with their stats and contribution ranking."""
        if not self.db.is_connected():
            return []
        try:
            users = list(
                self.db.db.users.find(
                    {},
                    {
                        "password_hash": 0,
                        "_id": 0,
                    },
                ).sort("stats.downloaded_tracks_count", -1)
            )
            return self._sanitize_doc(users)
        except Exception as e:
            logger.error(f"Error fetching team leaderboard: {e}")
            return []

    def get_activity_logs(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Retrieve recent team activity logs."""
        if not self.db.is_connected():
            return []
        try:
            logs = list(
                self.db.db.activity_logs.find({}, {"_id": 0})
                .sort("timestamp", -1)
                .limit(limit)
            )
            return self._sanitize_doc(logs)
        except Exception as e:
            logger.error(f"Error fetching activity logs: {e}")
            return []

    # ─── Admin Management Operations & Role CRUD ────────────────

    def get_all_users(self) -> List[Dict[str, Any]]:
        """Retrieve all users with role, metrics and active status."""
        if not self.db.is_connected():
            return []
        try:
            users = list(self.db.db.users.find({}, {"password_hash": 0, "_id": 0}).sort("created_at", -1))
            return self._sanitize_doc(users)
        except Exception as e:
            logger.error(f"Error fetching users list: {e}")
            return []

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Retrieve single user document by username."""
        if not self.db.is_connected() or not username:
            return None
        user = self.db.db.users.find_one({"username": username.strip().lower()}, {"password_hash": 0, "_id": 0})
        return self._sanitize_doc(user) if user else None

    def upsert_user(self, data: Dict[str, Any]) -> bool:
        """Create or update a user account and role permission."""
        if not self.db.is_connected() or not data.get("username"):
            return False
        username = data["username"].strip().lower()
        existing = self.db.db.users.find_one({"username": username})
        now = datetime.utcnow()

        if existing:
            # Update existing
            update_fields: Dict[str, Any] = {
                "display_name": data.get("display_name", existing.get("display_name", username)),
                "email": data.get("email", existing.get("email", "")),
                "role": data.get("role", existing.get("role", "collector")),
                "is_active": data.get("is_active", existing.get("is_active", True)),
                "updated_at": now,
            }
            if data.get("password") and data["password"].strip():
                update_fields["password_hash"] = self.hash_password(data["password"].strip())
            self.db.db.users.update_one({"username": username}, {"$set": update_fields})
            return True
        else:
            # Create new
            pwd = data.get("password", "").strip() or "123456"
            user_doc = {
                "username": username,
                "display_name": data.get("display_name", "").strip() or username,
                "password_hash": self.hash_password(pwd),
                "email": data.get("email", "").strip().lower(),
                "role": data.get("role", "collector"),
                "is_active": data.get("is_active", True),
                "created_at": now,
                "updated_at": now,
                "last_login": None,
                "stats": {
                    "crawled_tracks_count": 0,
                    "downloaded_tracks_count": 0,
                    "direct_links_count": 0,
                    "last_action": "Tài khoản vừa được tạo",
                    "last_active_at": now,
                },
            }
            self.db.db.users.insert_one(user_doc)
            return True

    def admin_reset_password(self, username: str, new_password: str) -> bool:
        """Admin resets a member's password."""
        if not self.db.is_connected() or not username or not new_password:
            return False
        res = self.db.db.users.update_one(
            {"username": username.strip().lower()},
            {"$set": {"password_hash": self.hash_password(new_password)}},
        )
        return res.modified_count > 0

    def admin_toggle_user_status(self, username: str, is_active: bool) -> bool:
        """Admin enables/disables a user account."""
        if not self.db.is_connected() or not username:
            return False
        res = self.db.db.users.update_one(
            {"username": username.strip().lower()},
            {"$set": {"is_active": is_active}},
        )
        return res.modified_count > 0

    def admin_delete_user(self, username: str) -> bool:
        """Admin deletes a user account (except default admin)."""
        if not self.db.is_connected() or username.strip().lower() == "admin":
            return False
        res = self.db.db.users.delete_one({"username": username.strip().lower()})
        return res.deleted_count > 0

    # ─── Shared Team Profiles (Spotify & Proxies) ───────────────

    def get_team_profiles(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all shared Spotify and Proxy profiles."""
        if not self.db.is_connected():
            return {"spotify": [], "proxy": []}
        docs = list(self.db.db.team_configs.find({}, {"_id": 0}))
        return {
            "spotify": [d for d in docs if d.get("type") == "spotify"],
            "proxy": [d for d in docs if d.get("type") == "proxy"],
        }

    def add_team_profile(self, profile: Dict[str, Any]) -> bool:
        """Add or update a shared team config profile."""
        if not self.db.is_connected() or not profile.get("profile_id"):
            return False
        self.db.db.team_configs.update_one(
            {"profile_id": profile["profile_id"]},
            {"$set": profile},
            upsert=True,
        )
        return True

    def delete_team_profile(self, profile_id: str) -> bool:
        """Delete a shared team config profile."""
        if not self.db.is_connected() or not profile_id:
            return False
        res = self.db.db.team_configs.delete_one({"profile_id": profile_id})
        return res.deleted_count > 0

    def get_system_settings(self) -> Dict[str, Any]:
        """Get global system configuration settings from MongoDB."""
        if not self.db.is_connected():
            return {}
        doc = self.db.db.system_settings.find_one({"setting_id": "global_settings"}, {"_id": 0})
        if not doc:
            doc = {
                "setting_id": "global_settings",
                "audio_bitrate": "320k",
                "download_delay": 5.0,
                "batch_size": 50,
                "cooldown_seconds": 120,
                "active_spotify_profile": "spotify_default",
                "proxy_enabled": False,
                "r2_storage_enabled": False,
                "r2_bucket_name": "",
            }
            self.db.db.system_settings.insert_one(doc)
        return doc

    def save_system_settings(self, settings_dict: Dict[str, Any]) -> bool:
        """Save global system configuration settings to MongoDB."""
        if not self.db.is_connected():
            return False
        settings_dict["setting_id"] = "global_settings"
        self.db.db.system_settings.update_one(
            {"setting_id": "global_settings"},
            {"$set": settings_dict},
            upsert=True,
        )
        return True
