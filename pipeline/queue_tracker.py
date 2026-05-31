from typing import Set

class QueueTracker:
    """
    Maintains state for the billing queue.
    Keeps track of which visitors are currently in the BILLING zone.
    """
    def __init__(self):
        # Set of visitor IDs currently in the queue
        self.in_queue: Set[str] = set()

    def update(self, visitor_id: str, zone_id: str):
        """Update queue state based on current zone."""
        if zone_id == "BILLING":
            self.in_queue.add(visitor_id)
        else:
            self.in_queue.discard(visitor_id)

    def remove(self, visitor_id: str):
        """Remove a visitor from queue (e.g. they exited)."""
        self.in_queue.discard(visitor_id)

    def get_queue_depth(self) -> int:
        """Return the current number of people in the billing queue."""
        return len(self.in_queue)
