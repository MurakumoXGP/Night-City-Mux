from evennia.commands.default.muxcommand import MuxCommand
from world.hangouts.models import HangoutDB


class CmdHangoutAdmin(MuxCommand):
    """
    Staff commands for managing hangout locations.

    Usage:
        +hoadmin/create <name>
        +hoadmin/setroom <#>=here or <#>=<area_code>
        +hoadmin/setdesc <#>=<description>
        +hoadmin/setdistrict <#>=<district>
        +hoadmin/delete <#>=yes
        +hoadmin/set <#>
        +hoadmin/setho <area_code>
        +hoadmin/setrewards eb=<min>-<max>
        +hoadmin/setrewards ip=<min>-<max>
        +hoadmin/rewards
        +hoadmin/list

    Examples:
        +hoadmin/create Lizzie's Bar
        +hoadmin/setroom 1=here
        +hoadmin/setroom 1=NC01
        +hoadmin/setdesc 1=A seedy bar in Watson known for its Braindance shows.
        +hoadmin/setdistrict 1=Watson
        +hoadmin/set 3
        +hoadmin/setho NC01
        +hoadmin/setrewards eb=10-50
        +hoadmin/setrewards ip=0.5-2.0
        +hoadmin/rewards
        +hoadmin/list
        +hoadmin/delete 1=yes
    """

    key = "+hoadmin"
    aliases = ["+hangoutadmin"]
    locks = "cmd:perm(Builder)"
    help_category = "Staff - Hangouts"

    def _get_script(self):
        from evennia.scripts.models import ScriptDB
        try:
            return ScriptDB.objects.get(db_key="hangout_daily_script")
        except ScriptDB.DoesNotExist:
            return None

    def _format_separator(self, width=78):
        return "|m" + "=" * width + "|n"

    def _format_section(self, width=78):
        return "|m" + "-" * width + "|n"

    def _find_room_by_code(self, area_code):
        from typeclasses.rooms import Room
        area_code = area_code.strip().upper()
        for room in Room.objects.all():
            if (room.db.area_code or "").upper() == area_code:
                return room
        return None

    def func(self):
        caller = self.caller

        if not self.switches:
            caller.msg("Usage: +hoadmin/<switch> - see |whelp +hoadmin|n for staff commands.")
            caller.msg("Example: |w+hoadmin/list|n to see all hangouts.")
            return

        # +hoadmin/list
        if "list" in self.switches:
            hangouts = HangoutDB.get_all_hangouts()
            script = self._get_script()
            featured_id = None
            if script:
                featured_id = script.db.featured_hangout_id

            if not hangouts:
                caller.msg("|rNo hangouts found.|n")
                return

            caller.msg(self._format_separator())
            caller.msg("|y           * * * HANGOUT LIST (STAFF) * * *|n")
            caller.msg(self._format_separator())
            caller.msg(f"  |w{'#':>3} | {'Name':<30} | {'District':<15} | Room|n")
            caller.msg(self._format_section())

            for h in sorted(hangouts, key=lambda x: x.db.hangout_id or 0):
                hid = h.db.hangout_id or h.id
                room = h.db.room
                room_code = room.db.area_code if room else "Not set"
                featured = "|y[TODAY]|n" if hid == featured_id else ""
                active = "" if h.db.active else "|r[INACTIVE]|n"
                caller.msg(
                    f"  {hid:>3} | {h.key:<30} | "
                    f"{(h.db.district or 'Unknown'):<15} | "
                    f"{room_code} {featured}{active}"
                )

            caller.msg(self._format_separator())
            return

        # +hoadmin/create <name>
        if "create" in self.switches:
            if not self.args:
                caller.msg("Usage: +hoadmin/create <name>")
                return
            name = self.args.strip()
            hangout = HangoutDB.create(
                key=name,
                room=None,
                category="Social",
                district="Unassigned",
                description="No description set."
            )
            caller.msg(
                f"|gCreated hangout |w#{hangout.db.hangout_id}|g: {name}|n"
            )
            caller.msg(
                "Use |w+hoadmin/setroom|n and |w+hoadmin/setdesc|n to finish setup."
            )
            return

        # +hoadmin/set <#> -- set featured hangout by ID directly
        if "set" in self.switches:
            if not self.args:
                caller.msg("Usage: +hoadmin/set <hangout #>")
                return
            try:
                hangout_id = int(self.args.strip())
            except ValueError:
                caller.msg("|rPlease provide a valid hangout number.|n")
                return

            script = self._get_script()
            if not script:
                caller.msg(
                    "|rHangout script is not running. "
                    "Ask a developer to start it.|n"
                )
                return

            ok, result = script.force_new_hangout(hangout_id)
            if not ok:
                caller.msg(f"|r{result}|n")
                return

            caller.msg(
                f"|gToday's featured hangout has been set to "
                f"|w#{hangout_id}: {result.key}|g.|n"
            )
            return

        # +hoadmin/setho <area_code>
        if "setho" in self.switches:
            if not self.args:
                caller.msg("Usage: +hoadmin/setho <area_code>")
                caller.msg("Example: +hoadmin/setho NC01")
                return

            area_code = self.args.strip().upper()
            room = self._find_room_by_code(area_code)
            if not room:
                caller.msg(f"|rNo room found with area code '{area_code}'.|n")
                return

            all_hangouts = HangoutDB.get_all_hangouts()
            hangout = None
            for h in all_hangouts:
                if h.db.room and h.db.room == room:
                    hangout = h
                    break

            if not hangout:
                caller.msg(
                    f"|rNo hangout is associated with room '{area_code}'.|n"
                )
                caller.msg(
                    "That room isn't in the hangout list. "
                    "Use |w+hoadmin/create|n and |w+hoadmin/setroom|n first."
                )
                return

            script = self._get_script()
            if not script:
                caller.msg(
                    "|rHangout script is not running. "
                    "Ask a developer to start it.|n"
                )
                return

            script.force_new_hangout(hangout.db.hangout_id)
            caller.msg(
                f"|gToday's featured hangout has been set to "
                f"|w{hangout.key}|g ({area_code}).|n"
            )
            return

        # +hoadmin/rewards
        if "rewards" in self.switches:
            script = self._get_script()
            if not script:
                caller.msg("|rHangout script is not running.|n")
                return
            caller.msg(self._format_separator())
            caller.msg("|y       * * * HANGOUT REWARD SETTINGS * * *|n")
            caller.msg(self._format_separator())
            caller.msg(f"|wEB Range:|n {script.db.eb_min} - {script.db.eb_max}")
            caller.msg(f"|wIP Range:|n {script.db.ip_min} - {script.db.ip_max}")
            caller.msg("|wReward Interval:|n Random 25-45 minutes per character")
            caller.msg("|wRequired Players:|n 2+ approved players in room")
            caller.msg(self._format_separator())
            return

        # +hoadmin/setrewards eb=<min>-<max> or ip=<min>-<max>
        if "setrewards" in self.switches:
            if not self.args or "=" not in self.args:
                caller.msg("Usage: +hoadmin/setrewards eb=<min>-<max>")
                caller.msg("       +hoadmin/setrewards ip=<min>-<max>")
                caller.msg("Example: +hoadmin/setrewards eb=10-50")
                caller.msg("Example: +hoadmin/setrewards ip=0.5-2.0")
                return

            reward_type, value = self.args.split("=", 1)
            reward_type = reward_type.strip().lower()

            if "-" not in value:
                caller.msg("|rFormat must be <min>-<max>, e.g. 10-50|n")
                return

            min_val, max_val = value.split("-", 1)
            try:
                min_val = float(min_val.strip())
                max_val = float(max_val.strip())
            except ValueError:
                caller.msg("|rMin and max must be numbers.|n")
                return

            if min_val >= max_val:
                caller.msg("|rMin must be less than max.|n")
                return

            script = self._get_script()
            if not script:
                caller.msg("|rHangout script is not running.|n")
                return

            if reward_type == "eb":
                script.set_rewards(eb_min=int(min_val), eb_max=int(max_val))
                caller.msg(
                    f"|gEB reward range set to "
                    f"|w{int(min_val)}-{int(max_val)}eb|g.|n"
                )
            elif reward_type == "ip":
                script.set_rewards(ip_min=min_val, ip_max=max_val)
                caller.msg(
                    f"|gIP reward range set to |w{min_val}-{max_val} IP|g.|n"
                )
            else:
                caller.msg("|rUnknown reward type. Use 'eb' or 'ip'.|n")
            return

        # Commands below require <#>=<value>
        if not self.args or "=" not in self.args:
            caller.msg("Usage: +hoadmin/<switch> <#>=<value>")
            return

        hangout_id, value = self.args.split("=", 1)
        value = value.strip()

        try:
            hangout_id = int(hangout_id.strip())
        except ValueError:
            caller.msg("|rPlease provide a valid hangout number.|n")
            return

        hangout = HangoutDB.get_by_hangout_id(hangout_id)
        if not hangout:
            caller.msg(f"|rNo hangout found with ID #{hangout_id}.|n")
            return

        # +hoadmin/setroom <#>=here or <#>=<area_code>
        if "setroom" in self.switches:
            if value.lower() == "here":
                room = caller.location
            else:
                room = self._find_room_by_code(value)
                if not room:
                    caller.msg(f"|rNo room found with area code '{value}'.|n")
                    return

            hangout.db.room = room
            area_code = room.db.area_code or "unknown"
            caller.msg(
                f"|gSet room for hangout |w#{hangout_id}|g "
                f"to |w{room.key}|g ({area_code}).|n"
            )
            return

        # +hoadmin/setdesc <#>=<description>
        if "setdesc" in self.switches:
            hangout.db.description = value
            caller.msg(
                f"|gUpdated description for hangout |w#{hangout_id}|g.|n"
            )
            return

        # +hoadmin/setdistrict <#>=<district>
        if "setdistrict" in self.switches:
            hangout.db.district = value
            caller.msg(
                f"|gSet district for hangout |w#{hangout_id}|g "
                f"to |w{value}|g.|n"
            )
            return

        # +hoadmin/delete <#>=yes
        if "delete" in self.switches:
            if value.lower() != "yes":
                caller.msg(
                    f"To delete hangout #{hangout_id}, type: "
                    f"|w+hoadmin/delete {hangout_id}=yes|n"
                )
                return
            name = hangout.key
            hangout.delete()
            caller.msg(f"|gDeleted hangout: |w{name}|g.|n")
            return

        caller.msg("|rUnknown switch. See |whelp +hoadmin|n for staff commands.|n")
