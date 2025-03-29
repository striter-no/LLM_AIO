import urllib 
import requests
import enum

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

def gpt_tts(text: str, voice: Voice, output: str):
    voice = voice.value
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