import io
import sys
import unittest
import asyncio
import random
from contextlib import redirect_stdout
from .utils import *

from queuebot import QueueBot, QueueConfig, DiscordUser

config = {
    "SECRET_TOKEN": "NOONEWILLEVERGUESSTHISSUPERSECRETSTRINGMWAHAHAHA",
    "TA_ROLES": ["UGTA"],
    "LISTEN_CHANNELS": ["join-queue"],
    "CHECK_VOICE_WAITING": "False",
    "VOICE_WAITING": "waiting-room",
    "ALERT_ON_FIRST_JOIN": "True",
    "VOICE_OFFICES": ["Office Hours Room 1", "Office Hours Room 2", "Office Hours Room 3"],
    "ALERTS_CHANNEL": "queue-alerts",
}
config = QueueConfig(config, test_mode=True)

# TODO Comment each test case

class QueueTest(unittest.TestCase):
    def setUp(self):
        random.seed(SEED)
        self.config = config.copy()
        self.bot = QueueBot(self.config, None, testing=True)
        # self.bot.waiting_room = MockVoice(config.VOICE_WAITING)
        self.bot.logger = MockLogger()
        self.bot.office_rooms = [MockVoice(name) for name in config.VOICE_OFFICES]

    def reset_vc_queue(self):
        # Reset queue
        russ = get_rand_element(ALL_TAS)
        message = MockMessage("!q clear", russ)
        with io.StringIO() as buf, redirect_stdout(buf):
            run(self.bot.queue_command(message))

        self.assertEqual(len(self.bot._queue), 0)

        # Empty voice channels
        for v in self.bot.office_rooms:
            v.members = []

    def test_no_tas(self):
        # No TAs in rooms
        student = get_rand_element(ALL_STUDENTS)

        self.assertEqual(len(self.bot._queue), 0)

        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q join", student)
            run(self.bot.queue_command(message))
            self.assertTrue(buf.getvalue().strip().startswith(
                f"SEND: ✅ {student.get_mention()} you have been added at position #1"))

        self.assertEqual(len(self.bot._queue), 1)

        self.reset_vc_queue()

    def test_one_ta(self):
        ta = get_rand_element(ALL_TAS)
        office_room = get_rand_element(self.bot.office_rooms)
        office_room.members.append(ta)

        student = get_rand_element(ALL_STUDENTS)
        self.assertEqual(len(self.bot._queue), 0)

        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q join", student)
            run(self.bot.queue_command(message))

            self.assertTrue(buf.getvalue().strip().startswith(
                f"SEND: {ta.get_mention()} The queue is no longer empty"))

        self.assertEqual(len(self.bot._queue), 1)

        self.reset_vc_queue()


    def get_mentions_from_send(self, buf):
        send_str = buf.getvalue().strip().split("\n", 1)[0]

        assert send_str.startswith("SEND:")
        assert "<@" in send_str
        assert "The queue is no longer empty" in send_str

        return send_str.lstrip("SEND: ") \
                        .rstrip(" The queue is no longer empty") \
                        .split(" ")

    def test_many_tas_one_room(self):
        tas = get_n_rand(ALL_TAS, 3)
        office_room = get_rand_element(self.bot.office_rooms)
        office_room.members.extend(tas)

        mention_set = set()
        student = get_rand_element(ALL_STUDENTS)
        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q join", student)
            run(self.bot.queue_command(message))
            mentions = self.get_mentions_from_send(buf)
            mention_set.update(mentions)

        for ta in tas:
            self.assertTrue(ta.get_mention() in mention_set)
            mention_set.remove(ta.get_mention())

        self.assertEqual(len(mention_set), 0)

        self.reset_vc_queue()

    def test_many_tas_all_rooms(self):
        tas = get_n_rand(ALL_TAS, 5)
        tas_copy = tas.copy()

        while len(tas) > 0:
            for office_room in self.bot.office_rooms:
                # If we run out of TAs while going through all the rooms
                if len(tas) == 0:
                    break
                office_room.add_member(tas.pop())

        mention_set = set()
        student = get_rand_element(ALL_STUDENTS)
        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q join", student)
            run(self.bot.queue_command(message))
            mentions = self.get_mentions_from_send(buf)
            mention_set.update(mentions)

        for ta in tas_copy:
            self.assertTrue(ta.get_mention() in mention_set)
            mention_set.remove(ta.get_mention())

        self.assertEqual(len(mention_set), 0)

        self.reset_vc_queue()

    def test_ta_with_student(self):
        busy_room, open_room = get_n_rand(self.bot.office_rooms, 2)
        busy_ta, open_ta = get_n_rand(ALL_TAS, 2)
        busy_student, open_student = get_n_rand(ALL_STUDENTS, 2)

        busy_room.add_many_members(busy_ta, busy_student)
        open_room.add_member(open_ta)

        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q join", busy_student)
            run(self.bot.queue_command(message))
            mentions = self.get_mentions_from_send(buf)
        self.assertEqual(mentions, [open_ta.get_mention()])

    def test_ta_with_student2(self):
        rooms = get_n_rand(self.bot.office_rooms, 3)
        busy_rooms = rooms[:-1]
        open_room = rooms[-1]
        busy_ta, open_ta = get_n_rand(ALL_TAS, 2)
        students = [ None ]
        open_student = None

        while open_student in students:
            students = get_n_rand(ALL_STUDENTS, 5)
            open_student = get_rand_element(ALL_STUDENTS)

        busy_rooms[0].add_many_members(busy_ta, *students[:-2])
        busy_rooms[1].add_many_members(busy_ta, *students[-2:])
        open_room.add_member(open_ta)

        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q join", open_student)
            run(self.bot.queue_command(message))

            mentions = self.get_mentions_from_send(buf)
        self.assertEqual(mentions, [open_ta.get_mention()])

    def test_two_tas(self):
        tas = get_n_rand(ALL_TAS, 2)
        rooms = get_n_rand(self.bot.office_rooms, 2)
        rooms[0].add_member(tas[0])
        rooms[1].add_member(tas[1])

        students = get_n_rand(ALL_STUDENTS, 2)

        # Check for both alerted
        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q join", students[0])
            run(self.bot.queue_command(message))
            ta_list = set(self.get_mentions_from_send(buf))

        for ta in tas:
            ta_list.remove(ta.get_mention())
        self.assertEqual(len(ta_list), 0)

        # Remove first student from queue
        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q next", tas[0])
            run(self.bot.queue_command(message))

        self.assertEqual(len(self.bot._queue), 0)

        # First ta helps first student
        rooms[0].add_member(students[0])

        # Another student joins
        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q join", students[1])
            run(self.bot.queue_command(message))
            ta_list = self.get_mentions_from_send(buf)
            self.assertEqual(ta_list, [tas[1].get_mention()])

if __name__ == '__main__':
    unittest.main()
