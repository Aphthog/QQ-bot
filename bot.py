import nonebot
from nonebot.adapters.onebot import V11Adapter

nonebot.init()
nonebot.get_driver().register_adapter(V11Adapter)
nonebot.load_plugins("plugins")
nonebot.run()
