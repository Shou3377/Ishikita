import sqlite3
from contextlib import closing
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import managedb as db
import weekly


class WeeklyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path_patch = patch.object(db, 'DB_PATH', Path(self.directory.name) / 'test.db')
        self.path_patch.start()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self.path_patch.stop)

    def test_sunday_boundary(self):
        before = datetime(2026, 10, 10, 23, 59, 59, tzinfo=weekly.JST)
        after = datetime(2026, 10, 11, tzinfo=weekly.JST)
        self.assertEqual(weekly.week_bounds(before)[1].day, 4)
        self.assertEqual(weekly.week_bounds(after)[1], after)

    def test_history_migration(self):
        with closing(sqlite3.connect(db.DB_PATH)) as conn, conn:
            conn.execute('CREATE TABLE atcoder_ac_problems (atcoder_user_id TEXT, problem_id TEXT, PRIMARY KEY(atcoder_user_id, problem_id))')
            conn.execute('CREATE TABLE atcoder_sync (atcoder_user_id TEXT PRIMARY KEY, last_submission_second INTEGER)')
            conn.execute("INSERT INTO atcoder_ac_problems VALUES ('user', 'old')")
            conn.execute("INSERT INTO atcoder_sync VALUES ('user', 100)")
        self.assertEqual(db.get_ac_cache('user'), (-1, ['old']))
        db.save_ac_cache('user', 100, {'old': 20})
        db.save_ac_cache('user', 200, {'old': 150})
        with closing(sqlite3.connect(db.DB_PATH)) as conn, conn:
            self.assertEqual(conn.execute('SELECT first_ac_second FROM atcoder_ac_problems').fetchone()[0], 20)

    def test_current_week_points(self):
        now = datetime(2026, 10, 9, 12, tzinfo=weekly.JST)
        start = weekly.week_bounds(now)[1]
        a, b = int(start.timestamp()), int(now.timestamp())
        db.get_ac_cache('user')
        db.save_ac_cache('user', b + 1, {'old': a - 1, 'first': a, 'current': b, 'future': b + 1, 'unrated': a + 1})
        db.save_ac_cache('user', b + 1, {'old': a + 2})
        with patch.object(weekly.ac.atcuser, 'getaclist', return_value=[]), patch.object(weekly.ac, 'get_difficulties', return_value={'old': 999, 'first': 100, 'current': 200, 'future': 999}):
            self.assertEqual(weekly.current_week_points('user', now), (start, now, (3, 300, 1)))
            self.assertEqual(weekly.current_week_points('user', now, include_total=True),
                             (start, now, (3, 300, 1), (4, 1299, 1)))
            next_week = datetime(2026, 10, 11, tzinfo=weekly.JST)
            self.assertEqual(weekly.current_week_points('user', next_week)[2], (0, 0, 0))
        with patch.object(weekly.ac.atcuser, 'getaclist', return_value=None):
            self.assertIsNone(weekly.current_week_points('user', now))

    def test_report_and_retry(self):
        now = datetime(2026, 10, 11, tzinfo=weekly.JST)
        start, end = weekly.week_bounds(now)
        a, b = int(start.timestamp()), int(end.timestamp())
        self.assertTrue(db.connect('123', 'user'))
        db.get_ac_cache('user')
        db.save_ac_cache('user', b, {'old': a - 1, 'first': a, 'last': b - 1, 'next': b})
        db.save_ac_cache('user', b, {'old': a + 100})
        with patch.object(weekly.ac, 'get_difficulties', return_value={'old': 900, 'first': 100, 'last': 200, 'next': 500}), patch.object(weekly.ac.atcuser, 'getaclist', return_value=['old', 'first', 'last', 'next']), patch.object(weekly.time, 'sleep'):
            key, pages = weekly.prepare_report(now, {'123': 'Alice'})
        self.assertEqual(len(pages), 1)
        self.assertIn('Alice: 300pt', pages[0][1])
        self.assertNotIn('<123>', pages[0][1])
        self.assertEqual(weekly.prepare_report(now, {'123': 'Alice'}), (key, pages))
        weekly.mark_sent(key, pages[0][0])
        self.assertEqual(weekly.prepare_report(now), (key, []))

    def test_api_failure_does_not_mark_sent(self):
        db.connect('123', 'user')
        with patch.object(weekly.ac, 'get_difficulties', return_value=None):
            with self.assertRaises(RuntimeError):
                weekly.prepare_report()
        with closing(sqlite3.connect(db.DB_PATH)) as conn, conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM weekly_reports').fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
