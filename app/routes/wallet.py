import json
import logging
import os
import uuid
from typing import Optional

import requests
from airpress import PKPass
from fastapi import APIRouter, Cookie, Depends, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from google.auth import crypt, jwt
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import error_wrappers, validator

from app.models.info import InfoModel
from app.models.user import PublicContact, UserModel, user_to_dict
from app.util.authentication import Authentication
from app.util.database import Session, get_session, get_user
from app.util.errors import Errors
from app.util.settings import Settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/wallet", tags=["API", "MobileWallet"], responses=Errors.basic_http()
)


class GoogleWallet:
    def __init__(self):
        self.auth_dict = json.loads(
            Settings().google_wallet.auth_json.get_secret_value()
        )
        self.auth()
        # [START auth]

    def auth(self):
        """Create authenticated HTTP client using a service account file."""
        self.credentials = Credentials.from_service_account_info(
            self.auth_dict,
            scopes=["https://www.googleapis.com/auth/wallet_object.issuer"],
        )

        self.client = build("walletobjects", "v1", credentials=self.credentials)

    # [END auth]
    # [START createObject]
    def create_object(
        self, issuer_id: str, class_suffix: str, user_data: UserModel
    ) -> str:
        """Create an object.

        Args:
            issuer_id (str): The issuer ID being used for this request.
            class_suffix (str): Developer-defined unique ID for the pass class.
            object_suffix (str): Developer-defined unique ID for the pass object.

        Returns:
            The pass object ID: f"{issuer_id}.{object_suffix}"
        """
        user_id = str(user_data.id)
        team_number = str(user_data.team_number)
        # Check if the object exists
        try:
            self.client.eventticketobject().get(
                resourceId=f"{issuer_id}.{user_id}"
            ).execute()
        except HttpError as e:
            if e.status_code != 404:
                # Something else went wrong...
                print(e.error_details)
                return f"{issuer_id}.{user_id}"
        else:
            print(f"Object {issuer_id}.{user_id} already exists!")
            return f"{issuer_id}.{user_id}"

        # See link below for more information on required properties
        # https://developers.google.com/wallet/tickets/events/rest/v1/eventticketobject
        new_object = {
            "id": f"{issuer_id}.{user_id}",
            "classId": f"{issuer_id}.{class_suffix}",
            "state": "ACTIVE",
            "barcode": {
                "type": "QR_CODE",
                "value": user_id,
            },
            "locations": [
                {
                    "latitude": 28.601393474451346,
                    "longitude": -81.19867982973763,
                }
            ],
            "seatInfo": {
                "section": {"defaultValue": {"language": "en-US", "value": team_number}}
            },
            "ticketHolderName": user_data.first_name + " " + user_data.last_name,
            "ticketNumber": user_id,
        }

        # Create the object
        response = self.client.eventticketobject().insert(body=new_object).execute()

        print("Object insert response")
        print(response)

        return f"{issuer_id}.{user_id}"

    # [END createObject]
    def create_jwt_existing_objects(
        self, issuer_id: str, user_id: str, suffix: str
    ) -> str:
        """Generate a signed JWT that references an existing pass object.

        When the user opens the "Add to Google Wallet" URL and saves the pass to
        their wallet, the pass objects defined in the JWT are added to the
        user's Google Wallet app. This allows the user to save multiple pass
        objects in one API call.

        The objects to add must follow the below format:

        {
            'id': 'ISSUER_ID.OBJECT_SUFFIX',
            'classId': 'ISSUER_ID.CLASS_SUFFIX'
        }

        Args:
            issuer_id (str): The issuer ID being used for this request.

        Returns:
            An "Add to Google Wallet" link
        """

        # Multiple pass types can be added at the same time
        # At least one type must be specified in the JWT claims
        # Note: Make sure to replace the placeholder class and object suffixes
        objects_to_add = {
            # Event tickets
            "eventTicketObjects": [
                {"id": f"{issuer_id}.{user_id}", "classId": f"{issuer_id}.{suffix}"}
            ],
        }

        # Create the JWT claims
        claims = {
            "iss": self.credentials.service_account_email,
            "aud": "google",
            "origins": ["www.example.com"],
            "typ": "savetowallet",
            "payload": objects_to_add,
        }

        # The service account credentials are used to sign the JWT
        signer = crypt.RSASigner.from_service_account_info(self.auth_dict)
        token = jwt.encode(signer, claims).decode("utf-8")

        return f"https://pay.google.com/gp/v/save/{token}"

    # [END jwtExisting]


if Settings().google_wallet.enable:
    google_wallet = GoogleWallet()

"""
Used to get Discord image.
"""


def get_img(url):
    resp = requests.get(url, stream=True)
    status = resp.status_code
    if status < 400:
        return resp.raw.read()
    else:
        return get_img("https://cdn.hackucf.org/PFP.png")


"""
User data -> Apple Wallet blob
"""


