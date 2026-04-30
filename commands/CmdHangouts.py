"""
Hangouts system - Player commands for Night City MUSH.
"""
from evennia.commands.default.muxcommand import MuxCommand
from world.hangouts.models import HangoutDB
from world.utils.character_utils import is_character_approved


class CmdHangout(MuxCommand):
    """
    View hangout locations and today's featured hangout.

    Usage:
        +hangout              - Show today's featured hangout
        +hangout/all          - Show all hangouts
        +hangout/go           - Travel to today's featured hangout
        +hangout <number>     - View details about a specific hangout
        +hangout/jump <number> - Travel to a specific hangout

    The daily hangout changes at midnight PST. If 2 or more approved
    players are present at the featured hangout, rewards are given
    periodically.
    """

    key = "+hangout"
    aliases = ["+hangouts", "+hotspot", "+hotspots",
               "+dir", "+directory", "+yp", "+yellowpages"]
    locks = "cmd:all()"
    help_category = "RP Commands"

    def _get_script(self):
        from evennia.scripts.models import ScriptDB
        try:
            return ScriptDB.objects.get(db_key="hangout_daily_script")
        except ScriptDB.DoesNotExist:
            return None

    def _get_featured_hangout(self):
        script = self._get_script()
        if not script:
            return None
        return script.get_featured_hangout()

    def _format_separator(self, width=78):
        return "|m" + "=" * width + "|n"

    def _format_section(self, width=78):
        return "|m" + "-" * width + "|n"

    def _display_featured(self):
        caller = self.caller
        hangout = self._get_featured_hangout()

        caller.msg(self._format_separator())
        caller.msg("|y         * * * TODAY'S HANGOUT * * *|n")
        caller.msg(self._format_separator())

        if not hangout:
            caller.msg("|rNo featured hangout has been selected yet.|n")
            caller.msg("Check back later or ask a staff member.")
        else:
            room = hangout.db.room
            area_code = room.db.area_code if room else "Unknown"
            area_name = hangout.db.district or "Unknown District"
            player_count = len([
                obj for obj in room.contents if obj.has_account
            ]) if room else 0

            caller.msg(f"|wLocation:|n {hangout.key}")
            caller.msg(f"|wDistrict:|n {area_name}")
            caller.msg(f"|wArea Code:|n {area_code}")
            caller.msg(f"|wPlayers Present:|n {player_count}")
            caller.msg(self._format_section())
            caller.msg(hangout.db.description or "No description available.")
            caller.msg(self._format_section())
            caller.msg(
                "|yIf 2+ approved players are present, rewards are given periodically.|n"
            )
            caller.msg(
                "Use |w+hangout/go|n to travel there."
            )

        caller.msg(self._format_separator())

    def _display_all(self):
        caller = self.caller
        hangouts = HangoutDB.get_visible_hangouts(caller)
        featured = self._get_featured_hangout()
        featured_id = featured.db.hangout_id if featured else None

        if not hangouts:
            caller.msg("|rNo hangouts found.|n")
            return

        caller.msg(self._format_separator())
        caller.msg("|y               * * * HANGOUT DIRECTORY * * *|n")
        caller.msg(self._format_separator())

        district_groups = {}
        for h in hangouts:
            district = h.db.district or "Uncategorized"
            if district not in district_groups:
                district_groups[district] = []
            room = h.db.room
            player_count = len([
                obj for obj in room.contents if obj.has_account
            ]) if room else 0
            district_groups[district].append((h, player_count))

        for district in sorted(district_groups.keys()):
            caller.msg(self._format_section())
            caller.msg(f"|w{district}|n")
            for hangout, player_count in sorted(
                district_groups[district],
                key=lambda x: x[0].db.hangout_id or 0
            ):
                hid = hangout.db.hangout_id or hangout.id
                featured_marker = "|y[TODAY]|n " if hid == featured_id else ""
                caller.msg(
                    f"  |w{hid:>3}|n | {featured_marker}{hangout.key} "
                    f"({player_count} players)"
                )
                caller.msg(f"       {hangout.db.description or 'No description.'}")

        caller.msg(self._format_separator())
        caller.msg("Use |w+hangout/go|n to travel to today's hangout.")
        caller.msg("Use |w+hangout/jump <#>|n to travel to a specific hangout.")
        caller.msg(self._format_separator())

    def _travel_to(self, hangout):
        caller = self.caller

        if not is_character_approved(caller):
            caller.msg(
                "|rYou must be approved by staff before traveling to hangouts.|n"
            )
            return

        room = hangout.db.room
        if not room:
            caller.msg("|rThat hangout's location is not properly set up.|n")
            return

        if caller.location == room:
            caller.msg("|rYou are already there.|n")
            return

        old_location = caller.location
        if old_location:
            old_location.msg_contents(
                f"|y{caller.key}|n heads out to {hangout.key}.",
                exclude=caller
            )

        caller.move_to(room, quiet=True)
        room.msg_contents(
            f"|y{caller.key}|n arrives.",
            exclude=caller
        )
        caller.msg(f"|mYou head to |w{hangout.key}|m.|n")
        caller.execute_cmd("look")

    def func(self):
        caller = self.caller

        # +hangout/go - travel to today's featured hangout
        if "go" in self.switches:
            hangout = self._get_featured_hangout()
            if not hangout:
                caller.msg("|rNo featured hangout has been selected today.|n")
                return
            self._travel_to(hangout)
            return

        # +hangout/jump <#> - travel to specific hangout
        if any(s in self.switches for s in ["jump", "tel", "join", "visit"]):
            if not self.args:
                caller.msg("Usage: +hangout/jump <number>")
                return
            try:
                hid = int(self.args.strip())
            except ValueError:
                caller.msg("|rPlease provide a valid hangout number.|n")
                return
            hangout = HangoutDB.get_by_hangout_id(hid)
            if not hangout:
                caller.msg("|rHangout not found.|n")
                return
            self._travel_to(hangout)
            return

        # +hangout/all - show all hangouts
        if "all" in self.switches:
            self._display_all()
            return

        # +hangout <number> - view specific hangout details
        if self.args and not self.switches:
            try:
                hid = int(self.args.strip())
                hangout = HangoutDB.get_by_hangout_id(hid)
                if not hangout:
                    caller.msg("|rHangout not found.|n")
                    return
                caller.msg(self._format_separator())
                caller.msg(f"|wHangout #{hid}: {hangout.key}|n")
                caller.msg(self._format_section())
                caller.msg(f"|wDistrict:|n {hangout.db.district or 'Unknown'}")
                caller.msg(f"|wCategory:|n {hangout.db.category or 'Unknown'}")
                room = hangout.db.room
                if room:
                    caller.msg(f"|wArea Code:|n {room.db.area_code or 'Unknown'}")
                caller.msg(self._format_section())
                caller.msg(hangout.db.description or "No description available.")
                caller.msg(self._format_separator())
                return
            except ValueError:
                caller.msg("|rPlease provide a valid hangout number.|n")
                return

        # Default - show today's featured hangout
        self._display_featured()