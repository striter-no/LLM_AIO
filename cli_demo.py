import src.gpt as gpt

chat = gpt.Chat(
    provider=gpt.provider_stock.PollinationsAI
)

if __name__ == "__main__":
    chat.imageGeneration(
        "A cat on the ground",
        "flux",
        (1000, 1000),
        "./runtime/images/cat.png"
    )

    answer = chat.addMessage(
        "What is that?",
        ["./runtime/images/cat.png"],
        specified_model=gpt.models_stock.claude_3_5_sonnet.name
    )

    print(answer)