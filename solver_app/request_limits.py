from starlette.responses import JSONResponse


class UploadBodyLimitMiddleware:
    def __init__(self, app, max_body_bytes: int):
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] != "/api/recognise":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length is not None and content_length.isdigit():
            if int(content_length) > self.max_body_bytes:
                await self._too_large(scope, receive, send)
                return

        messages = []
        total_bytes = 0
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] == "http.request":
                total_bytes += len(message.get("body", b""))
                if total_bytes > self.max_body_bytes:
                    await self._too_large(scope, receive, send)
                    return
                if not message.get("more_body", False):
                    break
            elif message["type"] == "http.disconnect":
                break

        async def replay_receive():
            if messages:
                return messages.pop(0)
            return await receive()

        await self.app(scope, replay_receive, send)

    async def _too_large(self, scope, receive, send):
        response = JSONResponse(
            {"detail": "Image uploads must be 8 MiB or smaller."},
            status_code=413,
        )
        await response(scope, receive, send)
