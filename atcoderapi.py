"""
description:
    this file is used to get the data from atcoder

    acuser : a class to manage the AtCoder user ID.
"""

import requests

class atcuser:
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
