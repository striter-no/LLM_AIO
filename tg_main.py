from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile
from aiogram.types import Message
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram import types

import src.sql_db as sql_db
import src.xml_utils as xml
import src.gpt as gpt
import src.gpt_utils as gpt_utils

import json as jn
import asyncio
import random
import uuid
import os

dp = Dispatcher()
bot: Bot = None;

tgconf = jn.load(open("./configs/dev/bot_cfg.json"))
gptconf = jn.load(open("./configs/system_prompt.json"))
sys_prompt = gpt_utils.compile_system_request(gptconf)

msgsconf = jn.load(open("./configs/messages.json"))

users = sql_db.DataBase("./databases/users.sqllite")

MAIN_PROVIDER = gpt.provider_stock.PollinationsAI

def md2esc(target: str) -> str:
    simbs = ['(', ')', '~', '#', '+', '-', '=', '{', '}', '.', '!' ]
    for i in simbs:
        target = target.replace(i, f'\\{i}')
    return target

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
    text = message.text or message.caption or "Запрос не предоставлен..."
    token = str(uuid.uuid4())
    
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
                await message.reply(msgsconf["commands"][opcode], parse_mode=ParseMode.MARKDOWN)
            else:
                await message.reply(msgsconf["commands"]["unknown"], parse_mode=ParseMode.MARKDOWN)

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
                    users.set(uid, {"base_model": "gpt-4o-mini", "img_model": "flux", "messages": []})

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
                    users.set(uid, {"base_model": "gpt-4o-mini", "img_model": "flux", "messages": []})

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
                    users.set(uid, {"base_model": "gpt-4o-mini", "img_model": "flux", "messages": []})
                
                user_data = users.get(uid)
                await bot.send_message(message.chat.id, f"Ваша статистика:\n\nОсновная (текстовая) модель: {user_data["base_model"]}\nМодель для изображений: {user_data["img_model"]}\nКоличество сообщений: {len(user_data["messages"])}")

        else:
            message_todel = await bot.send_message(message.chat.id, "В процессе ответа...")
            if users.get(uid) is None:
                users.set(uid, {"base_model": "gpt-4o-mini", "img_model": "flux", "messages": []})
            
            user_data = users.get(uid)
            chat = gpt.Chat( provider=MAIN_PROVIDER, model=user_data["base_model"])
            chat.systemQuery = sys_prompt
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
            
            print(answer)
            parsed_ans = xml.parse_xml_like(answer)

            if parsed_ans.get("image", None) is not None:
                print(parsed_ans)
                print(parsed_ans["resolution"].split())
                time, tries = 1, 0
                while True:
                    try:
                        img_url = await chat.imageGenerationAsync(
                            prompt=parsed_ans["image"], 
                            model=user_data["img_model"], 
                            resolution=(int(parsed_ans["resolution"].split()[0]), int(parsed_ans["resolution"].split()[1])),
                            specified_provider=gpt.provider_stock.PollinationsImage,
                            filename=f"./runtime/images/answer_img_{token}.png" 
                        )
                        break
                    except Exception as e:
                        print(f"Error generating image: {e}")
                        await asyncio.sleep(time)
                        time *= 1.5
                        tries += 1
                        if tries >= 5:
                            await bot.send_message(message.chat.id, "Не удалось выполнить генерацию. Попробуйте еще раз")
                repl = f"**>{parsed_ans["image"]}||\n{parsed_ans["answer"]}"
                try:
                    await bot.send_photo(message.chat.id, img_url, caption=md2esc(repl), parse_mode = ParseMode.MARKDOWN_V2)
                    if parsed_ans.get('file_img', False) != False:
                        imgfile = FSInputFile(f"./runtime/images/answer_img_{token}.png", filename="Generated Image")
                        await bot.send_document(message.chat.id, imgfile)
                except Exception as e:
                    await bot.delete_message(message.chat.id, message_todel.message_id)
                    print(e)
                    if "caption is too long" in str(e):
                        await bot.send_photo(message.chat.id, img_url)
                        if not parsed_ans.get('file_img', False):
                            imgfile = FSInputFile(f"./runtime/images/answer_img_{token}.png", filename="Generated Image")
                            await bot.send_document(message.chat.id, imgfile)
                        await bot.send_message(message.chat.id, md2esc(repl), parse_mode = ParseMode.MARKDOWN_V2)
                        print(f"Error sending image: {e}")
                    elif "parse" in str(e):
                        await bot.send_photo(message.chat.id, img_url)
                        await bot.send_message(message.chat.id, f"Image prompt:\n{parsed_ans["image"]}\n\nAnswer: {parsed_ans["answer"]}")
                    else:
                        print(img_url)
                        await bot.send_message(message.chat.id, "Не удалось выполнить генерацию\\. Попробуйте еще раз", parse_mode=ParseMode.MARKDOWN_V2)
                os.remove(f"./runtime/images/answer_img_{token}.png")
            else:
                await bot.delete_message(message.chat.id, message_todel.message_id)
                try:
                    await message.reply(md2esc(parsed_ans["answer"]), parse_mode=ParseMode.MARKDOWN_V2)
                except:
                    try:
                        await message.reply(parsed_ans["answer"], parse_mode=ParseMode.MARKDOWN)
                    except:
                        await message.reply(parsed_ans["answer"])
            
            

