"""
    Discription:
        This file contains functions to manage the database for storing user mappings between Discord and AtCoder IDs.
        DB : userid, atcoderid, point

        connect(discord_user_id, atcoder_user_id) : a function to connect to the database and store the mapping.
"""

import sqlite3
from contextlib import closing


def _init_ac_cache(conn):
    conn.execute('''
        CREATE TABLE IF NOT EXISTS atcoder_sync (
            atcoder_user_id TEXT PRIMARY KEY,
            last_submission_second INTEGER NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS atcoder_ac_problems (
            atcoder_user_id TEXT NOT NULL,
            problem_id TEXT NOT NULL,
            PRIMARY KEY (atcoder_user_id, problem_id)
        )
    ''')


def get_ac_cache(atcoder_user_id):
    """Return (latest saved submission second, sorted AC IDs).

    SQLite errors propagate to the caller; a missing cache starts at -1.
    """
    with closing(sqlite3.connect('user_data.db')) as conn, conn:
        _init_ac_cache(conn)
        row = conn.execute(
            'SELECT last_submission_second FROM atcoder_sync WHERE atcoder_user_id = ?',
            (atcoder_user_id,),
        ).fetchone()
        problems = conn.execute(
            'SELECT problem_id FROM atcoder_ac_problems WHERE atcoder_user_id = ? ORDER BY problem_id',
            (atcoder_user_id,),
        ).fetchall()
        return (row[0] if row else -1), [problem[0] for problem in problems]


def save_ac_cache(atcoder_user_id, last_submission_second, problem_ids):
    """Commit AC IDs and their cursor together; concurrent saves cannot regress."""
    with closing(sqlite3.connect('user_data.db')) as conn, conn:
        _init_ac_cache(conn)
        conn.executemany(
            'INSERT OR IGNORE INTO atcoder_ac_problems VALUES (?, ?)',
            ((atcoder_user_id, problem_id) for problem_id in problem_ids),
        )
        conn.execute('''
            INSERT INTO atcoder_sync VALUES (?, ?)
            ON CONFLICT(atcoder_user_id) DO UPDATE SET
                last_submission_second = MAX(last_submission_second, excluded.last_submission_second)
        ''', (atcoder_user_id, last_submission_second))

def connect(discord_user_id, atcoder_user_id):
    try:
        conn = sqlite3.connect('user_data.db')
        cursor = conn.cursor()

        # Create table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_mapping (
                discord_user_id TEXT PRIMARY KEY,
                atcoder_user_id TEXT NOT NULL,
                point INTEGER DEFAULT 0,
                num_of_ac INTEGER DEFAULT 0
            )
        ''')

        # Insert or replace the user mapping
        cursor.execute('''
            INSERT OR REPLACE INTO user_mapping (discord_user_id, atcoder_user_id, point, num_of_ac)
            VALUES (?, ?, ?, ?)
        ''', (discord_user_id, atcoder_user_id, 0, 0))

        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        conn.close()

def get_atcoder_id(discord_user_id):
    try:
        conn = sqlite3.connect('user_data.db')
        cursor = conn.cursor()

        cursor.execute('''
            SELECT atcoder_user_id FROM user_mapping WHERE discord_user_id = ?
        ''', (discord_user_id,))
        result = cursor.fetchone()

        if result:
            return result[0]
        else:
            return None
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None
    finally:
        conn.close()

def get_point(discord_user_id):
    try:
        conn = sqlite3.connect('user_data.db')
        cursor = conn.cursor()

        cursor.execute('''
            SELECT point FROM user_mapping WHERE discord_user_id = ?
        ''', (discord_user_id,))
        result = cursor.fetchone()

        if result:
            return result[0]
        else:
            return None
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None
    finally:
        conn.close()

def get_num_of_ac(discord_user_id):
    try:
        conn = sqlite3.connect('user_data.db')
        cursor = conn.cursor()

        cursor.execute('''
            SELECT num_of_ac FROM user_mapping WHERE discord_user_id = ?
        ''', (discord_user_id,))
        result = cursor.fetchone()

        if result:
            return result[0]
        else:
            return None
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None
    finally:
        conn.close()

def update_point(discord_user_id, new_point):
    try:
        conn = sqlite3.connect('user_data.db')
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE user_mapping SET point = ? WHERE discord_user_id = ?
        ''', (new_point, discord_user_id))

        conn.commit()
        return True
    except sqlite3.Error as e:
        print("Database error: {e}")
        return False
    finally:
        conn.close()

def update_ac_points(discord_user_id, atcoder_user_id, now_ac, difficulty_sum):
    """Replace the old score with the current total of solved difficulties."""
    conn = None
    try:
        conn = sqlite3.connect('user_data.db')
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute(
            'SELECT point, num_of_ac FROM user_mapping WHERE discord_user_id = ? AND atcoder_user_id = ?',
            (discord_user_id, atcoder_user_id),
        ).fetchone()
        if row is None:
            return None
        point, previous_ac = row
        additional_ac = max(0, now_ac - previous_ac)
        new_point = difficulty_sum
        conn.execute(
            'UPDATE user_mapping SET point = ?, num_of_ac = ? WHERE discord_user_id = ?',
            (new_point, now_ac, discord_user_id),
        )
        conn.commit()
        return additional_ac, new_point
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None
    finally:
        if conn is not None:
            conn.close()


def add_point(discord_user_id, additional_point):
    get_point_value = get_point(discord_user_id)
    if get_point_value is None:
        print(f"{discord_user_id} のポイントを取得できませんでした．")
        return False

    new_point = get_point_value + additional_point
    return update_point(discord_user_id, new_point)
