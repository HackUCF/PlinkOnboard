import time
from functools import wraps
from typing import Optional

from fastapi import Request, status
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt

# Import options and errors
from app.util.errors import Errors
from app.util.settings import Settings

if Settings().telemetry.enable:
    from sentry_sdk import set_user


class Authentication:
    def __init__(self):
        super(Authentication, self).__init__

    def admin_validate(token):
        if not token:
            return False

        try:
            payload = jwt.decode(
                token,
                Settings().jwt.secret.get_secret_value(),
                algorithms=Settings().jwt.algorithm,
            )
            is_admin: bool = payload.get("sudo", False)
            creation_date: float = payload.get("issued", -1)
        except Exception:
            return False

        if not is_admin:
            return False

        if time.time() > creation_date + Settings().jwt.lifetime_sudo:
            return False

        return True

    def admin(func):
        @wraps(func)
        async def wrapper(request: Request, token: Optional[str], *args, **kwargs):
            # Validate auth.
            if not token:
                return RedirectResponse(
                    "/discord/new?redir=" + request.url.path,
                    status_code=status.HTTP_302_FOUND,
                )

            try:
                payload = jwt.decode(
                    token,
                    Settings().jwt.secret.get_secret_value(),
                    algorithms=Settings().jwt.algorithm,
                )
                is_admin: bool = payload.get("sudo", False)
                creation_date: float = payload.get("issued", -1)
            except Exception:
                tr = Errors.generate(
                    request,
                    403,
                    "Invalid token provided. Please log in again (refresh the page) and try again.",
                )
                tr.delete_cookie(key="token")
                return tr

            if not is_admin:
                return Errors.generate(
                    request,
                    403,
                    "You are not a sudoer.",
                    essay="If you think this is an error, please try logging in again.",
                )

            if time.time() > creation_date + Settings().jwt.lifetime_sudo:
                return Errors.generate(
                    request,
                    403,
                    "Session not new enough to verify sudo status.",
                    essay="Unlike normal log-in, non-bot sudoer sessions only last a day. This is to ensure the security of Hack@UCF member PII. "
                    "Simply re-log into Onboard to continue.",
                )

            return await func(request, token, *args, **kwargs)

        return wrapper

    def member(func):
        @wraps(func)
        async def wrapper_member(
            request: Request,
            token: Optional[str],
            payload: Optional[object],
            *args,
            **kwargs,
        ):
            # Validate auth.
            if not token:
                return RedirectResponse(
                    "/discord/new?redir=" + request.url.path,
                    status_code=status.HTTP_302_FOUND,
                )

            try:
                payload = jwt.decode(
                    token,
                    Settings().jwt.secret.get_secret_value(),
                    algorithms=Settings().jwt.algorithm,
                )
                creation_date: float = payload.get("issued", -1)
            except Exception:
                tr = Errors.generate(
                    request,
                    403,
                    "Invalid token provided. Please log in again (refresh the page) and try again.",
                )
                tr.delete_cookie(key="token")
                return tr

            if time.time() > creation_date + Settings().jwt.lifetime_user:
                return Errors.generate(
                    request,
                    403,
                    "Session expired.",
                    essay="Sessions last for about fifteen weeks. You need to re-log-in between semesters.",
                )
            if Settings().telemetry.enable:
                set_user({"id": payload["id"]})

            return await func(request, token, payload, *args, **kwargs)

        return wrapper_member
