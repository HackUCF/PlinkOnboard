import boto3, json, requests
from boto3.dynamodb.conditions import Key, Attr

from jose import JWTError, jwt

from fastapi import APIRouter, Cookie, Request, Response, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.encoders import jsonable_encoder

from pydantic import validator, error_wrappers

from typing import Optional
from models.user import UserModelMutable
from models.info import InfoModel
from models.user import PublicContact

from util.authentication import Authentication
from util.errors import Errors
from util.options import Options
from util.discord import Discord
from util.plinko import Plinko
from util.kennelish import Kennelish, Transformer

import asyncio

options = Options.fetch()

templates = Jinja2Templates(directory="templates")

router = APIRouter(prefix="/plinko", tags=["HPCC"], responses=Errors.basic_http())


@router.get("/")
async def get_root():
    return InfoModel(
        name="PlinkOnboard",
        description="Horse Plinko-specific APIs",
        credits=[
            PublicContact(
                first_name="Jeffrey",
                surname="DiVincent",
                ops_email="jdivincent@hackucf.org",
            )
        ],
    )


@router.get("/waitlist")
async def get_waitlist():
    signups, waitlist_status, group = Plinko.get_waitlist_status()

    return {"signups": signups, "status": waitlist_status, "group": group}


@router.get("/drop-out")
@Authentication.member
async def get_waitlist(
    request: Request,
    token: Optional[str] = Cookie(None),
    payload: Optional[object] = {},
):
    """
    Quit HPCC.
    """

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(options.get("aws").get("dynamodb").get("table"))

    # user_data = table.get_item(Key={"id": payload.get("id")}).get("Item", None)

    table.update_item(
        Key={"id": payload.get("id")},
        UpdateExpression="SET waitlist = :waitlist",
        ExpressionAttributeValues={":waitlist": 0},
    )

    return RedirectResponse("/profile/", status_code=status.HTTP_302_FOUND)


@router.get("/team")
@Authentication.member
async def get_team_info(
    request: Request,
    token: Optional[str] = Cookie(None),
    payload: Optional[object] = {},
):
    """
    Gets team information of a given user.
    """

    team = Plinko.get_team(payload.get("id"))
    if team:
        return team
    else:
        Errors.generate(request, 400, "User is not in any teams.")


@router.get("/bot")
@Authentication.admin
async def get_team_info(
    request: Request, token: Optional[str] = Cookie(None), run: Optional[str] = "FAIL"
):
    """
    Expose teams for a given run in a format understood by PlinkoBot.
    """

    if run == "FAIL":
        return Errors.generate(request, 404, "Missing ?run")

    # Get all participants
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(options.get("aws").get("dynamodb").get("table"))
    data = table.scan().get("Items", None)

    output = []

    # Find hightest index.
    team_count = -1
    for user in data:
        team_number = int(user.get("team_number"))
        if team_number > team_count:
            team_count = team_number

    # Populate output with correct number of indexes.
    for i in range(team_count):
        output.append([])

    for user in data:
        if user.get("assigned_run").lower() == run.lower() and user.get("team_number"):
            team_idx = int(user.get("team_number")) - 1

            output[team_idx].append(user.get("discord_id"))

    return output


@router.get("/scanner")
@Authentication.admin
async def get_waitlist(request: Request, token: Optional[str] = Cookie(None)):
    return templates.TemplateResponse("checkin_qr.html", {"request": request})


