"""
Staff command to award apartments to players.

Usage:
  +rent/award <character>=<apartment type>

Awards an apartment of the specified type to a character without charging rent.
Must be used in a rental lobby or rental floor zone.
Works for all apartment types including Corporate Conapt and other
role-restricted housing. Only usable by Admin-level staff.

Example:
  +rent/award Kimmy=Corporate Conapt
  +rent/award Johnny=Luxury Penthouse
"""

from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils import create
from world.rental_data import RENTAL_TYPES
from world.rental_service import (
    get_lobby_for_rent,
    get_floor_rooms,
    get_available_apartment_number,
    get_used_apartment_numbers,
    get_apartment_hierarchy,
    create_apartment_rooms,
    ensure_rent_collection_script,
    normalize_housing_data,
)
from typeclasses.rental import RentableRoom
import random


class CmdRentAward(MuxCommand):
    """
    Award an apartment to a player. Staff only.

    Usage:
      +rent/award <character>=<apartment type>

    Awards an apartment of the specified type to a character without
    charging rent or checking role requirements. Must be used while
    standing in a rental lobby or rental floor.

    Available types:
      Living on The Street, Living on The Street in a Vehicle,
      Cube Hotel, Cargo Container, Studio Apartment,
      One-Bedroom Apartment, Two-Bedroom Apartment,
      Corporate Conapt, Upscale Conapt, Luxury Penthouse,
      Corporate Beaverville House, Corporate Beaverville McMansion,
      Custom, Encampment

    Examples:
      +rent/award Kimmy=Corporate Conapt
      +rent/award Johnny=Luxury Penthouse
    """

    key = "+rent/award"
    aliases = ["rent/award"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        caller = self.caller
        location = caller.location

        if not self.lhs or not self.rhs:
            caller.msg("Usage: +rent/award <character>=<apartment type>")
            return

        char_name = self.lhs.strip()
        apt_type = self.rhs.strip()

        # Validate apartment type
        if apt_type not in RENTAL_TYPES:
            type_list = "\n  ".join(sorted(RENTAL_TYPES.keys()))
            caller.msg(f"'{apt_type}' is not a valid apartment type. Valid types:\n  {type_list}")
            return

        # Find the target character
        target = caller.search(char_name, global_search=True)
        if not target:
            return

        if not hasattr(target, "db"):
            caller.msg(f"{char_name} is not a valid character.")
            return

        # Check target doesn't already have housing
        existing = target.attributes.get("rented_room")
        if existing:
            caller.msg(
                f"{target.key} already has a rental ({existing.key}). "
                f"Use +rent/leave on their character first, or +clearrental to force-clear it."
            )
            return

        # Must be in a rental zone
        lobby = get_lobby_for_rent(location)
        if not lobby:
            caller.msg(
                "You must be standing in a rental lobby or rental floor to award housing. "
                "Go to an appropriate building first."
            )
            return

        # Determine floor
        floors = get_floor_rooms(lobby)
        if not floors:
            caller.msg("No rental floors found in this building. Set up floors with +manage first.")
            return

        floor_room = random.choice(floors)

        # Get apartment number
        apt_num = get_available_apartment_number(floor_room)
        if not apt_num:
            caller.msg("No apartment numbers available on this floor.")
            return

        # Get building info
        main_hierarchy = get_apartment_hierarchy(lobby, floor_room=floor_room)
        building_name = main_hierarchy[0] if main_hierarchy and main_hierarchy[0] else lobby.key
        district = main_hierarchy[1] if len(main_hierarchy) >= 2 else "Unknown"

        data = RENTAL_TYPES[apt_type]

        # Create the apartment
        main = create.create_object(
            RentableRoom,
            key=f"{apt_num} Main Room",
            location=floor_room.location,
        )
        main.db.rental_type = apt_type
        main.db.apartment_number = apt_num
        main.db.building_name = building_name
        main.db.location_hierarchy = main_hierarchy
        main.db.area_name = main_hierarchy[0] if main_hierarchy else building_name
        main.db.area_code = apt_num
        # Staff-awarded housing: 0 rent regardless of type
        main.db.rent_cost = 0
        main.db.purchase_cost = data.get("purchase") or 0

        # Create exits
        create.create_object(
            typeclass="typeclasses.exits.Exit",
            key=apt_num,
            location=floor_room,
            destination=main,
            aliases=[apt_num],
        )
        create.create_object(
            typeclass="typeclasses.exits.Exit",
            key="Out",
            location=main,
            destination=floor_room,
            aliases=["O"],
        )

        # Register on floor
        floor_hd = normalize_housing_data(getattr(floor_room.db, "housing_data", None)) or {}
        used = get_used_apartment_numbers(floor_room)
        used.add(str(apt_num))
        floor_hd["apartment_numbers"] = used
        floor_room.db.housing_data = floor_hd

        # Create child rooms for multi-room types
        if data.get("rooms", 1) > 1:
            create_apartment_rooms(main, apt_type, apt_num, building_name, district)

        # Assign to character -- bypass role and cost checks
        main.db.owner = target
        main.db.residents = [target]
        main.db.co_residents = {}
        main.db.partners = []
        main.db.room_owners = {}
        main.db.purchased = False
        main.db.rent_due_date = main.get_next_rent_due_date()
        main.db.staff_awarded = True
        main.set_rental_type(apt_type)
        target.attributes.add("rented_room", main)
        ensure_rent_collection_script(main)

        caller.msg(
            f"Awarded |w{apt_type}|n (#{apt_num}) in {building_name} to |w{target.key}|n. "
            f"Rent set to 0eb (staff award)."
        )
        if target.sessions.all():
            target.msg(
                f"|gStaff has awarded you a {apt_type} in {building_name}.|n "
                f"Use the exit '{apt_num}' on the rental floor, or |whome|n to go there directly."
            )
        target.db.home_location = main
