from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile
from aiogram.types import Message
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

import src.sql_db as sql_db
import src.xml_utils as xml
import src.gpt as gpt

import json as jn
import asyncio
import random

dp = Dispatcher()
bot: Bot = None;

tgconf = jn.load(open("./configs/dev/bot_cfg.json"))
gptconf = jn.load(open("./configs/system_prompt.json"))
msgsconf = jn.load(open("./configs/messages.json"))

users = sql_db.DataBase("./databases/users.sqllite")

MAIN_PROVIDER = gpt.provider_stock.PollinationsAI

def check_file(path: str) -> bool:
    try:
        with open(path, "r") as f:
            f.read()
        return True
    except Exception as e:
        print(f"Error while checking file {path}: {str(e)}")
        return False

@dp.message()
async def handle_message(message: Message) -> None:
    global bot

    uid = message.from_user.id
    text = message.text or message.caption
    token = random.randint(0, 10000)
    
    images = []
    files  = []
    file_id, file_name, extension = None, None, None

    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
        extension = ""
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_name = f"{file_id}.jpg"
        extension = ".png"
    elif message.document is None and message.photo is None:
        pass
    else:
        await message.reply("Неизвестный формат файла, поддерживаются только текстовые файлы и изображения")
        return

    if file_id:
        dfile = await bot.get_file(file_id)
        api_path = dfile.file_path
        fpath = f"./runtime/userdata/{file_name}"
        await bot.download_file(api_path, fpath)

        if extension == "":
            if (check_file(fpath)):
                files.append(fpath)
        elif extension == ".png":
            images.append(fpath)

    if text:
        if text[0] == '/':
            command = text[1:].lower()
            opcode = command.split(' ')[0]

            if opcode in msgsconf["commands"]:
                await message.reply(msgsconf["commands"][opcode])
            else:
                await message.reply(msgsconf["commands"]["unknown"])

            if opcode == "clear":
                if users.get(uid) is None:
                    await bot.send_message(message.chat.id, "Еще нет контекста для очистки")
                    return
                user_data = users.get(uid)
                user_data["messages"] = []
                users.set(uid, user_data)

            if opcode == "model":
                if len(command.split(' ')) < 2:
                    await bot.send_message(message.chat.id, "Недостаточно аргументов, вам нужно указать модель")
                    return
                
                model_name = command.split(' ')[1]
                if users.get(uid) is None:
                    users.set(uid, {"base_model": "o3-mini", "img_model": "flux", "messages": []})

                if model_name in gpt.models_stock.ModelUtils.convert and not (model_name in gpt.image_models):
                    user_data = users.get(uid)
                    user_data["base_model"] = model_name
                    users.set(uid, user_data)
                    await bot.send_message(message.chat.id, f"Базовая модель установлена на {model_name}")
                elif model_name in gpt.image_models:
                    await bot.send_message(message.chat.id, f"Базовая модель не может быть установлена на {model_name}, т.к. это модель для генерации изображений")
                else:
                    await bot.send_message(message.chat.id, f"Нет модели с таким именем: {model_name}")
            
            if opcode == "img_model":
                if len(command.split(' ')) < 2:
                    await bot.send_message(message.chat.id, "Недостаточно аргументов, вам нужно указать модель")
                    return
                
                if users.get(uid) is None:
                    users.set(uid, {"base_model": "o3-mini", "img_model": "flux", "messages": []})

                model_name = command.split(' ')[1]
                if model_name in gpt.image_models:
                    user_data = users.get(uid)
                    user_data["img_model"] = model_name
                    users.set(uid, user_data)
                    await bot.send_message(message.chat.id, f"Базовая модель установлена на {model_name}")
                else:
                    await bot.send_message(message.chat.id, f"Нет модели с таким именем: {model_name}")

            if opcode == "stats":
                if users.get(uid) is None:
                    users.set(uid, {"base_model": "o3-mini", "img_model": "flux", "messages": []})
                
                user_data = users.get(uid)
                await bot.send_message(message.chat.id, f"Ваша статистика:\n\nОсновная (текстовая) модель: {user_data["base_model"]}\nМодель для изображений: {user_data["img_model"]}\nКоличество сообщений: {len(user_data["messages"])}")

        else:
            if users.get(uid) is None:
                users.set(uid, {"base_model": "o3-mini", "img_model": "flux", "messages": []})
            
            user_data = users.get(uid)
            chat = gpt.Chat( provider=MAIN_PROVIDER, model=user_data["base_model"])
            chat.systemQuery = gptconf["general"]
            chat.messages = user_data["messages"]
            
            time = 1
            while True:
                try:
                    answer = await chat.addMessageAsync( query=text, images=images, text_files=files )
                    break
                except gpt.g4f.errors.ResponseStatusError as e:
                    if "500" in str(e):
                        await bot.send_message(message.chat.id, "Ваша текущая конфигурация не подходит под вашу задачу, попробуйте поменять модель")
                        return
                except Exception as e:
                    print(f"Error adding message: {e}")
                    await asyncio.sleep(time)
                    time *= 1.5

            user_data["messages"].append((text, answer))
            users.set(uid, user_data)
            
            parsed_ans = xml.parse_xml_like(answer)

            if parsed_ans.get("image", None) is not None:
                img_url = await chat.imageGenerationAsync(
                    prompt=parsed_ans["image"], 
                    model=user_data["img_model"], 
                    resolution=(1024, 1024), 
                    filename=f"./runtime/images/answer_img_{token}.png"
                )
                await bot.send_photo(message.chat.id, img_url, caption=parsed_ans["answer"], parse_mode=None)
            else:
                await message.reply(parsed_ans["answer"], parse_mode=None)

async def main() -> None:
    global bot
    bot = Bot(token=tgconf["API_KEY"], default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
    print("Started")
    await dp.start_polling(bot)
    
    users.close()

if __name__ == "__main__":
    asyncio.run(main())