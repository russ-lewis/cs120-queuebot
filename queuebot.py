"""
Author: Benjamin Perumala

How to create/add Bot to Discord Server:
    1. Go to https://discord.com/developers/applications and create a new App
    2. Go to the bot tab on the left and click "Add a Bot" to convert the app to a bot account
    3. Name it, give it profile picture, etc.
        3.5 Enable the "Server Members Intent" option under the "Privileged Gateway Intents"
            if you intend on enabling the config values "CHECK_VOICE_WAITING" or "ALERT_ON_FIRST_JOIN"
    4. Click the "Copy" button to copy the Bot's Token
    5. Copy this into SECRET_TOKEN's key within the config.json file
        (If you do not have this file, run the bot file and it'll generate one for you)
    6. Fill out other config information. ROLES is a list of Administrators/TAs. CHANNEL is the channel
       the bot will look at for commands
    6. Replace the client_id param with your secret token then go to that location within a web browser
    https://discordapp.com/oauth2/authorize?&client_id=REPLACE_WITH_YOUR_CLIENT_ID&scope=bot&permissions=84032
    7. Choose the server you want the bot to join
    8. Run this script


NOTICES:
    - This is the first time I've used asyncio so best
    practices, etc. may not have been entirely followed.

    - This bot has a "global" queue and as a result, expects to run on a single
    server (using a single bot in multiple servers will not work). This can easily
    be solved by having the queue be a dictionary that maps a server/channel to a queue
    but is out of scope for this project.
    (QueueBot.update_presence() would likely need to be removed as each server would
    then have a different queue size)
"""

import os
import sys
import json
import logging
import logging.handlers
import asyncio
import discord

from enum import Enum
from collections import deque


class DiscordUser():
    """
    A simplified class to compare and store discord users
    This is used instead of the discord user object to facilitate testing

    Parameters:
        uuid: discord's unique identifier for a user
        name: username of a user
        discriminator: the four numbers that used after the username
                       for the external representation of a user
                       example: For "someuser#1234", 1234 is the discriminator
        nick: nickname of the user if it's different than the username. None otherwise
    """
    def __init__(self, uuid, name, discriminator, nick):
        self.uuid = uuid
        self.name = name
        self.discriminator = discriminator
        self.nick = nick
        self.join_time = None

    def get_mention(self):
        """
        Mention a user within a message

        Returns: A string that mentions the user
        """
        return f"<@{self.uuid}>"

    def get_tag(self):
        """
        Get a user's discord tag (how users externally add/mention friends)
        Format is username#NNNN where N is a number

        Returns: The user's discord tag
        """
		# External representation of a user
        return f"{self.name}#{self.discriminator}"

    def get_name(self):
        """
        Get the user's display name within the server

        Returns: The user's display name
        """
        if self.nick is None:
            return self.name

        return self.nick

    def __str__(self):
        """
        Returns the discord internal representation of a user
        format: "<@USERID_HERE>"
        """
        return self.get_tag()

    def __eq__(self, other):
        """
        If other is DiscordUser ot discord.member.Member,
        it checks the uuids to see if they match.
        If it is not one of the two objects, it compares other
        with self.uuid

        Parameters:
            other: object to compare against

        Returns: True if objects have same uuid
        """

        if isinstance(other, DiscordUser):
            return self.uuid == other.uuid
        elif isinstance(other, discord.member.Member):
            return self.uuid == other.id

        return other == self.uuid


