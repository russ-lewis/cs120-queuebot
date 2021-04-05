import unittest
import asyncio
import random

def run(ctx):
    return asyncio.get_event_loop().run_until_complete(ctx)


SEED = 16516549879132134

random.seed(SEED)


def get_rand_element(list_):
    index = random.randint(0, len(list_) - 1)
    return list_[index]

def get_n_rand(list_, n):
    assert len(list_) >= n

    items = set()
    while len(items) < n:
        items.add(get_rand_element(list_))

    return list(items)

def gen_id(n):
    retval = 0
    for _ in range(n):
        retval = retval * 10 + random.randint(1, 9)

    return retval

class MockLogger:
    def __init__(self):
        pass

    def info(self, str):
        pass

    def debug(self, str):
        pass

class MockRole:
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return self.name == other

    def __str__(self):
        return str(self.name)

    def __repr__(self):
        return f"MockRole('{self.name}')"

class MockAuthor:
    def __init__(self, name, nick, roles=[]):
        self.id = gen_id(18)
        self.name = name
        self.discriminator = str(gen_id(4))
        self.nick = nick
        self.mention = self.get_mention()
        self.roles = [MockRole(r) for r in roles]

    def get_mention(self):
        return f"<@{self.id}>"

    def __eq__(self, other):
        return self.id == other

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return f"MockAuthor('{self.name}')"


class MockMessage:
    def __init__(self, content, author, mentions=None):
        self.content = content
        self.author = author
        self.channel = None
        self.mentions = mentions if mentions is not None else []

class MockVoice:
    def __init__(self, name, members=None):
        self.id = gen_id(18)
        self.name = name
        self.members = members if members is not None else []

    def add_member(self, member):
        assert member not in self.members
        self.members.append(member)

    def add_many_members(self, *args):
        for m in args:
            assert isinstance(m, MockAuthor)
            self.add_member(m)

    def remove_member(self, member):
        assert member in self.members
        self.members.remove(member)

    def remove_many_members(self, members):
        for m in members:
            assert isinstance(m, MockAuthor)
            self.remove_member(m)

    def __len__(self):
        return len(self.members)

    def __contains__(self, item):
        return self.members.__contains__(item)

    def __str__(self):
        return str(self.members)

    def __repr__(self):
        return f"MockVoice('{self.name}', members={self.members})"

TA_NAMES = [
    ("Russ", None),
    ("Nick", None),
    ("Connor", None),
    ("Tyler", None),
    ("Jordan", None),
    ("Kaylee", None),
]

STUDENT_NAMES = [
    ("Wumpus", None),
    ("QuirkyDude", "Very Quirky"),
    ("SigmundNeil", None),
    ("MysticalSchala", None),
    ("CallMeEleven", None),
    ("FlyingOtus", None),
    ("FunnyRabbit", "Hop"),
    ("SmugAlien", None),
    ("CakeIsALie", "I'm a potato"),
    ("SleepyCamel", "5 more minutes"),
    ("PotatoChip", "Tomato Sauce"),
    ("AspiringJumino", None),
    ("DeterminedHuman", None),
    ("BadgerBadgerBadger", "It's a snaaaake!"),
    ("SingingBard", None),
    ("FarerStella", None),
    ("KorokHunter900", None),
    ("SleepyMorizora", "Zzzzzzz"),
    ("IsometricCubes", "ThreeSquared"),
    ("UnderwaterFish", "GlubGlub"),
    ("AnnoyingGoose", "Honk"),
    ("DancingCrab", None),
    ("ExplorerSteve", None),
    ("WanderingPainter", "Heading East"),
]

ALL_STUDENTS = [ MockAuthor(*user) for user in STUDENT_NAMES ]
ALL_TAS = [ MockAuthor(*user, ["UGTA"]) for user in TA_NAMES ]

assert len(set([user.id for user in ALL_STUDENTS])) == len(ALL_STUDENTS), "User IDs not unique"
