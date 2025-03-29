from pydub import AudioSegment
from pydub.playback import play
import src.openai_tts as tts
import src.gpt as gpt
import src.reco_voice as rv
import time as tm

chat = gpt.Chat(
    model="claude-3.7-sonnet",
    provider=gpt.provider_stock.PollinationsAI
)

reco = None

def process_response(text: str):
    try:
        print(text)
        reco.stop()
        time = 2
        while True:
            try:
                answer = chat.addMessage( query=text )
                break
            except gpt.g4f.errors.ResponseStatusError as e:
                print(e)
                if "500" in str(e):
                    print("Model error: " + str(e))
                    return
            except Exception as e:
                print(f"Error adding message: {e}")
                tm.sleep(time)
                time *= 1.5
        tts.gpt_tts(
            "Разговаривай натурально на русском языке (без какого-либо акцента). Тебе надо сказать: " + answer,
            tts.Voice.ash,
            "./runtime/voice_response.mp3"
        )
        print("Starting voice response")
        play(AudioSegment.from_mp3("./runtime/voice_response.mp3"))
        print("Next")
        tm.sleep(1)
        reco.resume_recognition()  # Возобновляем распознавание после воспроизведения
    except Exception as e:
        print(f"Error during processing response: {e}")

if __name__ == "__main__":
    reco = rv.SpeechRecognition("ru-RU", process_response)

    reco.start_work()

    # Добавьте цикл, чтобы программа не завершалась сразу
    try:
        while True:
            time.sleep(1)  # Просто поддерживаем главный поток активным
    except KeyboardInterrupt:
        reco.stop()  # Остановите распознавание при выходе