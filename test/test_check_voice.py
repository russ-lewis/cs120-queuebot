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
    "CHECK_VOICE_WAITING": "True",
    "VOICE_WAITING": "waiting-room",
    "ALERT_ON_FIRST_JOIN": "False",
    "VOICE_OFFICES": ["Office Hours Room 1", "Office Hours Room 2"],
    "ALERTS_CHANNEL": "queue-alerts",
}
config = QueueConfig(config, test_mode=True)

# TODO Comment each test case

class QueueTest(unittest.TestCase):
    def setUp(self):
        random.seed(SEED)
        self.config = config.copy()
        self.bot = QueueBot(self.config, None, testing=True)
        self.bot.logger = MockLogger()
        self.bot.waiting_room = MockVoice(config.VOICE_WAITING)

    def reset_vc_queue(self):
        # Reset queue
        russ = get_rand_element(ALL_TAS)
        message = MockMessage("!q clear", russ)
        with io.StringIO() as buf, redirect_stdout(buf):
            run(self.bot.queue_command(message))

        self.assertEqual(len(self.bot._queue), 0)

        self.bot.waiting_room.members = []

    def test_one_not_in(self):
        student = get_rand_element(ALL_STUDENTS)

        self.assertEqual(len(self.bot._queue),  0)

        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q join", student)
            run(self.bot.queue_command(message))

        self.assertEqual(len(self.bot._queue), 0)

        self.bot.waiting_room.add_member(student)

        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q join", student)
            run(self.bot.queue_command(message))

        self.assertEqual(len(self.bot._queue),  1)

        self.reset_vc_queue()

    def test_one_not_in2(self):
        num_waiting = 0
        students = get_n_rand(ALL_STUDENTS, 6)
        while len(students) > 0:
            wumpus = students[-1]
            if random.randint(0, 1) == 1:
                students.pop()
                num_waiting += 1
                self.bot.waiting_room.add_member(wumpus)

            with io.StringIO() as buf, redirect_stdout(buf):
                message = MockMessage("!q join", wumpus)
                run(self.bot.queue_command(message))

            self.assertEqual(len(self.bot._queue), num_waiting)

        self.reset_vc_queue()

    def test_q_list(self):
        students = get_n_rand(ALL_STUDENTS, 6)
        self.bot.waiting_room.add_many_members(*students)

        for i in range(len(students)):
            s = students[i]
            with io.StringIO() as buf, redirect_stdout(buf):
                message = MockMessage("!q join", s)
                run(self.bot.queue_command(message))

            did_leave = False
            if random.randint(0, 1) == 1:
                did_leave = True
                # print("Removing")
                self.bot.waiting_room.remove_member(s)

            with io.StringIO() as buf, redirect_stdout(buf):
                message = MockMessage("!q list", s)
                run(self.bot.queue_command(message))

                f_val = buf.getvalue().split(", ")[-1]
                f_val = f_val[:-4].lstrip("value='")  # Get rid of ')]\n at end
                f_val = f_val.split("\\n")
            compare = f"**{i+1}.** {s.get_mention()}" + (" ** * **" if did_leave else "")

            self.assertEqual(compare, f_val[i])

    def test_simple_next_voice(self):
        ta = get_rand_element(ALL_TAS)
        student = get_rand_element(ALL_STUDENTS)

        for i in range(2):
            self.assertEqual(len(self.bot._queue), 0)
            with io.StringIO() as buf, redirect_stdout(buf):
                message = MockMessage("!q next", ta)
                run(self.bot.queue_command(message))

                self.assertEqual("SEND: Queue is empty\n", buf.getvalue())

            self.bot.waiting_room.add_member(student)
            with io.StringIO() as buf, redirect_stdout(buf):
                message = MockMessage("!q join", student)
                run(self.bot.queue_command(message))

            self.assertEqual(len(self.bot._queue), 1)
            if i == 0:
                voice_state = "(in voice)"
            else:
                self.bot.waiting_room.remove_member(student)
                voice_state = "(**not** in voice)"

            with io.StringIO() as buf, redirect_stdout(buf):
                message = MockMessage("!q next", ta)
                run(self.bot.queue_command(message))
                self.assertEqual(f"SEND: The next person is {student.get_mention()} {voice_state}\nRemaining people in the queue: 0\n",
                                buf.getvalue())

            if student in self.bot.waiting_room:
                self.bot.waiting_room.remove_member(student)


if __name__ == '__main__':
    unittest.main()
