import src.openai_tts as tts

tts.gpt_tts(
    "Разговаривай натурально на русском языке (без какого-либо акцента). Скажи в ответ этот текст: Привет, как я могу помочь?",
    tts.Voice.ash,
    "./runtime/voice_response.mp3"
)