
from dotenv import load_dotenv
load_dotenv()

import nonebot
from nonebot.adapters.onebot import V11Adapter

nonebot.init()
nonebot.get_driver().register_adapter(V11Adapter)
nonebot.load_plugins("plugins")

# 离线文档插件（import 时自动初始化）
# import nonebot_plugin_docs  # noqa: F401

nonebot.run()
#           .venv/Scripts/python.exe bot.py