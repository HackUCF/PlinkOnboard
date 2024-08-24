import json, re, uuid
import os
import requests
import logging

from datetime import datetime, timedelta
import time
from typing import Optional, Union

# FastAPI
from fastapi import Depends, FastAPI, HTTPException, status, Request, Response, Cookie
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from jose import JWTError, jwt
from urllib.parse import urlparse
from requests_oauthlib import OAuth2Session


# Import the page rendering library
from app.util.kennelish import Kennelish

# Import middleware
from app.util.authentication import Authentication
from app.util.database import get_session, init_db
from app.util.forms import Forms

# Import error handling
from app.util.errors import Errors

# Import options
from app.util.settings import Settings
from app.util.plinko import Plinko
from app.util.discord import Discord

# Import data types
from app.models.user import UserModel, DiscordModel, user_to_dict

# import db functions
from app.util.database import get_session, init_db, get_user, get_user_discord

# Import routes
from app.routes import api, admin, wallet, plinko

# Init Logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# Initiate FastAPI.
app = FastAPI()
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="./app/static"), name="static")

# Import endpoints from ./routes
app.include_router(api.router)
app.include_router(admin.router)
app.include_router(wallet.router)
app.include_router(plinko.router)

@app.get("/")
async def index(request: Request, token: Optional[str] = Cookie(None)):
    """
    Home page.
    """
    try:
        if token is None:
            raise JWTError("Token is None")
        payload = jwt.decode(
            token,
            Settings().jwt.secret.get_secret_value(),
            algorithms=Settings().jwt.algorithm,
        )

        if payload.get("waitlist") and payload.get("waitlist") > 0:
            return RedirectResponse("/profile/", status_code=status.HTTP_302_FOUND)
        elif payload.get("sudo") == True:
            return RedirectResponse("/profile/", status_code=status.HTTP_302_FOUND)
        else:
            return RedirectResponse("/join/", status_code=status.HTTP_302_FOUND)
    except JWTError:
        return RedirectResponse(
            "/discord/new/?redir=/", status_code=status.HTTP_302_FOUND
        )

"""
Redirects to Discord for OAuth.
This is what is linked to by Onboard.
"""

@app.get("/discord/new/")
async def oauth_transformer(redir: str = "/join/2"):
    # Open redirect check
    hostname = urlparse(redir).netloc
    logger.debug(f"Hostname: {hostname}")
    if hostname != "" and hostname != Settings().http.domain:
        redir = "/join/2"

    oauth = OAuth2Session(
        Settings().discord.client_id,
        redirect_uri=Settings().discord.redirect_base + "_redir",
        scope=Settings().discord.scope,
    )
    authorization_url, state = oauth.authorization_url(
        "https://discord.com/api/oauth2/authorize"
    )

    rr = RedirectResponse(authorization_url, status_code=302)

    rr.set_cookie(key="redir_endpoint", value=redir)

    return rr

"""
Logs the user into Onboard via Discord OAuth and updates their Discord metadata.
This is what Discord will redirect to.
"""

