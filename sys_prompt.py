import src.gpt_utils as utils
import json

data = json.load(open("./configs/system_prompt.json"))
utils.compile_system_request(data)