import asyncio
import json

import aiohttp


class Sender:
    host = "push.gp"

    def __init__(self, loop):
        self.session = aiohttp.ClientSession(loop=loop)
        self.loop = loop

    async def cleanup(self):
        await self.session.close()

    def notify(self, *args):
        coro = self._send_notification(*args)
        future = asyncio.ensure_future(coro, loop=self.loop)
        future.add_done_callback(lambda f: f.result())

    async def _send_notification(self, user_id, type, scope, payload):
        url = "http://{}/users/{}".format(self.host, user_id)
        body = {'type': type, 'scope': scope, 'payload': payload}
        headers = {'Content-Type': 'application/json'}
        await self.session.post(url, json.dumps(body), headers=headers)
