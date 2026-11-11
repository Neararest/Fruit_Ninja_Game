from contextlib import closing
import hashlib
import os
import sqlite3
from datetime import datetime


class DatabaseManager:
    def __init__(self, db_path="fruit_ninja.db"):
        self.db_path = db_path
        folder = os.path.dirname(self.db_path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return closing(conn)

    @staticmethod
    def _hash_password(password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def _init_db(self):
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS solo_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    missed INTEGER NOT NULL,
                    level INTEGER NOT NULL,
                    played_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS multi_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    p1_user_id INTEGER,
                    p1_name TEXT NOT NULL,
                    p2_name TEXT NOT NULL,
                    p1_score INTEGER NOT NULL,
                    p2_score INTEGER NOT NULL,
                    level INTEGER NOT NULL,
                    winner TEXT NOT NULL,
                    highscore INTEGER NOT NULL,
                    played_at TEXT NOT NULL,
                    FOREIGN KEY (p1_user_id) REFERENCES users (id)
                )
                """
            )
            conn.commit()

    def register_user(self, username: str, password: str):
        username = username.strip()
        if len(username) < 3:
            return False, "Username minimal 3 karakter!", None
        if len(username) > 18:
            return False, "Username maksimal 18 karakter!", None
        if len(password) < 3:
            return False, "Password minimal 3 karakter!", None

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        pw_hash = self._hash_password(password)

        try:
            with self._get_conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                    (username, pw_hash, now_str),
                )
                conn.commit()
                user_id = cur.lastrowid
                user_data = {
                    "id": user_id,
                    "username": username,
                    "is_guest": False,
                }
                return True, f"Akun '{username}' berhasil dibuat!", user_data
        except sqlite3.IntegrityError:
            return False, f"Username '{username}' sudah terdaftar!", None
        except Exception as e:
            return False, f"Gagal mendaftar: {e}", None

    def login_user(self, username: str, password: str):
        username = username.strip()
        if not username or not password:
            return False, "Username dan password wajib diisi!", None

        pw_hash = self._hash_password(password)
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, username, password_hash FROM users WHERE username = ?",
                (username,),
            )
            row = cur.fetchone()
            if not row:
                return False, f"Akun '{username}' tidak ditemukan!", None
            if row["password_hash"] != pw_hash:
                return False, "Password salah!", None

            user_data = {
                "id": row["id"],
                "username": row["username"],
                "is_guest": False,
            }
            return True, f"Selamat datang kembali, {row['username']}!", user_data

    def get_user_stats(self, user_dict):
        if not user_dict:
            return {"highscore": 0, "total_games": 0, "avg_score": 0.0, "max_level": 1}

        username = user_dict.get("username", "Guest")
        user_id = user_dict.get("id")

        with self._get_conn() as conn:
            cur = conn.cursor()
            if user_id is not None:
                cur.execute(
                    """
                    SELECT
                        COALESCE(MAX(score), 0) AS highscore,
                        COUNT(*) AS total_games,
                        COALESCE(AVG(score), 0) AS avg_score,
                        COALESCE(MAX(level), 1) AS max_level
                    FROM solo_scores
                    WHERE user_id = ? OR username = ?
                    """,
                    (user_id, username),
                )
            else:
                cur.execute(
                    """
                    SELECT
                        COALESCE(MAX(score), 0) AS highscore,
                        COUNT(*) AS total_games,
                        COALESCE(AVG(score), 0) AS avg_score,
                        COALESCE(MAX(level), 1) AS max_level
                    FROM solo_scores
                    WHERE username = ?
                    """,
                    (username,),
                )
            row = cur.fetchone()
            return {
                "highscore": int(row["highscore"]) if row else 0,
                "total_games": int(row["total_games"]) if row else 0,
                "avg_score": round(float(row["avg_score"]), 1) if row else 0.0,
                "max_level": int(row["max_level"]) if row else 1,
            }

    def save_solo_score(self, user_dict, score: int, missed: int, level: int):
        if not user_dict:
            user_dict = {"id": None, "username": "Guest", "is_guest": True}

        prev_stats = self.get_user_stats(user_dict)
        prev_best = prev_stats["highscore"]
        is_new_high = score > prev_best and score > 0

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO solo_scores (user_id, username, score, missed, level, played_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_dict.get("id"),
                    user_dict.get("username", "Guest"),
                    int(score),
                    int(missed),
                    int(level),
                    now_str,
                ),
            )
            conn.commit()

        return {
            "is_new_highscore": is_new_high,
            "highscore": max(prev_best, int(score)),
        }

    def save_multi_score(self, user_dict, p1_score: int, p2_score: int, level: int, p2_name: str = "Player 2"):
        if not user_dict:
            user_dict = {"id": None, "username": "Player 1", "is_guest": True}

        p1_name = user_dict.get("username", "Player 1")
        if p1_score > p2_score:
            winner = p1_name
        elif p2_score > p1_score:
            winner = p2_name
        else:
            winner = "Draw"

        highscore = max(int(p1_score), int(p2_score))
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO multi_scores (
                    p1_user_id, p1_name, p2_name, p1_score, p2_score, level, winner, highscore, played_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_dict.get("id"),
                    p1_name,
                    p2_name,
                    int(p1_score),
                    int(p2_score),
                    int(level),
                    winner,
                    highscore,
                    now_str,
                ),
            )
            conn.commit()

        return {
            "winner": winner,
            "highscore": highscore,
        }

    def get_solo_leaderboard(self, limit: int = 10):
        """
        Mengembalikan daftar peringkat pemain berdasarkan Highscore tertinggi per akun/username.
        """
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                    username,
                    MAX(score) AS highscore,
                    MAX(level) AS max_level,
                    COUNT(*) AS total_games,
                    MAX(played_at) AS last_played
                FROM solo_scores
                GROUP BY LOWER(username)
                ORDER BY highscore DESC, max_level DESC, last_played DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cur.fetchall()
            result = []
            for idx, r in enumerate(rows, start=1):
                result.append(
                    {
                        "rank": idx,
                        "username": r["username"],
                        "highscore": r["highscore"],
                        "max_level": r["max_level"],
                        "total_games": r["total_games"],
                        "last_played": r["last_played"],
                    }
                )
            return result

    def get_registered_usernames(self, exclude_username: str = None, limit: int = 6) -> list[str]:
        """
        Mengembalikan daftar username yang terdaftar (untuk pilihan cepat Player 2 di Multiplayer).
        """
        with self._get_conn() as conn:
            cur = conn.cursor()
            if exclude_username:
                cur.execute(
                    "SELECT username FROM users WHERE LOWER(username) != LOWER(?) ORDER BY id DESC LIMIT ?",
                    (exclude_username, limit),
                )
            else:
                cur.execute("SELECT username FROM users ORDER BY id DESC LIMIT ?", (limit,))
            return [r["username"] for r in cur.fetchall()]

    def get_multi_leaderboard(self, limit: int = 10):
        """
        Mengembalikan daftar pertandingan Multiplayer dengan skor tertinggi.
        """
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                    p1_name,
                    p2_name,
                    p1_score,
                    p2_score,
                    level,
                    winner,
                    highscore,
                    played_at
                FROM multi_scores
                ORDER BY highscore DESC, level DESC, played_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cur.fetchall()
            result = []
            for idx, r in enumerate(rows, start=1):
                result.append(
                    {
                        "rank": idx,
                        "p1_name": r["p1_name"],
                        "p2_name": r["p2_name"],
                        "p1_score": r["p1_score"],
                        "p2_score": r["p2_score"],
                        "level": r["level"],
                        "winner": r["winner"],
                        "highscore": r["highscore"],
                        "played_at": r["played_at"],
                    }
                )
            return result

