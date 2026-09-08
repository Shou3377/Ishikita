"""
    Discription:
        This file contains functions to manage the database for storing user mappings between Discord and AtCoder IDs.
        DB : userid, atcoderid, point

        connect(discord_user_id, atcoder_user_id) : a function to connect to the database and store the mapping.
"""

import sqlite3
import atcoderapi as ac

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

def update_ac_points(discord_user_id, atcoder_user_id, now_ac):
    """Save points and the AC watermark atomically, preventing duplicate awards."""
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
        new_point = point + 10 * additional_ac
        conn.execute(
            'UPDATE user_mapping SET point = ?, num_of_ac = ? WHERE discord_user_id = ?',
            (new_point, max(previous_ac, now_ac), discord_user_id),
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
