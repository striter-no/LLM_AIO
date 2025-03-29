import src.reco_voice as rv

def simple_callback(text: str):
    print(f"Received text: {text}")

if __name__ == "__main__":

    reco = rv.SpeechRecognition(
        "ru-RU",
        simple_callback
    )

    print(
        reco.recognize_audio(
            "./runtime/userdata/AwACAgIAAxkBAAIEO2fn7kMP2QmIeSXyceqg4ckPtHOuAALKaAACoiZBS645cHTUfNh7NgQ.wav"
        )
    )

    # reco.start_work()
    # reco.stop()