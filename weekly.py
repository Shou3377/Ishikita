"""Weekly first-AC difficulty reports, Sunday 00:00 JST boundaries."""
import time
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone

import atcoderapi as ac
import managedb as db

JST = timezone(timedelta(hours=9))


def week_bounds(now=None):
    now = (now or datetime.now(JST)).astimezone(JST)
    end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end -= timedelta(days=(end.weekday() + 1) % 7)
    return end - timedelta(days=7), end


def period_points(atcoder_id, start_second, end_second, difficulties):
    """Read first ACs in a half-open interval from the synchronized cache."""
    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        problems = conn.execute('''SELECT problem_id FROM atcoder_ac_problems
            WHERE atcoder_user_id = ? AND first_ac_second >= ? AND first_ac_second < ?''',
            (atcoder_id, start_second, end_second)).fetchall()
    return (len(problems),
            sum(difficulties.get(problem, 0) for (problem,) in problems),
            sum(problem not in difficulties for (problem,) in problems))


def current_week_points(atcoder_id, now=None, include_total=False):
    now = (now or datetime.now(JST)).astimezone(JST)
    start = week_bounds(now)[1]
    try:
        if ac.atcuser.getaclist(atcoder_id) is None:
            return None
        difficulties = ac.get_difficulties()
        if difficulties is None:
            return None
        # Include submissions in the command's current second.
        stats = period_points(atcoder_id, int(start.timestamp()), int(now.timestamp()) + 1, difficulties)
        if include_total:
            total = period_points(atcoder_id, 0, int(now.timestamp()) + 1, difficulties)
            return start, now, stats, total
        return start, now, stats
    except sqlite3.Error:
        return None


def prepare_report(now=None):
    start, end = week_bounds(now)
    key = int(end.timestamp())
    with closing(sqlite3.connect(db.DB_PATH)) as conn, conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS weekly_reports (
            week_end INTEGER, page INTEGER, content TEXT NOT NULL,
            sent INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (week_end, page))''')
        rows = conn.execute(
            'SELECT page, content, sent FROM weekly_reports WHERE week_end = ? ORDER BY page',
            (key,),
        ).fetchall()
        if rows:
            return key, [(page, content) for page, content, sent in rows if not sent]
        exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='user_mapping'").fetchone()
        users = conn.execute('SELECT discord_user_id, atcoder_user_id FROM user_mapping ORDER BY discord_user_id').fetchall() if exists else []

    difficulties = ac.get_difficulties() if users else {}
    if difficulties is None:
        raise RuntimeError('週間通知: difficulty取得失敗')
    lines = []
    for discord_id, atcoder_id in users:
        if ac.atcuser.getaclist(atcoder_id) is None:
            raise RuntimeError('週間通知: AC履歴取得失敗')
        count, points, _ = period_points(atcoder_id, int(start.timestamp()), key, difficulties)
        lines.append(f'<{discord_id}>: {points:,}pt（新規AC {count}問）')
        time.sleep(1.1)
    header = f'週間獲得ポイント（日本時間）\n{start:%Y/%m/%d} 00:00 ～ {end:%Y/%m/%d} 00:00\n'
    pages = []
    content = header
    for line in lines or ['登録ユーザーはいません。']:
        if len(content) + len(line) + 1 > 1900:
            pages.append(content)
            content = header
        content += line + '\n'
    pages.append(content)
    with closing(sqlite3.connect(db.DB_PATH)) as conn, conn:
        conn.executemany('INSERT OR IGNORE INTO weekly_reports (week_end, page, content) VALUES (?, ?, ?)',
                         ((key, page, content) for page, content in enumerate(pages)))
        rows = conn.execute('SELECT page, content FROM weekly_reports WHERE week_end = ? AND sent = 0 ORDER BY page', (key,)).fetchall()
    return key, rows


def mark_sent(key, page):
    with closing(sqlite3.connect(db.DB_PATH)) as conn, conn:
        conn.execute('UPDATE weekly_reports SET sent = 1 WHERE week_end = ? AND page = ?', (key, page))
