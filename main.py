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
    async def moonphase_cmd(self, event: AstrMessageEvent):
        """
        查询指定时刻的月相。从消息文本解析时间（输入日期格式YYYY-MM-DD HH:MM（北京时间），默认现在），直接回复。
        """
        message_str = event.message_str  # 用户发的纯文本消息字符串
        message_chain = (event.get_messages())  # 用户所发的消息的消息链 # from astrbot.api.message_components import *
        logger.info(message_chain)

        idx = message_str.find("/moonphase")
        time = message_str[idx + len("/moonphase") :].strip() or None

        if time is None:
            time_data = datetime.now(CN)
        else:
            time_data = datetime.strptime(time, "%Y-%m-%d %H:%M")
            time_data = time_data.replace(tzinfo=CN)

        data_dict = moon_phase(time_data)
        show_time = time_data.strftime("%Y-%m-%d %H:%M")

        reply=f"查询时间为{show_time}时的月相：月龄：{data_dict['age']}天，月面照明率：{data_dict['illumination']},月相：{data_dict['phase_name']}。"

        yield event.plain_result(reply)  # 发送一条纯文本消息


    @filter.llm_tool(name="get_moon_phase_tool")
    async def get_moon_phase_tool(self, event: AstrMessageEvent, time: str | None = None):
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
            time_data = datetime.now(CN)
        else:
            time_data = datetime.strptime(time, "%Y-%m-%d %H:%M")
            time_data = time_data.replace(tzinfo=CN)

        data_dict = moon_phase(time_data)
        show_time = time_data.strftime("%Y-%m-%d %H:%M")
        reply=f"查询时间为{show_time}时的月相：月龄：{data_dict['age']}天，月面照明率：{data_dict['illumination']},月相：{data_dict['phase_name']}。"

        return reply

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