class QueueConfig:
    """
    A storage class which holds all config values for QueueBot.
    On initialization, it does simple validation checks to see if
    the given config is properly configured. This object does not check
    if the values work for a given discord server - that must be verified
    after authentication has taken place.

    Paramters:
        config_obj: a dictionary with config options (see README for all options)
        from_env: True if config values come from environmental variables (for Docker)
        test_mode: set to True for unit test cases
    """
    def __init__(self, config_obj, from_env=False, test_mode=False):
        self.original_config = config_obj
        self.clean_config = self._validate_config(config_obj, from_env)
        self.from_env = from_env
        self.test_mode = test_mode
        self.version = "1.0.0"

        # Each dictionary attribute becomes a constantly field
        for key, val in self.clean_config.items():
            setattr(self, key.upper(), val)

    def _validate_config(self, config_obj, from_env):
        """
        Do basic error checking

        Parmeters:
            config_object: a dictionary with config options (see README for all options)
            from_env: True if config values come from environmental variables (for Docker)

        Returns: A clean dictionary (whitespace trimmed, etc.) with config options
        NOTE: This method terminates the program if a config option is invalid
        """
        # TODO Logger Level config option
        prefix = "QUEUE_" if from_env else ""
        error = {
            "SECRET_TOKEN": "You must update this field before the bot will connect",
            "TA_ROLES": "This field is required to allow administrators to remove users from the queue",
            "LISTEN_CHANNELS": "You must update this field to allow the bot to read commands",
            "VOICE_WAITING": "You must define which voice channel is a waiting room when you have CHECK_VOICE_WAITING enabled",
            "VOICE_OFFICES": "You must define Office Hour(s) voice channels when you have ALERT_ON_FIRST_JOIN is enabled",
            "ALERTS_CHANNEL": "You must define an alerts channel so the bot can send you notification message"
        }

        config_clean = {
            "SECRET_TOKEN": config_obj["SECRET_TOKEN"].strip(),
            "TA_ROLES": [r.strip() for r in config_obj["TA_ROLES"] if r],
            "CHECK_VOICE_WAITING": config_obj["CHECK_VOICE_WAITING"].strip().lower() == "true",
            "LISTEN_CHANNELS": [c.strip().lstrip("#") for c in config_obj["LISTEN_CHANNELS"] if c],
            "ALERT_ON_FIRST_JOIN": config_obj["ALERT_ON_FIRST_JOIN"].strip().lower() == "true",
        }

        if config_clean["ALERT_ON_FIRST_JOIN"]:
            config_clean["ALERTS_CHANNEL"] = config_obj["ALERTS_CHANNEL"].strip()

        if config_clean["CHECK_VOICE_WAITING"]:
            config_clean["VOICE_WAITING"] = config_obj["VOICE_WAITING"].strip()

        if config_clean["ALERT_ON_FIRST_JOIN"]:
            config_clean["VOICE_OFFICES"] = [v.strip()
                                             for v in config_obj["VOICE_OFFICES"] if v]

        if config_clean["SECRET_TOKEN"] == "YOUR_SECRET_TOKEN_HERE":
            print(prefix + "SECRET_TOKEN is empty!")
            print(error["SECRET_TOKEN"])
            sys.exit(1)

        # Simple error checking. Make sure non-booleans are nonempty
        for key, val in config_clean.items():
            if isinstance(val, bool):
                continue
            if len(val) == 0:
                print(prefix + key, "is empty!")
                print(error[key])
                sys.exit(1)

        if config_clean["CHECK_VOICE_WAITING"] and config_clean["ALERT_ON_FIRST_JOIN"] and \
                        config_clean["VOICE_WAITING"] in config_clean["VOICE_OFFICES"]:
            print(config_clean["VOICE_WAITING"], "can be either the waiting room or an office room not both!")
            sys.exit(1)

        return config_clean

    def copy(self):
        return QueueConfig(self.original_config.copy(),
                           from_env=self.from_env, test_mode=self.test_mode)

    def __str__(self):
        retval = []
        banner_width = 60
        prefix = "QUEUE_" if self.from_env else ""
        retval.append('=' * banner_width + "\n")
        retval.append(f"VERSION: {self.version}\n")
        for key, val in self.clean_config.items():
            if key == "SECRET_TOKEN":
                val = '*' * 40
            retval.append(f"{prefix}{key}: {val}\n")
        retval.append('=' * banner_width + "\n")

        return "".join(retval)


class CmdPrefix(Enum):
    SUCCESS = object()
    WARNING = object()
    ERROR = object()

# TODO Alert user if they're in voice channel and not in queue?

