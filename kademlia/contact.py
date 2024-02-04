from datetime import datetime
from typing import Optional

from .id import ID
from .interfaces import IProtocol
from .main import DEBUG


class Contact:

    def __init__(self, id: ID, protocol=None):
        # Protocol should only be None if DEBUG? TODO: Is this true?
        if protocol is None and not DEBUG:
            raise ValueError("No protocol given to Contact.")
        self.protocol: Optional[IProtocol] = protocol
        self.id = id
        self.last_seen: datetime = datetime.now()

    def touch(self) -> None:
        """Updates the last time the contact was seen."""
        self.last_seen = datetime.now()
