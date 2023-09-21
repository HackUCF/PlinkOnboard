from pydantic import BaseModel
from typing import Optional


class DiscordModel(BaseModel):
    email: Optional[str] = None
    mfa: Optional[bool] = None
    avatar: Optional[str] = None
    banner: Optional[str] = None
    color: Optional[int] = None
    nitro: Optional[int] = None
    locale: Optional[str] = None
    username: str


class UserModel(BaseModel):
    # Identifiers
    id: str

    # PII
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""
    email: Optional[str] = ""
    did_get_shirt: Optional[bool] = False

    # The MLH required stuff
    did_agree_to_do_kh: Optional[bool] = False  # must be True to compete

    # HPCC data (user-mutable)
    team_name: Optional[str] = ""
    availability: Optional[str] = ""

    # Permissions and Member Status
    sudo: Optional[bool] = False

    # Collected from Discord
    discord_id: str
    discord: DiscordModel

    # Collected from HackUCF Onboard
    hackucf_id: Optional[str] = None
    experience: Optional[int] = None

    # HPCC data (internal)
    waitlist: Optional[int] = None
    team_number: Optional[int] = None
    assigned_run: Optional[str] = ""

    checked_in: Optional[bool] = False

    did_get_shirt: Optional[bool] = False


# What admins can edit.
class UserModelMutable(BaseModel):
    # Identifiers
    id: str

    # PII
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""
    email: Optional[str] = ""
    shirt_size: Optional[str] = ""

    # The MLH required stuff
    did_agree_to_do_kh: Optional[bool] = False  # must be True to compete

    # HPCC data (user-mutable)
    team_name: Optional[str] = ""
    availability: Optional[str] = ""

    # Permissions and Member Status
    sudo: Optional[bool] = False

    # Collected from Discord
    discord_id: Optional[str]
    discord: Optional[DiscordModel]

    # Collected from HackUCF Onboard
    hackucf_id: Optional[str] = None
    experience: Optional[int] = None

    # HPCC data (internal)
    waitlist: Optional[int] = None
    team_number: Optional[int] = None
    assigned_run: Optional[str] = ""

    checked_in: Optional[bool] = False

    did_get_shirt: Optional[bool] = False


class PublicContact(BaseModel):
    first_name: str
    surname: str
    ops_email: str
