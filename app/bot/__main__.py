"""
Entry point for running the bot as a module: python -m app.bot
"""
import asyncio
from app.bot.run_bot import main

if __name__ == "__main__":
    asyncio.run(main())
