"""
discription:
    Calsses for a discord bot that manages AtCoder user information and contest information.
    
    register(ctx) : a command to register a discord user ID and an AtCoder user ID.
"""

import asyncio, os, sys, discord
from pathlib import Path
from dotenv import load_dotenv
from discord.ext import commands, tasks

import managedb as db
import atcoderapi as ac

INTERVAL = 300 #データをチェックする間隔(s).

load_dotenv(Path(__file__).resolve().parent / '.env', encoding='utf-8-sig')
TOKEN = os.getenv('DISCORD_TOKEN')
_channel_id = os.getenv('CHANNEL_ID') or os.getenv('DISCORD_CHANNEL_ID')
CHANNEL_ID = int(_channel_id) if _channel_id else None

#botのintentsを設定.
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

#コマンドを取得.
bot = commands.Bot(command_prefix='!', intents=intents)

# discord userと atcoder userを紐付けるコマンド.
@bot.command()
async def idregister(ctx, atcoder_user_id: str = None):
    if not atcoder_user_id:
        await send_message(ctx, "使い方: !idregister AtCoderユーザー名")
        return
    if not await asyncio.to_thread(ac.atcuser.isidexist, atcoder_user_id):
        await send_message(ctx, 
            "AtCoder user ID を確認できませんでした．\n" +
            "確認してからもう一度入力してください．"
        )
        return

    user_id = str(ctx.author.id)

    if not db.connect(user_id, atcoder_user_id):
        await send_message(ctx, "登録に失敗しました．\n")
    else:
        await send_message(ctx, "登録に成功しました．\n")

#userのポイントを確認するコマンド.
@bot.command()
async def pointcheck(ctx):
    user_id = str(ctx.author.id)
    point = db.get_point(user_id)

    if point is None:
        await send_message(ctx, "ポイントを確認できませんでした．\n")
    else:
        await send_message(ctx, f"あなたのポイントは {point} です．\n")

#userのAtCoder IDとポイントを確認するコマンド.
@bot.command()
async def checkacid(ctx):
    user_id = str(ctx.author.id)
    atcoder_user_id = db.get_atcoder_id(user_id)
    point = db.get_point(user_id)

    if atcoder_user_id is None:
        await send_message(ctx, "AtCoder user ID を確認できませんでした．\n")
    else:
        await send_message(ctx, f"あなたの AtCoder user ID は {atcoder_user_id} です．\n")

#userのステータスを表示するコマンド.
@bot.command()
async def showstatus(ctx):
    discord_user_id = str(ctx.author.id)
    atcoder_user_id = db.get_atcoder_id(discord_user_id)


    if atcoder_user_id is None:
        await send_message(ctx, "AtCoder user ID を確認できませんでした．\n")
    else:
        nowac = await asyncio.to_thread(ac.atcuser.getnumofac, atcoder_user_id)
        if nowac is None:
            await send_message(ctx, "AC数を取得できませんでした。時間をおいて再度お試しください。")
            return
        result = db.update_ac_points(discord_user_id, atcoder_user_id, nowac)
        if result is None:
            await send_message(ctx, "ポイントの更新に失敗しました。")
            return
        additional_ac, new_point = result
        text = ""
        if additional_ac > 0:
            text += f"ポイントが追加されました\n"
            text += f"AC数 +={additional_ac} -> {new_point}pt\n"
            text += f"\n"

        await send_message(
            ctx,
            text +
            f"{atcoder_user_id}\n" +
            f"   AC数 {nowac}\n" +
            f"   ポイント : {new_point}\n" +
            f"\n" +
            f"https://atcoder.jp/users/{atcoder_user_id}\n"
        )

#メッセージを送信する. 特定のチャンネルにのみ送信する.
async def send_message(ctx, message):
    if ctx.channel.id == CHANNEL_ID:
        await ctx.channel.send(message)
        return 0

# botの起動確認.
@bot.command()
async def ping(ctx):
    await ctx.send("pong")

# botの実行.

@tasks.loop(seconds=INTERVAL)
async def check_data():
    print("running\n")

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} (ID: {bot.user.id})')
    print('------')
    if not check_data.is_running():
        check_data.start()

def executebot():
    try:
        if not TOKEN:
            raise ValueError(".env に DISCORD_TOKEN を設定してください。")
        if CHANNEL_ID is None:
            raise ValueError(".env に CHANNEL_ID を設定してください。")
        bot.run(TOKEN)
    except Exception as e:
        print(f"Error occurred while running the bot: {e}")
        sys.exit(1)
