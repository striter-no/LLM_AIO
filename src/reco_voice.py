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
    
    def recognize_audio(self, audio_path, lang: str | None = None) -> str:
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
    
    def start_work(self):
        self.is_running.set()
        print("Starting recognition thread")
        self._reco_worker()
    
    def stop(self):
        self.is_running.clear()
        self.audio_queue.put(None)  # Сигнализируем о завершении потока
    
    def resume_recognition(self):
        if not self.is_running.is_set():
            print("Resuming recognition")
            self.start_work()  # Перезапускаем распознавание
    
    def _reco_worker(self):
        with sr.Microphone() as source:
            print("Listening...")
            while self.is_running.is_set():
                audio = self._recoginzer.listen(source)
                self.audio_queue.put(audio)

                if not self.audio_queue.empty():
                    audio = self.audio_queue.get()
                    if audio is None:  # Проверка на None
                        break
                    text = self.recognize_audio(audio)
                    self.audio_queue.queue.clear()
                    if text:
                        self.callback(text)  # Вызываем коллбек с распознанным текстом
                        # Очищаем очередь