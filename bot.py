
from dotenv import load_dotenv
load_dotenv()

import nonebot
from nonebot.adapters.onebot import V11Adapter

nonebot.init()
nonebot.get_driver().register_adapter(V11Adapter)

# 安全层（import 即激活注入检测 preprocessor）
import qq_bot.security.preprocessor  # noqa: F401

nonebot.load_plugins("qq_bot/plugins")

nonebot.run()
#           .venv/Scripts/python.exe bot.py