@router.get("/checkin")
@Authentication.admin
async def checkin(
    request: Request,
    token: Optional[str] = Cookie(None),
    member_id: Optional[str] = "FAIL",
    run: Optional[str] = "FAIL",
):
    """
    Check-in a user for a given run.
    """

    if member_id == "FAIL" or run == "FAIL":
        return Errors.generate(request, 404, "User Not Found (or run not defined)")

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(options.get("aws").get("dynamodb").get("table"))

    user_data = table.get_item(Key={"id": member_id}).get("Item", None)

    if not user_data:
        return {
            "success": False,
            "msg": "Invalid membership ID. Did you show the right QR code?",
            "user": {},
        }

    if user_data.get("assigned_run").lower() != run.lower():
        return {
            "success": False,
            "msg": "You are not competing today.",
            "user": user_data,
        }

    table.update_item(
        Key={"id": member_id},
        UpdateExpression="SET checked_in = :checked_in",
        ExpressionAttributeValues={":checked_in": True},
    )

    user_data["checked_in"] = True

    message_text = f"""Hello {user_data.get('first_name', 'Plinktern')},

This message is confirming that you have been *checked in* to the Horse Plinko Cyber Challenge run for {run}.

You are on Team {user_data.get("team_number", 'Unassigned')}.

Please follow the signs to your .
"""

    Discord.send_message(user_data.get("discord_id"), message_text)

    return {"success": True, "msg": "Checked in!", "user": user_data}


@router.get("/join")
@Authentication.member
async def join_waitlist(
    request: Request,
    token: Optional[str] = Cookie(None),
    payload: Optional[object] = {},
):
    signups, waitlist_status, group = Plinko.get_waitlist_status(plus_one=True)
    print(waitlist_status)

    # start adding the person to the list!
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(options.get("aws").get("dynamodb").get("table"))

    user_data = table.get_item(Key={"id": payload.get("id")}).get("Item", None)

    if user_data.get("sudo") == True:
        return templates.TemplateResponse(
            "denied.html",
            {
                "request": request,
                "rationale": "You are an admin. Organizers cannot compete, silly!",
            },
        )

    if waitlist_status == "Closed":
        print(user_data.get("waitlist", -1))
        if user_data.get("waitlist", -1) == 1:
            return templates.TemplateResponse("approved.html", {"request": request})
        elif user_data.get("waitlist", -1) > 1:
            return templates.TemplateResponse(
                "waitlist.html",
                {"request": request, "group": user_data.get("waitlist")},
            )
        else:
            return templates.TemplateResponse(
                "denied.html",
                {
                    "request": request,
                    "rationale": "We have ran out of space in the Horse Plinko Cyber Challenge, and the waitlist is too long.",
                },
            )

    # Check if user is an Organizer (i.e., they are on the banned guild)
    check_organizer = Discord.check_presence(
        user_data.get("discord_id"), options.get("discord", {}).get("banned_guild_id")
    )
    if check_organizer:
        return templates.TemplateResponse(
            "denied.html",
            {
                "request": request,
                "rationale": "You are an organizer. Organizers cannot compete, silly!",
            },
        )

    # I know this isn't the best approach, but it works, so I'll do it anyways.
    # But this just checks if you meet our arbitrary requirements.
    elgible, elgible_rationale = Plinko.check_elgible(user_data)

    # If spots open...
    if elgible:
        # If user already has a spot, show it.
        if user_data.get("waitlist") != None:
            old_group_if_rechecking = user_data.get("waitlist", 0)
            if old_group_if_rechecking == 1:
                return templates.TemplateResponse("approved.html", {"request": request})

            # check if user is about to jeopardize their waitlist position
            elif old_group_if_rechecking != 0 and group > old_group_if_rechecking:
                return templates.TemplateResponse(
                    "waitlist.html",
                    {"request": request, "group": old_group_if_rechecking},
                )

        # Add to waitlist (or roster)
        print(f"We can update -> {group}")
        table.update_item(
            Key={"id": payload.get("id")},
            UpdateExpression="SET waitlist = :waitlist",
            ExpressionAttributeValues={":waitlist": group},
        )

        if waitlist_status == "Waitlisted":
            return templates.TemplateResponse(
                "waitlist.html", {"request": request, "group": group}
            )

        if waitlist_status == "Open":
            return templates.TemplateResponse("approved.html", {"request": request})
    else:
        if not elgible_rationale.get("kh_checked"):
            return templates.TemplateResponse(
                "denied.html",
                {
                    "request": request,
                    "rationale": "You did not agree to fill out the Knight Hacks form. This is a required field as a part of our partnership with Knight Hacks.",
                },
            )
        else:
            return templates.TemplateResponse(
                "denied.html",
                {
                    "request": request,
                    "rationale": "Please enter your first and last name.",
                },
            )
