# -*- coding: utf-8 -*-
"""
Therapy max-Humanity ceiling calculation (CP:R core, pg. 229).

"Humanity cannot be fully regained without the removal of cyberware. Each
piece of cyberware will decrease your maximum Humanity by 2. Each piece of
Borgware cyberware lowers maximum Humanity by 4 instead. Cyberware with 0
Humanity Loss on installation will not decrease your maximum Humanity."

This is a distinct value from the character's *current* Humanity/loss
tracking on CharacterSheet -- it is never stored, and must be recalculated
fresh every time Therapy is run, since it changes as cyberware is
installed/removed.
"""


def get_therapy_ceiling(character_sheet):
    """
    Calculate the maximum Humanity a character could ever regain via Therapy,
    based on their currently installed cyberware.

    Returns a dict:
      {
        "standard_count": int,   # non-Borgware, non-zero-HL pieces (-2 each)
        "borgware_count": int,   # Borgware pieces (-4 each)
        "depression": int,       # total points shaved off the ceiling
        "natural_ceiling": int,  # empathy*10 or humanity_max_override
        "ceiling": int,          # natural_ceiling - depression, floored at 0
      }
    """
    from django.apps import apps

    CyberwareInstance = apps.get_model("inventory", "CyberwareInstance")
    sheet_pk = getattr(character_sheet, "pk", None)
    if sheet_pk is None:
        installed = CyberwareInstance.objects.none()
    else:
        installed = CyberwareInstance.objects.filter(
            character_sheet_id=sheet_pk, installed=True
        ).select_related("cyberware")

    standard_count = 0
    borgware_count = 0
    for inst in installed:
        cw = inst.cyberware
        if not cw:
            continue
        if (cw.humanity_loss or 0) == 0:
            continue  # 0 HL on install -- does not depress the ceiling
        if (cw.type or "").strip() == "Borgware":
            borgware_count += 1
        else:
            standard_count += 1

    depression = (standard_count * 2) + (borgware_count * 4)
    natural_ceiling = (
        character_sheet.humanity_max_override
        if character_sheet.humanity_max_override is not None
        else (character_sheet.empathy * 10)
    )
    ceiling = max(0, natural_ceiling - depression)

    return {
        "standard_count": standard_count,
        "borgware_count": borgware_count,
        "depression": depression,
        "natural_ceiling": natural_ceiling,
        "ceiling": ceiling,
    }