@dp.inline_query()
async def send_photo(inline_query: types.InlineQuery):
    # Пример URL изображения
    text = inline_query.query
    uid = inline_query.from_user.id
    token = random.randint(0, 10000)
    text_res = "Internal error occurred"

    if users.get(uid) is None:
        users.set(uid, {"base_model": "gpt-4o-mini", "img_model": "flux", "messages": []})
    
    user_data = users.get(uid)
    chat = gpt.Chat( provider=MAIN_PROVIDER, model=user_data["base_model"])
    chat.systemQuery = gptconf["general"]
    chat.messages = user_data["messages"]
    
    text = "Сгенерируй изображение по такому запросу: " + text
    print(text)

    time = 1
    while True:
        try:
            answer = await chat.addMessageAsync( query=text )
            break
        except gpt.g4f.errors.ResponseStatusError as e:
            if "500" in str(e):
                print(f"Error 500 response")
                # await bot.send_message(message.chat.id, "Ваша текущая конфигурация не подходит под вашу задачу, попробуйте поменять модель")
                return
        except Exception as e:
            print(f"Error adding message: {e}")
            
            await asyncio.sleep(time)
            time *= 1.5

    user_data["messages"].append((text, answer))
    users.set(uid, user_data)
    
    print(answer)

    parsed_ans = xml.parse_xml_like(answer)
    if parsed_ans.get("image", None):
        img_url = await chat.imageGenerationAsync(
            prompt=parsed_ans["image"], 
            model=user_data["img_model"], 
            resolution=(2000, 2000), 
            filename=f"./runtime/images/inline_result.png"
        )
        repl = f"**>{parsed_ans["image"]}||"
        print(f"Generated:\n{repl}\n\n{img_url}\n{str(uuid.uuid4())}")
        results = [
            types.InlineQueryResultPhoto(
                id=str(uuid.uuid4()),  # Уникальный ID (до 64 байт)
                photo_url=img_url,
                thumbnail_url=img_url,
                caption=md2esc(repl),
                parse_mode=ParseMode.MARKDOWN_V2,
                photo_width=2000,  # Добавьте ширину
                photo_height=2000
            )
        ]
        try:
            await bot.answer_inline_query(inline_query.id, results=results, cache_time=300, is_personal=True)
        except Exception as e:
            print(f"Error sending inline query: {e}")

    

async def main() -> None:
    global bot
    bot = Bot(token=tgconf["API_KEY"], default=DefaultBotProperties())
    print("Started")
    await dp.start_polling(bot)
    
    users.close()

if __name__ == "__main__":
    asyncio.run(main())