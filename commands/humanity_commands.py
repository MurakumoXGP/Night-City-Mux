"""
Humanity tracking commands.

+humanity <name>               - View a character's humanity (staff only)
+humanity/set <name>=<current> - Set current humanity (staff only)
+humanity/restore <name>=<amt> - Restore humanity by amount, up to max (staff only)
+humanity/lose <name>=<amt>    - Remove humanity by amount (staff only)
"""

from evennia.commands.default.muxcommand import MuxCommand
from world.cyberpunk_sheets.models import CharacterSheet
from world.utils.formatting import header, footer


def _get_sheet(caller, name):
    """Resolve character name to sheet. Returns (character, sheet) or (None, None)."""
    target = caller.search(name, global_search=True)
    if not target:
        return None, None
    if not hasattr(target, "character_sheet") or not target.character_sheet:
        caller.msg(f"{target.key} has no character sheet.")
        return None, None
    return target, target.character_sheet


def _humanity_max(sheet):
    """Maximum humanity = override if set, else empathy * 10."""
    override = getattr(sheet, "humanity_max_override", None)
    if override is not None:
        return int(override)
    empathy = getattr(sheet, "empathy", None) or getattr(sheet, "db", None) and getattr(sheet.db, "empathy", None)
    if empathy is None:
        empathy = 1
    return int(empathy) * 10


def _humanity_current(character, sheet):
    """Current humanity from sheet, falling back to character db."""
    val = getattr(sheet, "humanity", None)
    if val is None:
        val = getattr(character.db, "humanity", None)
    return int(val) if val is not None else _humanity_max(sheet)


def _set_humanity(character, sheet, value):
    """Write humanity value to both sheet and character db."""
    value = max(0, value)
    sheet.humanity = value
    sheet.save(skip_recalculation=True)
    character.db.humanity = value


