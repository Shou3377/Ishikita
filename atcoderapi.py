"""
description:
    this file is used to get the data from atcoder

    acuser : a class to manage the AtCoder user ID.
"""

import time
import sqlite3
import math
import threading

import requests
import managedb as db

_difficulty_cache = None
_difficulty_cached_at = 0
_difficulty_lock = threading.Lock()


def get_difficulties():
    """Fetch displayed difficulties, sharing a one-hour cache across users."""
    global _difficulty_cache, _difficulty_cached_at
    with _difficulty_lock:
        if _difficulty_cache is not None and time.monotonic() - _difficulty_cached_at < 3600:
            return _difficulty_cache
        try:
            response = requests.get(
                'https://kenkoooo.com/atcoder/resources/problem-models.json', timeout=30,
            )
            response.raise_for_status()
            models = response.json()
            if not isinstance(models, dict) or not models:
                return None
            difficulties = {}
            for problem_id, model in models.items():
                if not isinstance(model, dict):
                    return None
                value = model.get('difficulty')
                if value is None:
                    continue
                if type(value) not in (int, float) or not math.isfinite(value):
                    return None
                displayed = value if value >= 400 else 400 * math.exp(value / 400 - 1)
                difficulties[problem_id] = math.floor(displayed + 0.5)
            _difficulty_cache = difficulties
            _difficulty_cached_at = time.monotonic()
            return difficulties
        except (requests.RequestException, ValueError):
            return None

class atcuser:
    @staticmethod
    def get_ac_points(atcoder_user_id):
        """Return (unique AC count, difficulty sum, unrated count), or None."""
        problems = atcuser.getaclist(atcoder_user_id)
        if problems is None:
            return None
        if not problems:
            return 0, 0, 0
        difficulties = get_difficulties()
        if difficulties is None:
            return None
        problems = set(problems)
        return (
            len(problems),
            sum(difficulties.get(problem, 0) for problem in problems),
            sum(problem not in difficulties for problem in problems),
        )

    #check if the AtCoder user ID exists.
    @staticmethod
    def isidexist(ctx):

        atcoder_user_id = ctx
        url = f"https://atcoder.jp/users/{atcoder_user_id}"
        try:
            response = requests.get(url, timeout=10)
        except requests.RequestException:
            return False
        if response.status_code == 200:
            return True
        else:
            return False

    #get num of AC problems of the user.
    @staticmethod
    def getnumofac(atcoder_user_id):
        url = f"https://kenkoooo.com/atcoder/atcoder-api/v3/user/ac_rank?user={atcoder_user_id}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            numofac = data.get("count") if isinstance(data, dict) else None
            return numofac if type(numofac) is int and numofac >= 0 else None
        except (requests.RequestException, ValueError):
            return None

    @staticmethod
    def getaclist(atcoder_user_id):
        """Return sorted, unique AC problem IDs; return None on fetch failure.

        AC IDs and the latest fetched submission time are cached in SQLite.
        Subsequent calls fetch only newer submissions, returning the full list.
        An empty list means no accepted submissions were found. This function
        performs blocking requests; use asyncio.to_thread from bot commands.
        """
        url = "https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions"
        try:
            last_second, _ = db.get_ac_cache(atcoder_user_id)
            from_second = last_second + 1
            while True:
                response = requests.get(
                    url,
                    params={"user": atcoder_user_id, "from_second": from_second},
                    timeout=10,
                )
                response.raise_for_status()
                submissions = response.json()
                if not isinstance(submissions, list):
                    return None
                if not submissions:
                    return db.get_ac_cache(atcoder_user_id)[1]

                accepted = set()
                latest_second = from_second - 1
                for submission in submissions:
                    if not isinstance(submission, dict):
                        return None
                    epoch_second = submission.get("epoch_second")
                    problem_id = submission.get("problem_id")
                    result = submission.get("result")
                    if (type(epoch_second) is not int
                            or epoch_second < from_second
                            or not isinstance(problem_id, str)
                            or not problem_id
                            or not isinstance(result, str)):
                        return None
                    latest_second = max(latest_second, epoch_second)
                    if result == "AC":
                        accepted.add(problem_id)

                db.save_ac_cache(atcoder_user_id, latest_second, accepted)
                from_second = latest_second + 1
                # Space out requests to the public API, including pagination.
                time.sleep(1)
        except (requests.RequestException, ValueError, sqlite3.Error):
            return None
