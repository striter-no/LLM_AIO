from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile
from aiogram.types import Message
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram import types

from pydub import AudioSegment

import src.sql_db as sql_db
import src.xml_utils as xml
import src.gpt as gpt
import src.gpt_utils as gpt_utils
import src.reco_voice as rv
import src.openai_tts as tts

import datetime as dtm
import time as modtime
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

def ogg_to_wav(filename: str) -> str:
    sound = AudioSegment.from_file(filename, format="ogg")
    sound.export(f"{filename[:-4]}.wav", format="wav")
    os.remove(filename)
    return f"{filename[:-4]}.wav"

def md2esc(target: str) -> str:
    simbs = ['(', ')', '#', '+', '-', '=', '{', '}', '.', '!' ]
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

async def gpt_message_bot_proceed(token: str, voice_out: bool, uid: str, message: Message, text: str, images: list[str], files: list[str], retry: bool = False):
    if message is None:
        return
    
    chat_id = message.chat.id if isinstance(message, Message) else message
    message_id = message.message_id if isinstance(message, Message) else None

    message_todel = await bot.send_message(chat_id, "В процессе ответа...") if isinstance(message, Message) else None
    if users.get(uid).get("voice", None) is None:
        data = users.get(uid)
        data["voice"] = "ash"
        users.set(uid, data)

    user_data = users.get(uid)
    chat = gpt.Chat( provider=MAIN_PROVIDER, model=user_data["base_model"])
    chat.systemQuery = sys_prompt
    chat.messages = user_data["messages"]
    
    if len(user_data["messages"]) == 0:
        retry = False
    
    if retry:
        text = user_data["messages"][-1][0]
        del user_data["messages"][-1]

    time = 1
    while True:
        try:
            answer = await chat.addMessageAsync( query=text, images=images, text_files=files )
            break
        except gpt.g4f.errors.ResponseStatusError as e:
            print(e)
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
    if answer.count("<answer>") == 0:
        answer = "<answer>" + "\n" + answer

    if answer.count("</answer>") == 0:
        answer += "\n</answer>"

    parsed_ans = xml.parse_xml_like(answer)
    if parsed_ans.get('answer', False) == False:
        parsed_ans["answer"] = "Нет ответа"
    if parsed_ans.get('resolution', False) == False:
        parsed_ans["resolution"] = "2000 2000"

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
                    await bot.send_message(chat_id, "Не удалось выполнить генерацию. Попробуйте еще раз")
        repl = f"**>{md2esc(parsed_ans["image"]).replace('\n', '\n>')}||\n{md2esc(parsed_ans["answer"])}"
        try:
            if message_todel: await bot.delete_message(chat_id, message_todel.message_id)
            await bot.send_photo(chat_id, img_url, caption=md2esc(repl), parse_mode = ParseMode.MARKDOWN_V2)
            if parsed_ans.get('file_img', False) != False:
                print("File img:", parsed_ans.get('file_img', False))
                imgfile = FSInputFile(f"./runtime/images/answer_img_{token}.png", filename="Generated Image")
                await bot.send_document(chat_id, imgfile)
        except Exception as e:
            if message_todel: await bot.delete_message(chat_id, message_todel.message_id)
            print(e)
            if "caption is too long" in str(e):
                await bot.send_photo(chat_id, img_url)
                if parsed_ans.get('file_img', False) != False:
                    imgfile = FSInputFile(f"./runtime/images/answer_img_{token}.png", filename="Generated Image")
                    await bot.send_document(chat_id, imgfile)
                await bot.send_message(chat_id, md2esc(repl), parse_mode = ParseMode.MARKDOWN_V2)
                print(f"Error sending image: {e}")
            elif "parse" in str(e):
                await bot.send_photo(chat_id, img_url)
                await bot.send_message(chat_id, f"Image prompt:\n{parsed_ans["image"]}\n\nAnswer: {parsed_ans["answer"]}")
            else:
                print(img_url)
                await bot.send_message(chat_id, "Не удалось выполнить генерацию\\. Попробуйте еще раз", parse_mode=ParseMode.MARKDOWN_V2)
        os.remove(f"./runtime/images/answer_img_{token}.png")
    else:
        if message_todel: await bot.delete_message(chat_id, message_todel.message_id)
        if (not voice_out) and (parsed_ans.get("voice_out", False) == False):
            try:
                await bot.send_message(chat_id, md2esc(parsed_ans["answer"]), parse_mode=ParseMode.MARKDOWN_V2)
            except:
                try:
                    await bot.send_message(chat_id, parsed_ans["answer"], parse_mode=ParseMode.MARKDOWN)
                except:
                    await bot.send_message(chat_id, parsed_ans["answer"])
        else:
            try:
                tts.gpt_tts(
                    "Разговаривай натурально на русском языке (без какого-либо акцента). Скажи в ответ этот текст: " + parsed_ans["answer"],
                    user_data["voice"],
                    f"./runtime/voice_response_{token}.mp3"
                )
                await bot.send_voice(
                    chat_id, FSInputFile(f"./runtime/voice_response_{token}.mp3")
                )
                if user_data["voice_descript"]:
                    out_str = f"**>{md2esc(parsed_ans["answer"]).replace('\n', '\n>')} ||"
                    print(out_str)
                    await bot.send_message(chat_id, out_str, parse_mode=ParseMode.MARKDOWN_V2)
                os.remove(f"./runtime/voice_response_{token}.mp3")
            except Exception as e:
                print(f"Error while sending voice/synthesis of the voice response: {e}")
                try:
                    if message_id: await message.reply(md2esc(parsed_ans["answer"]), parse_mode=ParseMode.MARKDOWN_V2)
                    else: await bot.send_message(chat_id, md2esc(parsed_ans["answer"]), parse_mode=ParseMode.MARKDOWN_V2)
                except:
                    try:
                        if message_id: await message.reply(parsed_ans["answer"], parse_mode=ParseMode.MARKDOWN)
                        else: await bot.send_message(chat_id, parsed_ans["answer"], parse_mode=ParseMode.MARKDOWN)
                    except:
                        if message_id: await message.reply(parsed_ans["answer"])
                        else: await bot.send_message(chat_id, parsed_ans["answer"])