class QueueBot(discord.Client):
    """
    Instantiate the QueueBot that connects to a Discord server to manage a single queue

    Parameters:
        config: A QueueConfig object specifying config options
        logger: A logger object created from Python's logging module
        testing: Used for unit testing. Leave as False unless testing
    """

    # TODO Use config testing instead of optional param
    def __init__(self, config, logger, testing=False):
        assert isinstance(config, QueueConfig)

        intents = discord.Intents.default()
        intents.typing = False
        intents.presences = False
        intents.dm_messages = False
        intents.invites = False
        # Cache voice channels only if queuebot checks voice channel state
        intents.members = True if config.CHECK_VOICE_WAITING or config.ALERT_ON_FIRST_JOIN else False
        super().__init__(intents=intents)  # Initialize discord.py properties

        self.is_initialized = False
        self.config = config
        self.logger = logger
        # This queue holds DiscordUser objects
        # Items are pulled off the left and pushed onto the right
        self._queue = deque()

        self.testing = testing
        self.waiting_room = None
        self.alerts_channel = None

        self.msg_help = {
            "STUDENT": """__STUDENT COMMANDS:__
> `!q help` - Get this help message
> `!q join`  - Join the queue
> `!q leave` - Leave the queue
> `!q position` - See how many people are in front of you
> `!q list` - Get a list of the next 10 people in line""",

            "TA": """__TA COMMANDS:__
> `!q help` - Get this help message
> `!q ping` - Bot should reply with `Pong!` Used to make sure bot can receive/send messages
> `!q next` - Get the next person to help **(REMOVES FROM QUEUE)**
> `!q peek` - See the next person in the queue WITHOUT removing them
> `!q clear` - Empty the queue (requires confirmation)
> `!q add @user` - add @user to the end of the queue (you must @mention the person)
> `!q remove @user` - remove @user from the queue (you must @mention the person)
> `!q front @user` - adds/moves @user to the front of the queue (you must @mention the person)
> `!q list` - Get a list of the next 10 people in line

NOTE: Student commands are commands that require no permissions to run (TAs can also run student commands)"""
        }

    async def on_ready(self):
        """
        Discord.py calls this on initialization (does not run in testing mode)
        It does some setup and saves the waiting room voice channel to self.waiting_room

        Returns: None
        """
        self.logger.info('Logged in as {0}!'.format(self.user))

        if len(self.guilds) == 0:
            self.logger.error("The bot is not connected to any servers! " +
                              "Please add the bot to a server as shown in the README")

        self.logger.debug(f"Found server '{self.guilds[0].name}'. Comparing config to server channels")

        if self.config.CHECK_VOICE_WAITING:
            self.waiting_room = await self.get_waiting_room(self.guilds[0].voice_channels)
        if self.config.ALERT_ON_FIRST_JOIN:
            self.office_rooms = await self.get_office_rooms(self.guilds[0].voice_channels)
            self.alerts_channel = await self.get_alerts_channel(self.guilds[0].text_channels)

        await self.check_listen_channels(self.guilds[0].text_channels)

        await self.update_presence()
        self.is_initialized = True

    async def get_waiting_room(self, voice_channels):
        """
        Search all guild voice channels to find self.config.VOICE_WAITING
        NOTE: This function terminates the program if it can't find the voice channel

        Parameters:
            voice_channels: list of all voice channels in the guild

        Returns: discord.py object represending waiting room voice channel
        """
        for channel in voice_channels:
            if channel.name == self.config.VOICE_WAITING:
                self.logger.debug("Found waiting room voice channel")
                return channel

        self.logger.error(f"Unable to find voice channel '{self.config.VOICE_WAITING}'!" +
                          "\nAvailable voice channels: " + ", ".join([f"'{c.name}'" for c in voice_channels]))
        sys.exit(1)

    async def get_office_rooms(self, voice_channels):
        """
        Search all guild voice channels to find self.config.VOICE_OFFICES
        NOTE: This function terminates the program if it can't find all the voice channels

        Parameters:
            voice_channels: list of all voice channels in the guild

        Returns: list of discord.py objects represending office hour voice channels
        """
        config_offices = set(self.config.VOICE_OFFICES)
        office_channels = list(filter(lambda c: c.name in config_offices, voice_channels))

        if len(office_channels) != len(config_offices):
            missing = config_offices - set([v.name for v in office_channels])

            self.logger.error(f"Unable to find the following office channels: " + ", ".join([f"'{v}'" for v in missing]))
            self.logger.error("Available voice channels: " + ", ".join([f"'{c.name}'" for c in voice_channels]))
            sys.exit(1)

        self.logger.debug("Found all office room voice channels")

        return office_channels

    async def get_alerts_channel(self, text_channels):
        """
        Search all guild text channels to find self.config.ALERT_CHANNEL
        NOTE: This function terminates the program if it can't find all the voice channels

        Parameters:
            voice_channels: list of all text channels in the guild

        Returns: discord.py objects represending alert text channel
        """
        alert_channel = self.config.ALERTS_CHANNEL

        for channel in text_channels:
            if channel.name == alert_channel:
                self.logger.debug("Found alerts text channel")
                return channel

        self.logger.error(f"Unable to find voice channel '{alert_channel}'!")
        self.logger.error("Available text channels: " + ", ".join([f"'{c.name}'" for c in text_channels]))
        sys.exit(1)

    async def check_listen_channels(self, text_channels):
        """
        Search all guild text channels to ensure all channels in self.config.LISTEN_CHANNELS exist
        NOTE: This function terminates the program if it can't find all the voice channels

        Parameters:
            voice_channels: list of all text channels in the guild

        Returns: None
        """
        avail_channels = set()
        for channel in text_channels:
            avail_channels.add(channel.name)

        for channel in self.config.LISTEN_CHANNELS:
            if channel not in avail_channels:
                self.logger.error(f"Unable to find listen channel '{channel}'!")
                sys.exit(1)

        self.logger.debug("Found all listen text channels")

    async def on_message(self, message):
        if not self.is_initialized:
            return

        # Ignore Direct Messages
        if not isinstance(message.channel, discord.TextChannel):
            return

        # Ignore bot messages
        if message.author == self.user:
            return

        # Ignore channels that are not config.CHANNEL
        if message.channel.name not in self.config.LISTEN_CHANNELS:
            return

        self.logger.info('[#{0.channel}] {0.author} ({0.author.id}): {0.content}'.format(message))

        # All commands start with !q
        if message.content.lower().startswith("!q"):
            try:
                update = await self.queue_command(message)

                # Update Bot's user status to show # of people in the queue
                # (queue_command will return True if queue was modified)
                if update:
                    await self.update_presence()
            except Exception as e:
                self.logger.error(e)
                await self.send(message.channel, "An error has occurred.", CmdPrefix.ERROR)
                raise e

    async def update_presence(self):
        """
        Update the bot's profile activity to show how many people
        are in the queue

        Returns: None
        """

        # TODO If discord ever allows it, update presences to remove "Playing" from "Playing ### people in queue"
        person = "people" if len(self._queue) != 1 else "person"
        await self.change_presence(activity=discord.Game(name=f"{len(self._queue)} {person} in queue"))
        self.logger.info('Queue state: ' + ", ".join(str(el) for el in self._queue))

    async def send(self, channel, content=None, message_type=None, *, embed=None, allowed_mentions=None):
        """
        Simple wrapper of discord.py's send method.
        This is primarily used when in testing mode as it prints out the message
        """
        prefix_emote = ""
        if message_type is None:
            pass
        elif message_type is CmdPrefix.WARNING:
            prefix_emote = "⚠️"
        elif message_type is CmdPrefix.SUCCESS:
            prefix_emote = "✅"
        elif message_type is CmdPrefix.ERROR:
            prefix_emote = "‼️"

        if prefix_emote:
            content = prefix_emote + " " + content

        if not self.testing:
            self.logger.info(f"[{channel.name}]  [#{self.user}] [embed? {embed is not None}] {content.rstrip() if content else ''}")
            return await channel.send(content=content, embed=embed, allowed_mentions=allowed_mentions)
        else:
            print("SEND:", content, end="")
            if embed:
                print(f" embed.title='{embed.title}', embed.description={embed.description}, fields={embed.fields}")
            else:
                print()  # End current line

    async def queue_command(self, message):
        """
        Takes a !q ______ command and attempts to parse it
        discord.py likely has a better way to do this but I
        did this option for the sake of simplicity

        Parameters:
            message: A discord.py message object where the message starts with '!q'

        Returns: True if queue updated (False otherwise)
        """
        full_command = message.content.split()
        channel = message.channel
        author = message.author

        user = DiscordUser(author.id, author.name, author.discriminator, author.nick)

        if len(full_command) < 2 or len(full_command) > 3:
            await self.send(channel, f"{user.get_mention()} invalid syntax. Type `!q join` to join the queue or `!q help` for all commands", CmdPrefix.WARNING)
            return False

        for i in range(len(full_command)):
            full_command[i] = full_command[i].lower()
        command = full_command[1]

        """ STUDENT COMMANDS """

        if command == "ping":
            return await self.q_ping(channel)
        elif command == "help":
            return await self.q_help(user, channel, message.author)
        elif command == "join" or command == "addme":
            return await self.q_join(user, channel)
        elif command == "leave" or command == "removeme":
            return await self.q_leave(user, channel)
        elif command == "position" or command == "pos":
            return await self.q_position(user, channel)
        elif command == "list":
            return await self.q_list(user, channel)
        elif command == "count" or command == "length":
            return await self.q_count(user, channel)

        """ TA COMMANDS """

        # Make sure user is a TA for rest of commands
        if not await self.is_ta(author.roles):
            await self.send(channel, f"{user.get_mention()} invalid format. Type `!q join` to join the queue or `!q help` for all commands", CmdPrefix.WARNING)
            return False

        if len(full_command) == 2:
            # TODO Option to skip over students in another office room
            # TODO next and peek should have similar code (next just removes)
            if command == "next" or command == "remove" or command == "pop":
                return await self.q_pop(user, channel)
            elif command == "peek":
                return await self.q_peek(user, channel)
            elif command == "clear" or command == "empty":
                return await self.q_clear(user, channel)

        # Don't check for length (user could accidentally write out name - including spaces - instead of mentioning)
        # As a result, the command will account for it and print out the necessary warning message
        if command == "add":
            return await self.q_add_other(user, message.mentions, channel)
        elif command == "remove":
            return await self.q_remove_other(user, message.mentions, channel)
        elif command == "front":
            return await self.q_move_front_other(user, message.mentions, channel)

        # Didn't find matching command
        await self.send(channel, f"{user.get_mention()} invalid format. Type `!q join` to join the queue or `!q help` for all commands", CmdPrefix.WARNING)
        return False

    async def q_ping(self, channel):
        """
        If a user sends !q ping, reply with "Pong!"
        Can be run by anyone

        Parameters:
            channel: discord.py channel object to send message to

        Returns: False (doesn't update queue)
        """
        await self.send(channel, "Pong!")
        return False

    async def q_help(self, user, channel, author):
        """
        If a user sends !q help, send a Direct Message
        to a given user with a list of available commands
        If they have a TA role, it will list student commands
        as well as TA commands
        Can be run by anyone

        Parameters:
            user: DiscordUser object representing the user who ran the command
            channel: discord.py channel to send the message to
            author: discord.py user associated with user parameter (used to check roles)

        Returns: False (doesn't update queue)
        """
        user_uuid = self.get_user(user.uuid)
        command = f"{self.msg_help['STUDENT']}"
        if await self.is_ta(author.roles):
            command += "\n\n" + self.msg_help["TA"]
            self.logger.info("    > Sent TA help command")
        else:
            self.logger.info("    > Sent student help command")

        await user_uuid.send(command)
        await self.send(channel, f"{user.get_mention()} a list of the commands has been sent to your Direct Messages", CmdPrefix.SUCCESS)
        return False

    async def alert_avail_tas(self):
        """
        Notify available TAs when someone joins the queue
        (where an available TA is a TA who is in an office hours
        room without a student in it)

        Returns: Number of TAs mentioned
        """
        if not self.config.ALERT_ON_FIRST_JOIN:
            return

        self.logger.debug("Getting active TAs for ALERT_ON_FIRST_JOIN")

        actives = []
        for room in self.office_rooms:
            tas = []
            has_student = False
            for user in room.members:
                if await self.is_ta(user.roles):
                    tas.append(user)
                else:
                    has_student = True

            if len(tas) > 0 and not has_student:
                actives.extend(tas)

        if len(actives) == 0:
            self.logger.debug("No active TAs to message about nonempty queue")
            return 0

        message = " ".join([ta.mention for ta in actives]) + " The queue is no longer empty"
        await self.send(self.alerts_channel, message)
        return len(actives)

    async def q_join(self, user, channel):
        """
        If a user sends "!q join", attempt to add them to the queue
        The user must be within the config["WAITING_ROOM"] voice channel before joining
        Can be run by anyone

        Parameters:
            user: DiscordUser object representing the user who ran the command
            channel: discord.py channel object to send message to

        Returns: True if the user is added to the queue
        """
        if user in self._queue:
            index = self._queue.index(user)
            await self.send(channel, f"{user.get_mention()} you are already in the queue at position #{index+1}", CmdPrefix.WARNING)
            return False

        if self.config.CHECK_VOICE_WAITING and user not in self.waiting_room.members:
            await self.send(channel, f"{user.get_mention()} Please join the '{self.config.VOICE_WAITING}' \
voice channel then __run `!q join` again__\n", CmdPrefix.WARNING)
            return False

        self._queue.append(user)
        self.logger.debug("Queue length after adding user = " + str(len(self._queue)))
        if len(self._queue) == 1:
            await self.alert_avail_tas()
        await self.send(channel, f"""{user.get_mention()} you have been added at position #{len(self._queue)}
*Please stay in the voice channel while you wait*""", CmdPrefix.SUCCESS)
        return True

    async def q_leave(self, user, channel):
        """
        If a user sends "!q leave", attempt to remove them to the queue
        Can be run by anyone

        Parameters:
            user: DiscordUser object representing the user who ran the command
            channel: discord.py channel object to send message to

        Returns: True if the user is removed from the queue
        """
        if user in self._queue:
            self._queue.remove(user)
            await self.send(channel, f"{user.get_mention()} you have been removed from the queue", CmdPrefix.SUCCESS)
            return True
        else:
            await self.send(channel, f"{user.get_mention()} you can not be removed from the queue because you never joined it", CmdPrefix.WARNING)
            return False

    async def q_position(self, user, channel):
        """
        If a user sends "!q position", tell them their position within the queue
        Can be run by anyone

        Parameters:
            user: DiscordUser object representing the user who ran the command
            channel: discord.py channel object to send message to

        Returns: False (doesn't update queue)
        """
        if user in self._queue:
            index = self._queue.index(user)
            await self.send(channel, f"{user.get_mention()} you are at position #{index+1}")
        else:
            await self.send(channel, f"{user.get_mention()} you are not in the queue")

        return False

    async def is_ta(self, roles):
        """
        Checks to see if a given user's role list is a TA
        from config.TA_ROLES

        Parameters:
            roles: A discord.py user's role list to check

        Returns: True if the user is a TA (False otherwise)
        """
        for r in roles:
            if r.name in self.config.TA_ROLES:
                return True
        return False

    async def q_pop(self, user, channel):
        """
        If a user sends "!q pop" or "!q next",
        removes the next person from the queue
        Must be run by a user with a TA role

        Parameters:
            user: DiscordUser object representing the user who ran the command
            channel: discord.py channel object to send message to

        Returns: True if a user is removed
        """
        # Remove the next person from the queue
        if len(self._queue) == 0:
            await self.send(channel, "Queue is empty")
            return False
        else:
            q_next = self._queue.popleft()
            in_voice = ""
            if self.config.CHECK_VOICE_WAITING:
                in_voice = " (in voice)" if q_next in self.waiting_room.members else " (**not** in voice)"

            await self.send(channel, f"""The next person is {q_next.get_mention()}{in_voice}
Remaining people in the queue: {len(self._queue)}""")
            return True

    async def q_peek(self, user, channel):
        """
        Check to see who is next in line without removing them
        Must be run by a user with a TA role

        Parameters:
            user: DiscordUser object representing the user who ran the command
            channel: discord.py channel object to send message to

        Returns: False (doesn't update queue)
        """
        # See who the next person is without removing them
        if len(self._queue) == 0:
            await self.send(channel, "Queue is empty")
        else:
            await self.send(channel, f"Next in line: {self._queue[0].get_mention()}")

        return False

    async def q_add_other(self, user, mentions, channel):
        """
        Run when a TA calls "!q add @user". It will add the specified user
        to the queue if they are not already in there. A user can only give one
        user at a time (discord's API does not maintain mention order)
        Must be run by a user with a TA role

        Parameters:
            user: DiscordUser object representing the user who ran the command
            mentions: list of mentions from the message object
            channel: discord.py channel object to send message to

        Returns: True if queue is updated; False otherwise
        """
        # Make sure mentions contains only one user
        if len(mentions) != 1:
            await self.send(channel, f"{user.get_mention()} invalid syntax. You must mention the user to add", CmdPrefix.ERROR)
            return False
        else:
            author = mentions[0]
            q_user = DiscordUser(author.id, author.name, author.discriminator, author.nick)

            if q_user in self._queue:
                index = self._queue.index(q_user)
                await self.send(channel, f"{user.get_mention()} That person is already in the queue at position #{index}", CmdPrefix.WARNING)
                return False
            else:
                self._queue.append(q_user)
                await self.send(channel, f"{user.get_mention()} the person has been added at position #{len(self._queue)}", CmdPrefix.SUCCESS)
                return True

    async def q_remove_other(self, user, mentions, channel):
        """
        Run when a TA calls "!q remove @user". It will remove the specified user
        to the queue if they are in the queue. This command can only add one
        user at a time (discord.py does not maintain mention order)
        Doesn't check if user is a TA

        Parameters:
            user: DiscordUser object representing the user who ran the command
            mentions: list of mentions from the message object
            channel: discord.py channel object to send message to

        Returns: True if queue is updated; False otherwise
        """
        if len(mentions) != 1:
            await self.send(channel, f"{user.get_mention()} invalid syntax. You must mention the user to remove", CmdPrefix.ERROR)
            return False
        else:
            author = mentions[0]
            q_user = DiscordUser(author.id, author.name, author.discriminator, author.nick)

            if q_user in self._queue:
                self._queue.remove(q_user)
                await self.send(channel, f"{q_user.get_name()} has been removed from the queue", CmdPrefix.SUCCESS)
                return True
            else:
                await self.send(channel, f"{q_user.get_name()} is not in the queue", CmdPrefix.WARNING)
                return False

    async def q_move_front_other(self, user, mentions, channel):
        """
        Run when a TA calls "!q front @user". It will add the specified user
        to the front of the queue. This command can only add one
        user at a time (discord.py does not maintain mention order)
        Doesn't check if user is a TA

        Parameters:
            user: DiscordUser object representing the user who ran the command
            mentions: list of mentions from the message object
            channel: discord.py channel object to send message to

        Returns: True if queue is updated; False otherwise
        """
        if len(mentions) != 1:
            await self.send(channel, f"{user.get_mention()} invalid syntax. You must mention the user to remove", CmdPrefix.ERROR)
            return False
        else:
            author = mentions[0]
            q_user = DiscordUser(author.id, author.name, author.discriminator, author.nick)

            if q_user in self._queue:
                self._queue.remove(q_user)
            self._queue.appendleft(q_user)

            await self.send(channel, f"{q_user.get_name()} has been moved to the front of the queue", CmdPrefix.SUCCESS)
            return True

    async def q_list(self, user, channel):
        """
        When a user runs "!q list" it will send a discord embed containing the next
        10 people within the list (people past 10 are not shown)

        Parameters:
            user: DiscordUser object representing the user who ran the command
            mentions: list of mentions from the message object
            channel: discord.py channel object to send message to

        Returns: False (doesn't update queue)
        """
        # List the next 10 people within the queue in a nice formatted box (embed)
        # TODO If no one is in the queue, simplify card
        user_list = []
        if len(self._queue) == 0:
            user_list.append("No one in queue")
        else:
            for i in range(0, min(10, len(self._queue))):
                user = self._queue[i]
                in_voice = ""
                if self.config.CHECK_VOICE_WAITING:
                    in_voice = ' ** * **' if user not in self.waiting_room.members else ''  # Bold *
                user_list.append(f"**{i+1}.** {user.get_mention()}{in_voice}")

            if len(self._queue) == 11:
                user_list.append("\n1 other not shown")
            elif len(self._queue) > 11:
                user_list.append(f"\n{len(self._queue)-10} others not shown")

            if self.config.CHECK_VOICE_WAITING:
                user_list.append("\n** * ** = user not in voice channel")

        embed = discord.Embed(title="Queue List", description=f"Total in queue: {len(self._queue)}")
        embed.add_field(name="Next 10 people:", value="\n".join(user_list), inline=False)
        await self.send(channel, embed=embed)
        return False

    async def q_count(self, user, channel):
        """
        If a user sends "!q count" or "!q length",
        return a message with the number of people within the queue
        Can be run by anyone

        Parameters:
            user: DiscordUser object representing the user who ran the command
            channel: discord.py channel object to send message to

        Returns: False (doesn't update queue)
        """
        if len(self._queue) == 1:
            await self.send(channel, f"{user.get_mention()} there is 1 person in the queue")
        else:
            await self.send(channel, f"{user.get_mention()} there are {len(self._queue)} people in the queue")
        return False

    async def q_clear(self, user, channel):
        """
        Asks a confirmation message asking if the user wants to clear the queue
        Must be run by a user with a TA role

        Parameters:
            user: DiscordUser object representing the user who ran the command
            channel: discord.py channel object to send message to

        Returns: True if queue cleared; False otherwise
        """
        def check(reaction, user):
            # Couldn't get self.is_ta() working since it was an asynchronous routine
            has_ta_role = False
            for r in user.roles:
                if r.name in self.config.TA_ROLES:
                    has_ta_role = True
                    break

            if user == self.user or not has_ta_role:
                return False

            if str(reaction.emoji) == '✅':
                return True
            raise asyncio.TimeoutError()

        if len(self._queue) == 0:
            await self.send(channel, "Queue is already empty")
            return False

        if self.testing:
            print("In testing mode; not sending confirmation message")
            self._queue.clear()
            return True

        message = await self.send(channel, """Are you sure you want to clear the queue?
React with ✅ to confirm or ❌ to cancel""")

        await message.add_reaction("✅")
        await message.add_reaction("❌")
        try:
            reaction, user = await self.wait_for('reaction_add', timeout=60.0, check=check)
        except asyncio.TimeoutError:
            await message.edit(content="Clearing queue canceled")
            return False
        else:
            self.logger.info(f"Emptying queue as per {user}'s request...")
            self.logger.debug("Queue prior to clearing: " +
                              ", ".join(str(el) for el in self._queue))
            self._queue.clear()
            await message.edit(content="Queue has been emptied")
            return True



