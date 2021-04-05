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
    "ALERT_ON_FIRST_JOIN": "False",
    "VOICE_OFFICES": ["Office Hours Room 1", "Office Hours Room 2"],
    "ALERTS_CHANNEL": "queue-alerts",
}
config = QueueConfig(config, test_mode=True)

# TODO Comment each test case

russ = MockAuthor("Russ", None, ["UGTA"])

class QueueTest(unittest.TestCase):
    def setUp(self):
        random.seed(SEED)
        self.config = config.copy()
        self.bot = QueueBot(self.config, None, testing=True)
        self.bot.logger = MockLogger()
        self.bot.waiting_room = MockVoice("Waiting Room")


    def test_ping(self):
        message = MockMessage("!q ping", get_rand_element(ALL_STUDENTS))

        with io.StringIO() as buf, redirect_stdout(buf):
            run(self.bot.queue_command(message))
            self.assertEqual('SEND: Pong!\n', buf.getvalue())

    def test_simple_join(self):
        command_runner = get_rand_element(ALL_STUDENTS)

        self.assertEqual(len(self.bot._queue), 0)

        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q join", command_runner)
            run(self.bot.queue_command(message))

        self.assertEqual(len(self.bot._queue), 1)

        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q join", command_runner)
            run(self.bot.queue_command(message))

        self.assertEqual(len(self.bot._queue), 1)

    def test_simple_next(self):
        ta = get_rand_element(ALL_TAS)
        student = get_rand_element(ALL_STUDENTS)

        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q next", ta)
            run(self.bot.queue_command(message))

            self.assertEqual("SEND: Queue is empty\n", buf.getvalue())

        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q join", student)
            run(self.bot.queue_command(message))

        self.assertEqual(len(self.bot._queue), 1)

        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q next", ta)
            run(self.bot.queue_command(message))
            self.assertEqual(f"SEND: The next person is {student.get_mention()}\nRemaining people in the queue: 0\n",
                             buf.getvalue())

        self.assertEqual(len(self.bot._queue), 0)

        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q next", ta)
            run(self.bot.queue_command(message))

            self.assertEqual("SEND: Queue is empty\n", buf.getvalue())

    def test_multi_join(self):
        wumpus, quirky, cyber = get_n_rand(ALL_STUDENTS, 3)

        self.assertEqual(len(self.bot._queue),  0)

        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q join", wumpus)
            run(self.bot.queue_command(message))

        self.assertEqual(len(self.bot._queue),  1)

        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q join", quirky)
            run(self.bot.queue_command(message))

        self.assertEqual(len(self.bot._queue),  2)

        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q join", wumpus)
            run(self.bot.queue_command(message))

        self.assertEqual(len(self.bot._queue),  2)

        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q join", cyber)
            run(self.bot.queue_command(message))

        self.assertEqual(len(self.bot._queue),  3)

        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q join", wumpus)
            run(self.bot.queue_command(message))

        self.assertEqual(len(self.bot._queue),  3)

    def test_join_invalids(self):
        wumpus, quirky, cyber, squid = get_n_rand(ALL_STUDENTS, 4)
        self.assertEqual(len(self.bot._queue),  0)

        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q", wumpus)
            run(self.bot.queue_command(message))

        self.assertEqual(len(self.bot._queue),  0)

        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q joint", quirky)
            run(self.bot.queue_command(message))

        self.assertEqual(len(self.bot._queue),  0)

        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q leave", cyber)
            run(self.bot.queue_command(message))

        self.assertEqual(len(self.bot._queue),  0)

        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q leave", squid)
            run(self.bot.queue_command(message))

        self.assertEqual(len(self.bot._queue),  0)

    def test_simple_leave(self):
        wumpus, cyber = get_n_rand(ALL_STUDENTS, 2)
        self.assertEqual(len(self.bot._queue),  0)

        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q leave", wumpus)
            run(self.bot.queue_command(message))

        self.assertEqual(len(self.bot._queue),  0)

        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q join", cyber)
            run(self.bot.queue_command(message))

        self.assertEqual(len(self.bot._queue),  1)

        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q leave", wumpus)
            run(self.bot.queue_command(message))

        self.assertEqual(len(self.bot._queue),  1)

        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q leave", cyber)
            run(self.bot.queue_command(message))

        self.assertEqual(len(self.bot._queue),  0)

    def test_random_joinleave(self):
        q = []
        q_len = 0
        students = ALL_STUDENTS.copy()

        random.shuffle(students)
        for user in students:
            opt = random.randint(0, 1)
            if opt:
                message = MockMessage("!q join", user)
                if user not in q:
                    q_len += 1
                    q.append(user)
            else:
                message = MockMessage("!q leave", user)
                try:
                    index = q.index(user)
                except ValueError:
                    index = -1
                if index >= 0:
                    q_len -= 1
                    q.pop(index)

            with io.StringIO() as buf, redirect_stdout(buf):
                run(self.bot.queue_command(message))
                self.assertEqual(len(self.bot._queue), q_len)

    def test_clear(self):
        students = ALL_STUDENTS.copy()

        random.shuffle(students)
        for max_len in range(len(students)):

            random.shuffle(students)
            for i in range(max_len):
                message = MockMessage("!q join", students[i])
                with io.StringIO() as buf, redirect_stdout(buf):
                    run(self.bot.queue_command(message))

                self.assertEqual(len(self.bot._queue), i+1)

            message = MockMessage("!q clear", russ)
            with io.StringIO() as buf, redirect_stdout(buf):
                run(self.bot.queue_command(message))

            self.assertEqual(len(self.bot._queue), 0)

    def test_position(self):
        students = ALL_STUDENTS.copy()

        with io.StringIO() as buf, redirect_stdout(buf):
            message = MockMessage("!q position", students[0])
            run(self.bot.queue_command(message))
            self.assertEqual(f"SEND: {students[0].get_mention()} you are not in the queue\n", buf.getvalue())

        random.shuffle(students)
        for user in students:
            message = MockMessage("!q join", user)
            with io.StringIO() as buf, redirect_stdout(buf):
                run(self.bot.queue_command(message))

        for i in range(len(students)):
            user = students[i]
            with io.StringIO() as buf, redirect_stdout(buf):
                message = MockMessage("!q position", user)
                run(self.bot.queue_command(message))
                self.assertEqual(f"SEND: {user.get_mention()} you are at position #{i+1}\n", buf.getvalue())

        self.assertEqual(len(students), len(self.bot._queue))

        rand_user = get_rand_element(students)
        message = MockMessage("!q clear", rand_user)
        with io.StringIO() as buf, redirect_stdout(buf):
            run(self.bot.queue_command(message))

        self.assertEqual(len(students), len(self.bot._queue))

        message = MockMessage("!q clear", russ)
        with io.StringIO() as buf, redirect_stdout(buf):
            run(self.bot.queue_command(message))

        self.assertEqual(len(self.bot._queue), 0)

    # TODO Implement
    def test_help(self):
        pass

    def test_small_list(self):
        students = get_n_rand(ALL_STUDENTS, 10)
        random.shuffle(students)

        message = MockMessage("!q list", get_rand_element(students))
        with io.StringIO() as buf, redirect_stdout(buf):
            run(self.bot.queue_command(message))
            self.assertEqual("SEND: None embed.title='Queue List', embed.description=Total in queue: 0, fields=[EmbedProxy(inline=False, name='Next 10 people:', value='No one in queue')]\n",
                             buf.getvalue())

        expected_value = []
        for i in range(len(students)):
            user = students[i]
            # Add user to queue
            message = MockMessage("!q join", user)
            self.bot.waiting_room.members.append(user)
            with io.StringIO() as buf, redirect_stdout(buf):
                run(self.bot.queue_command(message))

            expected_value.append(f"**{i+1}.** {user.get_mention()}")

            with io.StringIO() as buf, redirect_stdout(buf):
                rand_user = get_rand_element(students)
                message = MockMessage("!q list", rand_user)
                run(self.bot.queue_command(message))

                title, description, _, f_name, f_val= buf.getvalue().split(", ")
                f_val = f_val[:-4]  # Get rid of ')]\n at end

            self.assertEqual(f"embed.description=Total in queue: {i+1}", description)
            compare = "value='" + "\\n".join(expected_value)
            self.assertEqual(compare, f_val)

    # TODO Test !q list with more than 10 students

    def test_list_voice_users(self):
        # TODO Test to make sure astrisk by name shows up *ONLY* if they're in the voice room
        pass

    def test_join_remove(self):
        not_queued = ALL_STUDENTS.copy()
        random.shuffle(not_queued)
        queued = []

        while len(not_queued) != 0:
            user = not_queued.pop()
            queued.append(user)

            if random.random() > 0.5:
                message = MockMessage("!q join", user)
            else:
                message = MockMessage("!q add " + user.get_mention(), russ, [user])
            with io.StringIO() as buf, redirect_stdout(buf):
                run(self.bot.queue_command(message))

            if len(not_queued) > 0:
                not_in = get_rand_element(not_queued)
                message = MockMessage("!q remove " + not_in.get_mention(), russ, [not_in])
                with io.StringIO() as buf, redirect_stdout(buf):
                    run(self.bot.queue_command(message))

            self.assertEqual(user.id, self.bot._queue[-1].uuid)
            self.assertEqual(len(queued), len(self.bot._queue))

        random.shuffle(queued)
        for _ in range(len(queued)):
            user = queued.pop()
            if random.random() > 0.5:
                message = MockMessage("!q remove " + user.get_mention(), russ, [user])
            else:
                message = MockMessage("!q leave", user)
            with io.StringIO() as buf, redirect_stdout(buf):
                run(self.bot.queue_command(message))

            self.assertEqual(len(queued), len(self.bot._queue))

        self.assertEqual(0, len(self.bot._queue))

    def test_invalid_join_remove(self):
        not_queued = ALL_STUDENTS.copy()
        random.shuffle(not_queued)

        for user in not_queued:
            # TODO Change into two separate tests (one with !q leave one with !q remove)
            if random.random() > 0.5:
                message = MockMessage("!q remove " + user.get_mention(), russ, [user])
            else:
                message = MockMessage("!q leave", user)

            with io.StringIO() as buf, redirect_stdout(buf):
                run(self.bot.queue_command(message))

        self.assertEqual(0, len(self.bot._queue))

        for i in range(len(not_queued)-1):
            users_add = not_queued[i:i+random.randint(2,3)]
            message = MockMessage("!q add ", russ, users_add)
            with io.StringIO() as buf, redirect_stdout(buf):
                run(self.bot.queue_command(message))

            self.assertEqual(0, len(self.bot._queue))

        for user in not_queued:
            rand_user = get_rand_element(not_queued)
            message = MockMessage("!q add ", user, [rand_user])
            with io.StringIO() as buf, redirect_stdout(buf):
                run(self.bot.queue_command(message))

            self.assertEqual(0, len(self.bot._queue))

    def test_peek(self):
        students = ALL_STUDENTS.copy()
        random.shuffle(students)

        for i in range(len(students)):
            student = students[i]
            message = MockMessage("!q join", student)
            with io.StringIO() as buf, redirect_stdout(buf):
                run(self.bot.queue_command(message))

            self.assertEqual(i+1, len(self.bot._queue))

        q_size = len(students)
        for s in students:
            message = MockMessage("!q peek", russ)
            with io.StringIO() as buf, redirect_stdout(buf):
                run(self.bot.queue_command(message))
                self.assertEqual(f"SEND: Next in line: {s.get_mention()}\n", buf.getvalue())

            q_size -= 1
            message = MockMessage("!q next", russ)
            with io.StringIO() as buf, redirect_stdout(buf):
                run(self.bot.queue_command(message))
                self.assertEqual(f"SEND: The next person is {s.get_mention()}\nRemaining people in the queue: {q_size}\n", buf.getvalue())

        message = MockMessage("!q peek", russ)
        with io.StringIO() as buf, redirect_stdout(buf):
            run(self.bot.queue_command(message))
            self.assertEqual(f"SEND: Queue is empty\n", buf.getvalue())

    def test_count(self):
        students = ALL_STUDENTS.copy()
        random.shuffle(students)

        rand_student = get_rand_element(students)
        message = MockMessage("!q count", rand_student)
        with io.StringIO() as buf, redirect_stdout(buf):
            run(self.bot.queue_command(message))
            self.assertEqual(f"SEND: {rand_student.get_mention()} there are 0 people in the queue\n", buf.getvalue())

        for i in range(len(students)):
            student = students[i]
            message = MockMessage("!q join", student)
            with io.StringIO() as buf, redirect_stdout(buf):
                run(self.bot.queue_command(message))

            rand_student = get_rand_element(students)
            message = MockMessage("!q count", rand_student)
            with io.StringIO() as buf, redirect_stdout(buf):
                run(self.bot.queue_command(message))
                if i == 0:
                    self.assertEqual(f"SEND: {rand_student.get_mention()} there is 1 person in the queue\n", buf.getvalue())
                else:
                    self.assertEqual(f"SEND: {rand_student.get_mention()} there are {i+1} people in the queue\n", buf.getvalue())

    def test_front_simple(self):
        # Add to front when queue is empty queue
        rand_student = get_rand_element(ALL_STUDENTS)
        ta = get_rand_element(ALL_TAS)

        message = MockMessage("!q front " + rand_student.get_mention(), ta, [rand_student])
        with io.StringIO() as buf, redirect_stdout(buf):
            run(self.bot.queue_command(message))
            self.assertEqual(len(self.bot._queue), 1)

        message = MockMessage("!q next", ta)
        with io.StringIO() as buf, redirect_stdout(buf):
            run(self.bot.queue_command(message))
            self.assertEqual(f"SEND: The next person is {rand_student.get_mention()}\nRemaining people in the queue: 0\n",
                             buf.getvalue())

    def test_front_simple2(self):
        # TA moves student to front when list already has two students
        num_students = 4
        front_student, *next_students = get_n_rand(ALL_STUDENTS, num_students+1)

        for student in next_students:
            message = MockMessage("!q join", student)
            with io.StringIO() as buf, redirect_stdout(buf):
                run(self.bot.queue_command(message))
        self.assertEqual(len(self.bot._queue), num_students)

        ta = get_rand_element(ALL_TAS)
        message = MockMessage("!q front " + front_student.get_mention(), ta, [front_student])
        with io.StringIO() as buf, redirect_stdout(buf):
            run(self.bot.queue_command(message))
            self.assertEqual(len(self.bot._queue), num_students+1)

        q_len = num_students
        message = MockMessage("!q next", ta)
        with io.StringIO() as buf, redirect_stdout(buf):
            run(self.bot.queue_command(message))
            self.assertEqual(f"SEND: The next person is {front_student.get_mention()}\nRemaining people in the queue: {q_len}\n",
                            buf.getvalue())

        for student in next_students:
            q_len -= 1
            message = MockMessage("!q next", ta)
            with io.StringIO() as buf, redirect_stdout(buf):
                run(self.bot.queue_command(message))
                self.assertEqual(f"SEND: The next person is {student.get_mention()}\nRemaining people in the queue: {q_len}\n",
                                 buf.getvalue())

        self.assertEqual(len(self.bot._queue), 0)

    def test_front_multiple(self):
        # Run !q front multiple times on empty queue
        num_students = 10
        students = get_n_rand(ALL_STUDENTS, num_students)
        ta = get_rand_element(ALL_TAS)

        for student in students:
            message = MockMessage("!q front " + student.get_mention(), ta, [student])
            with io.StringIO() as buf, redirect_stdout(buf):
                run(self.bot.queue_command(message))

        self.assertEqual(len(self.bot._queue), num_students)

        students = students[::-1]
        for student in students:
            message = MockMessage("!q next", ta)
            with io.StringIO() as buf, redirect_stdout(buf):
                run(self.bot.queue_command(message))
                self.assertTrue(buf.getvalue().startswith(f"SEND: The next person is {student.get_mention()}"))

        self.assertEqual(len(self.bot._queue), 0)

    def test_front_in_queue(self):
        # Calling !q front on last student in queue should move them to the front
        num_students = 5
        ta = get_rand_element(ALL_TAS)
        students = get_n_rand(ALL_STUDENTS, num_students)

        for student in students:
            message = MockMessage("!q add " + student.get_mention(), ta, [student])
            with io.StringIO() as buf, redirect_stdout(buf):
                run(self.bot.queue_command(message))

        self.assertEqual(len(self.bot._queue), num_students)

        student = students[-1]
        message = MockMessage("!q front " + student.get_mention(), ta, [student])
        with io.StringIO() as buf, redirect_stdout(buf):
            run(self.bot.queue_command(message))

        self.assertEqual(len(self.bot._queue), num_students)

        message = MockMessage("!q next", ta)
        with io.StringIO() as buf, redirect_stdout(buf):
            run(self.bot.queue_command(message))
            self.assertTrue(buf.getvalue().startswith(f"SEND: The next person is {student.get_mention()}"))

        self.assertEqual(len(self.bot._queue), num_students-1)

    # TODO Test q front with a student in the middle of the queue

    # TODO Test a variety of invalid commands

if __name__ == '__main__':
    unittest.main()
