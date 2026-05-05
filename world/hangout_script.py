"""
Hangout daily script for Night City MUSH.

Runs daily at midnight server time. Randomly selects an active hangout
with a room assigned as the featured hangout of the day. Exposes
force_new_hangout() for staff to manually override the selection.

Initialized by world/world_scripts.py via init_hangout_system().
"""

import random
import datetime
from evennia import DefaultScript, create_script
from evennia.scripts.models import ScriptDB
from evennia.utils.logger import log_info, log_err


class HangoutFeaturedScript(DefaultScript):
    """
    Daily script that picks a random featured hangout at midnight.
    Staff can override with force_new_hangout(hangout_id).
    """

    def at_script_creation(self):
        self.key = "hangout_daily_script"
        self.desc = "Daily hangout selection script"
        self.interval = 3600  # Check every hour; midnight logic handled in at_repeat
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

        # Run immediately on creation to set today's hangout
        self._try_daily_selection()

    def at_start(self):
        """Called when the script starts or server restarts."""
        self._try_daily_selection()

    def at_repeat(self):
        """Called every hour. Triggers new selection if date has changed."""
        self._try_daily_selection()

    def _try_daily_selection(self):
        """
        Select a new featured hangout if we have not done so today.
        Uses server local date. Fires at most once per calendar day.
        """
        today = datetime.date.today().isoformat()
        if self.db.last_selection_date == today:
            return  # Already selected today

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
                f"#{chosen.db.hangout_id} - {chosen.key}"
            )
        except Exception as e:
            log_err(f"HangoutDailyScript: Error during daily selection: {e}")

    def force_new_hangout(self, hangout_id):
        """
        Staff override. Set the featured hangout by hangout_id.
        Also updates last_selection_date so the daily auto-pick
        will not overwrite this until tomorrow.

        Args:
            hangout_id (int): The hangout_id to set as featured.
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
            log_info(
                f"HangoutDailyScript: Featured hangout manually set to "
                f"#{hangout_id} - {hangout.key}"
            )
            return True, hangout
        except Exception as e:
            log_err(f"HangoutDailyScript: Error in force_new_hangout: {e}")
            return False, str(e)

    def set_rewards(self, eb_min=None, eb_max=None, ip_min=None, ip_max=None):
        """Update reward ranges."""
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
