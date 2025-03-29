import urllib 
import requests
import enum

voices = [ "alloy", "echo", "fable", "onyx", "nova", "shimmer", "coral", "verse", "ballad", "ash", "sage", "amuch", "dan" ]

class Voice(enum.Enum):
    alloy = "alloy"
    echo = "echo"
    fable = "fable"
    onyx = "onyx"
    nova = "nova"
    shimmer = "shimmer"
    coral = "coral"
    verse = "verse"
    ballad = "ballad"
    ash = "ash"
    sage = "sage"
    amuch = "amuch"
    dan = "dan"

def url_encode(text: str):
    return urllib.parse.quote(text)

def gpt_tts(text: str, voice: Voice | str, output: str):
    voice = voice.value if isinstance(voice, Voice) else voice
    url = f"https://text.pollinations.ai/{url_encode(text)}?model=openai-audio&voice={voice}"
    response = requests.get(url)
    if 'audio/mpeg' in response.headers.get('Content-Type', ''):
        with open(output, 'wb') as f:
            f.write(response.content)
        print(f"Audio saved successfully as {output}")
    else:
        print("Error: Expected audio response, received:")
        print(f"Content-Type: {response.headers.get('Content-Type')}")
        print(response.text)