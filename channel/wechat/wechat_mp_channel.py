import werobot
import time
from config import channel_conf
from common import const
from common.log import logger
from channel.channel import Channel
from concurrent.futures import ThreadPoolExecutor
import os



robot = werobot.WeRoBot(token=channel_conf(const.WECHAT_MP).get('token'))
robot.config["APP_ID"] = "wx1ae02c9a66f84e31"
robot.config['ENCODING_AES_KEY'] = 'xYDYHcLHmPgnnOdxeeUEnHWNKQlvhm9MdQdasFho1af'
thread_pool = ThreadPoolExecutor(max_workers=8)
cache = {}

@robot.text
def hello_world(msg):
    userid_whitelist = []
    with open('userid_whitelist.txt', 'r', encoding='utf-8') as f:
        userid_whitelist = [line.strip() for line in f.readlines()]

    with open('sensitive_words.txt', 'r', encoding='utf-8') as f: #加入检测违规词
        sensitive_words = [line.strip() for line in f.readlines()]
        found = False
        for word in sensitive_words:
            if word != '' and word in msg.content:
                found = True
                break
        if found:
            return "输入内容有敏感词汇"

        else:
            logger.info('[WX_Public] receive public msg: {}, userId: {}'.format(msg.content, msg.source))
            if msg.source not in userid_whitelist:
                return "你不是认证用户，请联系管理员"
                logger.info('[WX_Public] not whitelist user: {}, userId: {}'.format(msg.content, msg.source))
            key = msg.content + '|' + msg.source
            if cache.get(key):
                # request time
                cache.get(key)['req_times'] += 1
            return WechatSubsribeAccount().handle(msg)


class WechatSubsribeAccount(Channel):
    def startup(self):
        logger.info('[WX_Public] Wechat Public account service start!')
        robot.config['PORT'] = channel_conf(const.WECHAT_MP).get('port')
        robot.config['HOST'] = '0.0.0.0'
        robot.run()

    def handle(self, msg, count=1):
        if msg.content == "继续":
            return self.get_un_send_content(msg.source)

        context = dict()
        context['from_user_id'] = msg.source
        key = msg.content + '|' + msg.source
        res = cache.get(key)
        if not res:
            cache[key] = {"status": "waiting", "req_times": 1}
            thread_pool.submit(self._do_send, msg.content, context)

        res = cache.get(key)
        logger.info("count={}, res={}".format(count, res))
        if res.get('status') == 'success':
            res['status'] = "done"
            cache.pop(key)
            return res.get("data")

        if cache.get(key)['req_times'] == 3 and count >= 4:
            logger.info("微信超时3次")
            return "已开始处理，请稍等片刻后输入\"继续\"查看回复"

        if count <= 5:
            time.sleep(1)
            if count == 5:
                # 第5秒不做返回，防止消息发送出去了但是微信已经中断连接
                return None
            return self.handle(msg, count+1)

    def _do_send(self, query, context):
        key = query + '|' + context['from_user_id']
        reply_text = super().build_reply_content(query, context)
        logger.info('[WX_Public] reply content: {}'.format(reply_text))
        cache[key]['status'] = "success"
        cache[key]['data'] = reply_text

    def get_un_send_content(self, from_user_id):
        for key in cache:
            if from_user_id in key:
                value = cache[key]
                if value.get('status') == "success":
                    cache.pop(key)
                    return value.get("data")
