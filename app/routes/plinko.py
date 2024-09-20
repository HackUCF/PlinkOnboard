import asyncio
import logging
import uuid
from typing import Optional

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from pydantic import error_wrappers, validator
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.sqltypes import UUID
from sqlmodel import Session, select

from app.models.info import InfoModel
from app.models.user import (
    DiscordModel,
    PublicContact,
    UserModel,
    UserModelMutable,
    user_to_dict,
)
from app.util.authentication import Authentication
from app.util.database import Session, get_session, get_user
from app.util.discord import Discord
from app.util.errors import Errors
from app.util.kennelish import Kennelish, Transformer
from app.util.plinko import Plinko
from app.util.settings import Settings
from app.util.websockets import ConnectionManager

logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory="app/templates")

router = APIRouter(prefix="/plinko", tags=["HPCC"], responses=Errors.basic_http())

wsm = ConnectionManager()


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


@router.websocket("/ws/{token}")
async def plinko_ws(websocket: WebSocket, token: str):
    # Token validate
    valid_token = Authentication.admin_validate(token)
    if not valid_token:
        wsm.disconnect(websocket)

    client_id = await wsm.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await wsm.broadcast(data)
    except WebSocketDisconnect:
        wsm.disconnect(websocket)


@router.get("/waitlist")
async def get_waitlist(
    session: Session = Depends(get_session),
):
    signups, waitlist_status, group = Plinko.get_waitlist_status(session)

    return {"signups": signups, "status": waitlist_status, "group": group}


@router.get("/drop-out")
@Authentication.member
async def get_waitlist(
    request: Request,
    token: Optional[str] = Cookie(None),
    payload: Optional[object] = {},
    session: Session = Depends(get_session),
):
    """
    Quit HPCC.
    """
    logger.info(f"User {payload.get('id')} is dropping out of HPCC.")
    user_data = get_user(session, uuid.UUID(payload.get("id")))
    user_data.waitlist = 0
    session.add(user_data)
    session.commit()

    return RedirectResponse("/profile/", status_code=status.HTTP_302_FOUND)


@router.get("/team")
@Authentication.member
async def get_team_info(
    request: Request,
    token: Optional[str] = Cookie(None),
    payload: Optional[object] = {},
    session: Session = Depends(get_session),
):
    """
    Gets team information of a given user.
    """

    team = Plinko.get_team(session, payload.get("id"))
    if team:
        return team
    else:
        Errors.generate(request, 400, "User is not in any teams.")


@router.get("/bot")
@Authentication.admin
async def get_team_info(
    request: Request,
    token: Optional[str] = Cookie(None),
    run: Optional[str] = "FAIL",
    session: Session = Depends(get_session),
):
    """
    Expose teams for a given run in a format understood by PlinkoBot.
    """

    if run == "FAIL":
        return Errors.generate(request, 404, "Missing ?run")

    # Get all participants
    statement = select(UserModel).options(selectinload(UserModel.discord))
    users = session.exec(statement)
    data = []
    for user in users:
        user = user_to_dict(user)
        data.append(user)

    output = []
    # Find hightest index.
    team_count = -1
    for user in data:
        if user.get("team_number"):
            team_number = int(user.get("team_number"))
            if team_number > team_count:
                team_count = team_number

    # Populate output with correct number of indexes.
    for i in range(team_count):
        output.append([])

    for user in data:
        if (
            user.get("assigned_run").lower() == run.lower()
            and user.get("team_number")
            and user.get("waitlist") == 1
        ):
            team_idx = int(user.get("team_number")) - 1

            output[team_idx].append(user.get("discord_id"))

    return output


@router.get("/scanner")
@Authentication.admin
async def get_waitlist(request: Request, token: Optional[str] = Cookie(None)):
    return templates.TemplateResponse("checkin_qr.html", {"request": request})


@router.get("/dash")
@Authentication.admin
async def get_dash(request: Request, token: Optional[str] = Cookie(None)):
    return templates.TemplateResponse("dash.html", {"request": request})


@router.get("/scoreboard")
@Authentication.admin
async def get_scoreboard(request: Request, token: Optional[str] = Cookie(None)):
    return templates.TemplateResponse(
        "scoreboard.html", {"request": request, "domain": Settings().http.domain}
    )


@router.get("/scoreboard/edit")
@Authentication.admin
async def hack_scoreboard(request: Request, token: Optional[str] = Cookie(None)):
    return templates.TemplateResponse(
        "scoreboard_editor.html", {"request": request, "domain": Settings().http.domain}
    )


@router.get("/checkin")
@Authentication.admin
async def checkin(
    request: Request,
    token: Optional[str] = Cookie(None),
    member_id: Optional[uuid.UUID] = "FAIL",
    run: Optional[str] = "FAIL",
    session: Session = Depends(get_session),
):
    """
    Check-in a user for a given run.
    """

    if member_id == "FAIL" or run == "FAIL":
        return Errors.generate(request, 404, "User Not Found (or run not defined)")

    user_data = get_user(session, member_id)

    if not user_data:
        query = session.query(UserModel).filter(UserModel.hackucf_id == member_id)
        user_data = query.first()
        if not user_data:
            return {
                "success": False,
                "msg": "Invalid membership ID. Did you show the right QR code?",
                "user": {},
            }

    if user_data.assigned_run.lower() != run.lower():
        return {
            "success": False,
            "msg": "You are not competing today.",
            "user": user_data,
        }

    user_data.checked_in = True
    session.add(user_data)
    session.commit()

    team_number = -1
    if user_data.team_number:
        team_number = user_data.team_number

    return {"success": True, "msg": "Checked in!", "user": user_data}


@router.get("/join")
@Authentication.member
async def join_waitlist(
    request: Request,
    token: Optional[str] = Cookie(None),
    payload: Optional[object] = {},
    session: Session = Depends(get_session),
):
    signups, waitlist_status, group = Plinko.get_waitlist_status(session, plus_one=True)
    print(waitlist_status)

    # start adding the person to the list
    user_data = get_user(session, uuid.UUID(payload.get("id")))

    if user_data.sudo == True:
        return templates.TemplateResponse(
            "denied.html",
            {
                "request": request,
                "rationale": "You are an admin. Organizers cannot compete, silly!",
            },
        )

    if waitlist_status == "Closed":
        logger.info(user_data.waitlist, -1)
        if user_data.waitlist == 1:
            return templates.TemplateResponse("approved.html", {"request": request})
        elif user_data.waitlist > 1:
            return templates.TemplateResponse(
                "waitlist.html",
                {"request": request, "group": user_data.waitlist},
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
        user_data.discord_id, Settings().discord.organizer_guild_id
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
        if user_data.waitlist != None:
            old_group_if_rechecking = user_data.waitlist
            if old_group_if_rechecking == 1:
                return templates.TemplateResponse("approved.html", {"request": request})

            # check if user is about to jeopardize their waitlist position
            elif old_group_if_rechecking != 0 and group > old_group_if_rechecking:
                return templates.TemplateResponse(
                    "waitlist.html",
                    {"request": request, "group": old_group_if_rechecking},
                )

        # Add to waitlist (or roster)
        logger.info(f"We can update -> {group}")
        user_data.waitlist = group
        session.add(user_data)
        session.commit()

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
