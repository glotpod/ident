from aiohttp.web import HTTPException


class HTTPUnprocessableEntity(HTTPException):
    status_code = 422
    reason = "Unprocessable Entity"
