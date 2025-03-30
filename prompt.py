
text = """
<thinking>
{
    "title": "Identifying Key Information",
    "content": "To begin solving this problem, we need to carefully examine the given information and identify the crucial elements that will guide our solution process. This involves...",
    "next_action": "continue",
    "confidence": 0.8
}

{
    "title": "...",
    "content": "...",
    "next_action": "continue",
    "confidence": 0.85
}

...
</thinking>
<answer>Разобравшись в проблеме я пришел к такому выводу: ...</answer>
"""

print(text.replace('\n', '\\n').replace('"', '\\"'))