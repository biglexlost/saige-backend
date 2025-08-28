from typing import Optional


class BookingAdapter:
    """Simple booking stub. Replace with vendor integration later."""

    async def find_slot(self, service: str, preferences: Optional[str] = None) -> str:
        # Return a placeholder suggestion
        return "Tuesday at 2 PM"

    async def confirm(self, service: str, slot: str) -> bool:
        return True