@app.get("/api/oauth/")
async def oauth_transformer_new(
    request: Request,
    response: Response,
    code: str,
    redir: str = "/join/2",
    redir_endpoint: Optional[str] = Cookie(None),
    session: Session = Depends(get_session),
):

    # Open redirect check
    if redir == "_redir":
        redir = redir_endpoint or "/join/2"

    hostname = urlparse(redir).netloc

    if hostname != "" and hostname != Settings().http.domain:
        redir = "/join/2"

    if code is None:
        return Errors.generate(
            request,
            401,
            "You declined Discord log-in",
            essay="We need your Discord account to sign up for the Horse Plinko Cyber Challenge.",
        )

    # Get data from Discord
    oauth = OAuth2Session(
        Settings().discord.client_id,
        redirect_uri=Settings().discord.redirect_base + "_redir",
        scope=Settings().discord.scope,
    )

    token = oauth.fetch_token(
        "https://discord.com/api/oauth2/token",
        client_id=Settings().discord.client_id,
        client_secret=Settings().discord.secret.get_secret_value(),
        code=code,
    )

    r = oauth.get("https://discord.com/api/users/@me")
    discordData = r.json()

    # Generate a new user ID or reuse an existing one.
    user = get_user_discord(session, discordData["id"], use_selectinload=True)

    # TODO implament Onboard Federation

    is_new = False


    if user:
        member_id = user.id
        do_sudo = user.sudo
    else:
            if not discordData.get("verified"):
                tr = Errors.generate(
                    request,
                    403,
                    "Discord email not verfied please try again",
                )
                return tr
            infra_email = ""
            discord_id = discordData["id"]
            Discord().join_plinko_server(discord_id, token)
            user = UserModel(discord_id=discord_id)
            discord_data = {
                "email": discordData.get("email"),
                "mfa": discordData.get("mfa_enabled"),
                "avatar": f"https://cdn.discordapp.com/avatars/{discordData['id']}/{discordData['avatar']}.png?size=512",
                "banner": f"https://cdn.discordapp.com/banners/{discordData['id']}/{discordData['banner']}.png?size=1536",
                "color": discordData.get("accent_color"),
                "nitro": discordData.get("premium_type"),
                "locale": discordData.get("locale"),
                "username": discordData.get("username"),
                "user_id": user.id,
            }
            discord_model = DiscordModel(**discord_data)
            user.discord = discord_model
            session.add(user)
            session.commit()
            session.refresh(user)

    # Create JWT. This should be the only way to issue JWTs.
    jwtData = {
        "discord": token,
        "name": discordData["username"],
        "pfp": discordData.get("avatar"),
        "id": str(member_id),
        "sudo": do_sudo,
        "issued": time.time(),
    }
    bearer = jwt.encode(
        jwtData,
        Settings().jwt.secret.get_secret_value(),
        algorithm=Settings().jwt.algorithm,
    )
    rr = RedirectResponse(redir, status_code=status.HTTP_302_FOUND)
    if user.sudo:
        max_age = Settings().jwt.lifetime_sudo
    else:
        max_age = Settings().jwt.lifetime_user
    if Settings().env == "dev":
        rr.set_cookie(
            key="token",
            value=bearer,
            httponly=True,
            samesite="lax",
            secure=False,
            max_age=max_age,
        )
    else:
        rr.set_cookie(
            key="token",
            value=bearer,
            httponly=True,
            samesite="lax",
            secure=True,
            max_age=max_age,
        )

    # Clear redirect cookie.
    rr.delete_cookie("redir_endpoint")

    return rr

"""
Renders the landing page for the sign-up flow.
"""

@app.get("/join/")
async def join(request: Request, token: Optional[str] = Cookie(None), session: Session = Depends(get_session)):
    signups, wl_status, group = Plinko.get_waitlist_status(session)
    if token is None:
        return templates.TemplateResponse(
            "signup.html", {"request": request, "waitlist_status": wl_status}
        )
    else:
        try:
            payload = jwt.decode(
                token,
                Settings().jwt.secret.get_secret_value(),
                algorithms=Settings().jwt.algorithm,
            )

            user_data = get_user(session, uuid.UUID(payload.get("id")))

            if user_data.get("waitlist") and user_data.get("waitlist") > 0:
                return RedirectResponse("/profile", status_code=status.HTTP_302_FOUND)

        except Exception as e:
            pass

        return RedirectResponse("/join/2/", status_code=status.HTTP_302_FOUND)

"""
Renders a basic "my membership" page
"""

@app.get("/profile/")
@Authentication.member
async def profile(
    request: Request,
    token: Optional[str] = Cookie(None),
    payload: Optional[object] = {},
    session: Session = Depends(get_session),
):
    # Get data from DynamoDB
    user_data = get_user(session, uuid.UUID(payload.get("id")))

    team_data = Plinko.get_team(session, payload.get("id"))

    return templates.TemplateResponse(
        "profile.html",
        {"request": request, "user_data": user_to_dict(user_data), "team_data": team_data},
    )

"""
Renders a Kennelish form page, complete with stylings and UI controls.
"""

@app.get("/join/{num}/")
@Authentication.member
async def forms(
    request: Request,
    token: Optional[str] = Cookie(None),
    payload: Optional[object] = {},
    num: str = "1",
    session: Session = Depends(get_session),
):
    # AWS dependencies

    if num == "1":
        return RedirectResponse("/join/", status_code=status.HTTP_302_FOUND)

    data = Forms.get_form_body(num)

    # Get data from DynamoDB
    user_data = get_user(session, uuid.UUID(payload.get("id")))

    # Have Kennelish parse the data.
    body = Kennelish.parse(data, user_to_dict(user_data))

    return templates.TemplateResponse(
        "form.html",
        {
            "request": request,
            "icon": payload["pfp"],
            "name": payload["name"],
            "id": payload["id"],
            "body": body,
        },
    )

@app.get("/final")
async def final(request: Request):
    return templates.TemplateResponse("done.html", {"request": request})

@app.get("/logout")
async def logout(request: Request):
    rr = RedirectResponse("/", status_code=status.HTTP_302_FOUND)
    rr.delete_cookie(key="token")
    return rr

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
