import json
import requests
import boto3
from boto3.dynamodb.conditions import Key, Attr

from util.options import Options

options = Options.fetch()

headers = {
    "Authorization": f"Bot {options.get('discord', {}).get('bot_token')}",
    "Content-Type": "application/json",
    "X-Audit-Log-Reason": "Hack@UCF OnboardLite Bot",
}


class Plinko:
    """
    This function handles HPCC_specigic stuff.
    """

    def __init__(self):
        pass

    def check_elgible(user_data):
        data = {
            "has_first_name": user_data.get("first_name") != None,
            "has_last_name": user_data.get("last_name") != None,
            "kh_checked": user_data.get("did_agree_to_do_kh") == True
        }

        for value in data.values():
            if value == False:
                return False, data

        return True, data

    def get_waitlist_status(plus_one=False):
        """
        Return waitlist metadata as (current_count, status, group #)
        """
        participation_cap = 119 - 4  # save for uBuffalo
        waitlist_groups = 15  # 150, 180, 210, etc.
        hard_cap = 200 - 4  # save for uBuffalo

        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(options.get("aws").get("dynamodb").get("table"))
        data = table.scan(FilterExpression=Attr("waitlist").gt(0)).get(
            "Items", None
        )  # on a list
        current_count = len(data)
        currently_registered = 0
        for user in data:
            if user.get("waitlist", 0) == 1:
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