@dp.message()
async def handle_message(message: Message) -> None:
    global bot

    uid = message.from_user.id
    text = message.text or message.caption or "Запрос не предоставлен..."
    voice_out = False
    token = str(uuid.uuid4())
    
    if users.get(uid) is None:
        users.set(uid, {"base_model": "gpt-4o-mini", "img_model": "flux", "messages": [], "voice": "ash", "voice_descript": False, "last_activity": modtime.time(), "user_id": message.from_user.id, "remind_time": "6"})

    if users.get(uid).get("voice_descript", None) is None:
        data = users.get(uid)
        data["voice_descript"] = False
        users.set(uid, data)
    
    if users.get(uid).get("last_activity", None) is None:
        data = users.get(uid)
        data["last_activity"] = modtime.time()
        users.set(uid, data)
    
    if users.get(uid).get("user_id", None) is None:
        data = users.get(uid)
        data["user_id"] = message.from_user.id
        users.set(uid, data)
    
    if users.get(uid).get("remind_time", None) is None:
        data = users.get(uid)
        data["remind_time"] = "6"
        users.set(uid, data)
    
    images = []
    files  = []
    file_id, file_name, extension = None, None, None

    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
        extension = "text"
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_name = f"{file_id}.jpg"
        extension = "img"
    elif message.voice:
        file_id = message.voice.file_id
        file_name = f"{file_id}.ogg"
        extension = "voice"
        voice_out = True
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

        if extension == "text":
            if (check_file(fpath)):
                files.append(fpath)
        elif extension == "img":
            images.append(fpath)
        elif extension == "voice":
            reco = rv.SpeechRecognition( "ru-RU", None )
            text = reco.recognize_audiofile(ogg_to_wav(fpath))
            user_data = users.get(uid)
            if user_data["voice_descript"]:
                await message.reply(f"**>{md2esc(text).replace('\n', '\n>')}||", parse_mode=ParseMode.MARKDOWN_V2)
            print(text)

    if text:
        if text[0] == '/':
            command = text[1:]
            opcode = command.split(' ')[0]

            if not (opcode in ["voicedesc", "remindt"]):
                if opcode in msgsconf["commands"]:
                    await message.reply(msgsconf["commands"][opcode], parse_mode=ParseMode.MARKDOWN)
                else:
                    await message.reply(msgsconf["commands"]["unknown"], parse_mode=ParseMode.MARKDOWN)

            if opcode == "remindt":
                if len(command.split()) < 2:
                    await bot.send_message(message.chat.id, "Недостаточно аргументов, вам нужно указать время напоминания")
                
                remind_time = command.split(' ')[1]
                user_data = users.get(uid)
                user_data["remind_time"] = remind_time
                users.set(uid, user_data)

                await message.reply(f"Напоминание установлено на {remind_time} часов", parse_mode=ParseMode.MARKDOWN)

            if opcode == "voicedesc":
                user_data = users.get(uid)
                user_data["voice_descript"] = not user_data["voice_descript"]
                users.set(uid, user_data)
                await message.reply(f"Расшифровка голосовых: {'включено' if user_data['voice_descript'] else 'выключено'}", parse_mode=ParseMode.MARKDOWN)

            if opcode == "clear":
                user_data = users.get(uid)
                user_data["messages"] = []
                users.set(uid, user_data)

            if opcode == "voice":
                
                if len(command.split()) < 2:
                    await bot.send_message(message.chat.id, "Недостаточно аргументов, вам нужно указать голосовую модель (/voices для списка)")
                    return

                user_data = users.get(uid)
                if not command.split(' ')[1] in tts.voices:
                    await bot.send_message(message.chat.id, f"Неверное имя голосового модели: {command.split(' ')[1]}")
                    return
                user_data["voice"] = command.split(' ')[1]
                users.set(uid, user_data)

            if opcode == "model":
                if len(command.split(' ')) < 2:
                    await bot.send_message(message.chat.id, "Недостаточно аргументов, вам нужно указать модель")
                    return
                
                model_name = command.split(' ')[1]

                if model_name in gpt.models_stock.ModelUtils.convert and not (model_name in gpt.image_models):
                    user_data = users.get(uid)
                    user_data["base_model"] = model_name
                    users.set(uid, user_data)
                    await bot.send_message(message.chat.id, f"Базовая модель установлена на {model_name}")
                elif model_name in gpt.image_models:
                    await bot.send_message(message.chat.id, f"Базовая модель не может быть установлена на {model_name}, т.к. это модель для генерации изображений")
                else:
                    await bot.send_message(message.chat.id, f"Нет модели с таким именем: {model_name}")
            
            if opcode == "imgm":
                if len(command.split(' ')) < 2:
                    await bot.send_message(message.chat.id, "Недостаточно аргументов, вам нужно указать модель")
                    return
                

                model_name = command.split(' ')[1]
                if model_name in gpt.image_models:
                    user_data = users.get(uid)
                    user_data["img_model"] = model_name
                    users.set(uid, user_data)
                    await bot.send_message(message.chat.id, f"Базовая модель установлена на {model_name}")
                else:
                    await bot.send_message(message.chat.id, f"Нет модели с таким именем: {model_name}")

            if opcode == "stats":
                
                user_data = users.get(uid)
                await bot.send_message(message.chat.id, f"Ваша статистика:\n\nОсновная (текстовая) модель: {user_data["base_model"]}\nМодель для изображений: {user_data["img_model"]}\nКоличество сообщений: {len(user_data["messages"])}")

            if opcode == "retry":
                try:
                    await gpt_message_bot_proceed(
                        token, voice_out, uid, message, text, images, files, retry = True
                    )
                except Exception as e:
                    print(f"Error in retry: {e}")
                    await bot.send_message(message.chat.id, f"Произошла ошибка при повторной попытке. Можете попробовать еще раз или очистить контекст и попробовать еще раз.")
                    return
        else:
            try:
                await gpt_message_bot_proceed(
                    token, voice_out, uid, message, text, images, files, retry = False
                )
            except Exception as e:
                print(f"Error while generating answer: {e}")
                await bot.send_message(message.chat.id, f"Произошла ошибка при генерации. Можете попробовать еще раз или очистить контекст и попробовать еще раз.")
                return

