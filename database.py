import sqlite3
import logging
from datetime import datetime
from contextlib import contextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_name="bot_database.db"):
        self.db_name = db_name
        self.init_db()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    balance INTEGER DEFAULT 0,
                    last_opened TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Таблица карточек пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    card_name TEXT,
                    rarity TEXT,
                    file_path TEXT,
                    obtained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_sold BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')

    def add_user(self, user_id, username):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO users (user_id, username) 
                VALUES (?, ?)
            ''', (user_id, username))

    def get_user(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            return cursor.fetchone()

    def update_balance(self, user_id, amount):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET balance = balance + ? 
                WHERE user_id = ?
            ''', (amount, user_id))
            return cursor.rowcount > 0

    def update_last_opened(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET last_opened = ? 
                WHERE user_id = ?
            ''', (datetime.now(), user_id))

    def can_open_box(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT last_opened FROM users WHERE user_id = ?', (user_id,))
            user = cursor.fetchone()

            if not user or not user['last_opened']:
                return True

            last_opened = datetime.fromisoformat(user['last_opened'])
            time_passed = (datetime.now() - last_opened).total_seconds()
            return time_passed >= 3600  # 1 час

    def add_card(self, user_id, card_name, rarity, file_path):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_cards (user_id, card_name, rarity, file_path)
                VALUES (?, ?, ?, ?)
            ''', (user_id, card_name, rarity, file_path))
            return cursor.lastrowid

    def sell_card(self, card_id, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Получаем редкость карточки
            cursor.execute('''
                SELECT rarity FROM user_cards 
                WHERE id = ? AND user_id = ? AND is_sold = 0
            ''', (card_id, user_id))
            card = cursor.fetchone()

            if card:
                # Помечаем как проданную
                cursor.execute('''
                    UPDATE user_cards 
                    SET is_sold = 1 
                    WHERE id = ? AND user_id = ?
                ''', (card_id, user_id))
                return card['rarity']
            return None

    def get_user_cards(self, user_id, unsold_only=True):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if unsold_only:
                cursor.execute('''
                    SELECT * FROM user_cards 
                    WHERE user_id = ? AND is_sold = 0 
                    ORDER BY obtained_at DESC
                ''', (user_id,))
            else:
                cursor.execute('''
                    SELECT * FROM user_cards 
                    WHERE user_id = ? 
                    ORDER BY obtained_at DESC
                ''', (user_id,))
            return cursor.fetchall()

    def get_top_players(self, limit=10):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    u.user_id,
                    u.username,
                    u.balance,
                    COUNT(uc.id) as card_count
                FROM users u
                LEFT JOIN user_cards uc ON u.user_id = uc.user_id AND uc.is_sold = 0
                GROUP BY u.user_id
                ORDER BY u.balance DESC, card_count DESC
                LIMIT ?
            ''', (limit,))
            return cursor.fetchall()

    def get_card_count(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) as count 
                FROM user_cards 
                WHERE user_id = ? AND is_sold = 0
            ''', (user_id,))
            return cursor.fetchone()['count']