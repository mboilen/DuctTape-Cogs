import discord
from discord.ext import commands

class Signal:
	"""Signals users to assemble"""

	def __init__(self, bot):
		self.bot = bot


	async def signal(self):
	
		await self.bot.say("Signal!")

	async def sigset(self):
	
		await self.bot.say("Sigset!")


def setup(bot):
	bot.add_cog(Mycog((bot)))
