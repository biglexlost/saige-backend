#!/usr/bin/env python3
"""
JAIMES AI Executive - Quick Start Example
This example demonstrates how to get started with JAIMES in testing mode.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from core_system.jaimes_testing_version import JAIMESTestingSystem


async def quick_start_demo():
    """Quick start demonstration of JAIMES capabilities."""

    print("🚗 JAIMES AI Executive - Quick Start Demo")
    print("=" * 50)
    print("🎯 This demo shows JAIMES capabilities without requiring API keys")
    print("💡 Perfect for testing and evaluation!")
    print()

    # Initialize JAIMES in testing mode
    print("🔧 Initializing JAIMES Testing System...")
    jaimes = JAIMESTestingSystem()
    await jaimes.initialize()
    print("✅ JAIMES initialized successfully!")
    print()

    # Demo scenarios
    scenarios = [
        {
            "title": "🔄 Returning Customer Recognition",
            "phone": "(919) 555-0123",
            "input": "My brakes are making a grinding noise",
            "description": "JAIMES recognizes returning customer and pulls service history",
        },
        {
            "title": "🚗 License Plate Magic",
            "phone": "(919) 555-9999",
            "input": "ABC123, 27701",
            "description": "Instant vehicle lookup from license plate and ZIP code",
        },
        {
            "title": "🔧 Manual Vehicle Entry",
            "phone": "(919) 555-8888",
            "input": "I have a 2020 Ford F-150 and need an oil change",
            "description": "Traditional vehicle information collection with pricing",
        },
    ]

    for i, scenario in enumerate(scenarios, 1):
        print(f"📞 Demo {i}: {scenario['title']}")
        print(f"📝 Description: {scenario['description']}")
        print(f"🗣️  Customer says: \"{scenario['input']}\"")
        print("🤖 JAIMES responds:")
        print("-" * 40)

        try:
            # Process the conversation
            response = await jaimes.process_conversation(
                user_input=scenario["input"],
                session_id=f"demo_{i}",
                caller_phone=scenario["phone"],
            )

            # Display response
            if response and "response" in response:
                print(f"   {response['response'].get('text', 'Processing...')}")

                # Show additional info if available
                if response.get("vehicle_info"):
                    print(f"🚗 Vehicle: {response['vehicle_info']}")

                if response.get("pricing_info"):
                    print(f"💰 Pricing: {response['pricing_info']}")

                if response.get("recall_info"):
                    print(f"🚨 Safety Alert: {response['recall_info']}")
            else:
                print("   [Demo response processing...]")

        except Exception as e:
            print(f"   ❌ Demo error: {e}")

        print()
        print("=" * 50)
        print()

    print("🎉 Quick Start Demo Complete!")
    print()
    print("🚀 Next Steps:")
    print("   1. Try the interactive demo: python main.py --mode testing --demo")
    print("   2. Run batch tests: python main.py --mode testing --batch")
    print("   3. Configure APIs for production: cp .env.example .env")
    print("   4. Read the documentation in Documentation/ folder")
    print()
    print("💡 Questions? Check README.md or Documentation/ folder")


if __name__ == "__main__":
    try:
        asyncio.run(quick_start_demo())
    except KeyboardInterrupt:
        print("\n👋 Demo interrupted. Goodbye!")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        print(
            "💡 Make sure you've installed requirements: pip install -r requirements.txt"
        )
