import boto3, json, requests
from boto3.dynamodb.conditions import Key, Attr

from jose import JWTError, jwt

from fastapi import APIRouter, Cookie, Request, Response, Body
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.encoders import jsonable_encoder

from pydantic import validator, error_wrappers

from typing import Optional, Any
from models.user import UserModelMutable
from models.info import InfoModel

from util.authentication import Authentication
from util.errors import Errors
from util.options import Options
from util.discord import Discord
from util.kennelish import Kennelish, Transformer

options = Options.fetch()

templates = Jinja2Templates(directory="templates")

router = APIRouter(prefix="/admin", tags=["Admin"], responses=Errors.basic_http())


@router.get("/")
@Authentication.admin
async def admin(request: Request, token: Optional[str] = Cookie(None)):
    """
    Renders the Admin home page.
    """
    payload = jwt.decode(
        token,
        options.get("jwt").get("secret"),
        algorithms=options.get("jwt").get("algorithm"),
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
):
    """
    API endpoint that gets a specific user's data as JSON
    """
    if member_id == "FAIL":
        return {"data": {}, "error": "Missing ?member_id"}

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(options.get("aws").get("dynamodb").get("table"))
    data = table.get_item(Key={"id": member_id}).get("Item", None)

    if not data:
        return Errors.generate(request, 404, "User Not Found")

    return {"data": data}


@router.get("/get_by_snowflake/")
@Authentication.admin
async def admin_get_snowflake(
    request: Request,
    token: Optional[str] = Cookie(None),
    discord_id: Optional[str] = "FAIL",
):
    """
    API endpoint that gets a specific user's data as JSON, given a Discord snowflake.
    Designed for trusted federated systems to exchange data.
    """
    if discord_id == "FAIL":
        return {"data": {}, "error": "Missing ?discord_id"}

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(options.get("aws").get("dynamodb").get("table"))
    data = table.scan(FilterExpression=Attr("discord_id").eq(str(discord_id))).get(
        "Items"
    )

    print(data)

    if not data:
        # Try a legacy-user-ID search (deprecated, but still neccesary)
        data = table.scan(FilterExpression=Attr("discord_id").eq(int(discord_id))).get(
            "Items"
        )
        print(data)

        if not data:
            return Errors.generate(request, 404, "User Not Found")

    data = data[0]

    return {"data": data}


@router.post("/message/")
@Authentication.admin
async def admin_post_discord_message(
    request: Request,
    token: Optional[str] = Cookie(None),
    member_id: Optional[str] = "FAIL",
    payload: dict = Body(None),
):
    """
    API endpoint that gets a specific user's data as JSON
    """
    if member_id == "FAIL":
        return {"data": {}, "error": "Missing ?member_id"}

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(options.get("aws").get("dynamodb").get("table"))
    data = table.get_item(Key={"id": member_id}).get("Item", None)

    if not data:
        return Errors.generate(request, 404, "User Not Found")

    message_text = payload.get("msg")

    res = Discord.send_message(data.get("discord_id"), message_text)

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
):
    """
    API endpoint that modifies a given user's data
    """
    member_id = input_data.id

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(options.get("aws").get("dynamodb").get("table"))
    old_data = table.get_item(Key={"id": member_id}).get("Item", None)

    if not old_data:
        return Errors.generate(request, 404, "User Not Found")

    # Take Pydantic data -> dict -> strip null values
    new_data = {k: v for k, v in jsonable_encoder(input_data).items() if v is not None}

    # Existing  U  Provided
    union = {**old_data, **new_data}

    # This is how this works:
    # 1. Get old data
    # 2. Get new data (pydantic-validated)
    # 3. Union the two
    # 4. Put back as one giant entry

    table.put_item(Item=union)

    return {"data": union, "msg": "Updated successfully!"}


@router.get("/list")
@Authentication.admin
async def admin_list(request: Request, token: Optional[str] = Cookie(None)):
    """
    API endpoint that dumps all users as JSON.
    """
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(options.get("aws").get("dynamodb").get("table"))
    data = table.scan().get("Items", None)
    return {"data": data}


@router.get("/csv")
@Authentication.admin
async def admin_list(request: Request, token: Optional[str] = Cookie(None)):
    """
    API endpoint that dumps all users as CSV.
    """
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(options.get("aws").get("dynamodb").get("table"))
    data = table.scan().get("Items", None)

    output = "Membership ID, First Name, Last Name, NID, Is Returning, Gender, Major, Class Standing, Shirt Size, Discord Username, Experience, Cyber Interests, Event Interest, Is C3 Interest, Comments, Ethics Form Timestamp, Minecraft, Infra Email\n"
    for user in data:
        output += f'"{user.get("id")}", '
        output += f'"{user.get("first_name")}", '
        output += f'"{user.get("surname")}", '
        output += f'"{user.get("nid")}", '
        output += f'"{user.get("is_returning")}", '
        output += f'"{user.get("gender")}", '
        output += f'"{user.get("major")}", '
        output += f'"{user.get("class_standing")}", '
        output += f'"{user.get("shirt_size")}", '
        output += f'"{user.get("discord", {}).get("username")}", '
        output += f'"{user.get("experience")}", '
        output += f'"{user.get("curiosity")}", '
        output += f'"{user.get("attending")}", '
        output += f'"{user.get("c3_interest")}", '

        output += f'"{user.get("comments")}", '

        output += f'"{user.get("ethics_form", {}).get("signtime")}", '
        output += f'"{user.get("minecraft")}", '
        output += f'"{user.get("infra_email")}"\n'

    return Response(content=output, headers={"Content-Type": "text/csv"})