# TODO Move below functions to dedicated file
def get_config_json():
    """
    Opens and ensures config.json config file is valid
    If config.json does not exist, it creates it then exits the program

    Returns: Dictionary with config key/values
    """
    CONFIG_FILE = "config.json"

    # Generate secrets.json if not exist
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            f.write("""{
    "SECRET_TOKEN": "YOUR_SECRET_TOKEN_HERE",
    "TA_ROLES": [],
    "LISTEN_CHANNELS": [],
    "CHECK_VOICE_WAITING": "False",
    "VOICE_WAITING": "",
    "ALERT_ON_FIRST_JOIN": "False",
    "ALERTS_CHANNEL": "",
    "VOICE_OFFICES": []
}""")

        print("config.json not found. Please add your secret token and ensure \
your bot is already in the desired server")
        sys.exit(1)

    # Read secrets.json file
    with open(CONFIG_FILE) as f:
        data = json.load(f)

    return data


def get_config_env():
    """
    Get config values from environment variables.
    Will throw a KeyError if any environment variables do not exist

    Returns: Dictionary with config key/values
    """

    return {
        "SECRET_TOKEN": os.environ["QUEUE_SECRET_TOKEN"],
        "TA_ROLES": os.environ["QUEUE_TA_ROLES"].split(","),
        "LISTEN_CHANNELS": os.environ["QUEUE_LISTEN_CHANNELS"].split(","),
        "VOICE_OFFICES": os.environ["QUEUE_VOICE_OFFICES"].split(","),
        "CHECK_VOICE_WAITING": os.environ.get("QUEUE_CHECK_VOICE_WAITING", "False"),
        "VOICE_WAITING": os.environ.get("QUEUE_VOICE_WAITING", "").strip(),
        "ALERT_ON_FIRST_JOIN": os.environ.get("QUEUE_ALERT_ON_FIRST_JOIN", "False"),
        "ALERTS_CHANNEL": os.environ.get("QUEUE_ALERTS_CHANNEL", "").strip(),
    }


