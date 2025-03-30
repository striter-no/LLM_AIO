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
from typing import Any

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
import enum
import uuid
import os, re

class Utils:
    @staticmethod
    def ogg_to_wav(filename: str) -> str:
        sound = AudioSegment.from_file(filename, format="ogg")
        sound.export(f"{filename[:-4]}.wav", format="wav")
        os.remove(filename)
        return f"{filename[:-4]}.wav"

    @staticmethod
    def md2esc(target: str) -> str:
        simbs = ['(', ')', '#', '+', '-', '=', '{', '}', '.', '!', '<', '>', '|']
        # Create a regex pattern to match characters that need escaping
        pattern = r'(?<!\\)(' + '|'.join(map(re.escape, simbs)) + ')'
        # Replace with escaped characters
        return re.sub(pattern, r'\\\1', target)

    @staticmethod
    def check_file(path: str) -> bool:
        try:
            with open(path, "r") as f:
                f.read()
            return True
        except Exception as e:
            print(f"Error while checking file {path}: {str(e)}")
            return False

class Configs:
    def __init__(
        self, 
        bot_config: str,
        gpt_config: str,
        messages_config: str,
        user_database: str,
        exclude_conf_answ: list[str],
        main_text_provider: gpt.provider_stock,
        main_img_provider: gpt.provider_stock,
    ):
        self.telegram = jn.load(open(bot_config, 'r'))
        self.gpt = jn.load(open(gpt_config, 'r'))
        self.messages = jn.load(open(messages_config, 'r'))

        self.text_provider = main_text_provider
        self.img_provider = main_img_provider

        self.exclude_conf_answ = exclude_conf_answ
        self.users = sql_db.DataBase(user_database)

        self.enhances = self.gpt["enhances"]
        self.side_prompts = self.gpt["side-sys-prompts"]
        self.system_prompt = gpt_utils.compile_system_request(self.gpt)

class UserDatabase:
    def __init__(self, configs: Configs):
        self.configs = configs
    
    def close(self):
        self.configs.users.close()

    def default_set(self, uid: int):
        self.configs.users.set(uid, {
            "base_model": "gpt-4o-mini", 
            "img_model": "flux", 
            "messages": [], 
            "voice": "ash", 
            "voice_descript": False, 
            "last_activity": modtime.time(),
            "remind_time": "6"
        })
    
    def ensure(self, uid: int, key: str, value: Any):
        if self.configs.users.get(uid) is None:
            self.default_set(uid)
        
        if self.configs.users.get(uid).get(key, None) is None:
            data = self.configs.users.get(uid)
            data[key] = value
            self.configs.users.set(uid, data)
    
    def exists(self, uid: str):
        return self.configs.users.get(uid) is not None

    def get(self, uid: str, key: str):
        if self.configs.users.get(uid) is None:
            return None
        
        return self.configs.users.get(uid).get(key, None)
    
    def data(self, uid: str):
        return self.configs.users.get(uid)

    def set(self, uid: int, key: str, value: Any):
        if self.configs.users.get(uid) is None:
            return False

        data = self.configs.users.get(uid)
        data[key] = value
        self.configs.users.set(uid, data)
        
        return True

class GPTApp:
    def __init__(self, text_model: str, img_model: str, configs: Configs, userdb: UserDatabase):
        self.configs = configs
        self.text_model = text_model
        self.img_model = img_model
        self.userdb = userdb

        self.chat = gpt.Chat(
            model=self.text_model,
            provider=configs.text_provider
        )

        self.chat.systemQuery = self.configs.system_prompt
    
    def load_messages(self, uid: int):
        self.chat.messages = self.userdb.get(uid, "messages")
    
    async def text_query(self, query: str, images: list[str], files: list[str]) -> tuple[bool, str]:
        time = 1
        while True:
            try:
                answer = await self.chat.addMessageAsync( query=query, images=images, text_files=files )
                return True, answer
            except gpt.g4f.errors.ResponseStatusError as e:
                if "500" in str(e):
                    return False, "Ваша текущая конфигурация не подходит под вашу задачу, попробуйте поменять модель"
            except Exception as e:
                print(f"Error adding message: {e}")
                await asyncio.sleep(time)
                time *= 1.5

    async def image_query(self, query: str, width: int, height: int, filename: str, max_retries: int = 5) -> tuple[bool, str]:
        time, tries = 1, 0
        while True:
            try:
                img_url = await self.chat.imageGenerationAsync(
                    prompt=query, 
                    model=self.img_model, 
                    resolution=(width, height),
                    specified_provider=self.configs.img_provider,
                    filename=filename
                )
                return True, img_url
                break
            except Exception as e:
                print(f"Error generating image: {e}")
                await asyncio.sleep(time)
                time *= 1.5
                tries += 1
                if tries >= max_retries:
                    return False, "Не удалось выполнить генерацию. Попробуйте еще раз"

    def voice_query(self, query: str, voice: str, filepath: str):
        tts.gpt_tts("Разговаривай натурально на русском языке (без какого-либо акцента). Скажи в ответ этот текст: " + query, voice, filepath )

    def parse_answer(self, answer: str) -> dict:
        if answer.count("<answer>") == 0:
            answer = "<answer>" + "\n" + answer
        if answer.count("</answer>") == 0:
            answer += "\n</answer>"

        parsed_ans = xml.parse_xml_like(answer)

        if parsed_ans.get('answer', False) == False:
            parsed_ans["answer"] = "Нет ответа"
        if parsed_ans.get('image', False) != False and parsed_ans.get('resolution', False) == False:
            parsed_ans["resolution"] = "2000 2000"
        
        return parsed_ans
    
