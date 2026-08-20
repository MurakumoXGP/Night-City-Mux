# -*- coding: utf-8 -*-
"""
Therapy - Medtech Humanity restoration (CP:R core, pg. 229-230).

Once per week (per Medtech, resets Friday midnight PST, any target),
a Medtech (or anyone with Medicine role ability rank > 0) can attempt
Therapy on another character to restore lost Humanity.

Suck-it-up is a homebrew quick-option addition alongside the two canon
tiers (Standard/Extreme); it is not from the core rulebook.

Critical success (natural 10) grants +3 bonus Humanity on top of the
normal roll, on a successful check. Critical failure (natural 1) is an
unconditional bad outcome regardless of the adjusted total: the target
loses 3 Humanity, floored at 1 (Therapy can never drive a character to
0 Humanity).
"""
import random
import traceback

from evennia import Command
from evennia.utils.evmenu import EvMenu
from evennia.utils import logger

from world.therapy_system import get_or_create_therapy_system
from world.therapy_utils import get_therapy_ceiling
from world.cyberpunk_sheets.services import CharacterMoneyService
from world.utils.character_utils import get_technique_value
from world.utils.roll_utils import roll_skill_check, format_roll_details


THERAPY_TIERS = {
    "suckitup": {"label": "Suck-it-up", "cost": 50, "dv": 12, "heal_dice": None, "heal_flat": 1},
    "standard": {"label": "Standard", "cost": 100, "dv": 15, "heal_dice": (2, 6), "heal_flat": None},
    "extreme": {"label": "Extreme", "cost": 500, "dv": 17, "heal_dice": (4, 6), "heal_flat": None},
}

# Target-facing flavor text, keyed by tier and outcome.
CRIT_FAIL_TARGET_MSG = {
    "suckitup": "Turns out 'get over it' was NOT the breakthrough moment your therapist thought it was. You lose 3 Humanity.",
    "standard": "Something about the questions about your mother hit way too close to home. You lose 3 Humanity.",
    "extreme": "The Ludovico technique was maybe not calibrated correctly. You lose 3 Humanity.",
}
CRIT_SUCCESS_TARGET_PREFIX = {
    "suckitup": "Turns out sucking it up WAS actually the breakthrough. Buttercup no more.",
    "standard": "Something clicked, maybe it really was about your mother.",
    "extreme": "You got the good drugs, fancy snacks, and the Ludovico rig didnt even scratch your eyes, Good shit.",
}


def _get_medical_tech_skill(character):
    from world.chargen_constants import get_medical_tech_skill
    return get_medical_tech_skill(
        getattr(character.db, "medicine_pharma", 0),
        getattr(character.db, "medicine_cryo", 0),
    )


def _has_medicine(character):
    role = (getattr(character.db, "role", None) or "").strip()
    if role == "Medtech":
        return True
    skills = getattr(character.db, "skills", None) or {}
    return (skills.get("medicine", 0) or 0) > 0


class CmdTherapy(Command):
    """
    Attempt Therapy on another character to restore lost Humanity.

    Usage:
      therapy <target>

    Only Medtechs (or characters with Medicine role ability rank > 0) can
    run this command. You cannot perform Therapy on yourself. Once
    attempted, successful or not, you cannot attempt Therapy again
    until the weekly reset (Friday midnight PST), regardless of target.

    Opens a menu showing your target's current Humanity, how much of
    their maximum Humanity is depressed by installed cyberware (shown
    only as counts by category, not what the cyberware actually is), and
    lets you choose a Therapy tier to attempt.
    """

    key = "therapy"
    locks = "cmd:all()"
    help_category = "Roleplay Utilities"

    def func(self):
        caller = self.caller
        if not self.args or not self.args.strip():
            caller.msg("Usage: therapy <target>")
            return

        if not _has_medicine(caller):
            caller.msg("Only Medtechs (or those with Medicine role ability) can perform Therapy.")
            return

        target = caller.search(self.args.strip(), global_search=True)
        if not target:
            return

        if target == caller:
            caller.msg(
                "You cant therap yourself choom...Is therap the right verb? "
                "Who cares you still cant do it!"
            )
            return

        sheet = getattr(target, "character_sheet", None)
        if not sheet:
            caller.msg(f"{target.key} doesn't have a character sheet yet.")
            return

        therapy_system = get_or_create_therapy_system()
        if not therapy_system:
            caller.msg("Error: Unable to initialize the Therapy system. Please contact an admin.")
            return

        if not therapy_system.can_attempt_therapy(caller):
            caller.msg("You have already performed Therapy this week. Please try again next week.")
            return

        caller.ndb.therapy_target_id = target.id
        EvMenu(caller, "commands.therapy_commands", startnode="therapy_menu", cmd_on_exit=None)