def get_config():
    """
    Get config information required to run QueueBot. First checks to see if environment
    flag variable is set. If not, check (and/or create) config.json file

    Returns: Dictionary with config key/values
    """
    if "QUEUE_USE_ENV" in os.environ:
        return QueueConfig(get_config_env())
    else:
        return QueueConfig(get_config_json())


def setup_loggers():
    """
    Setup queuebot and discord.py loggers

    Returns: queuebot logger
    """
    if not os.path.exists("logs"):
        os.mkdir("logs")

    discord_logger = logging.getLogger("discord")
    discord_logger.setLevel(logging.WARNING)
    queue_logger = logging.getLogger("queuebot")
    queue_logger.setLevel(logging.DEBUG)

    # discord.py file logging
    d_filehandler = logging.handlers.RotatingFileHandler(filename="logs/discord.log", encoding="utf-8", maxBytes=1000000, backupCount=5)
    d_filehandler.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s')
    d_filehandler.setFormatter(formatter)
    discord_logger.addHandler(d_filehandler)

    # queuebot.py console logging
    console = logging.StreamHandler(sys.stdout)
    formater = logging.Formatter('[%(asctime)s] [%(levelname)-8s] %(message)s',
                                 datefmt="%Y-%m-%d %H:%M:%S")
    console.setFormatter(formater)
    queue_logger.addHandler(console)

    # queuebot.py file logging
    q_filehandler = logging.handlers.RotatingFileHandler(filename="logs/queuebot.log", encoding="utf-8", maxBytes=1000000, backupCount=5)
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s')
    q_filehandler.setFormatter(formatter)
    queue_logger.addHandler(q_filehandler)

    return queue_logger


def main():
    queue_logger = setup_loggers()
    config = get_config()
    queue_logger.info("Config:\n" + str(config))

    # Run Bot
    client = QueueBot(config, queue_logger)
    client.run(config.SECRET_TOKEN)


if __name__ == "__main__":
    main()
