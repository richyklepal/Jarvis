"""Text Jarvis from your phone through Telegram (free).

Setup, once:
  1. In Telegram, message @BotFather, send /newbot, pick a name. Copy the token it gives you.
  2. Put it in .env as TELEGRAM_BOT_TOKEN, then run:  python main.py --telegram
  3. Message your new bot. It replies with your user ID. Put that in .env as
     TELEGRAM_ALLOWED_USER_ID and restart. From then on it only answers you.

Send text or voice notes. Voice notes are transcribed on your computer with Whisper.
Commands: /new starts a fresh conversation, /id shows your user ID.
"""

import json
import os
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.telegram.org"
MAX_MSG = 4000


class Telegram:
    def __init__(self, token):
        self.token = token

    def call(self, method, http_timeout=40, **params):
        data = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None}).encode()
        req = urllib.request.Request(f"{API}/bot{self.token}/{method}", data=data)
        with urllib.request.urlopen(req, timeout=http_timeout) as r:
            body = json.loads(r.read().decode())
        if not body.get("ok"):
            raise RuntimeError(body.get("description", "Telegram error"))
        return body["result"]

    def send(self, chat_id, text):
        text = text or "(empty reply)"
        for i in range(0, len(text), MAX_MSG):
            self.call("sendMessage", chat_id=chat_id, text=text[i:i + MAX_MSG])

    def download(self, file_id, suffix):
        path = self.call("getFile", file_id=file_id)["file_path"]
        url = f"{API}/file/bot{self.token}/{path}"
        fd, local = tempfile.mkstemp(suffix=suffix)
        with urllib.request.urlopen(url, timeout=60) as r, os.fdopen(fd, "wb") as f:
            f.write(r.read())
        return local


def _voice_to_text(bot, msg):
    from audio.stt import transcribe_file

    media = msg.get("voice") or msg.get("audio")
    local = bot.download(media["file_id"], ".ogg")
    try:
        return transcribe_file(local)
    finally:
        try:
            os.remove(local)
        except OSError:
            pass


def run(jarvis):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("[Telegram] Set TELEGRAM_BOT_TOKEN in .env first (get one from @BotFather).")
    allowed = os.environ.get("TELEGRAM_ALLOWED_USER_ID", "").strip()
    bot = Telegram(token)
    me = bot.call("getMe")
    print(f"[Telegram] @{me['username']} is listening.", "Locked to your account." if allowed else
          "Not locked yet — message the bot to get your user ID.")

    offset = None
    while True:
        try:
            # long poll: Telegram holds the request up to 50s waiting for a message
            updates = bot.call("getUpdates", http_timeout=60, offset=offset, timeout=50,
                               allowed_updates='["message"]')
        except (urllib.error.URLError, TimeoutError, RuntimeError) as e:
            print(f"[Telegram] connection problem: {e}. Retrying in 5s.")
            time.sleep(5)
            continue

        for upd in updates:
            offset = upd["update_id"] + 1
            msg = upd.get("message")
            if not msg:
                continue
            chat_id = msg["chat"]["id"]
            user_id = str(msg.get("from", {}).get("id", ""))
            text = (msg.get("text") or "").strip()

            if text.startswith("/id") or text.startswith("/start") or not allowed:
                note = "" if allowed else (
                    "\n\nAdd this to Jarvis's .env as TELEGRAM_ALLOWED_USER_ID and restart. "
                    "Until then I won't answer anything else.")
                bot.send(chat_id, f"Your Telegram user ID is {user_id}.{note}")
                continue
            if user_id != allowed:
                continue  # stay silent for anyone who isn't you

            try:
                if msg.get("voice") or msg.get("audio"):
                    bot.call("sendChatAction", chat_id=chat_id, action="typing")
                    text = _voice_to_text(bot, msg)
                    if not text:
                        bot.send(chat_id, "I couldn't make out that voice note. Try again?")
                        continue
                    bot.send(chat_id, f"🎙 {text}")
                if text.startswith("/new"):
                    jarvis.reset(f"tg:{chat_id}")
                    bot.send(chat_id, "Fresh conversation.")
                    continue
                if not text:
                    bot.send(chat_id, "Send me text or a voice note.")
                    continue
                bot.call("sendChatAction", chat_id=chat_id, action="typing")
                bot.send(chat_id, jarvis.ask(f"tg:{chat_id}", text))
            except Exception as e:  # one bad message shouldn't kill the bot
                print(f"[Telegram] error: {e}")
                try:
                    bot.send(chat_id, f"Something broke on my end: {e}")
                except Exception:
                    pass
