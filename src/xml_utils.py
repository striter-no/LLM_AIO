import re

def parse_xml_like(text):
    # Замена экранированных символов на плейсхолдеры
    escaped_lt = '__ESCAPED_LT__'
    escaped_gt = '__ESCAPED_GT__'
    text = re.sub(r'\\(<)', escaped_lt, text)
    text = re.sub(r'\\(>)', escaped_gt, text)
    
    tokens = re.split(r'(</?\w+>)', text, flags=re.DOTALL)
    stack = [(None, {}, False)]  # (tag_name, obj, is_defined)
    root = stack[0][1]

    for token in tokens:
        token = token.strip()
        if not token:
            continue
        if token.startswith('</'):
            # Обработка закрывающего тега
            tag_name = token[2:-1]
            if len(stack) < 2:
                raise ValueError(f"Unmatched closing tag: {tag_name}")
            current_tag, current_obj, is_defined = stack.pop()
            if current_tag != tag_name:
                raise ValueError(f"Tag mismatch: {current_tag} vs {tag_name}")
            parent_tag, parent_obj, parent_defined = stack[-1]
            parent_obj[current_tag] = current_obj
        elif token.startswith('<'):
            # Обработка открывающего тега
            tag_name = token[1:-1]
            stack.append((tag_name, {}, False))
        else:
            # Обработка текстового токена
            if len(stack) < 2:
                continue  # Игнорируем текст вне тегов
            current_tag, current_obj, is_defined = stack[-1]
            stripped_text = token.strip()
            if not stripped_text:
                continue  # Пропускаем пустые текстовые токены
            if not is_defined:
                # Создаем новую строку, если тег еще не определен
                stack[-1] = (current_tag, stripped_text, True)
            else:
                # Добавляем текст к существующей строке с переносом
                if isinstance(current_obj, dict):
                    raise ValueError(f"Tag {current_tag} contains both text and nested tags")
                stack[-1] = (current_tag, f"{current_obj}\n{stripped_text}", True)

    if len(stack) != 1:
        raise ValueError("Unclosed tags remaining")
    
    # Восстановление экранированных символов
    def unescape(obj):
        if isinstance(obj, dict):
            return {k: unescape(v) for k, v in obj.items()}
        elif isinstance(obj, str):
            return obj.replace(escaped_lt, '<').replace(escaped_gt, '>')
        else:
            return obj
    
    return unescape(root)

def xml_escape(text: str):
    # Замена символов в тексте на экранированные символы
    return text.replace('<', '\\<')