"""
Voucher typeclass - IC objects that can hold multiple items.

A voucher represents in-character objects. Multiple items may be combined
onto a single voucher. Vouchers can be picked up and dropped like regular items.
"""
from typeclasses.objects import Object
from world.utils.formatting import sheet_header, sheet_section, footer


def _default_items():
    return []


def _is_valid_numbering_owner(obj):
    """Only real characters count as a numbering owner -- a voucher passing
    through a room, exit, or other container shouldn't trigger a renumber."""
    if not obj:
        return False
    from world.utils.character_utils import get_character_sheet
    return get_character_sheet(obj) is not None


def get_next_voucher_number(owner_id):
    """
    Return the next available voucher number for a given character id.
    """
    from evennia.utils.search import search_tag

    existing = search_tag("voucher", category="object")
    max_num = 0
    for obj in existing:
        if getattr(obj.db, "voucher_owner_id", None) != owner_id:
            continue
        num = getattr(obj.db, "voucher_number", None)
        if isinstance(num, int) and num > max_num:
            max_num = num
    return max_num + 1


def _voucher_numbers_held_by(owner_id, exclude_id=None):
    """All voucher_number values currently held by a given character id."""
    from evennia.utils.search import search_tag

    nums = set()
    for obj in search_tag("voucher", category="object"):
        if exclude_id is not None and obj.id == exclude_id:
            continue
        if getattr(obj.db, "voucher_owner_id", None) != owner_id:
            continue
        num = getattr(obj.db, "voucher_number", None)
        if isinstance(num, int):
            nums.add(num)
    return nums


class Voucher(Object):
    """
    A voucher is a physical object that holds a list of IC items.
    Each item: {name, description, quantity, ic_location, cloneable, created_by}
    """
    def at_object_creation(self):
        super().at_object_creation()
        self.db.voucher_items = []
        self.db.concealed = False
        self.db.locked = False
        self.db.ic_owner = ""  # Character name for +owner
        self.db.voucher_alias = ""  # Custom alias (max 20 chars)
        self.tags.add("voucher", category="object")
        self._assign_voucher_number()

    def _assign_voucher_number(self):
        """
        Assign a voucher number scoped to whoever currently holds it, the
        same way CyberwareInstance.slot_number is scoped per-character.
        Numbers stay stable as the voucher changes hands, EXCEPT when the
        new holder already has a voucher using that same number -- in that
        case (and only that case) it's bumped to the next free number for
        the new holder, so numbers never collide within one character's
        held vouchers.
        """
        owner = self.location
        if not _is_valid_numbering_owner(owner):
            return
        owner_id = owner.id
        current_num = getattr(self.db, "voucher_number", None)
        prior_owner_id = getattr(self.db, "voucher_owner_id", None)

        if prior_owner_id == owner_id and isinstance(current_num, int):
            return  # same holder as before, nothing to do

        if isinstance(current_num, int):
            held = _voucher_numbers_held_by(owner_id, exclude_id=self.id)
            if current_num not in held:
                # No collision -- keep the same number, just update ownership.
                self.db.voucher_owner_id = owner_id
                return

        self.db.voucher_owner_id = owner_id
        self.db.voucher_number = get_next_voucher_number(owner_id)

    def at_after_move(self, source_location, **kwargs):
        """Re-check numbering whenever the voucher actually changes hands."""
        move_hook = getattr(super(), "at_after_move", None)
        if callable(move_hook):
            move_hook(source_location, **kwargs)
        self._assign_voucher_number()

    def get_items(self):
        return self.db.voucher_items or []

    def set_items(self, items):
        try:
            from world.voucher.utils import normalize_voucher_items
            self.db.voucher_items = normalize_voucher_items(items)
        except Exception:
            # Fallback to raw assignment if utility import fails during startup/migration contexts.
            self.db.voucher_items = items

    def get_item_by_num(self, num):
        items = self.get_items()
        if 1 <= num <= len(items):
            return items[num - 1], num
        return None, None

    def is_empty(self):
        return len(self.get_items()) == 0

    def is_concealed(self):
        return bool(self.db.concealed)

    def is_locked(self):
        return bool(self.db.locked)

    def can_modify(self, character):
        """Locked vouchers can only be modified by owner."""
        if not self.is_locked():
            return True
        return self.location == character if character else False

    def at_pre_get(self, getter, **kwargs):
        """Locked vouchers can only be picked up by the person who locked them."""
        if not self.is_locked():
            return True
        locked_by = getattr(self.db, "locked_by", None)
        if locked_by and getter and getattr(getter, "id", None) == locked_by:
            return True
        if self.location == getter:
            return True  # Already carrying it
        if locked_by:
            getter.msg("That voucher is locked.")
        return False

    def return_appearance(self, looker, **kwargs):
        """Look shows voucher contents."""
        string = super().return_appearance(looker, **kwargs)
        items = self.get_items()
        if items:
            string += "\n|yContents:|n\n"
            for i, it in enumerate(items, 1):
                qty = it.get("quantity", 1)
                name = it.get("name", "?")
                loc = it.get("ic_location", "")
                loc_str = f" ({loc})" if loc else ""
                string += f"  {i}. {name}"
                if qty > 1:
                    string += f" x{qty}"
                string += f"{loc_str}\n"
        return string

    def format_sheet(self, width=80):
        """Format voucher for +sheet display."""
        items = self.get_items()
        num = getattr(self.db, "voucher_number", None)
        title = f"Voucher #{num}: {self.key}" if num else f"Voucher: {self.key}"
        out = sheet_header(title, width=width)
        out += sheet_section("Contents", width=width)
        if not items:
            out += "|w(empty)|n\n"
        else:
            out += f"|y{'#':<4}{'Item':<30}{'Qty':<8}{'Location':<20}|n\n"
            for i, it in enumerate(items, 1):
                name = (it.get("name", "?") or "?")[:29]
                qty = it.get("quantity", 1)
                loc = (it.get("ic_location", "") or "")[:19]
                out += f"|w{i:<4}{name:<30}{qty:<8}{loc:<20}|n\n"
        out += footer(width=width, fillchar="-")
        return out
