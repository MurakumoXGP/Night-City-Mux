"""
typeclasses/landing.py

The Landing Room is the first room new characters enter on Night City MUSH.
It displays server policy and blocks all movement until the player types
+agree to confirm they have read and will follow the rules.

Once agreed, the policy_agreed attribute is set on the character and the
lock cmdset is removed. The character may then proceed to chargen.
"""

from evennia import CmdSet, DefaultRoom
from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils import logger


# ---------------------------------------------------------------------------
# +agree command
# ---------------------------------------------------------------------------

class CmdAgree(MuxCommand):
    """
    Agree to the Night City MUSH rules and policies.

    Usage:
      +agree

    You must type +agree before you can leave this room. By doing so
    you confirm that you have read the server rules at
    https://nightcitymux.com/index.php?title=Policy
    and agree to abide by them. This is recorded on your character.
    """

    key = "+agree"
    aliases = ["agree"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        char = self.caller
        if char.attributes.get("policy_agreed"):
            char.msg("|yYou have already agreed to the rules.|n")
            return

        char.attributes.add("policy_agreed", True)

        # Remove the landing lock cmdset
        char.cmdset.delete("typeclasses.landing.LandingLockedCmdSet")

        char.msg(
            "\n|m=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=|n\n"
            "|gAgreement recorded.|n Welcome to Night City, choomba.\n"
            "You may now proceed to |wChargen|n to build your character,\n"
            "or type |wlook|n to take in your surroundings.\n"
            "|m=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=|n\n"
        )
        logger.log_info(f"Policy agreed by: {char.key}")


# ---------------------------------------------------------------------------
# Block cmdset -- added to characters in the landing room until they agree
# ---------------------------------------------------------------------------

class CmdBlockMovement(MuxCommand):
    """Intercepts all movement attempts until policy is agreed to."""

    key = "north"
    aliases = [
        "south", "east", "west", "up", "down",
        "ne", "nw", "se", "sw",
        "out", "in", "leave", "go",
        "chargen", "ooc", "ic",
    ]
    locks = "cmd:all()"
    help_category = "General"
    auto_help = False

    def func(self):
        self.caller.msg(
            "|rYou cannot leave until you have agreed to the server rules.|n\n"
            "Type |w+agree|n to confirm you have read and will follow the rules.\n"
            "Full policy: |chttps://nightcitymux.com/index.php?title=Policy|n"
        )


class LandingLockedCmdSet(CmdSet):
    """
    CmdSet applied to characters who have not yet agreed to policy.
    Blocks movement and provides only +agree and basic look/help commands.
    """
    key = "LandingLockedCmdSet"
    priority = 15  # High priority to override default movement commands
    mergetype = "Replace"
    no_exits = True

    def at_cmdset_creation(self):
        self.add(CmdAgree())
        self.add(CmdBlockMovement())


# ---------------------------------------------------------------------------
# Landing Room typeclass
# ---------------------------------------------------------------------------

class LandingRoom(DefaultRoom):
    """
    The first room new characters enter. Applies the LandingLockedCmdSet
    to any character who has not yet agreed to policy. Once +agree is
    typed the cmdset is removed and they are free to move.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.desc = self._build_desc()

    def _build_desc(self):
        return (
            "|m=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=|n\n"
            "|y[ NIGHT CITY MUSH -- WELCOME ]|n\n"
            "|m=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=|n\n"
            "\n"
            "  You are standing at the edge of Night City. The skyline bleeds\n"
            "  neon against a permanent overcast -- somewhere out there, people\n"
            "  are running jobs, pulling chrome, and dying for eddies. Before\n"
            "  you hit the streets, you need to know the rules.\n"
            "\n"
            "|m---------------------------------------------------------------|n\n"
            "|y  SERVER POLICY -- READ BEFORE PROCEEDING|n\n"
            "|m---------------------------------------------------------------|n\n"
            "\n"
            "  |w1.|n  Treat all players with respect. OOC harassment is grounds\n"
            "       for immediate removal.\n"
            "  |w2.|n  Separate IC and OOC. What happens in-game stays in-game.\n"
            "  |w3.|n  Play Fair: No metagaming, no OOC info used IC.\n"
            "  |w4.|n  Staff decisions are final. Bring disputes to +jobs/+requests.\n"
            "  |w5.|n  Adult content requires consent of all parties involved\n"
            "       and must be kept to private areas.\n"
            "  |w6.|n  All characters must be 16+. Any images used must be\n"
            "       legal within the territories of the USA.\n"
            "  |w7.|n  Characters must be approved before entering IC areas.\n"
            "  |w8.|n  Follow the Edgerunner Mission Kit setting priority.\n"
            "  |w9.|n  Inactivity over 30 days without notice may result in\n"
            "       character retirement.\n"
            "  |w10.|n Do not share account credentials with other players.\n"
            "  |w11.|n If something feels like a gray area, do not make\n"
            "       staff have to care about it.\n"
            "\n"
            "  Full policy and house rules:\n"
            "  |cPolicy ........ https://nightcitymux.com/index.php?title=Policy|n\n"
            "  |cHouse Rules ... https://nightcitymux.com/index.php?title=House_Rules|n\n"
            "\n"
            "|m---------------------------------------------------------------|n\n"
            "\n"
            "  Type |w+agree|n to confirm you have read the rules and are ready\n"
            "  to enter Night City. You cannot proceed until you do.\n"
            "\n"
            "|m=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=|n"
        )

    def at_object_receive(self, moved_obj, source_location, move_type="move", **kwargs):
        """Called when a character enters the room. Apply lock if not yet agreed."""
        super().at_object_receive(moved_obj, source_location, move_type=move_type, **kwargs)
        if not hasattr(moved_obj, "account"):
            return
        if moved_obj.attributes.get("policy_agreed"):
            return
        # Apply the lock cmdset if not already present
        if not moved_obj.cmdset.has("typeclasses.landing.LandingLockedCmdSet"):
            moved_obj.cmdset.add(
                "typeclasses.landing.LandingLockedCmdSet",
                persistent=True
            )
