import json
import logging
import uuid
from typing import List

import requests
from sqlalchemy.orm import selectinload

from app.models.user import DiscordModel, UserModel
from app.util.database import Session, get_user
from app.util.settings import Settings


class Plinko:
    """
    This function handles HPCC_specigic stuff.
    """

    def __init__(self):
        pass

    @staticmethod
    def check_elgible(user_data):
        data = {
            "has_first_name": user_data.first_name != None,
            "has_last_name": user_data.last_name != None,
            "kh_checked": user_data.did_agree_to_do_kh == True,
        }

        for value in data.values():
            if value == False:
                return False, data

        return True, data

    @staticmethod
    def get_team(session: Session, user_id):
        """
        Get team information for a given user, including team-mates
        """

        # Database connection to get user...

        user_data: UserModel = get_user(session, uuid.UUID(user_id))

        user_team_number = user_data.team_number
        user_run = user_data.assigned_run

        if not user_team_number or not user_run:
            return None

        teammates = []

        all_users_with_team_number: List[UserModel] = (
            session.query(UserModel)
            .filter(UserModel.team_number == user_team_number)
            .options(selectinload(UserModel.discord))
            .all()
        )

        for user in all_users_with_team_number:
            if user.assigned_run == user_run and user.waitlist == 1:
                user_lite = {
                    "first_name": user.first_name,
                    "discord_id": user.discord_id,
                    "discord_username": user.discord.username,
                }
                teammates.append(user_lite)

        return {"number": user_team_number, "run": user_run, "members": teammates}

    @staticmethod
    def get_waitlist_status(session: Session, plus_one=False):
        """
        Return waitlist metadata as (current_count, status, group #)
        """
        participation_cap = Settings().waitlist.participation_cap
        waitlist_groups = Settings().waitlist.waitlist_groups  # 150, 180, 210, etc.
        hard_cap = Settings().waitlist.hard_cap

        data = session.query(UserModel).filter(UserModel.waitlist > 0).all()
        current_count = len(data)
        currently_registered = 0
        for user in data:
            if user.waitlist == 1:
                currently_registered += 1

        if plus_one:
            current_count += 1

        # Gets the group number.
        # 0 is non-waitlisted.
        group = max(1, ((current_count - participation_cap) // waitlist_groups) + 2)
        capped = current_count > hard_cap

        # Get status string
        status = "Waitlisted"
        if capped:
            status = "Closed"
            group = 0
        elif group == 1 or currently_registered <= participation_cap:
            status = "Open"
            group = 1

        return current_count, status, group
