import re
import uuid
from typing import Any, Optional

from pydantic import BaseModel, validator
from sqlmodel import Field, Relationship, SQLModel


class DiscordModel(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: Optional[str] = None
    mfa: Optional[bool] = None
    avatar: Optional[str] = None
    banner: Optional[str] = None
    color: Optional[int] = None
    nitro: Optional[int] = None
    locale: Optional[str] = None
    username: str
    user_id: Optional[uuid.UUID] = Field(default=None, foreign_key="usermodel.id")
    user: "UserModel" = Relationship(back_populates="discord")


class UserModel(SQLModel, table=True):
    # Identifiers
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

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
    discord: DiscordModel = Relationship(back_populates="user")

    # Collected from HackUCF Onboard
    hackucf_id: Optional[uuid.UUID] = None
    experience: Optional[int] = None

    # HPCC data (internal)
    waitlist: Optional[int] = None
    team_number: Optional[int] = None
    assigned_run: Optional[str] = ""

    checked_in: Optional[bool] = False

    did_sign_photo_release: Optional[bool] = False

    did_get_shirt: Optional[bool] = False


# What admins can edit.
class UserModelMutable(BaseModel):
    # Identifiers
    id: str

    # PII
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[str]
    shirt_size: Optional[str]

    # The MLH required stuff
    did_agree_to_do_kh: Optional[bool]  # must be True to compete

    # HPCC data (user-mutable)
    team_name: Optional[str]
    availability: Optional[str]

    # Permissions and Member Status
    sudo: Optional[bool]

    # Collected from Discord
    discord_id: Optional[str]
    discord: Optional[DiscordModel]

    # Collected from HackUCF Onboard
    hackucf_id: Optional[str]
    experience: Optional[int]

    # HPCC data (internal)
    waitlist: Optional[int]
    team_number: Optional[int]
    assigned_run: Optional[str]

    checked_in: Optional[bool]

    did_sign_photo_release: Optional[bool]

    did_get_shirt: Optional[bool]


class PublicContact(BaseModel):
    first_name: str
    surname: str
    ops_email: str


def user_to_dict(model):
    if model is None:
        return None
    if isinstance(model, list):
        return [user_to_dict(item) for item in model]
    if isinstance(model, (SQLModel, BaseModel)):
        data = model.model_dump()
        for key, value in model.__dict__.items():
            if isinstance(value, (SQLModel, BaseModel)):
                data[key] = user_to_dict(value)
            elif (
                isinstance(value, list)
                and value
                and isinstance(value[0], (SQLModel, BaseModel))
            ):
                data[key] = user_to_dict(value)
        return data


def user_update_instance(instance: SQLModel, data: dict[str, Any]) -> None:
    for key, value in data.items():
        if isinstance(value, dict):
            nested_instance = getattr(instance, key, None)
            if nested_instance is not None:
                user_update_instance(nested_instance, value)
            else:
                nested_model_class = instance.__class__.__annotations__.get(key)
                if nested_model_class:
                    new_nested_instance = nested_model_class()
                    user_update_instance(new_nested_instance, value)
        else:
            if value is not None:
                setattr(instance, key, value)


# Removed unneeded functionality

# class CyberLabModel(SQLModel, table=True):
#    id: Optional[int] = Field(default=None, primary_key=True)
#    resource: Optional[bool] = False
#    clean: Optional[bool] = False
#    no_profane: Optional[bool] = False
#    access_control: Optional[bool] = False
#    report_damage: Optional[bool] = False
#    be_nice: Optional[bool] = False
#    can_revoke: Optional[bool] = False
#    signtime: Optional[int] = 0
#
#    user_id: Optional[int] = Field(default=None, foreign_key="usermodel.id")
#    user: "UserModel" = Relationship(back_populates="cyberlab_monitor")
#
# class MenteeModel(SQLModel, table=True):
#    id: Optional[int] = Field(default=None, primary_key=True)
#    schedule: Optional[str] = None
#    time_in_cyber: Optional[str] = None
#    personal_proj: Optional[str] = None
#    hope_to_gain: Optional[str] = None
#    domain_interest: Optional[str] = None
#
#    user_id: Optional[int] = Field(default=None, foreign_key="usermodel.id")
#    user: "UserModel" = Relationship(back_populates="mentee")