async def update_state():
    while True:
        with open("./runtime/aiogram_main.txt", "w") as f:
            f.write(f"{modtime.time()}")
        await asyncio.sleep(5)

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

async def check_old_users():
    while True:
        non_old = []
        for uid in users.all():
            user_data = users.get(uid)
            if user_data and not (None in (user_data.get("last_activity", None), user_data.get("remind_time", None))):
                # print(f"Checking user {uid}: {user_data["last_activity"]}")
                if modtime.time() - user_data["last_activity"] > 60 * 60 * float(user_data["remind_time"]):
                    print(f"Old user {uid}: {user_data["last_activity"]}")
                    # try:
                    await gpt_message_bot_proceed(
                        token = str(uuid.uuid4()), 
                        voice_out = False, 
                        uid = user_data.get("user_id", None),
                        message = user_data.get("user_id", None),
                        images = [],
                        files = [],
                        retry = False,
                        text = "Напиши какой-нибудь краткий вопрос или предложение вне контекста, как будто ты пишешь в давнюю переписку снова"
                    )
                    non_old.append(uid)
                    
                    # except Exception as e:
                    #     print(f"Error in old user cleanup: {e} ({uid} {user_data["user_id"]})")
                    # await bot.send_message(user_data["user_id"], )
            else:
                if user_data.get("last_activity", None) is None:
                    data = users.get(uid)
                    data["last_activity"] = modtime.time()
                    users.set(uid, data)
                
                if users.get(uid).get("remind_time", None) is None:
                    data = users.get(uid)
                    data["remind_time"] = "6"
                    users.set(uid, data)

        for uid in non_old:
            data = users.get(uid)
            data["last_activity"] = modtime.time()
            users.set(uid, data)

        await asyncio.sleep(60)

async def on_startup():
    asyncio.create_task(check_old_users())
    asyncio.create_task(update_state())

async def main() -> None:
    global bot
    await on_startup()
    bot = Bot(token=tgconf["API_KEY"], default=DefaultBotProperties(link_preview_is_disabled=True))
    print("Started")
    await dp.start_polling(bot)
    
    users.close()

if __name__ == "__main__":
    asyncio.run(main())