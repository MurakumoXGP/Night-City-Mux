"""
Daily Hangout Script for Night City MUSH.

Manages the daily featured hangout selection and reward system.
- Selects a new featured hangout at midnight PST daily
- Awards eb OR IP to approved players in the featured hangout
  at random intervals per character (25-45 minutes)
- Requires 2+ approved players in the room for rewards
"""
import random
from datetime import datetime
import pytz
from evennia import DefaultScript
from evennia.utils import logger


class HangoutDailyScript(DefaultScript):

    def at_script_creation(self):
        self.key = "hangout_daily_script"
        self.desc = "Manages daily hangout selection and rewards"
        self.interval = 60
        self.persistent = True
        self.db.featured_hangout_id = None
        self.db.last_reset_date = None
        self.db.eb_min = 10
        self.db.eb_max = 50
        self.db.ip_min = 0.5
        self.db.ip_max = 2.0
        self.db.next_reward_times = {}

    def at_repeat(self):
        self._check_daily_reset()
        self._check_rewards()

    def _get_pst_now(self):
        pst = pytz.timezone("America/Los_Angeles")
        return datetime.now(pst)

    def _check_daily_reset(self):
        now = self._get_pst_now()
        today_str = now.strftime("%Y-%m-%d")
        if self.db.last_reset_date == today_str:
            return
        self._select_new_hangout()
        self.db.last_reset_date = today_str

    def _select_new_hangout(self, forced_id=None):
        from world.hangouts.models import HangoutDB

        hangouts = [h for h in HangoutDB.get_all_hangouts() if h.db.active and h.db.room]

        if not hangouts:
            logger.log_info("HangoutScript: No active hangouts available.")
            return

        old_hangout_id = self.db.featured_hangout_id
        old_hangout = None
        if old_hangout_id:
            old_hangout = HangoutDB.get_by_hangout_id(old_hangout_id)

        if forced_id:
            new_hangout = HangoutDB.get_by_hangout_id(forced_id)
            if not new_hangout:
                logger.log_info(f"HangoutScript: Forced hangout ID {forced_id} not found.")
                return
        else:
            choices = [h for h in hangouts if h.db.hangout_id != old_hangout_id]
            if not choices:
                choices = hangouts
            new_hangout = random.choice(choices)

        self.db.featured_hangout_id = new_hangout.db.hangout_id

        # Notify players in old hangout room
        if old_hangout and old_hangout.db.room:
            new_name = new_hangout.key
            new_code = ""
            if new_hangout.db.room and new_hangout.db.room.db.area_code:
                new_code = f" ({new_hangout.db.room.db.area_code})"
            old_hangout.db.room.msg_contents(
                f"|yThe hangout scene has moved! Today it has shifted to "
                f"|w{new_name}|y{new_code}.|n"
            )

        logger.log_info(
            f"HangoutScript: New featured hangout is "
            f"{new_hangout.key} (#{new_hangout.db.hangout_id})"
        )

    def _check_rewards(self):
        from world.hangouts.models import HangoutDB
        from world.cyberpunk_sheets.services import CharacterMoneyService
        from world.utils.character_utils import is_character_approved

        if not self.db.featured_hangout_id:
            return

        hangout = HangoutDB.get_by_hangout_id(self.db.featured_hangout_id)
        if not hangout or not hangout.db.room:
            return

        room = hangout.db.room

        # Get approved players in the room
        players = [
            obj for obj in room.contents
            if obj.has_account and is_character_approved(obj)
        ]

        if len(players) < 2:
            return

        now_ts = datetime.now().timestamp()

        if not self.db.next_reward_times:
            self.db.next_reward_times = {}

        next_times = dict(self.db.next_reward_times)

        for player in players:
            pid = player.id
            next_time = next_times.get(pid, 0)

            if next_time == 0:
                # First time - set initial random timer
                delay = random.randint(25, 45) * 60
                next_times[pid] = now_ts + delay
                continue

            if now_ts < next_time:
                continue

            # Time to reward this player
            self._give_reward(player, hangout.key)

            # Set next reward time
            delay = random.randint(25, 45) * 60
            next_times[pid] = now_ts + delay

        self.db.next_reward_times = next_times

    def _give_reward(self, character, hangout_name):
        from world.cyberpunk_sheets.services import CharacterMoneyService
        from world.improvement_points import get_character_ip, add_ip_log_entry

        give_eb = random.choice([True, False])

        if give_eb:
            amount = random.randint(self.db.eb_min, self.db.eb_max)
            CharacterMoneyService.add_money(character, amount)
            character.msg(f"|yYou do a little Biz for |w{amount}eb|y.|n")
        else:
            amount = round(random.uniform(self.db.ip_min, self.db.ip_max), 1)
            current, spent, staff_awarded, _, _ = get_character_ip(character)
            new_ip = current + amount
            character.attributes.add("improvement_points", new_ip)
            character.attributes.add("ip_staff_awarded", staff_awarded + amount)
            add_ip_log_entry(
                character, amount, "Hangout",
                f"Hangout reward at {hangout_name}"
            )
            character.msg(
                f"|yBeing out and about has some perks, you get |w{amount} IP|y.|n"
            )

    def force_new_hangout(self, hangout_id):
        self._select_new_hangout(forced_id=hangout_id)
        now = self._get_pst_now()
        self.db.last_reset_date = now.strftime("%Y-%m-%d")

    def set_rewards(self, eb_min=None, eb_max=None, ip_min=None, ip_max=None):
        if eb_min is not None:
            self.db.eb_min = eb_min
        if eb_max is not None:
            self.db.eb_max = eb_max
        if ip_min is not None:
            self.db.ip_min = ip_min
        if ip_max is not None:
            self.db.ip_max = ip_max

    def get_featured_hangout(self):
        from world.hangouts.models import HangoutDB
        if not self.db.featured_hangout_id:
            return None
        return HangoutDB.get_by_hangout_id(self.db.featured_hangout_id)