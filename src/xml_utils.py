import re

def parse_xml_like(text):
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
            
            # Обработка дубликатов тегов
            if current_tag in parent_obj:
                existing = parent_obj[current_tag]
                if isinstance(existing, str) and isinstance(current_obj, str):
                    parent_obj[current_tag] = existing + '\n' + current_obj
                elif isinstance(existing, dict) and isinstance(current_obj, dict):
                    raise ValueError(f"Duplicate nested tags '{current_tag}' are not allowed")
                else:
                    raise ValueError(f"Conflicting content types in duplicate tag '{current_tag}'")
            else:
                parent_obj[current_tag] = current_obj
        elif token.startswith('<'):
            # Обработка открывающего тега
            tag_name = token[1:-1]
            stack.append((tag_name, {}, False))
        else:
            # Обработка текстового токена
            if len(stack) < 2:
                continue
            current_tag, current_obj, is_defined = stack[-1]
            stripped_text = token.strip()
            if not stripped_text:
                continue
            if not is_defined:
                stack[-1] = (current_tag, stripped_text, True)
            else:
                if isinstance(current_obj, dict):
                    raise ValueError(f"Tag {current_tag} contains both text and nested tags")
                stack[-1] = (current_tag, f"{current_obj}\n{stripped_text}", True)

    if len(stack) != 1:
        raise ValueError("Unclosed tags remaining")
    
    def unescape(obj):
        if isinstance(obj, dict):
            return {k: unescape(v) for k, v in obj.items()}
        elif isinstance(obj, str):
            return obj.replace(escaped_lt, '<').replace(escaped_gt, '>')
        return obj
    
    return unescape(root)

def xml_escape(text: str):
    # Замена символов в тексте на экранированные символы
    return text.replace('<', '\\<')