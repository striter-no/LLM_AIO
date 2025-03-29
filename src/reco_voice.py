from threading import Thread
from queue import Queue
import speech_recognition as sr

class SpeechRecognition:
    def __init__(self, language: str, callback, reco_type: str = "google"):
        self.language = language
        self.reco_type = reco_type

        self._recoginzer = sr.Recognizer()
        self.reco_thread = None
        self.audio_queue = Queue()

        self.callback = callback
    
    def recognize_audio(self, audio_path: str, lang: str | None = None) -> str:
        with sr.AudioFile(audio_path) as source:
            audio = self._recoginzer.record(source)
            text = self._recoginzer.recognize_google(audio, language=self.language if not lang else lang)
        return text

    def _reco_worker(self):
        while True:
            audio = self.audio_queue.get()  # retrieve the next audio processing job from the main thread
            if audio is None: break  # stop processing if the main thread is done

            try:
                text = self._recoginzer.recognize_google(audio, language=self.language)
                self.callback(text)
                # print("Google Speech Recognition thinks you said " + text)
            except sr.UnknownValueError:
                print("Google Speech Recognition could not understand audio")
            except sr.RequestError as e:
                print("Could not request results from Google Speech Recognition service; {0}".format(e))

            self.audio_queue.task_done()  # mark the audio processing job as completed in the queue

    def start_work(self):
        self.reco_thread = Thread(target=self._reco_worker)

        self.reco_thread.daemon = True

        print("Starting recognition thread")
        self.reco_thread.start()
        with sr.Microphone() as source:
            try:
                while True:  # repeatedly listen for phrases and put the resulting audio on the audio processing job queue
                    self.audio_queue.put(
                        self._recoginzer.listen(source)
                    )
            except KeyboardInterrupt:  # allow Ctrl + C to shut down the program
                pass
    
    def stop(self):
        self.audio_queue.join()
        self.audio_queue.put(None)
        self.reco_thread.join()