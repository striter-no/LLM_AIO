import json

def compile_response(data: dict):
    output = ""
    for key, value in data.items():
        output += f"<{key}>\n{value}\n</{key}>\n"
    return output

def compile_system_request(data: dict):
    nl = lambda x: f"\n{'='*x}\n\n"

    output  = "General request:" + nl(10) + data["general"] + nl(10)
    output += "Censure settings:" + nl(10)
    
    for content_type, forbidden in data["censure"].items():
        output += f"Для контента под типом {content_type}, запрещено: {forbidden}\n"

    output += nl(10)
    
    output += """Описание тегов для оформления. Каждый тег должен идти после другого, без вложенных. Используй данные теги при оформлении ответа:"""
    output += nl(10)
    for tag, (description, needed) in data["tags"].items():
        output += f"`{tag}` ({"ОБЯЗАТЕЛЕН для использования В ЛЮБОМ СЛУЧАЕ" if needed else "опционален, используется по ситуации"}): {description}\n"
    output += nl(10)

    output += "Запросы и примеры оформления твоих ответов на них с тегами:" + nl(10)
    for quest, answer in data["examples"].items():
        output += f"Запрос: `{quest}`\n\nОтвет: {compile_response(answer)}\n"

    # print(output)
    return output

if __name__ == "__main__":
    gptconf = json.load(open("./configs/system_prompt.json"))
    sys_prompt = compile_system_request(gptconf)
    print(json.dumps(sys_prompt, ensure_ascii=False, indent=2))