"""
Cyberpunk Red Hustle system - rules as written from the core book.

Whenever you have a full seven days free, you can work to earn eb.
Payment depends on Role, Role Ability Rank (1-4, 5-7, 8-10), and the outcome of rolling 1d6.
No DV roll - the 1d6 determines both the activity and payout directly.
"""
import random
from evennia import DefaultScript
from evennia.utils import gametime, create
from evennia.scripts.models import ScriptDB
from evennia.utils import logger
from world.cyberpunk_sheets.services import CharacterMoneyService
from world.hustle_data import HUSTLE_TABLES, get_hustle_result

# Role -> role ability skill name (matches character sheet / db.skills)
ROLE_ABILITIES = {
    "Rockerboy": "charismatic_impact",
    "Solo": "combat_awareness",
    "Netrunner": "interface",
    "Tech": "maker",
    "Medtech": "medicine",
    "Media": "credibility",
    "Exec": "teamwork",
    "Lawman": "backup",
    "Fixer": "operator",
    "Nomad": "moto",
}


def get_character_role(character):
    """Get character's role string."""
    if hasattr(character, "db") and getattr(character.db, "role", None):
        r = character.db.role
        if r:
            return str(r).strip()
    if hasattr(character, "character_sheet") and character.character_sheet:
        return getattr(character.character_sheet, "role", None)
    return None


def _normalize_role(role):
    """Normalize role string to table key (e.g. 'rockerboy' -> 'Rockerboy')."""
    if not role:
        return None
    role_str = str(role).strip()
    for key in ROLE_ABILITIES:
        if key.lower() == role_str.lower():
            return key
    return None


def get_role_ability_rank(character, role):
    """Get the character's Role Ability Rank (1-10) for their role."""
    role_key = _normalize_role(role) or role
    ability = ROLE_ABILITIES.get(role_key)
    if not ability:
        return 0
    # Check character.db.skills first
    skills = getattr(character.db, "skills", None) or {}
    rank = skills.get(ability, 0)
    if rank and isinstance(rank, (int, float)):
        return max(0, min(10, int(rank)))
    # Fall back to character sheet
    if hasattr(character, "character_sheet") and character.character_sheet:
        rank = getattr(character.character_sheet, ability, 0)
        if rank is not None:
            return max(0, min(10, int(rank)))
    return 0


