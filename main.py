from datetime import datetime

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from .moon_phase import CN, moon_phase


@register("astrbot_plugin_astronomy", "数星星的小白兔", "月相与日月升落查询", "v0.0.2")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""

    @filter.command("moonphase")
    @filter.llm_tool(name="get_moon_phase")
    async def moonphase(self, event: AstrMessageEvent, time: str | None = None):
        """
        查询指定时刻的月相。
        Args:time(str): 查询时间，格式 YYYY-MM-DD HH:MM（北京时间）。可省略，省略表示当前时刻。
        "今晚"等同今天 21:00，"明晚"等同明天 21:00。
        """
        message_chain = (
            event.get_messages()
        )  # 用户所发的消息的消息链 # from astrbot.api.message_components import *
        logger.info(message_chain)

        if time is None:
            message_str = event.message_str  # 用户发的纯文本消息字符串
            if "/moonphase" in message_str:
                idx = message_str.find("/moonphase")
                time = message_str[idx + len("/moonphase") :].strip() or None

        if time is None:
            time_data = datetime.now(CN)
        else:
            time_data = datetime.strptime(time, "%Y-%m-%d %H:%M")
            time_data = time_data.replace(tzinfo=CN)

        data_dict = moon_phase(time_data)
        show_time = time_data.strftime("%Y-%m-%d %H:%M")

        yield event.plain_result(
            f"查询时间为{show_time}时的月相：月龄：{data_dict['age']}天，月面照明率：{data_dict['illumination']},月相：{data_dict['phase_name']}。"
        )  # 发送一条纯文本消息

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
