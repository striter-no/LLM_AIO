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

    print(output)
    return output