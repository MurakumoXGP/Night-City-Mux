"""
Hangout typeclass for Night City MUSH.

Required by world/hangouts/models.py which expects this class at
typeclasses.hangouts.Hangout. All hangout data is stored on db
attributes managed by HangoutDB in world/hangouts/models.py.
This typeclass provides the Evennia object foundation.
"""

from evennia.objects.objects import DefaultObject


class Hangout(DefaultObject):
    """
    Typeclass for hangout location objects.

    Hangouts are invisible game objects that store metadata about
    in-world locations: name, district, category, description, and
    a reference to the actual room. All management is done via the
    +hangout command (commands/CmdHangouts.py).
    """

    def at_object_creation(self):
        """Set default attributes when a hangout is first created."""
        super().at_object_creation()
        self.db.hangout_id = None
        self.db.room = None
        self.db.district = "Unassigned"
        self.db.category = "Uncategorized"
        self.db.description = "No description set."
        self.db.hidden = False
        self.db.required_splats = []
        self.db.required_merits = []
        self.db.required_factions = []
