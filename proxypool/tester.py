import asyncio
import aiohttp
import time
import sys
try:
    from aiohttp import ClientError
except:
    from aiohttp import ClientProxyConnectionError as ProxyConnectionError
from proxypool.db import RedisClient
from proxypool.setting import *



class Tester(object):
    def __init__(self):
        self.redis = RedisClient()
    
    async def test_single_proxy(self, proxy, test_url):
        """
        测试单个代理
        :param proxy:
        :return:
        """
        headers = {
            'Proxy-Connection': 'keep-alive',
            'Cache-Control': 'max-age=0',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        conn = aiohttp.TCPConnector(verify_ssl=False)
        async with aiohttp.ClientSession(connector=conn) as session:
            try:
                if isinstance(proxy, bytes):
                    proxy = proxy.decode('utf-8')
                real_proxy = 'http://' + proxy
                print('正在测试', proxy)
                start_time = time.time()
                async with session.get(test_url, proxy=real_proxy, headers=headers, timeout=15,allow_redirects=False) as response:
                    end_time = time.time()
                    if response.status in VALID_STATUS_CODES:
                        ping = end_time - start_time
                        detection  = test_url.split(".")[1]
                        self.redis.db.update({"iport" : proxy, "pid" : 0},{"$set":{'number':INITIAL_SCORE}})
                        self.redis.add(proxy, score=MAX_SCORE, type=str(test_url).split(":")[0], detection=detection, ping=ping, pid=1)
                        print("代理可用"+ proxy+str(str(test_url).split(":")[0]))
                    else:
                        self.redis.decrease(proxy)
                        print('请求响应码不合法 ', response.status, 'IP', proxy)
            except (ClientError, aiohttp.client_exceptions.ClientConnectorError, asyncio.TimeoutError, AttributeError):
                self.redis.decrease(proxy)
                print('代理请求失败', proxy)

    def run(self):
        """
        测试主函数
        :return:
        """
        print('测试器开始运行')
        try:
            count = self.redis.db.count({"pid":0})
            print('当前剩余', count, '个代理')
            for i in range(0, count, BATCH_TEST_SIZE):
                start = i
                stop = min(i + BATCH_TEST_SIZE, count)
                print('正在测试第', start + 1, '-', stop, '个代理')
                test_proxies = self.redis.batch(start, stop)
                for test_url in TEST_URL:
                    loop = asyncio.get_event_loop()
                    tasks = [self.test_single_proxy(proxy, test_url) for proxy in test_proxies]
                    loop.run_until_complete(asyncio.wait(tasks))
                    sys.stdout.flush()
                    time.sleep(5)
        except Exception as e:
            print('测试器发生错误', e.args)