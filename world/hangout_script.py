"""
Hangout daily script for Night City MUSH.

Two responsibilities:
1. Daily selection -- at midnight picks a random active hangout with a room
   assigned as the featured hangout of the day. Stores featured_hangout_id
   and last_selection_date on self.db.

2. Reward loop -- every 5 minutes checks the featured hangout room. If 2+
   approved players are present, gives each eligible character either EB or
   IP (randomly chosen, not both) after a random 25-45 minute personal timer.
   Only writes to DB when state changes. Prunes stale entries for characters
   who have left or logged out.

Staff override: force_new_hangout(hangout_id) sets featured hangout manually.
Reward ranges: set_rewards(eb_min, eb_max, ip_min, ip_max) called by +hoadmin.

Initialized by world/world_scripts.py via init_hangout_system().
"""

import random
import datetime
from evennia import DefaultScript, create_script
from evennia.scripts.models import ScriptDB
from evennia.utils.logger import log_info, log_err


REWARD_TIMER_MIN = 25 * 60
REWARD_TIMER_MAX = 45 * 60
MIN_PLAYERS = 2


class HangoutFeaturedScript(DefaultScript):

    def at_script_creation(self):
        self.key = "hangout_daily_script"
        self.desc = "Daily hangout selection and reward script"
        self.interval = 300
        self.persistent = True
        self.start_delay = False
        self.db.eb_min = 10
        self.db.eb_max = 50
        self.db.ip_min = 0.5
        self.db.ip_max = 2.0
        self.db.featured_hangout_id = None
        self.db.last_selection_date = None
        self.db.next_reward_time = {}
        self._try_daily_selection()

    def at_start(self):
        self._try_daily_selection()

    def at_repeat(self):
        self._try_daily_selection()
        self._process_rewards()

    def _try_daily_selection(self):
        today = datetime.date.today().isoformat()
        if self.db.last_selection_date == today:
            return
        self._select_random_hangout()
        self.db.last_selection_date = today

    def _select_random_hangout(self):
        try:
            from world.hangouts.models import HangoutDB
            candidates = [
                h for h in HangoutDB.get_all_hangouts()
                if h.db.active and h.db.room is not None
            ]
            if not candidates:
                log_info("HangoutDailyScript: No eligible hangouts for daily selection.")
                self.db.featured_hangout_id = None
                return
            chosen = random.choice(candidates)
            self.db.featured_hangout_id = chosen.db.hangout_id
            log_info(
                f"HangoutDailyScript: Daily featured hangout set to "
                f"#{chosen.db.hangout_id} - {chosen.db.room.key if chosen.db.room else chosen.key}"
            )
        except Exception as e:
            log_err(f"HangoutDailyScript: Error during daily selection: {e}")

    def _process_rewards(self):
        hangout = self.get_featured_hangout()
        if not hangout or not hangout.db.room:
            return

        room = hangout.db.room
        room_name = room.key

        approved_chars = [
            obj for obj in room.contents
            if obj.has_account
            and not obj.tags.get("unapproved", category="approval")
        ]

        if len(approved_chars) < MIN_PLAYERS:
            if self.db.next_reward_time:
                present_ids = {obj.id for obj in approved_chars}
                stale = [cid for cid in self.db.next_reward_time if cid not in present_ids]
                if stale:
                    timers = dict(self.db.next_reward_time)
                    for cid in stale:
                        del timers[cid]
                    self.db.next_reward_time = timers
            return

        import time
        now = time.time()
        timers = dict(self.db.next_reward_time)
        changed = False
        present_ids = {obj.id for obj in approved_chars}

        stale = [cid for cid in timers if cid not in present_ids]
        if stale:
            for cid in stale:
                del timers[cid]
            changed = True

        for char in approved_chars:
            cid = char.id
            if cid not in timers:
                timers[cid] = now + random.randint(REWARD_TIMER_MIN, REWARD_TIMER_MAX)
                changed = True
                continue
            if now < timers[cid]:
                continue
            self._grant_reward(char, hangout, room_name)
            timers[cid] = now + random.randint(REWARD_TIMER_MIN, REWARD_TIMER_MAX)
            changed = True

        if changed:
            self.db.next_reward_time = timers

    def _grant_reward(self, char, hangout, room_name):
        try:
            give_eb = random.choice([True, False])
            if give_eb:
                amount = random.randint(int(self.db.eb_min or 10), int(self.db.eb_max or 50))
                current = char.db.eurodollars or 0
                char.db.eurodollars = current + amount
                char.msg(f"|y[ |wHANGOUT|y ] |nYou earn |w{amount}eb|n for roleplaying at |c{room_name}|n.")
            else:
                amount = round(random.uniform(float(self.db.ip_min or 0.5), float(self.db.ip_max or 2.0)), 1)
                current = char.db.improvement_points or 0.0
                char.db.improvement_points = round(current + amount, 1)
                char.msg(f"|y[ |wHANGOUT|y ] |nYou earn |w{amount} IP|n for roleplaying at |c{room_name}|n.")
        except Exception as e:
            log_err(f"HangoutDailyScript: Error granting reward to {char}: {e}")

    def force_new_hangout(self, hangout_id):
        try:
            from world.hangouts.models import HangoutDB
            hangout = HangoutDB.get_by_hangout_id(hangout_id)
            if not hangout:
                return False, f"No hangout found with ID #{hangout_id}."
            if not hangout.db.room:
                return False, f"Hangout #{hangout_id} has no room set."
            self.db.featured_hangout_id = hangout_id
            self.db.last_selection_date = datetime.date.today().isoformat()
            self.db.next_reward_time = {}
            log_info(f"HangoutDailyScript: Featured hangout manually set to #{hangout_id} - {hangout.db.room.key}")
            return True, hangout
        except Exception as e:
            log_err(f"HangoutDailyScript: Error in force_new_hangout: {e}")
            return False, str(e)

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
        if not self.db.featured_hangout_id:
            return None
        try:
            from world.hangouts.models import HangoutDB
            return HangoutDB.get_by_hangout_id(self.db.featured_hangout_id)
        except Exception:
            return None


def get_or_create_hangout_script():
    try:
        script = ScriptDB.objects.get(db_key="hangout_daily_script")
        return script
    except ScriptDB.DoesNotExist:
        try:
            script = create_script(HangoutFeaturedScript, key="hangout_daily_script")
            return script
        except Exception:
            try:
                return ScriptDB.objects.get(db_key="hangout_daily_script")
            except ScriptDB.DoesNotExist:
                return None
    except ScriptDB.MultipleObjectsReturned:
        scripts = ScriptDB.objects.filter(db_key="hangout_daily_script")
        for s in scripts[1:]:
            s.delete()
        return scripts[0]


def init_hangout_system():
    get_or_create_hangout_script()