class CmdHumanity(MuxCommand):
    """
    View and adjust a character's humanity. Admin only.

    Usage:
      +humanity <name>               - View humanity status
      +humanity/set <name>=<value>   - Set current humanity to exact value
      +humanity/restore <name>=<amt> - Restore humanity by amount (capped at max)
      +humanity/lose <name>=<amt>    - Remove humanity by amount (minimum 0)
      +humanity/max <name>=<value>   - Override humanity maximum (staff only)
      +humanity/max <name>=clear     - Remove override, restore Empathy x 10

    The normal humanity maximum is Empathy x 10. Use /max to set a permanent
    staff override for plot-driven permanent empathy damage. The override
    persists through cyberware changes and recalculations. Use /max clear
    to restore normal Empathy-based calculation.

    Examples:
      +humanity Kimmy
      +humanity/restore Kimmy=10
      +humanity/lose Kimmy=5
      +humanity/set Kimmy=35
      +humanity/max Kimmy=30
      +humanity/max Kimmy=clear
    """

    key = "+humanity"
    aliases = ["humanity"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        caller = self.caller
        switches = [s.lower() for s in self.switches] if self.switches else []

        if "set" in switches:
            self._do_set()
        elif "restore" in switches:
            self._do_restore()
        elif "lose" in switches:
            self._do_lose()
        elif "max" in switches:
            self._do_max()
        else:
            self._do_view()

    def _do_view(self):
        """Display humanity status for a character."""
        if not self.args:
            self.caller.msg("Usage: +humanity <name>")
            return
        character, sheet = _get_sheet(self.caller, self.args.strip())
        if not sheet:
            return

        current = _humanity_current(character, sheet)
        maximum = _humanity_max(sheet)
        empathy = getattr(sheet, "empathy", 1) or 1

        output = header(f"Humanity - {character.key}", width=60, fillchar="|m=|n")
        output += f"\n|yEmpathy:|n         {empathy}\n"
        override = getattr(sheet, "humanity_max_override", None)
        max_label = f"{maximum}"
        output += f"|yHumanity Maximum:|n {max_label}\n"
        output += f"|yHumanity Current:|n {current}/{maximum}\n"

        # Compute humanity loss breakdown
        cw_loss = getattr(sheet, "total_cyberware_humanity_loss", 0) or 0
        trauma_loss = getattr(sheet, "trauma_humanity_loss", 0) or 0
        total_loss = maximum - current
        output += f"|yTotal HL:|n        {total_loss} ({cw_loss} cyberware, {trauma_loss} trauma)\n"
        output += footer(width=60, fillchar="|m=|n")
        self.caller.msg(output)

    def _do_set(self):
        """Set current humanity to an exact value."""
        if not self.lhs or not self.rhs:
            self.caller.msg("Usage: +humanity/set <name>=<value>")
            return
        character, sheet = _get_sheet(self.caller, self.lhs.strip())
        if not sheet:
            return
        try:
            value = int(self.rhs.strip())
        except ValueError:
            self.caller.msg("Value must be a whole number.")
            return
        if value < 0:
            self.caller.msg("Humanity cannot be negative.")
            return

        maximum = _humanity_max(sheet)
        if value > maximum:
            self.caller.msg(f"Cannot set humanity above maximum ({maximum} = Empathy {getattr(sheet, 'empathy', 1)} x 10). Setting to {maximum}.")
            value = maximum

        old = _humanity_current(character, sheet)
        _set_humanity(character, sheet, value)
        self.caller.msg(f"Set {character.key}'s humanity to {value}/{maximum} (was {old}/{maximum}).")
        if character.sessions.all():
            character.msg(f"|yStaff has adjusted your humanity to {value}/{maximum}.|n")

    def _do_restore(self):
        """Restore humanity by an amount, capped at max."""
        if not self.lhs or not self.rhs:
            self.caller.msg("Usage: +humanity/restore <name>=<amount>")
            return
        character, sheet = _get_sheet(self.caller, self.lhs.strip())
        if not sheet:
            return
        try:
            amount = int(self.rhs.strip())
        except ValueError:
            self.caller.msg("Amount must be a whole number.")
            return
        if amount <= 0:
            self.caller.msg("Amount must be positive.")
            return

        maximum = _humanity_max(sheet)
        current = _humanity_current(character, sheet)
        new_val = min(maximum, current + amount)
        actual_gain = new_val - current

        if actual_gain <= 0:
            self.caller.msg(f"{character.key}'s humanity is already at maximum ({maximum}/{maximum}).")
            return

        _set_humanity(character, sheet, new_val)
        self.caller.msg(f"Restored {actual_gain} humanity for {character.key}. Now {new_val}/{maximum} (was {current}/{maximum}).")
        if character.sessions.all():
            character.msg(f"|gYour humanity has been restored by {actual_gain} points. Now {new_val}/{maximum}.|n")

    def _do_max(self):
        """Set or clear the humanity maximum override."""
        if not self.lhs or not self.rhs:
            self.caller.msg("Usage: +humanity/max <name>=<value>  OR  +humanity/max <name>=clear")
            return
        character, sheet = _get_sheet(self.caller, self.lhs.strip())
        if not sheet:
            return

        raw = self.rhs.strip().lower()
        if raw == "clear":
            sheet.humanity_max_override = None
            # Recalculate current humanity against natural ceiling
            natural = int(getattr(sheet, "empathy", 1) or 1) * 10
            current = _humanity_current(character, sheet)
            if current > natural:
                _set_humanity(character, sheet, natural)
            else:
                sheet.save(skip_recalculation=True)
            self.caller.msg(
                f"Cleared humanity max override for {character.key}. "
                f"Maximum is now {natural} (Empathy {getattr(sheet, 'empathy', 1) or 1} x 10)."
            )
            if character.sessions.all():
                character.msg("|yYour humanity maximum has been restored to your natural limit.|n")
            return

        try:
            value = int(raw)
        except ValueError:
            self.caller.msg("Value must be a whole number or 'clear'.")
            return
        if value < 0:
            self.caller.msg("Humanity maximum cannot be negative.")
            return
        if value > 100:
            self.caller.msg("Humanity maximum cannot exceed 100.")
            return

        natural = int(getattr(sheet, "empathy", 1) or 1) * 10
        sheet.humanity_max_override = value
        # If current humanity exceeds new max, cap it
        current = _humanity_current(character, sheet)
        if current > value:
            _set_humanity(character, sheet, value)
        else:
            sheet.save(skip_recalculation=True)

        self.caller.msg(
            f"Set {character.key}'s humanity maximum to |w{value}|n. "
            f"Current humanity: {min(current, value)}/{value}."
        )
        if character.sessions.all():
            character.msg(
                f"|yStaff has set your humanity maximum to {value}. "
                f"Current: {min(current, value)}/{value}.|n"
            )

    def _do_lose(self):
        """Remove humanity by an amount, minimum 0."""
        if not self.lhs or not self.rhs:
            self.caller.msg("Usage: +humanity/lose <name>=<amount>")
            return
        character, sheet = _get_sheet(self.caller, self.lhs.strip())
        if not sheet:
            return
        try:
            amount = int(self.rhs.strip())
        except ValueError:
            self.caller.msg("Amount must be a whole number.")
            return
        if amount <= 0:
            self.caller.msg("Amount must be positive.")
            return

        maximum = _humanity_max(sheet)
        current = _humanity_current(character, sheet)
        new_val = max(0, current - amount)
        actual_loss = current - new_val

        _set_humanity(character, sheet, new_val)
        self.caller.msg(f"Removed {actual_loss} humanity from {character.key}. Now {new_val}/{maximum} (was {current}/{maximum}).")
        if character.sessions.all():
            character.msg(f"|rYour humanity has decreased by {actual_loss} points. Now {new_val}/{maximum}.|n")
