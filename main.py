from datetime import datetime

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from .almanac import today_summary, wrapper
from .moon_phase import CN, moon_phase
from .riseset import BODIES, _parse_riseset_args, day_riseset, now_status


@register("astrbot_plugin_astronomy", "数星星的小白兔", "月相与日月升落查询", "v0.0.5")
class MyPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config=config
        self.lat = float(config.get("latitude", 31.94))
        self.lon = float(config.get("longitude", 118.79))

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

        reply=f"查询时间为{show_time}时的月相：\n月龄：{data_dict['age']}天，\n月面照明率：{data_dict['illumination']}，\n月相：{data_dict['phase_name']}。"

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

    @filter.command("risesetday")
    async def risesetday_cmd(self, event: AstrMessageEvent):
        """
        查询指定日期的天体升落情况。从消息文本解析时间（输入日期格式YYYY-MM-DD（北京时间），默认查询当日太阳），直接回复。
        当前支持SUN，MOON，八大行星。
        """
        message_str = event.message_str  # 用户发的纯文本消息字符串
        message_chain = (event.get_messages())  # 用户所发的消息的消息链 # from astrbot.api.message_components import *
        logger.info(message_chain)

        idx = message_str.find("/risesetday")
        text = message_str[idx + len("/risesetday") :]

        try:
            day, body, pos_fn, h0 = _parse_riseset_args(text)
        except ValueError as e:
            yield event.plain_result(f"参数没看懂：{e}\n格式示例：/risesetday 2026-11-04 SUN")
            return

        result = day_riseset(pos_fn, self.lat, self.lon, h0, day)

        reply=(f"查询日期为{result['date_local']}时天体{body}的升落情况：\n"
               f"升起时间：{result['rise_time']}，\n"
               f"中天时间：{result['transit_time']}，\n"
               f"中天高度：{result['transit_high']}，\n"
               f"落下时间: {result['set_time']}。")

        yield event.plain_result(reply)  # 发送一条纯文本消息

    @filter.llm_tool(name="get_riseset_day_tool")
    async def get_riseset_day_tool(self, event: AstrMessageEvent, time: str | None = None, body: str = "SUN"):
        """
        查询指定日期的天体升落情况。当前支持SUN，MOON，八大行星。
        Args:time(str): 查询时间，格式 YYYY-MM-DD（北京时间）。可省略，省略表示当前日期。
        body(str):查询天体，可省略，省略表示查询太阳（SUN）
        """
        message_chain = (
            event.get_messages()
        )  # 用户所发的消息的消息链 # from astrbot.api.message_components import *
        logger.info(message_chain)

        if time is None:
            day = datetime.now()
        else:
            try:
                day = datetime.strptime(time, "%Y-%m-%d")
            except ValueError:
                return f"参数没看懂：日期格式 YYYY-MM-DD，收到的是 {time}"

        body = body.upper()
        try:
            if body not in BODIES:
                raise ValueError(f"暂时只支持{'、'.join(BODIES)}，收到的是 {body}")
            pos_fn, h0 = BODIES[body]
        except ValueError as e:
            return f"参数没看懂：{e}\n格式要求：time:YYYY-MM-DD，body:'SUN'"
            

        result = day_riseset(pos_fn, self.lat, self.lon, h0, day)

        reply=(f"查询日期为{result['date_local']}时天体{body}的升落情况：\n"
               f"升起时间：{result['rise_time']}，\n"
               f"中天时间：{result['transit_time']}，\n"
               f"中天高度：{result['transit_high']}，\n"
               f"落下时间: {result['set_time']}。")

        return reply

    @filter.command("risesetbody")
    async def risesetbody_cmd(self, event: AstrMessageEvent):
        """
        查询指定的天体在此时的状态，以及下次的升落时间。默认查询太阳，直接回复。
        当前支持SUN，MOON，八大行星。
        """
        message_str = event.message_str  # 用户发的纯文本消息字符串
        message_chain = (event.get_messages())  # 用户所发的消息的消息链 # from astrbot.api.message_components import *
        logger.info(message_chain)

        idx = message_str.find("/risesetbody")
        text = message_str[idx + len("/risesetbody") :]

        try:
            _, body, pos_fn, h0 = _parse_riseset_args(text)
        except ValueError as e:
            yield event.plain_result(f"参数没看懂：{e}\n格式示例：/risesetbody SUN")
            return
        
        t_now = datetime.now()
        result = now_status(pos_fn, self.lat, self.lon, h0, t_now)

        reply=(f"当前查询天体为：{body}\n"
               f"天体当前状态：{result['status']}，\n"
               f"天体当前高度：{result['altitude']}，\n"
               f"下一次升起时间：{result['next_rise_time']}，\n"
               f"下一次中天时间：{result['next_transit_time']}，\n"
               f"下一次中天高度：{result['next_transit_high']}，\n"
               f"下一次落下时间: {result['next_set_time']}。")

        yield event.plain_result(reply)  # 发送一条纯文本消息

    @filter.llm_tool(name="get_riseset_body_tool")
    async def get_riseset_body_tool(self, event: AstrMessageEvent, body: str = "SUN"):
        """
        查询指定的天体在此时的状态，以及下次的升落时间。当前支持SUN，MOON，八大行星。
        Args: body(str):查询天体，可省略，省略表示查询太阳（SUN）。
        """
        message_chain = (
            event.get_messages()
        )  # 用户所发的消息的消息链 # from astrbot.api.message_components import *
        logger.info(message_chain)

        body = body.upper()
        try:
            if body not in BODIES:
                raise ValueError(f"暂时只支持{'、'.join(BODIES)}，收到的是 {body}")
            pos_fn, h0 = BODIES[body]
        except ValueError as e:
            return f"参数没看懂：{e}\n格式要求：body:'SUN'"
            
        t_now = datetime.now()
        result = now_status(pos_fn, self.lat, self.lon, h0, t_now)

        reply=(f"当前查询天体为：{body}\n"
               f"天体当前状态：{result['status']}，\n"
               f"天体当前高度：{result['altitude']}，\n"
               f"下一次升起时间：{result['next_rise_time']}，\n"
               f"下一次中天时间：{result['next_transit_time']}，\n"
               f"下一次中天高度：{result['next_transit_high']}，\n"
               f"下一次落下时间: {result['next_set_time']}。")

        return reply

    @filter.command("wrapperday")
    async def wrapperday_cmd(self, event: AstrMessageEvent):
        """
        查询指定日期的蒙影情况。从消息文本解析时间（输入日期格式YYYY-MM-DD（北京时间），默认查询当日），直接回复。
        """
        message_str = event.message_str  # 用户发的纯文本消息字符串
        message_chain = (event.get_messages())  # 用户所发的消息的消息链 # from astrbot.api.message_components import *
        logger.info(message_chain)

        idx = message_str.find("/wrapperday")
        time = message_str[idx + len("/wrapperday") :].strip() or None

        if time is None:
            time_data = datetime.now()
        else:
            try:
                time_data = datetime.strptime(time, "%Y-%m-%d")
            except ValueError:
                yield event.plain_result( f"参数没看懂：日期格式 YYYY-MM-DD，收到的是 {time}")

        date_local = time_data.strftime("%Y-%m-%d")
        result = wrapper(time_data, self.lat, self.lon)

        reply=(f"查询日期为{date_local}的蒙影情况：\n"
               f"{result}")

        yield event.plain_result(reply)  # 发送一条纯文本消息

    @filter.llm_tool(name="get_wrapper_day_tool")
    async def get_wrapper_day_tool(self, event: AstrMessageEvent, time: str | None = None):
        """
        查询指定日期的蒙影情况。
        Args:time(str): 查询时间，格式 YYYY-MM-DD（北京时间）。可省略，省略表示当天。
        """
        message_chain = (event.get_messages())  # 用户所发的消息的消息链 # from astrbot.api.message_components import *
        logger.info(message_chain)

        if time is None:
            time_data = datetime.now()
        else:
            try:
                time_data = datetime.strptime(time, "%Y-%m-%d")
            except ValueError:
                return f"参数没看懂：日期格式 YYYY-MM-DD，收到的是 {time}"

        date_local = time_data.strftime("%Y-%m-%d")
        result = wrapper(time_data, self.lat, self.lon)

        reply=(f"查询日期为{date_local}的蒙影情况：\n"
               f"{result}")

        return reply

    @filter.command("今日观星")
    async def today_star(self, event: AstrMessageEvent):
        """
        一次查询当天的综合天文信息，包括主要天体升落，月相，蒙影等。
        """
        reply=today_summary(self.lat, self.lon)
        yield event.plain_result(reply)  # 发送一条纯文本消息

    @filter.llm_tool(name="get_today_star_tool")
    async def get_today_star_tool(self, event: AstrMessageEvent):
        """
        一次查询当天的综合天文信息，包括主要天体升落，月相，蒙影等。可以用于回答今晚/今天是否适合观星、何时适合拍摄等笼统问题。
        """
        reply=today_summary(self.lat, self.lon)
        return reply

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
