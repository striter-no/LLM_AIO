from threading import Thread
from threading import Event
from queue import Queue
import speech_recognition as sr
from typing import Callable

class SpeechRecognition:
    def __init__(self, language: str, callback: Callable, reco_type: str = "google"):
        self.language = language
        self.reco_type = reco_type
        self._recoginzer = sr.Recognizer()
        self.audio_queue = Queue()
        self.callback = callback
        self.is_running = Event()
    
    def recognize_audiofile(self, audio_path, lang: str | None = None) -> str:
        try:
            with sr.AudioFile(audio_path) as source:
                audio = self._recoginzer.record(source)
                text = self._recoginzer.recognize_google(audio, language=self.language if not lang else lang)
            return text
        except sr.UnknownValueError:
            print(f"Unknown audio")
            return ""
        except sr.RequestError as e:
            print(f"Could not request results from Google Speech Recognition service: {e}")
            return ""
    
    def recognize_audio(self, audio, lang: str | None = None):
        try:
            text = self._recoginzer.recognize_google(audio, language=self.language if not lang else lang)
            return text
        except sr.UnknownValueError:
            print(f"Unknown audio")
            return ""
        except sr.RequestError as e:
            print(f"Could not request results from Google Speech Recognition service: {e}")
            return ""
    
    def start_work(self):
        self.is_running.set()
        print("Starting recognition thread")
        self._reco_worker()
    
    def stop(self):
        self.is_running.clear()
        while not self.audio_queue.empty():
            self.audio_queue.get()
        self.audio_queue.put(None)  # Сигнализируем о завершении потока
    
    def resume_recognition(self):
        if not self.is_running.is_set():
            print("Resuming recognition")
            self.start_work()  # Перезапускаем распознавание
    
    def _reco_worker(self):
        with sr.Microphone() as source:
            print("Listening...")
            glob_text = ""
            audio_chunks = []  # Список для хранения аудиочанков

            while self.is_running.is_set():
                audio = self._recoginzer.listen(source)
                audio_chunks.append(audio)

                # Объединяем все чанки, если длина текста не превышает разумный предел
                # можно использовать некоторую логику для проверки, когда останавливать слушание
                if len(audio_chunks) > 0:
                    combined_frame_data = b''.join(chunk.frame_data for chunk in audio_chunks)  # Объединяем данные
                    sample_rate = audio_chunks[0].sample_rate
                    sample_width = audio_chunks[0].sample_width

                    combined_audio = sr.AudioData(combined_frame_data, sample_rate, sample_width)  # Создаем новый объект AudioData
                
                    text = self.recognize_audio(combined_audio)
                    if text:
                        glob_text += text
                        self.callback(glob_text)
                        glob_text = ""  # Очищаем глобальный текст

                    # Сбрасываем список чанков после распознавания
                    audio_chunks = []  

            if audio_chunks:
                # Для окончания работы можно распознать оставшиеся чанки
                combined_frame_data = b''.join(chunk.frame_data for chunk in audio_chunks)
                combined_audio = sr.AudioData(combined_frame_data, audio_chunks[0].sample_rate, audio_chunks[0].sample_width)
                text = self.recognize_audio(combined_audio)
                if text:
                    glob_text += text
                    self.callback(glob_text)