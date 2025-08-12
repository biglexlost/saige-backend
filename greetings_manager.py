# src/greetings_manager.py
import random
from typing import List, Optional


class GreetingsManager:
    """Manages dynamic and localized greetings for JAIMES."""

    def __init__(
        self, shop_name: str, shop_location: str, location_style: str = "standard"
    ):
        self.shop_name = shop_name
        self.shop_location = shop_location
        self.location_style = location_style.lower()  # Ensure lowercase for comparison

        # --- Define pools of greetings ---
        # Initial Shop Greeting (from Cheat-Sheet)
        self._initial_shop_greetings = [
            f"{self.shop_name} of {self.shop_location} speaking. How can I help you today?",
            f"{self.shop_name} of {self.shop_location} speaking. Who do I have the pleasure speaking with?",
        ]

        # Returning Customer Greetings (Gender-Neutral, Varied)
        self._returning_greetings_standard = [
            "Welcome back, {name}! It's a pleasure to speak with you again.",
            "Hello again, {name}! We're glad you reached out to us.",
            "Greetings, {name}! Thank you for choosing {shop_name} once more.",
            "It's great to hear from you, {name}. How can we assist you today?",
            "A warm welcome back, {name}. We appreciate your continued trust in us.",
            "Hi there, {name}. How may we help you at {shop_name} today?",
            "So glad you called, {name}! We're always here to help.",
        ]

        # Southern Variants
        self._returning_greetings_southern = [
            "Well, howdy, {name}. It's truly good to hear from you.",
            "So glad you called, {name}! We're ready when you are.",
            "Welcome back, {name}. We're delighted to assist you at {shop_name}.",
        ]

        # Mapping location styles to greeting pools
        self._location_greeting_pools = {
            "standard": self._returning_greetings_standard,
            "southern": self._returning_greetings_southern,
            # Add more regions (new_england, west_coast, etc.) as needed
        }

    def get_initial_shop_greeting(self) -> str:
        """Returns a random initial greeting from the cheat-sheet options."""
        return random.choice(self._initial_shop_greetings)

    def get_returning_customer_greeting(self, customer_name: str) -> str:
        """Returns a personalized greeting for a returning customer based on location style."""
        pool = self._location_greeting_pools.get(
            self.location_style, self._returning_greetings_standard
        )
        template = random.choice(pool)
        return template.format(name=customer_name, shop_name=self.shop_name)

    def get_new_customer_vehicle_prompt(self) -> str:
        """Returns the prompt for new customer vehicle info."""
        return "Okay, welcome to {shop_name}! To help me understand your needs better, could you please tell me the year, make, model, and approximate mileage of your vehicle today?"

    def get_unrecognized_number_prompt(self) -> str:
        """Returns the prompt for unrecognized phone number flow."""
        return "Hello. This is James from {shop_name}. I don't seem to have a record for this number. Are you a returning customer?"

    def get_unrecognized_number_alt_prompt(self) -> str:
        """Returns the prompt for asking for alternative contact info."""
        return "Thank you. To help me locate your account, could you please provide the phone number or full name we might have on file for you?"

    def get_unrecognized_number_double_check_prompt(self) -> str:
        """Returns the prompt for asking for another possible number."""
        return "I'm still having trouble locating your existing record. Is there another phone number your account might be under, perhaps an older one or one associated with a family member?"

    def get_new_customer_transition(self) -> str:
        """Returns the transition phrase for a confirmed new customer."""
        return "Okay, no problem. It sounds like you might be a new customer to {shop_name}. No worries at all, we'd be happy to help you today."