class HustleSystem(DefaultScript):
    """
    Manages the weekly hustle system per Cyberpunk Red core book.
    Characters with 7 days free can attempt a hustle; 1d6 + Role Ability Rank
    determines payout (no DV roll).
    """
    def at_script_creation(self):
        self.key = "HustleSystem"
        self.desc = "Manages weekly hustle side jobs (Cyberpunk Red rules as written)"
        self.interval = 604800  # 1 week in seconds
        self.persistent = True
        self.db.last_attempt = {}  # character_id -> time.time() Unix timestamp of last attempt

    def at_start(self):
        """Initialize last_attempt if missing."""
        if not hasattr(self.db, "last_attempt") or self.db.last_attempt is None:
            self.db.last_attempt = {}

    def at_repeat(self):
        """Weekly tick - fires every 604800s from script creation date.
        The interval drifts from Friday over time so we MUST check the actual
        day before clearing. Clearing on the wrong day (e.g. Sunday) is what
        allows players to hustle twice per week.
        can_attempt_hustle() is the authoritative reset gate -- this only
        clears the dict as a housekeeping measure when it fires on Friday.
        """
        import datetime
        UTC_OFFSET = -8
        now_pst = datetime.datetime.utcnow() + datetime.timedelta(hours=UTC_OFFSET)
        if now_pst.weekday() == 4:  # Friday only
            self.db.last_attempt = {}
            logger.log_info("HustleSystem: Friday reset confirmed. Hustle attempts cleared.")
        else:
            logger.log_info(
                f"HustleSystem: at_repeat fired on {now_pst.strftime('%A')} (not Friday). "                f"Skipping clear -- can_attempt_hustle() handles the reset window."
            )

    def can_attempt_hustle(self, character):
        """
        Check if the character can attempt a hustle this week.
        Resets every Friday at midnight PST (UTC-8 standard, UTC-7 daylight).
        A character can hustle once per reset window.
        """
        import time
        import datetime

        # Determine current Friday midnight PST boundary
        # PST = UTC-8. Use UTC-8 for consistency regardless of daylight saving.
        UTC_OFFSET = -8
        now_utc = datetime.datetime.utcnow()
        now_pst = now_utc + datetime.timedelta(hours=UTC_OFFSET)

        # Find the most recent Friday midnight PST
        # weekday(): Monday=0, Friday=4
        days_since_friday = (now_pst.weekday() - 4) % 7
        last_friday_midnight = now_pst.replace(hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(days=days_since_friday)

        # Convert last Friday midnight PST back to UTC timestamp for comparison
        last_friday_utc = last_friday_midnight - datetime.timedelta(hours=UTC_OFFSET)
        last_friday_ts = last_friday_utc.timestamp()

        last_attempt_ts = self.db.last_attempt.get(character.id, 0)
        return last_attempt_ts < last_friday_ts

    def has_valid_role(self, character):
        """Check if character has a role with a hustle table."""
        role = get_character_role(character)
        if not role:
            return False
        # Normalize role name (e.g. "solo" -> "Solo")
        for key in HUSTLE_TABLES:
            if key.lower() == str(role).lower():
                return True
        return False

    def attempt_hustle(self, character):
        """
        Perform a hustle: roll 1d6, look up result by role and Role Ability Rank, pay character.
        Returns (success_bool, message, roll, rank, eb_earned).
        """
        if not self.can_attempt_hustle(character):
            return False, "You have already attempted your hustle this week. Try again next week.", 0, 0, 0

        role = get_character_role(character)
        if not role:
            return False, "You need a defined role to hustle.", 0, 0, 0

        # Normalize role to table key
        role_key = None
        for key in HUSTLE_TABLES:
            if key.lower() == str(role).lower():
                role_key = key
                break
        if not role_key:
            return False, f"No hustle table for role '{role}'.", 0, 0, 0

        rank = get_role_ability_rank(character, role_key)
        roll = random.randint(1, 100)
        activity, eb = get_hustle_result(role_key, roll, rank)

        if activity is None:
            return False, "An error occurred determining your hustle result.", 0, 0, 0

        # Record attempt - use time.time() (Unix epoch) so it compares correctly
        # against the datetime.timestamp() values in can_attempt_hustle()
        import time
        self.db.last_attempt[character.id] = time.time()

        # Pay character (even if 0 - they still "did" the hustle)
        CharacterMoneyService.add_money(character, eb)

        msg = f"{activity} You earned {eb} eb."
        return True, msg, roll, rank, eb


def get_or_create_hustle_system():
    """Get or create the HustleSystem script."""
    try:
        script = ScriptDB.objects.get(db_key="HustleSystem")
        logger.log_info("Retrieved existing HustleSystem.")
    except ScriptDB.DoesNotExist:
        script = create.create_script(HustleSystem, key="HustleSystem")
        if isinstance(script, bool):
            try:
                script = ScriptDB.objects.get(db_key="HustleSystem")
                logger.log_info("Created new HustleSystem and retrieved it.")
            except ScriptDB.DoesNotExist:
                logger.log_err("Failed to create HustleSystem script.")
                return None
        else:
            logger.log_info("Created new HustleSystem.")
    except ScriptDB.MultipleObjectsReturned:
        scripts = ScriptDB.objects.filter(db_key="HustleSystem")
        script = scripts.first()
        for extra in scripts[1:]:
            extra.delete()
        logger.log_info(f"Multiple HustleSystems found. Kept one and deleted {len(scripts) - 1} extra(s).")

    if script and hasattr(script, "is_active") and callable(script.is_active):
        if not script.is_active():
            script.start()
            logger.log_info("Started inactive HustleSystem.")
    else:
        logger.log_warn("Retrieved script is not a proper HustleSystem instance.")

    return script


def init_hustle_system():
    """Initialize the hustle system at server start (ensures script exists)."""
    get_or_create_hustle_system()