def therapy_menu(caller):
    """Entry node: show target's cyberware-limited ceiling and offer tiers."""
    logger.log_info(f"Entering therapy_menu for {caller.name}")
    try:
        target_id = caller.ndb.therapy_target_id
        from evennia.objects.models import ObjectDB
        try:
            target = ObjectDB.objects.get(id=target_id)
        except ObjectDB.DoesNotExist:
            caller.msg("Target no longer exists.")
            return "exit_menu"

        sheet = getattr(target, "character_sheet", None)
        if not sheet:
            caller.msg(f"{target.key} doesn't have a character sheet yet.")
            return "exit_menu"

        therapy_system = get_or_create_therapy_system()
        if not therapy_system or not therapy_system.can_attempt_therapy(caller):
            caller.msg("You have already performed Therapy this week. Please try again next week.")
            return "exit_menu"

        ceiling_info = get_therapy_ceiling(sheet)
        tech = get_technique_value(caller) or 0
        medtech_skill = _get_medical_tech_skill(caller)

        text = "|wTherapy!|n\n"
        text += "You have a full seven days free. Time to do some Therapy.\n\n"

        lines = []
        if ceiling_info["standard_count"]:
            lines.append(f"  Standard cyberware: {ceiling_info['standard_count']} piece(s) (-2 each)")
        if ceiling_info["borgware_count"]:
            lines.append(f"  Borgware: {ceiling_info['borgware_count']} piece(s) (-4 each)")
        if lines:
            text += f"{target.key}'s cyberware limits how much Humanity they can regain:\n"
            text += "\n".join(lines) + "\n"
        else:
            text += f"{target.key} has no cyberware depressing their maximum Humanity.\n"
        text += (
            f"  Maximum Humanity restorable via Therapy: {ceiling_info['ceiling']} "
            f"(currently at {sheet.humanity})\n\n"
        )

        text += f"You'll roll TECH ({tech}) + Medical Tech ({medtech_skill}) + 1d10 vs the Therapy's DV.\n\n"
        text += "Therapy resets every Friday at midnight PST.\n\n"
        text += f"Do you want to attempt Therapy on {target.key}?"

        options = (
            {
                "key": ("Suck-it-up", "suckitup", "1"),
                "desc": "Deduct 50eb, DV12 Roll, Restore 1 humanity",
                "goto": "select_suckitup",
            },
            {
                "key": ("Standard", "standard", "2"),
                "desc": "Deduct 100eb, DV15 Roll, Restore up to 2d6 Humanity",
                "goto": "select_standard",
            },
            {
                "key": ("Extreme", "extreme", "3"),
                "desc": "Deduct 500eb, DV17 Roll, Restore up to 4d6 Humanity",
                "goto": "select_extreme",
            },
            {
                "key": ("No", "n"),
                "desc": "Return to the game",
                "goto": "exit_menu",
            },
        )
        return text, options
    except Exception as e:
        logger.log_trace(f"Error in therapy_menu for {caller.name}: {str(e)}\n{traceback.format_exc()}")
        caller.msg("An error occurred while accessing the Therapy menu. Please try again later or contact an admin.")
        return "exit_menu"