def apple_wallet(user_data):
    # Create empty pass package
    p = PKPass()

    # Add locally stored assets
    with open(
        os.path.join(
            os.path.dirname(__file__), "..", "static", "apple_wallet", "icon.png"
        ),
        "rb",
    ) as file:
        ico_data = file.read()
        p.add_to_pass_package(("icon.png", ico_data))

    with open(
        os.path.join(
            os.path.dirname(__file__), "..", "static", "apple_wallet", "icon@2x.png"
        ),
        "rb",
    ) as file:
        ico_data = file.read()
        p.add_to_pass_package(("icon@2x.png", ico_data))

    pass_json = {
        "passTypeIdentifier": "pass.org.hackucf.join",
        "formatVersion": 1,
        "teamIdentifier": "VWTW9R97Q4",
        "organizationName": "Hack@UCF",
        "serialNumber": str(uuid.uuid4()),
        "description": "Horse Plinko Cyber Challenge",
        "locations": [
            {
                "latitude": 28.601366109876327,
                "longitude": -81.19867691612126,
                "relevantText": "You're near the CyberLab!",
            }
        ],
        "foregroundColor": "#D2990B",
        "backgroundColor": "#1C1C1C",
        "labelColor": "#ffffff",
        "logoText": "",
        "barcodes": [
            {
                "format": "PKBarcodeFormatQR",
                "message": str(user_data.get("id", "Unknown_ID")),
                "messageEncoding": "iso-8859-1",
                "altText": user_data.get("discord", {}).get("username", None),
            }
        ],
        "generic": {
            "primaryFields": [
                {
                    "label": "Name",
                    "key": "name",
                    "value": user_data.get("first_name", "")
                    + " "
                    + user_data.get("last_name", ""),
                }
            ],
            "secondaryFields": [
                {
                    "label": "Assigned Run",
                    "key": "run_day",
                    "value": user_data.get("assigned_run")
                    if user_data.get("assigned_run", None)
                    else "Not Assigned",
                },
                {
                    "label": "Team Number",
                    "key": "team_no",
                    "value": user_data.get("team_number")
                    if user_data.get("team_number", None)
                    else "Not Assigned",
                },
            ],
            "backFields": [
                {
                    "label": "View Profile",
                    "key": "view-profile",
                    "value": "You can view and edit your profile at https://hr.plinko.horse/profile.",
                    "attributedValue": "You can view and edit your profile at <a href='https://hr.plinko.horse/profile'>hr.plinko.horse</a>.",
                },
                {
                    "label": "Check In",
                    "key": "check-in",
                    "value": "Please visit ENG1-186 (the CyberLab) to check in at your assigned time.",
                    "attributedValue": "Please visit ENG1-186 (the CyberLab) to check in at your assigned time.",
                },
            ],
        },
    }

    # I am duplicating the file reads because it's easier than re-setting file pointers to the start of each file.
    # I think.

    # User profile image
    discord_img = user_data.get("discord", {}).get("avatar", False)
    if discord_img:
        img_data = get_img(discord_img)
        p.add_to_pass_package(("thumbnail.png", img_data))

        img_data = get_img(discord_img)
        p.add_to_pass_package(("thumbnail@2x.png", img_data))

    # HPCC logo.
    with open(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "static",
            "apple_wallet",
            "logo_reg@2x.png",
        ),
        "rb",
    ) as file:
        ico_data = file.read()
        p.add_to_pass_package(("logo@2x.png", ico_data))

    with open(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "static",
            "apple_wallet",
            "logo_reg.png",
        ),
        "rb",
    ) as file:
        ico_data = file.read()
        p.add_to_pass_package(("logo.png", ico_data))

    pass_data = json.dumps(pass_json).encode("utf8")

    p.add_to_pass_package(("pass.json", pass_data))

    # Add locally stored credentials
    # Add locally stored credentials
    key_path = Settings().apple_wallet.pki_dir / "hackucf.key"
    cert_path = (
        Settings().apple_wallet.pki_dir / "hackucf.pem"
    )  # Assuming a different cert file

    # Check if files exist before opening them
    if not key_path.exists():
        logger.error(f"File not found: {key_path}")
        raise FileNotFoundError(f"File not found: {key_path}")

    if not cert_path.exists():
        logger.error(f"File not found: {cert_path}")
        raise FileNotFoundError(f"File not found: {cert_path}")

    # Open the files
    with key_path.open("rb") as key, cert_path.open("rb") as cert:
        # Add credentials to pass package
        p.key = key.read()
        p.cert = cert.read()

    # As we've added credentials to pass package earlier we don't need to supply them to `.sign()`
    # This is an alternative to calling .sign() method with credentials as arguments.
    p.sign()

    return p


"""
Get API information.
"""


@router.get("/")
async def get_root():
    return InfoModel(
        name="Onboard for Mobile Wallets",
        description="Apple Wallet support.",
        credits=[
            PublicContact(
                first_name="Jeffrey",
                surname="DiVincent",
                ops_email="jdivincent@hackucf.org",
            )
        ],
    )


@router.get("/apple")
@Authentication.member
async def aapl_gen(
    request: Request,
    token: Optional[str] = Cookie(None),
    payload: Optional[object] = {},
    session: Session = Depends(get_session),
):
    # Get data from DynamoDB
    user_data = get_user(session, uuid.UUID(payload.get("id")))

    p = apple_wallet(user_to_dict(user_data))

    return Response(
        content=bytes(p),
        media_type="application/vnd.apple.pkpass",
        headers={"Content-Disposition": 'attachment; filename="hackucf.pkpass"'},
    )


@router.get("/google")
@Authentication.member
async def google_wallet(
    request: Request,
    token: Optional[str] = Cookie(None),
    payload: Optional[object] = {},
    session: Session = Depends(get_session),
):
    user_data = get_user(session, uuid.UUID(payload.get("id")))

    issuer_id = Settings().google_wallet.issuer_id
    # TODO fix this
    if user_data.assigned_run == "day1":
        class_suffix = Settings().google_wallet.class_suffix_day1
    elif user_data.assigned_run == "day2":
        class_suffix = Settings().google_wallet.class_suffix_day2
    else:
        return Errors()

    object_id = google_wallet.create_object(issuer_id, class_suffix, user_data)
    redir_url = google_wallet.create_jwt_existing_objects(
        issuer_id,
        str(user_data.id),
        class_suffix,
    )

    return RedirectResponse(redir_url)
