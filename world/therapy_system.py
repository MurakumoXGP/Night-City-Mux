# -*- coding: utf-8 -*-
"""
Therapy weekly cooldown tracking.

Mirrors world/hustle_system.py's cooldown approach: real wall-clock
timestamps compared against the most recent Friday-midnight-PST boundary,
NOT evennia.utils.gametime (gametime is absolute game time, not real time,
and using it here would reproduce the exact bug already fixed for Hustle --
characters being able to act unlimited times per "week").
"""
import datetime

from evennia import DefaultScript, create_script
from evennia.scripts.models import ScriptDB
from evennia.utils import logger

THERAPY_SCRIPT_KEY = "TherapySystem"
UTC_OFFSET = -8  # PST, standard offset (matches HustleSystem's convention)


class TherapySystem(DefaultScript):
    """
    Tracks each Medtech's last Therapy attempt. Resets every Friday at
    midnight PST -- a Medtech may perform Therapy on at most one patient
    per reset window, regardless of target.
    """

    def at_script_creation(self):
        self.key = THERAPY_SCRIPT_KEY
        self.desc = "Tracks weekly Therapy cooldown per Medtech"
        self.interval = 3600  # hourly housekeeping tick
        self.persistent = True
        self.repeats = -1
        self.db.last_attempt = {}

    def at_repeat(self):
        now_pst = datetime.datetime.utcnow() + datetime.timedelta(hours=UTC_OFFSET)
        if now_pst.weekday() == 4:  # Friday
            self.db.last_attempt = {}
            logger.log_info("TherapySystem: Friday reset confirmed. Therapy attempts cleared.")

    def can_attempt_therapy(self, character):
        """
        True if this Medtech has not yet performed Therapy since the most
        recent Friday midnight PST.
        """
        now_utc = datetime.datetime.utcnow()
        now_pst = now_utc + datetime.timedelta(hours=UTC_OFFSET)

        days_since_friday = (now_pst.weekday() - 4) % 7
        last_friday_midnight = now_pst.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - datetime.timedelta(days=days_since_friday)
        last_friday_utc = last_friday_midnight - datetime.timedelta(hours=UTC_OFFSET)
        last_friday_ts = last_friday_utc.timestamp()

        last_attempt_ts = (self.db.last_attempt or {}).get(character.id, 0)
        return last_attempt_ts < last_friday_ts

    def record_attempt(self, character):
        """Mark this Medtech as having used their Therapy attempt this week."""
        last_attempt = dict(self.db.last_attempt or {})
        last_attempt[character.id] = datetime.datetime.utcnow().timestamp()
        self.db.last_attempt = last_attempt


def get_or_create_therapy_system():
    """Get or create the singleton TherapySystem script."""
    try:
        script = ScriptDB.objects.get(db_key=THERAPY_SCRIPT_KEY)
    except ScriptDB.DoesNotExist:
        script = create_script(TherapySystem, key=THERAPY_SCRIPT_KEY)
    except ScriptDB.MultipleObjectsReturned:
        scripts = ScriptDB.objects.filter(db_key=THERAPY_SCRIPT_KEY)
        script = scripts.first()
        for extra in scripts[1:]:
            extra.delete()
    if script and not script.is_active:
        script.start()
    return script
