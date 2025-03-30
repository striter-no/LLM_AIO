import asyncio
import logging
import sys
from os import getenv
import json as jn
import shutil, os

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile
from aiogram.types import Message

import time

# Bot token can be obtained via https://t.me/BotFather

dp = Dispatcher()
bot = None
conf = jn.load(open("./configs/dev/bot_cfg.json"))
is_fallback_online = False

TOKEN = conf["API_KEY"]

async def is_online():
    with open("./runtime/aiogram_main.txt") as f:
        bot_time = f.read()
    if len(bot_time.strip()) == 0:
        await asyncio.sleep(0.5)
        with open("./runtime/aiogram_main.txt") as f:
            bot_time = f.read()

    curr_time = str(time.time())

    if abs(round(float(curr_time)) - round(float(bot_time))) >= 7:
        for i in range(3):
            await asyncio.sleep(2)
            with open("./runtime/aiogram_main.txt") as f:
                bot_time = f.read()
            curr_time = str(time.time())

            if abs(round(float(curr_time)) - round(float(bot_time))) < 7:
                break

        if abs(round(float(curr_time)) - round(float(bot_time))) >= 7:
            print(f"\rCurrent time: {round(float(curr_time))} | Bot time: {round(float(bot_time))}", end="")
            return False
    
    print(f"\rCurrent time: {round(float(curr_time))} | Bot time: {round(float(bot_time))} | Delta: {abs(round(float(curr_time)) - round(float(bot_time)))}", end="")
    return True

@dp.message()
async def echo_handler(message: Message) -> None:
    await bot.send_message(message.chat.id, "Этот бот офлайн. Вероятно он скоро будет в сети. В случае проблем писать @quitearno")

async def check_online():
    global is_fallback_online
    while True:
        if (await is_online()):
            
            print(" | Bot online", end = "")
            if is_fallback_online:
                await dp.stop_polling()
                is_fallback_online = False
        
        else:
            
            print(" | Bot offline", end = "")
            if not is_fallback_online:
                asyncio.create_task(dp.start_polling(bot))
                is_fallback_online = True

async def on_startup():
    asyncio.create_task(check_online())

async def main() -> None:
    global bot
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
    await check_online()
    

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    asyncio.run(main())