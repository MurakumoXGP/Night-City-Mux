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


# Reward timer bounds in seconds
REWARD_TIMER_MIN = 25 * 60   # 25 minutes
REWARD_TIMER_MAX = 45 * 60   # 45 minutes

# Minimum approved players required in room to trigger rewards
MIN_PLAYERS = 2


class HangoutFeaturedScript(DefaultScript):
    """
    Daily selection + 5-minute reward loop for the featured hangout.
    """

    def at_script_creation(self):
        self.key = "hangout_daily_script"
        self.desc = "Daily hangout selection and reward script"
        self.interval = 300   # 5 minutes
        self.persistent = True
        self.start_delay = False

        # Default reward ranges
        self.db.eb_min = 10
        self.db.eb_max = 50
        self.db.ip_min = 0.5
        self.db.ip_max = 2.0

        # Featured hangout
        self.db.featured_hangout_id = None
        self.db.last_selection_date = None

        # Reward timers: {character_id: server_timestamp_when_reward_fires}
        # Only written when a character enters or receives a reward.
        self.db.next_reward_time = {}

        self._try_daily_selection()

    def at_start(self):
        """Called when the script starts or server restarts."""
        self._try_daily_selection()

    def at_repeat(self):
        """Called every 5 minutes. Runs daily selection check then reward loop."""
        self._try_daily_selection()
        self._process_rewards()

    # ------------------------------------------------------------------
    # Daily selection
    # ------------------------------------------------------------------

    def _try_daily_selection(self):
        """
        Select a new featured hangout if we have not done so today.
        Fires at most once per calendar day.
        """
        today = datetime.date.today().isoformat()
        if self.db.last_selection_date == today:
            return

        self._select_random_hangout()
        self.db.last_selection_date = today

    def _select_random_hangout(self):
        """
        Pick a random active hangout that has a room assigned.
        Stores its hangout_id as the featured hangout.
        """
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

    # ------------------------------------------------------------------
    # Reward loop
    # ------------------------------------------------------------------

    def _process_rewards(self):
        """
        Every 5 minutes:
        - Find the featured hangout room.
        - Bail out if fewer than MIN_PLAYERS approved characters are present.
        - For each eligible character, check if their personal timer has fired.
        - Award EB or IP (randomly chosen, not both) and reset their timer.
        - Prune stale entries for characters no longer in the room.
        """
        hangout = self.get_featured_hangout()
        if not hangout or not hangout.db.room:
            return

        room = hangout.db.room
        room_name = room.key

        # Approved, logged-in characters currently in the room
        approved_chars = [
            obj for obj in room.contents
            if obj.has_account
            and not obj.tags.get("unapproved", category="approval")
        ]

        if len(approved_chars) < MIN_PLAYERS:
            # Not enough players -- prune any stale timers and return
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

        # Prune stale entries for characters no longer present
        stale = [cid for cid in timers if cid not in present_ids]
        if stale:
            for cid in stale:
                del timers[cid]
            changed = True

        for char in approved_chars:
            cid = char.id

            if cid not in timers:
                # New arrival -- assign a personal reward timer
                timers[cid] = now + random.randint(REWARD_TIMER_MIN, REWARD_TIMER_MAX)
                changed = True
                continue

            if now < timers[cid]:
                # Timer has not fired yet
                continue

            # Timer fired -- award EB or IP, not both
            self._grant_reward(char, hangout, room_name)

            # Reset timer for next cycle
            timers[cid] = now + random.randint(REWARD_TIMER_MIN, REWARD_TIMER_MAX)
            changed = True

        if changed:
            self.db.next_reward_time = timers

    def _grant_reward(self, char, hangout, room_name):
        """
        Award either EB or IP to a character. Randomly chooses one.
        Updates the character's sheet and sends a notification message.
        """
        try:
            give_eb = random.choice([True, False])

            if give_eb:
                amount = random.randint(
                    int(self.db.eb_min or 10),
                    int(self.db.eb_max or 50)
                )
                current = char.db.eurodollars or 0
                char.db.eurodollars = current + amount
                char.msg(
                    f"|y[ |wHANGOUT|y ] |n"
                    f"You earn |w{amount}eb|n for roleplaying at "
                    f"|c{room_name}|n."
                )
            else:
                amount = round(
                    random.uniform(
                        float(self.db.ip_min or 0.5),
                        float(self.db.ip_max or 2.0)
                    ), 1
                )
                current = char.db.improvement_points or 0.0
                char.db.improvement_points = round(current + amount, 1)
                char.msg(
                    f"|y[ |wHANGOUT|y ] |n"
                    f"You earn |w{amount} IP|n for roleplaying at "
                    f"|c{room_name}|n."
                )

        except Exception as e:
            log_err(f"HangoutDailyScript: Error granting reward to {char}: {e}")

    # ------------------------------------------------------------------
    # Staff interface
    # ------------------------------------------------------------------

    def force_new_hangout(self, hangout_id):
        """
        Staff override. Set the featured hangout by hangout_id.
        Updates last_selection_date so daily auto-pick will not overwrite
        this until tomorrow.

        Args:
            hangout_id (int): The hangout_id to set as featured.

        Returns:
            (True, hangout) on success, (False, error_string) on failure.
        """
        try:
            from world.hangouts.models import HangoutDB
            hangout = HangoutDB.get_by_hangout_id(hangout_id)
            if not hangout:
                return False, f"No hangout found with ID #{hangout_id}."
            if not hangout.db.room:
                return False, f"Hangout #{hangout_id} has no room set."

            self.db.featured_hangout_id = hangout_id
            self.db.last_selection_date = datetime.date.today().isoformat()
            # Clear existing timers so the new room starts fresh
            self.db.next_reward_time = {}

            log_info(
                f"HangoutDailyScript: Featured hangout manually set to "
                f"#{hangout_id} - {hangout.db.room.key}"
            )
            return True, hangout
        except Exception as e:
            log_err(f"HangoutDailyScript: Error in force_new_hangout: {e}")
            return False, str(e)

    def set_rewards(self, eb_min=None, eb_max=None, ip_min=None, ip_max=None):
        """Update reward ranges. Called by +hoadmin/setrewards."""
        if eb_min is not None:
            self.db.eb_min = eb_min
        if eb_max is not None:
            self.db.eb_max = eb_max
        if ip_min is not None:
            self.db.ip_min = ip_min
        if ip_max is not None:
            self.db.ip_max = ip_max

    def get_featured_hangout(self):
        """
        Return the current featured HangoutDB object, or None.
        """
        if not self.db.featured_hangout_id:
            return None
        try:
            from world.hangouts.models import HangoutDB
            return HangoutDB.get_by_hangout_id(self.db.featured_hangout_id)
        except Exception:
            return None


# ------------------------------------------------------------------
# Initialization helpers
# ------------------------------------------------------------------

def get_or_create_hangout_script():
    """
    Get the existing hangout_daily_script or create it if it does not exist.
    Safe to call multiple times.
    """
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
    """Initialize the hangout system at server start."""
    get_or_create_hangout_script()
