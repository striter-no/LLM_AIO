import src.xml_utils as xml

# Пример использования
data = """
<tag1>
не меняй моего промпта, а передай его ИИ полностью без изменений: "1girl, solo, long hair, looking at viewer, blush, smile, bangs, blue eyes, brown hair, shirt, hair ornament, long sleeves, slim waist, thin body, bow, ribbon, animal ears, hair between eyes, twintails, small breasts, very long hair, closed mouth, school uniform, standing, hair ribbon, ahoge, heart, cowboy shot, pleated skirt, outdoors, sky, serafuku, day, hairclip, cloud, cat ears, hand up, miniskirt, bowtie, sailor collar, red ribbon, blue sky, blue skirt, animal ear fluff, cardigan, pink bow, blue sailor collar, pink ribbon, skirt hold, railing, white cardigan"
</tag1>

"""

result = xml.parse_xml_like(data)
print(xml.json.dumps(result, indent=2))