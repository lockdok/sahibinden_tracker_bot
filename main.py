"""Точка входа приватного Telegram-трекера объявлений Sahibinden."""
import argparse,asyncio,logging,os
from pathlib import Path
import yaml
from dotenv import load_dotenv
ROOT=Path(__file__).parent; load_dotenv(ROOT/".env")
logging.basicConfig(level=logging.INFO,format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
def load_config():
    with (ROOT/"config.yaml").open(encoding="utf-8") as file: config=yaml.safe_load(file)
    config["telegram"]["bot_token"]=os.environ.get("TELEGRAM_BOT_TOKEN",""); config["telegram"]["chat_id"]=os.environ.get("TELEGRAM_CHAT_ID","")
    if not config["telegram"]["bot_token"] or not config["telegram"]["chat_id"]: raise RuntimeError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
    return config
def main():
    p=argparse.ArgumentParser(); p.add_argument("command",choices=["bot","check"]); args=p.parse_args(); config=load_config()
    if args.command=="bot":
        from src.bot import build_application
        from src.db import init_db
        asyncio.run(init_db()); build_application(config).run_polling(allowed_updates=["message"])
    else:
        from src.checker import run_daily_check
        print(asyncio.run(run_daily_check(config)))
if __name__=="__main__": main()