class TelegramApp:
    def __init__(self, configs: Configs, userdb: UserDatabase, status_file: str):
        self.configs = configs
        self.userdb = userdb
        self.status_file = status_file

        self.dp = Dispatcher()
        self.bot = Bot(
            token=self.configs.telegram["API_KEY"], 
            default=DefaultBotProperties(link_preview_is_disabled=True)
        )

    async def update_state(self):
        while True:
            with open(self.status_file, "w") as f:
                f.write(f"{modtime.time()}")
            await asyncio.sleep(5)

    async def __on_startup(self):
        asyncio.create_task(self.check_old_users())
        asyncio.create_task(self.update_state())

    async def start(self):
        await self.__on_startup()

        @self.dp.message()
        async def callback(message: Message):
            await self.message_handler(message)

        print(f"Starting...")
        await self.dp.start_polling(self.bot)
        self.userdb.close()
    
    async def download_doc(self, message: Message) -> tuple[bool, str, str]:
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
        elif message.document is None and message.photo is None:
            return False, "No content", "None"
        else:
            return False, "Неизвестный формат файла, поддерживаются только текстовые файлы и изображения", "None"
        
        dfile = await self.bot.get_file(file_id)
        api_path = dfile.file_path
        fpath = f"./runtime/userdata/{file_name}"
        await self.bot.download_file(api_path, fpath)

        return True, fpath, extension

    async def bot_voice(self, chat_id: int, pathfile: str, uid: int, text_ver: str | None = None) -> None:
        await self.bot.send_voice(
            chat_id, FSInputFile(pathfile)
        )
        if self.userdb.get(uid, "voice_descript") and text_ver:
            out_str = f"**>{Utils.md2esc(text_ver).replace('\n', '\n>')} ||"
            await self.bot_send_text(chat_id, out_str)

    async def bot_image(self, chat_id: int, caption: str, pathfile: str | None = None, imgurl: str | None = None) -> None:
        try:
            await self.bot.send_photo(
                chat_id,
                FSInputFile(pathfile) if pathfile else imgurl,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except Exception as e:
            if "caption is too long" in str(e):
                await self.bot.send_photo(chat_id, FSInputFile(pathfile) if pathfile else imgurl)
                await self.bot_send_text(chat_id, caption)

    async def bot_send_text(self, chat_id: int, text: str) -> None:
        if not (text and len(text) > 0):
            return
        try:
            await self.bot.send_message(chat_id, text, parse_mode=ParseMode.MARKDOWN_V2)
        except Exception as ex:
            print(f"Error sending message in MD2 format: {ex}")
            try:
                await self.bot.send_message(chat_id, text, parse_mode=ParseMode.MARKDOWN)
            except Exception as ex2:
                print(f"Error sending message in MD format: {ex2}")
                await self.bot.send_message(chat_id, text)

    async def bot_document(self, chat_id, documentpath: str, docname: str, caption: str | None = None):
        try:
            await self.bot.send_document(
                chat_id,
                FSInputFile(documentpath),
                filename=docname,
                caption=caption
            )
        except Exception as e:
            if "caption is too long" in str(e):
                await self.bot.send_document(chat_id, FSInputFile(documentpath), filename=docname)
                await self.bot_send_text(chat_id, caption)

    async def proceed_commands(self, uid: int, text: str) -> None:
        command = text[1:]
        opcode = command.split(' ')[0]
        args = command.split(' ')[1:]
        out = ""

        if not (opcode in self.configs.exclude_conf_answ):
            if opcode in self.configs.messages["commands"]:
                out += self.configs.messages["commands"][opcode] + '\n\n'
            else:
                return self.configs.messages["commands"]["unknown"]

        if opcode == "remindt":
            if len(args) < 1:
                return out + "Недостаточно аргументов, вам нужно указать время напоминания"
            
            self.userdb.set(uid, "remind_time", args[0])
            return out + f"Напоминание установлено на {args[0]} часов"

        elif opcode == "voicedesc":
            self.userdb.set(uid, "voice_descript", not self.userdb.get(uid, "voice_descript"))
            return out + f"Расшифровка голосовых: {'включено' if user_data['voice_descript'] else 'выключено'}"

        elif opcode == "clear":
            self.userdb.set(uid, "messages", [])
            return out

        elif opcode == "voice":
            if len(args) < 1:
                return out + "Недостаточно аргументов, вам нужно указать голосовую модель (`/voices` для списка)"
            
            if not args[0] in tts.voices: return out + f"Неверное имя голосового модели: {args[0]}"
            self.userdb.set(uid, 'voice', args[0])

            return out

        elif opcode == "model":
            if len(args) < 1:
                return "Недостаточно аргументов, вам нужно указать модель"
            
            model_name = args[0]

            if model_name in gpt.models_stock.ModelUtils.convert and not (model_name in gpt.image_models):
                self.userdb.set(uid, "base_model", model_name)
                return out + f"Базовая модель установлена на {model_name}"
            elif model_name in gpt.image_models:
                return out + f"Базовая модель не может быть установлена на {model_name}, т.к. это модель для генерации изображений"
            else:
                return out + f"Нет модели с таким именем: {model_name}"
        
        elif opcode == "imgm":
            if len(args) < 1:
                return "Недостаточно аргументов, вам нужно указать модель"
        
            model_name = args[0]
            if model_name in gpt.image_models:
                self.userdb.set(uid, "img_model", model_name)
                return out + f"Базовая модель установлена на {model_name}"
            else:
                return out + f"Нет модели с таким именем: {model_name}"

        elif opcode == "stats":
            user_data = self.userdb.data(uid)
            return out + f"Ваша статистика:\n\nОсновная (текстовая) модель: {user_data["base_model"]}\nМодель для изображений: {user_data["img_model"]}\nКоличество сообщений: {len(user_data["messages"])}"

        elif opcode == "retry":
            try:
                return "gpt:retry"
            except Exception as e:
                print(f"Error in retry: {e}")
                return out + f"Произошла ошибка при повторной попытке. Можете попробовать еще раз или очистить контекст и попробовать еще раз."

        return out

    async def side_ask(self, uid: int, request: str, system_prompt: str, req_type: str = "text", images: list[str] = [], files: list[str] = []) -> tuple[bool, str]:
        gptapp = GPTApp(
            text_model = self.userdb.get(uid, 'base_model'),
            img_model = self.userdb.get(uid, 'img_model'),
            configs = self.configs,
            userdb = self.userdb
        )
        gptapp.load_messages(uid)
        gptapp.chat.setSystemQuery(system_prompt)

        if req_type == "text":
            return await gptapp.text_query(request, images, files)

    async def enhance_ask(self, uid: int, prompt: str, enhance_type: str, chat_id: int, gptapp: GPTApp):
        print(f"[gpt_section][enhance] Enhanceing {enhance_type}")
        sys_prompt = gpt_utils.compile_system_request(
            self.configs.gpt, ["answer"]
        ) + '\n\n' + self.configs.side_prompts["enhance"]

        # print(f"[gpt_section][enhance] Side-System prompt:\n {'='*20}\n{sys_prompt}\n{'='*20}")
        print(f"[gpt_section][enhance] Side-System prompt generated...")

        side_status, raw_side = await self.side_ask(
            uid,
            self.configs.enhances[enhance_type].replace("[PLACE HERE QUESTION]", prompt),
            sys_prompt,
            req_type = "text"
        )
        if not side_status:
            print(f"[{uid}][gpt_section][{enhance_type}] Error while enhancing {enhance_type}")
            await self.bot_send_text(chat_id = chat_id, text = "Произошла ошибка при улучшении изображения. Попробуйте еще раз")
            return
        raw_parsed = gptapp.parse_answer(raw_side)
        # print(raw_side)
        # print(f"[gpt_section][enhance] Parsed answer: {raw_parsed}")
        print(f"[gpt_section][enhance] Parsed answer made")
        answer = raw_parsed["answer"]
        return answer, raw_parsed

    async def gpt_answer(self, token: str, uid: int, chat_id: int, request: str, files: list[str], imgs: list[str]) -> None:
        pre_answer = ""
        gptapp = GPTApp(
            text_model = self.userdb.get(uid, 'base_model'),
            img_model = self.userdb.get(uid, 'img_model'),
            configs = self.configs,
            userdb = self.userdb
        )
        gptapp.load_messages(uid)
        print(f"[{uid}][gpt_section] Loaded messages ({len(gptapp.chat.messages)})")
        print(f"[{uid}][gpt_section] Starting first text request: {request}\n")
        message_todel = await self.bot.send_message(chat_id, "В процессе ответа...")
        status, raw_answer = await gptapp.text_query( query = request, files = files, images = imgs )
        if not status:
            print(f"[{uid}][gpt_section][error] Error while querying")
            await self.bot_send_text(chat_id, text = "Произошла ошибка во время генерации текста. Попробуйте еще раз")
            return
        
        try:
            print(f"[{uid}][gpt_section][try] Parsing response")
            parsed = gptapp.parse_answer(raw_answer)
            print(f"[{uid}][gpt_section][success] Parsed response: {parsed}")
        except Exception as e:
            print(f"[{uid}][gpt_section][except] Error in parsing answer: {e}\n============\n\n{raw_answer}\n\n============")
            await self.bot_send_text(chat_id = chat_id, text = "Произошла ошибка при парсинге ответа. Попробуйте еще раз")
            return
        

        if parsed.get("thinking", None) is not None or parsed.get("enhance", None) is not None and parsed.get("enhance", None) == "thinking":
            raw_answer, r_parsed = await self.enhance_ask(uid, request, "thinking", chat_id, gptapp)

            for chain in gpt_utils.get_chains(r_parsed["thinking"]):
                pre_answer += chain["title"] + '\n\n' + chain["content"] + '\n--------------\n'

        print(f"[{uid}][gpt_section] Adding new message to the context")
        messages = self.userdb.get(uid, "messages")
        messages.append((request, parsed["answer"]))
        self.userdb.set(uid, "messages", messages)

        

        if parsed.get("image", None) is not None:
            width, height = parsed.get("resolution").split(' ')
            print(f"[{uid}][gpt_section][image] Generating image: {width}x{height}")
            prompt = parsed.get("image")

            if parsed.get("enhance", None) is not None:
                prompt = await self.enhance_ask(uid, prompt, "image", chat_id, gptapp)

            await self.bot.edit_message_text(chat_id = chat_id, message_id = message_todel.message_id, text="Генерация изображения...")
            print(f"[{uid}][gpt_section][query] Asking for generation")
            status, imgurl = await gptapp.image_query( 
                prompt, 
                int(width), int(height), 
                f"./runtime/images/answer_img_{token}.jpg"
            )
            print(f"[{uid}][gpt_section][image] Ready")
            repl = f"**>{Utils.md2esc(prompt).replace('\n', '\n>')}||\n{Utils.md2esc(parsed["answer"])}"
            if status:
                print(f"[{uid}][gpt_section][image] Successfully")
                await self.bot_image(chat_id = chat_id, caption = repl, imgurl = imgurl)
                if parsed.get("file_img", False) != False:
                    print(f"[{uid}][gpt_section][message] Sending file of the image")
                    await self.bot_document(chat_id = chat_id, documentpath = imgurl, docname = f"Generated_Image.jpg")

            else: 
                print(f"[{uid}][gpt_section][image] Failed to create")
                await self.bot_send_text(chat_id = chat_id, text = "Произошла ошибка во время генерации изображения. Попробуйте еще раз")
        else:
            print(f"[{uid}][gpt_section][text] Text answer")
            if parsed.get("voice_out", False) != False:
                print(f"[{uid}][gpt_section][voice] Synthesizing voice...")
                await self.bot.edit_message_text(chat_id = chat_id, message_id = message_todel.message_id, text="Синтез голоса...")
                gptapp.voice_query( query = parsed["answer"], voice = self.userdb.get(uid, "voice"), filepath = f"./runtime/voice_{token}.mp3")
                print(f"[{uid}][gpt_section][voice] Synthesized voice")
                await self.bot_voice(chat_id, f"./runtime/voice_{token}.mp3", uid, parsed["answer"])
            else:
                print(f"[{uid}][gpt_section][text] Sending text message...")
                repl = f"**>{Utils.md2esc(pre_answer).replace('\n', '\n>')}||" + '\n' + Utils.md2esc(parsed["answer"])
                await self.bot_send_text(chat_id = chat_id, text = repl )

        print(f"[{uid}][gpt_section][msg_handler] Deleting temporary message")
        await self.bot.delete_message(chat_id, message_todel.message_id)

    async def check_old_users(self):
        while True:
            non_old = []
            for uid in self.userdb.configs.users.all():
                user_data = self.userdb.data(uid)
                if user_data and not (None in (user_data.get("last_activity", None), user_data.get("remind_time", None))):
                    # print(f"Checking user {uid}: {user_data["last_activity"]}")
                    if modtime.time() - user_data["last_activity"] > 60 * 60 * float(user_data["remind_time"]):
                        print(f"Old user {uid}: {user_data["last_activity"]}")
                        # try:
                        
                        await self.gpt_answer(
                            str(uuid.uuid4()), 
                            uid, 
                            uid, 
                            "Напиши какой-нибудь краткий вопрос или предложение вне контекста, как будто ты пишешь в давнюю переписку снова", 
                            [], []
                        )
                        
                        non_old.append(uid)
                        
                        # except Exception as e:
                        #     print(f"Error in old user cleanup: {e} ({uid} {user_data["user_id"]})")
                        # await bot.send_message(user_data["user_id"], )
                else:
                    self.userdb.ensure(uid, "remind_time", "6")
                    self.userdb.ensure(uid, "last_activity", modtime.time())

            for uid in non_old:
                self.userdb.set(uid, "last_activity", modtime.time())

            await asyncio.sleep(60)

    async def message_handler(self, message: Message) -> None:
        uid = message.from_user.id
        chat_id = message.chat.id
        token = str(uuid.uuid4())

        print(f"[{uid}][msg_handler] New message from `{uid}`")

        if not self.userdb.exists(uid):
            print(f"[{uid}][msg_handler][warn] New user: `{uid}`")
            self.userdb.default_set(uid)
        
        text = message.text or message.caption or "Запрос не предоставлен..."
        self.userdb.ensure(uid, "remind_time", "6")
        self.userdb.ensure(uid, "last_activity", modtime.time())
        self.userdb.ensure(uid, "voice_descript", False)
        self.userdb.ensure(uid, "voice", "ash")

        status, fpath, extension = await self.download_doc(message)
        print(f"[{uid}][msg_handler] Downloaded media: {status}/{fpath}/{extension}")
        files, images = [], []
        if status:
            if extension == "text":
                if (Utils.check_file(fpath)):
                    files.append(fpath)
            elif extension == "img":
                images.append(fpath)
            elif extension == "voice":
                reco = rv.SpeechRecognition( "ru-RU", None )
                text = reco.recognize_audiofile(Utils.ogg_to_wav(fpath))
                print(f"[{uid}][msg_handler][reco] Recognized: {text}")
                if self.userdb.get(uid, "voice_descript"):
                    await message.reply(f"**>{Utils.md2esc(text).replace('\n', '\n>')}||", parse_mode=ParseMode.MARKDOWN_V2)
        
        if text[0] == '/':
            print(f"[{uid}][msg_handler] Command section entered")
            answer = await self.proceed_commands(uid, text)
            print(f"[{uid}][msg_handler] Answer:\n{'='*10}\n{answer}\n{'='*10}\n")
            if answer == "gpt:retry":
                
                old_messages = self.userdb.get(uid, "messages")
                if len(old_messages) == 0:
                    await self.bot.send_message(chat_id, "Нет контекста для повтора")
                    return
                print(f"[{uid}][msg_handler] Retreing")
                messages = old_messages[:-1]
                self.userdb.set(uid, "messages", messages)
                text = old_messages[-1][0]
                print(f"[{uid}][msg_handler] Entering GPT retry section")
                await self.gpt_answer(token, uid, chat_id, text, files, images)
            else:
                print(f"[{uid}][msg_handler] Sending answer")
                await self.bot_send_text(chat_id, answer)
            return

        print(f"[{uid}][msg_handler] Entering GPT regular section")
        await self.gpt_answer(token, uid, chat_id, f"Request type: {extension}\n\nRequest: {text}", files, images)

if __name__ == "__main__":
    config = Configs(
        bot_config="./configs/dev/bot_cfg.json",
        gpt_config="./configs/system_prompt.json",
        messages_config="./configs/messages.json",
        user_database="./databases/users.sqllite",
        exclude_conf_answ=["voicedesc", "remindt"],
        main_text_provider=gpt.provider_stock.PollinationsAI,
        main_img_provider=gpt.provider_stock.PollinationsImage
    )

    userdb = UserDatabase(config)

    tg = TelegramApp(config, userdb, "./runtime/aiogram_main.txt")
    asyncio.run(tg.start())