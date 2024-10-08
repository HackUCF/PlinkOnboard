import json
import logging

import requests

from app.util.settings import Settings

logger = logging.getLogger(__name__)

if Settings().discord.enable:
    headers = {
        "Authorization": f"Bot {Settings().discord.bot_token.get_secret_value() }",
        "Content-Type": "application/json",
        "X-Audit-Log-Reason": "Hack@UCF OnboardLite Bot",
    }


class Discord:
    """
    This function handles Discord API interactions, including sending messages.
    """

    def __init__(self):
        pass

    @staticmethod
    def check_presence(discord_id, guild_id):
        if not Settings().discord.enable:
            return False
        """
        Checks if member is in a guild.
        """

        req = requests.get(
            f"https://discord.com/api/guilds/{guild_id}/members/{discord_id}",
            headers=headers,
        )

        joined = req.status_code < 400 or req.json().get("joined_at", False)

        return joined

    def assign_role(discord_id, role_id):
        discord_id = str(discord_id)

        req = requests.put(
            f"https://discord.com/api/guilds/{Settings().discord.guild_id}/members/{discord_id}/roles/{Settings.discord.member_role}",
            headers=headers,
        )

        return req.status_code < 400

    @staticmethod
    def get_dm_channel_id(discord_id):
        discord_id = str(discord_id)

        # Get DM channel ID.
        get_channel_id_body = {"recipient_id": discord_id}
        req = requests.post(
            f"https://discord.com/api/users/@me/channels",
            headers=headers,
            data=json.dumps(get_channel_id_body),
        )
        resp = req.json()

        return resp.get("id", None)

    @staticmethod
    def send_message(discord_id: str, message: str):
        discord_id = str(discord_id)
        channel_id = Discord.get_dm_channel_id(discord_id)

        send_message_body = {"content": message}
        req = requests.post(
            f"https://discord.com/api/channels/{channel_id}/messages",
            headers=headers,
            data=json.dumps(send_message_body),
        )
        print(req.text)

        return req.status_code < 400

    def join_plinko_server(self, discord_id: str, token):
        if not Settings().discord.enable:
            return
        if self.check_presence(discord_id, Settings().discord.guild_id) != "joined":
            logger.info(f"Joining {discord_id} to Plinko Discord")
            headers = {
                "Authorization": f"Bot {Settings().discord.bot_token.get_secret_value()}",
                "Content-Type": "application/json",
                "X-Audit-Log-Reason": "Hack@UCF OnboardLite Bot",
            }
            put_join_guild = {"access_token": token["access_token"]}
            requests.put(
                f"https://discordapp.com/api/guilds/{Settings().discord.guild_id}/members/{discord_id}",
                headers=headers,
                data=json.dumps(put_join_guild),
            )