def select_suckitup(caller):
    caller.ndb.therapy_tier = "suckitup"
    return "luck_menu"


def select_standard(caller):
    caller.ndb.therapy_tier = "standard"
    return "luck_menu"


def select_extreme(caller):
    caller.ndb.therapy_tier = "extreme"
    return "luck_menu"


def luck_menu(caller):
    """Optional: spend Luck for a +1-per-point bonus on the Therapy roll."""
    tier_key = caller.ndb.therapy_tier
    tier = THERAPY_TIERS[tier_key]
    current_luck = getattr(caller.db, "current_luck", 0) or 0

    if current_luck <= 0:
        caller.ndb.therapy_luck_spend = 0
        return "confirm_and_attempt"

    text = f"|w{tier['label']} Therapy selected.|n (Cost {tier['cost']} eb, DV{tier['dv']})\n\n"
    text += f"You have {current_luck} Luck available. Each point spent adds +1 to your roll.\n"
    text += "Spend Luck on this attempt?\n\n"
    text += "Select |wNo|n to spend none, or type a |wnumber|n for how much Luck to spend."

    options = (
        {"key": ("No", "no", "n", "0"), "desc": "No Luck is spent", "goto": "spend_luck_0"},
        {"key": "<#>", "desc": "Please put in how much Luck you would like to use", "goto": _process_luck_input},
        {"key": "_default", "goto": _process_luck_input},
    )
    return text, options


def _process_luck_input(caller, raw_string, **kwargs):
    raw = raw_string.strip()
    try:
        amount = int(raw)
    except ValueError:
        caller.msg("Invalid number.")
        return "luck_menu"

    current_luck = getattr(caller.db, "current_luck", 0) or 0
    if amount < 0:
        caller.msg("Invalid number.")
        return "luck_menu"
    if amount > current_luck:
        caller.msg("You do not have enough luck for this transaction")
        return "luck_menu"

    caller.ndb.therapy_luck_spend = amount
    return "confirm_and_attempt"


def spend_luck_0(caller):
    caller.ndb.therapy_luck_spend = 0
    return "confirm_and_attempt"


def confirm_and_attempt(caller):
    tier_key = caller.ndb.therapy_tier
    luck_spend = caller.ndb.therapy_luck_spend or 0
    return _run_therapy_attempt(caller, tier_key, luck_spend)


