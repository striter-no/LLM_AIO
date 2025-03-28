import src.xml_utils as xml

# Пример использования
data = """
<tag1>
data
newline and data
</tag1>
<tag2>
<tag3>
nested
</tag3>
</tag2>
"""

result = xml.parse_xml_like(data)
print(xml.json.dumps(result, indent=2))