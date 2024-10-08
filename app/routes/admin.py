import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Body, Cookie, Depends, Request, Response
from fastapi.templating import Jinja2Templates
from jose import jwt
from sqlalchemy.orm import selectinload
from sqlalchemy.types import UUID
from sqlmodel import Session, select

from app.models.user import (
    UserModel,
    UserModelMutable,
    user_to_dict,
    user_update_instance,
)
from app.util.authentication import Authentication
from app.util.database import get_session, get_user
from app.util.discord import Discord
from app.util.email import Email
from app.util.errors import Errors
from app.util.settings import Settings

logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory="app/templates")

router = APIRouter(prefix="/admin", tags=["Admin"], responses=Errors.basic_http())


@router.get("/")
@Authentication.admin
async def admin(request: Request, token: Optional[str] = Cookie(None)):
    """
    Renders the Admin home page.
    """
    if token is None:
        return Errors.generate(request, 401, "User not authorized. Try logging in?")
    payload = jwt.decode(
        token,
        Settings().jwt.secret.get_secret_value(),
        algorithms=Settings().jwt.algorithm,
    )
    return templates.TemplateResponse(
        "admin_searcher.html",
        {
            "request": request,
            "icon": payload["pfp"],
            "name": payload["name"],
            "id": payload["id"],
        },
    )


@router.get("/get/")
@Authentication.admin
async def admin_get_single(
    request: Request,
    token: Optional[str] = Cookie(None),
    member_id: Optional[str] = "FAIL",
    session: Session = Depends(get_session),
):
    """
    API endpoint that gets a specific user's data as JSON
    """
    if member_id == "FAIL":
        return {"data": {}, "error": "Missing ?member_id"}

    statement = (
        select(UserModel)
        .where(UserModel.id == uuid.UUID(member_id))
        .options(selectinload(UserModel.discord))
    )
    user_data = user_to_dict(session.exec(statement).one_or_none())

    if not user_data:
        return Errors.generate(request, 404, "User Not Found")

    return {"data": user_data}


@router.get("/get_by_snowflake/")
@Authentication.admin
async def admin_get_snowflake(
    request: Request,
    token: Optional[str] = Cookie(None),
    discord_id: Optional[str] = "FAIL",
    session: Session = Depends(get_session),
):
    """
    API endpoint that gets a specific user's data as JSON, given a Discord snowflake.
    Designed for trusted federated systems to exchange data.
    """
    if discord_id == "FAIL":
        return {"data": {}, "error": "Missing ?discord_id"}

    statement = (
        select(UserModel)
        .where(UserModel.discord_id == discord_id)
        .options(selectinload(UserModel.discord))
    )
    data = user_to_dict(session.exec(statement).one_or_none())
    # if not data:
    #    # Try a legacy-user-ID search (deprecated, but still neccesary)
    #    data = table.scan(FilterExpression=Attr("discord_id").eq(int(discord_id))).get(
    #        "Items"
    #    )
    #
    #    if not data:
    #        return Errors.generate(request, 404, "User Not Found")

    # data = data[0]

    return {"data": data}


@router.post("/message/")
@Authentication.admin
async def admin_post_discord_message(
    request: Request,
    token: Optional[str] = Cookie(None),
    member_id: Optional[str] = "FAIL",
    user_jwt: dict = Body(None),
    session: Session = Depends(get_session),
):
    """
    API endpoint that gets a specific user's data as JSON
    """
    if member_id == "FAIL":
        return {"data": {}, "error": "Missing ?member_id"}

    data = session.exec(
        select(UserModel).where(UserModel.id == uuid.UUID(member_id))
    ).one_or_none()

    if not data:
        return Errors.generate(request, 404, "User Not Found")

    message_text = user_jwt.get("msg")

    res = Discord.send_message(data.discord_id, message_text)

    if res:
        return {"msg": "Message sent."}
    else:
        return {"msg": "An error occured!"}


@router.post("/get/")
@Authentication.admin
async def admin_edit(
    request: Request,
    token: Optional[str] = Cookie(None),
    input_data: Optional[UserModelMutable] = {},
    session: Session = Depends(get_session),
):
    """
    API endpoint that modifies a given user's data
    """
    if not input_data:
        return Errors.generate(request, 400, "No data provided")
    member_id = uuid.UUID(input_data.id)
    filtered_data = {k: v for k, v in input_data.dict().items() if v is not None}
    logger.info(f"AUDIT: Editing user {member_id} with data {filtered_data}")
    member_data = get_user(session, member_id, use_selectinload=True)

    if not member_data:
        return Errors.generate(request, 404, "User Not Found")
    input_data = user_to_dict(input_data)
    input_data.pop("id")
    user_update_instance(member_data, input_data)
    member_reutrn = user_to_dict(member_data)
    session.add(member_data)
    session.commit()
    return {"data": member_reutrn, "msg": "Updated successfully!"}


@router.get("/list")
@Authentication.admin
async def admin_list(
    request: Request,
    token: Optional[str] = Cookie(None),
    session: Session = Depends(get_session),
):
    """
    API endpoint that dumps all users as JSON.
    """
    statement = select(UserModel).options(selectinload(UserModel.discord))
    users = session.exec(statement)
    data = []
    for user in users:
        user = user_to_dict(user)
        data.append(user)

    return {"data": data}


@router.get("/csv")
@Authentication.admin
async def admin_list_csv(
    request: Request,
    token: Optional[str] = Cookie(None),
    session: Session = Depends(get_session),
):
    """
    API endpoint that dumps all users as CSV.
    """
    statement = select(UserModel).options(selectinload(UserModel.discord))
    data = session.exec(statement)

    output = "id, first_name, last_name, email, shirt_size, discord_username, experience, waitlist, comments, team_name, availability, team_number, assigned_run \n"
    for user in data:
        user = user_to_dict(user)
        output += f'"{user.get("id")}", '
        output += f'"{user.get("first_name")}", '
        output += f'"{user.get("last_name")}", '
        output += f'"{user.get("email")}", '
        output += f'"{user.get("shirt_size")}", '
        output += f'"{user.get("discord", {}).get("username")}", '
        output += f'"{user.get("experience")}", '
        output += f'"{user.get("waitlist")}", '
        output += f'"{user.get("comments")}", '
        output += f'"{user.get("team_name")}", '
        output += f'"{user.get("availability")}", '
        output += f'"{user.get("team_number")}", '
        output += f'"{user.get("assigned_run")}" \n'
    return Response(content=output, headers={"Content-Type": "text/csv"})