def _run_therapy_attempt(caller, tier_key, luck_spend=0):
    """Roll the check, apply results, notify both parties with distinct messages."""
    logger.log_info(f"Entering _run_therapy_attempt ({tier_key}, luck_spend={luck_spend}) for {caller.name}")
    try:
        tier = THERAPY_TIERS[tier_key]
        target_id = caller.ndb.therapy_target_id
        from evennia.objects.models import ObjectDB
        try:
            target = ObjectDB.objects.get(id=target_id)
        except ObjectDB.DoesNotExist:
            caller.msg("Target no longer exists.")
            return "exit_menu"

        sheet = getattr(target, "character_sheet", None)
        if not sheet:
            caller.msg(f"{target.key} doesn't have a character sheet yet.")
            return "exit_menu"

        balance = CharacterMoneyService.get_balance(caller)
        if balance < tier["cost"]:
            caller.msg(f"You need {tier['cost']} eb for materials (you have {balance} eb).")
            return "exit_menu"

        therapy_system = get_or_create_therapy_system()
        if not therapy_system or not therapy_system.can_attempt_therapy(caller):
            caller.msg("You have already performed Therapy this week. Please try again next week.")
            return "exit_menu"

        # Materials are consumed regardless of success or failure.
        CharacterMoneyService.spend_money(caller, tier["cost"])
        therapy_system.record_attempt(caller)

        tech = get_technique_value(caller) or 0
        medtech_skill = _get_medical_tech_skill(caller)
        total, details = roll_skill_check(
            tech, medtech_skill, luck_spend=luck_spend, character=caller
        )
        # Hitting the DV exactly is a failure (matches world/utils/roll_utils.check_success).
        success = total > tier["dv"]
        is_crit_success = details.get("is_crit_success")
        is_crit_failure = details.get("is_crit_failure")

        breakdown = format_roll_details(details, tech, medtech_skill)
        roll_summary = f"Roll: {breakdown} = {total} vs DV{tier['dv']}"

        # Critical failure is an unconditional bad outcome, independent of
        # whether the (penalty-adjusted) total still cleared the DV.
        if is_crit_failure:
            new_humanity = max(1, sheet.humanity - 3)
            actual_loss = sheet.humanity - new_humanity
            sheet.humanity = new_humanity
            sheet.save()

            caller.msg(
                f"|rSession went sideways.|n {roll_summary} (natural 1). "
                f"Something you said really got to {target.key}. They lost {actual_loss} Humanity. "
                f"Materials ({tier['cost']} eb) wasted."
            )
            if hasattr(target, "msg"):
                target.msg(CRIT_FAIL_TARGET_MSG[tier_key])
            return "exit_menu"

        if not success:
            caller.msg(
                f"|rSession inconclusive.|n {roll_summary}. "
                f"{target.key} made no progress this week. Materials ({tier['cost']} eb) wasted."
            )
            if hasattr(target, "msg"):
                target.msg("You didnt make a breakthrough this week. No Humanity Restored.")
            return "exit_menu"

        ceiling_info = get_therapy_ceiling(sheet)
        if tier["heal_flat"] is not None:
            raw_heal = tier["heal_flat"]
        else:
            dice, sides = tier["heal_dice"]
            raw_heal = sum(random.randint(1, sides) for _ in range(dice))
        if is_crit_success:
            raw_heal += 3

        headroom = max(0, ceiling_info["ceiling"] - sheet.humanity)
        actual_heal = min(raw_heal, headroom)
        sheet.humanity = min(sheet.humanity + actual_heal, ceiling_info["ceiling"])
        sheet.save()

        if is_crit_success:
            caller.msg(
                f"|gBreakthrough session!|n {roll_summary} (natural 10). "
                f"{target.key} had a real breakthrough and regained {actual_heal} Humanity."
            )
        else:
            caller.msg(
                f"|gSession complete.|n {roll_summary}. "
                f"{target.key} regained {actual_heal} Humanity."
            )

        if tier_key == "suckitup":
            base_msg = f"You were told to suck it up buttercup. You restore {actual_heal} humanity."
        elif tier_key == "standard":
            base_msg = (
                f"A week of therapy and talking out your feelings and being asked questions "
                f"about your mother helped you restore {actual_heal} Humanity"
            )
        else:  # extreme
            base_msg = (
                f"Drugs, Safe spaces, and the Ludovico technique focused on questions about "
                f"your mother have helped you restore {actual_heal} Humanity"
            )

        if is_crit_success:
            target_msg = f"{CRIT_SUCCESS_TARGET_PREFIX[tier_key]} You restore {actual_heal} Humanity."
            if actual_heal < raw_heal:
                target_msg += " (capped by your cyberware's limit on maximum Humanity)."
        elif actual_heal < raw_heal:
            target_msg = base_msg + " (capped by your cyberware's limit on maximum Humanity)."
        else:
            target_msg = base_msg + "."

        if hasattr(target, "msg"):
            target.msg(target_msg)

        return "exit_menu"
    except Exception as e:
        logger.log_trace(f"Error in _run_therapy_attempt for {caller.name}: {str(e)}\n{traceback.format_exc()}")
        caller.msg("An error occurred while attempting Therapy. Please try again later or contact an admin.")
        return "exit_menu"


def exit_menu(caller):
    caller.ndb.therapy_target_id = None
    caller.ndb.therapy_tier = None
    caller.ndb.therapy_luck_spend = None
    return None