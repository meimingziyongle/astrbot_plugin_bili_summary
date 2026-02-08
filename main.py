import re
import aiohttp
import time
from astrbot.api.all import *

@register("bili_summary", "liangcha", "BiliBili Advanced Resolver", "1.3.5")
class BiliSummaryPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.api_url = "https://api.bilibili.com/x/web-interface/view?bvid="

    @event_message_type(EventMessageType.ALL)
    async def resolve_bili(self, event: AstrMessageEvent):
        try:
            # 获取消息文本内容
            msg = getattr(event, 'message_str', '')
            if not msg: return

            # 1. 识别链接 (BV号 或 b23.tv短链接)
            bvid = None
            bv_match = re.search(r"(BV[a-zA-Z0-9]{10})", msg)
            short_match = re.search(r"b23\.tv/[a-zA-Z0-9]+", msg)

            async with aiohttp.ClientSession() as session:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer': 'https://www.bilibili.com/'
                }

                if bv_match:
                    bvid = bv_match.group(1)
                elif short_match:
                    # 处理短链接重定向还原
                    short_url = f"https://{short_match.group(0)}"
                    async with session.get(short_url, headers=headers, allow_redirects=True) as resp:
                        real_url = str(resp.url)
                        bv_search = re.search(r"(BV[a-zA-Z0-9]{10})", real_url)
                        if bv_search: bvid = bv_search.group(1)

                if not bvid: return

                # 2. 请求详情数据
                async with session.get(f"{self.api_url}{bvid}", headers=headers) as resp:
                    if resp.status != 200: return
                    res = await resp.json()
                    if res.get('code') != 0: return
                    
                    d = res['data']
                    title = d.get('title', '无标题')
                    pic = d.get('pic', '')
                    up = d.get('owner', {}).get('name', '未知')
                    
                    # 时间/时长处理
                    duration_sec = d.get('duration', 0)
                    duration = f"{duration_sec // 60:02d}:{duration_sec % 60:02d}"
                    pubdate = time.strftime("%Y-%m-%d %H:%M", time.localtime(d.get('pubdate', 0)))
                    
                    # 统计数据
                    s = d.get('stat', {})
                    stats_text = f"🔥 播放:{s.get('view',0)}  💬 弹幕:{s.get('danmaku',0)}\n" \
                                 f"🪙 投币:{s.get('coin',0)}  ↪️ 分享:{s.get('share',0)}"
                    
                    # 分辨率简写
                    h = d.get('dimension', {}).get('height', 0)
                    if h >= 2160: q_res = "2160"
                    elif h >= 1440: q_res = "1440"
                    elif h >= 1080: q_res = "1080"
                    elif h >= 720: q_res = "720"
                    else: q_res = "480"

                    # 简介智能截断逻辑
                    desc = d.get('desc', '暂无简介').replace('\n', ' ')
                    threshold = 80 
                    final_desc = desc[:threshold] + "..." if len(desc) > threshold else desc

                    summary = (
                        f"🎬 {title}\n"
                        f"👤 UP主: {up}  ⏳ 时长: {duration}\n"
                        f"📅 发布: {pubdate}  📺 分辨率: {q_res}\n"
                        f"--------------------\n"
                        f"{stats_text}\n"
                        f"📝 简介: {final_desc}"
                    )
                    
                    # 构造消息链返回
                    yield event.chain_result([
                        Image.fromURL(pic),
                        Plain(summary)
                    ])

        except Exception:
            pass