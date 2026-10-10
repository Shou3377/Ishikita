"""
discription:
    Calsses for a discord bot that manages AtCoder user information and contest information.
    
    register(ctx) : a command to register a discord user ID and an AtCoder user ID.
"""

import asyncio, os, sqlite3, sys, time, discord
from pathlib import Path
from dotenv import load_dotenv
from discord.ext import commands, tasks

import managedb as db
import atcoderapi as ac
import weekly
import logging

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
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)


@bot.command()
async def help(ctx):
    await send_message(
        ctx,
        "!idregister AtCoderユーザー名\n"
        "   自分のDiscordアカウントにAtCoder IDを登録します.\n"
        "   例：!idregister chokudai\n"
        "!showstatus\n"
        "   今週と累計のAC数・獲得ポイントを表示します.\n"
        "!weeklyreport\n"
        "   今週の獲得ポイント一覧を表示します.\n"
        "!ping\n"
        "   Botが動いていれば `pong!` と返信します.\n"
        "!help\n"
        "   この案内を表示します.\n"
        "!weekly\n"
        "   週間通知のON/OFFを確認します.\n"
        "!weekly off / !weekly on\n"
        "   週間通知を停止／再開します（サーバー管理権限が必要）.\n"
        "\n"
        "今週は日曜0時（日本時間）を始点とします.\n"
        "ACした問題のdifficultyの合計をポイントとして集計します. 再ACは重複加算せず, "
        "diff未設定の問題は0点です.\n"
        "毎週土曜24時（日曜0時）以降に, 前の1週間の獲得ポイントを自動通知します."
    )

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
        await error_message(ctx, error_type="connectfail")
    else:
        await send_message(
            ctx, "登録に成功しました．\n"
            "初期化のため`!showstatus`を実行してください．\n")

#userのステータスを表示するコマンド.
@bot.command()
async def showstatus(ctx):

    discord_user_id = str(ctx.author.id)
    atcoder_user_id = db.get_atcoder_id(discord_user_id)

    if atcoder_user_id is None:
        await error_message(ctx, error_type="acidnone")
    else:
        stats = await asyncio.to_thread(weekly.current_week_points, atcoder_user_id, include_total=True)
        if stats is None:
            await error_message(ctx, error_type="acnone")
            return
        start, now, (nowac, new_point, unrated_count), (total_ac, total_point, total_unrated) = stats

        await send_message(
            ctx,
            f"{atcoder_user_id}\n" +
            f"   今週の新規AC数 : {nowac}\n" +
            f"   今週の獲得ポイント（diff合計） : {new_point:,}pt\n" +
            (f"   diff未設定 : {unrated_count}問（0点）\n" if unrated_count else "") +
            f"\n累計 :\n" +
            f"   累計AC数 : {total_ac}\n" +
            f"   累計獲得ポイント（diff合計） : {total_point:,}pt\n" +
            (f"   diff未設定 : {total_unrated}問（0点）\n" if total_unrated else "") +
            f"\n" +
            f"https://atcoder.jp/users/{atcoder_user_id}\n"
        )

@bot.command()
async def weeklyreport(ctx):
    if ctx.channel.id != CHANNEL_ID:
        return
    try:
        with sqlite3.connect(db.DB_PATH) as conn:
            users = conn.execute(
                'SELECT discord_user_id, atcoder_user_id FROM user_mapping ORDER BY discord_user_id'
            ).fetchall()
    except sqlite3.Error:
        await send_message(ctx, 'ユーザー情報を読み込めませんでした。')
        return

    if not users:
        await send_message(ctx, '登録ユーザーはいません。')
        return

    difficulties = ac.get_difficulties()
    if difficulties is None:
        await send_message(ctx, 'difficultyの取得に失敗しました。時間をおいて再度お試しください。')
        return

    user_names = {
        str(member.id): member.global_name or member.display_name or member.name
        for member in bot.get_all_members()
    }
    start, end = weekly.week_bounds()
    lines = []
    for discord_id, atcoder_id in users:
        if ac.atcuser.getaclist(atcoder_id) is None:
            continue
        count, points, _ = weekly.period_points(atcoder_id, int(start.timestamp()), int(end.timestamp()), difficulties)
        name = user_names.get(str(discord_id), str(discord_id))
        lines.append(f'{name}: {points:,}pt（新規AC {count}問）')
        time.sleep(1.1)

    if not lines:
        await send_message(ctx, '今週のACデータを取得できませんでした。')
        return

    header = f'週間獲得ポイント（日本時間）\n{start:%Y/%m/%d} 00:00 ～ {end:%Y/%m/%d} 00:00\n'
    message = header + ''.join(f'{line}\n' for line in lines)
    await send_message(ctx, message)

#メッセージを送信する. 特定のチャンネルにのみ送信する.
async def send_message(ctx, message):
    if ctx.channel.id == CHANNEL_ID:
        await ctx.channel.send(message)
        return 0

# botの起動確認.
@bot.command()
async def ping(ctx):
    await ctx.send("pong!")

# botの実行.

@bot.command(name='weekly')
async def weekly_settings(ctx, mode: str = None):
    if ctx.channel.id != CHANNEL_ID:
        return
    mode = mode.lower() if mode else None
    if mode not in (None, 'on', 'off'):
        await send_message(ctx, '使い方: !weekly（状態確認） / !weekly off（停止） / !weekly on（再開）')
        return
    if mode is not None:
        if ctx.guild is None or not ctx.author.guild_permissions.manage_guild:
            await send_message(ctx, '設定の変更には「サーバー管理」権限が必要です。')
            return
        db.set_weekly_notifications(mode == 'on')
    enabled = db.weekly_notifications_enabled()
    message = '週間通知はONです。' if enabled else '週間通知はOFFです。'
    if mode == 'on':
        message += '次回チェック時に、直近の終了済み週が未通知なら送信します。'
    await send_message(ctx, message)


@tasks.loop(minutes=5)
async def weekly_report():
    try:
        if not db.weekly_notifications_enabled():
            return
        user_names = {
            str(member.id): member.global_name or member.display_name or member.name
            for member in bot.get_all_members()
        }
        key, pages = await asyncio.to_thread(weekly.prepare_report, user_names=user_names)
        if not pages:
            return
        channel = bot.get_channel(CHANNEL_ID) or await bot.fetch_channel(CHANNEL_ID)
        for page, content in pages:
            if not db.weekly_notifications_enabled():
                return
            await channel.send(content, allowed_mentions=discord.AllowedMentions.none())
            await asyncio.to_thread(weekly.mark_sent, key, page)
    except Exception:
        logging.exception('週間通知に失敗しました。次回チェック時に再試行します。')


@weekly_report.before_loop
async def before_weekly_report():
    await bot.wait_until_ready()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} (ID: {bot.user.id})')
    print('------')
    if not weekly_report.is_running():
        weekly_report.start()

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

async def error_message(ctx, error_type):
    messages = {
        "pointnone": "ポイントを確認できませんでした。",
        "acidnone": "AtCoder user ID を確認できませんでした。",
        "acnone": "AC一覧またはdifficultyを取得できませんでした。時間をおいて再度お試しください。",
        "updatefail": "ポイントの更新に失敗しました。",
        "connectfail": "登録に失敗しました。",
    }
    await send_message(ctx, messages[error_type])
