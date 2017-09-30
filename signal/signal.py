import discord
from discord.ext import commands
from .utils.dataIO import dataIO
from .utils import checks
from discord import utils
from discord import ChannelType
import os
import random
from cogs.utils.chat_formatting import box, pagify, escape_mass_mentions
import re

class Signal:
	"""Signals users to assemble"""

	def __init__(self, bot):
		self.bot = bot
		self.file_path = "data/signal/signals.json"
		self.c_signals = dataIO.load_json(self.file_path)


	#the *, gameName : str allows for a multiword game name without quotes
	@commands.command(pass_context=True, no_pm=True)
	async def signal(self, ctx, *, gameName : str = None):
		"""Sends up a signal"""
		server = ctx.message.server
		game = None
		signals = self.c_signals.get(server.id)
		if signals:
			if gameName is None:
				#game is none, so find the default game for the channel
				#since this comprehension returns a list, make sure the channel isn't ambiguous
				gameTemp = [g for g in signals.values() if g['channel'] == ctx.message.channel.id]
				if len(gameTemp) > 1:
					await self.bot.say("The channel " + ctx.message.channel.name + " is the channel for multiple games (" + (", ".join([g['game'] for g in gameTemp])) + ").  Please specify game explicitly.")
					return
				if len(gameTemp) == 1:
					game = gameTemp[0]
			else:
				if gameName.lower() in signals:
					game = signals[gameName.lower()]
				if game is None:
					#I couldn't find the game by it's primary name.  Look for aliases.
					#(aliases might not exist)
					gameTemp = [g for g in signals.values() if (gameName.lower() in g.get('aliases', []))]
					if len(gameTemp) > 1:
						await self.bot.say("The name " + gameName + " is the alias for multiple games (" + (", ".join([g['game'] for g in gameTemp])) + ").  Please specify game by name, not alias.")
						return
					if len(gameTemp) == 1:
						game = gameTemp[0]
		
		if game is None:
			if gameName is None:
				await self.bot.say("No default game for #" + ctx.message.channel.name)
			else:
				await self.bot.say("No game " + gameName)
			return
				

		if not game['messages']:
			await self.bot.say("No messages defined for game " + game['game'])
			return
		msg = random.choice(game['messages'])
		channel = utils.get(server.channels, id=game['channel'], type=ChannelType.text)
		if channel:
			await self.bot.send_message(channel, msg)
		else:
			await self.bot.send_message("channel with id " + game['channel'] + " does not exist")

	@commands.group(pass_context=True, no_pm=True)
	async def sigset(self, ctx):
		"""Signal management"""
		if ctx.invoked_subcommand is None:
			await self.bot.send_cmd_help(ctx)

	@sigset.command(name="list", pass_context=True)
	async def ss_list(self, ctx):
		"""Shows signal list"""
		displayedValue = False
		output = []
		games = self.c_signals.get(ctx.message.server.id)
		if games:
			for game in games.values():
				displayedValue = True

				name = game['game']
				messages = game['messages']
				aliases = ", ".join(game.get('aliases', []))
				channelObj = utils.get(ctx.message.server.channels, id=game['channel'], type=ChannelType.text)
				if channelObj:
					channelName = channelObj.name
				else:
				 	channelName = "*unknown*"

				output.append("Game: " + name + "\n")
				output.append("Channel: #" + channelName + "\n")
				output.append("Aliases: " + aliases + "\n")
				output.append("Messages:\n")
				for msg in game['messages']:
					output.append("\t" + msg + "\n")
				output.append("\n")

		if displayedValue:
			await self.bot.say(box("".join(output), lang="py"))
		else:
			await self.bot.say("No games found")
		

	
	@sigset.command(name="addgame", pass_context=True)
	@checks.mod_or_permissions(administrator=True)
	async def ss_addgame(self, ctx, game : str, channel : str):
		"""Adds a game to signal (and a default channel)"""
		server = ctx.message.server
		channel = channel.lower()

		channelObj = utils.get(server.channels, name=channel, type=ChannelType.text)
		if not channelObj:
			await self.bot.say(channel + " does not exist on this server.")
			return

		if server.id not in self.c_signals:
			self.c_signals[server.id] = {}

		server_signals = self.c_signals[server.id]

		#Search by lower case, but preserve case
		if game.lower() in server_signals: 
			await self.bot.say(game + ' already exists')
			return

		server_signals[game.lower()] = {"game" : game,
						"channel" : channelObj.id,
						"messages" : []}

		self.save_settings()

		await self.bot.say("Created game " + game + " with default channel " + channel)

		return

	@sigset.command(name="delgame", pass_context=True)
	@checks.mod_or_permissions(administrator=True)
	async def ss_delgame(self, ctx, game : str):
		"""Deletes a game"""
		server = ctx.message.server
		games = self.c_signals.get(server.id)
		if games:
			try:
				del games[game.lower()]
				self.save_settings()
				await self.bot.say("Deleted " + game)
				return
			except:
				pass
		await self.bot.say("Couldn't find " + game)

		
	@sigset.command(name="addmsg", pass_context=True)
	@checks.mod_or_permissions(administrator=True)
	async def ss_addmsg(self, ctx, gameName : str, *, response : str=None):
		"""Adds a message to a signal"""
		server = ctx.message.server
		games = self.c_signals[server.id]
		game = None
		if games:
			game = games.get(gameName.lower())
		if not game:
			await self.bot.say(gameName + " not defined")
			return

		game['messages'].append(response)

		self.save_settings()

		await self.bot.say("Response added.")

	@sigset.command(name="delmsg", pass_context=True)
	@checks.mod_or_permissions(administrator=True)
	async def ss_delmsg(self, ctx, gameName : str):
		"""Let's you chose a message to remove"""
		server = ctx.message.server
		author = ctx.message.author
		games = self.c_signals[server.id]
		game = None
		if games:
			game = games.get(gameName.lower())
		if not game:
			await self.bot.say(gameName + " not defined")
			return

		messages = game['messages']
		if not messages:
			await self.bot.say(gameName + " has no messages to delete")
			return

		list = self.get_n_messages(messages, truncate=100)
		await self.bot.say(list + "\nType 'exit' to quit removal mode")

		msg = await self.bot.wait_for_message(author=author, timeout=15)
		if msg is None:
			await self.bot.say("Tired of waiting...")
			return
		if msg.content.lower().strip() == "exit":
			await self.bot.say("Removal mode quit")
			return

		try:
			i = int(msg.content)
			del messages[i]
			self.save_settings()
			await self.bot.say("Removed message.")
		except:
			await self.bot.say("Error removing message.")

	@sigset.command(name="aliases", pass_context=True)
	@checks.mod_or_permissions(administrator=True)
	async def ss_aliases(self, ctx, gameName : str, *, aliases : str=""):
		"""Adds a comma separated list of aliases to a game"""
		server = ctx.message.server
		games = self.c_signals[server.id]
		game = None
		if games:
			game = games.get(gameName.lower())
		if not game:
			await self.bot.say(gameName + " not defined")
			return
		game['aliases'] = re.split('\s*,\s*', aliases)
		self.save_settings()
		await self.bot.say("Set aliases to [" + ", ".join(game['aliases']) + "] for " + gameName)




	def get_n_messages(self, messages, *, truncate=2000):
		msg = ""
		i = 0
		for r in messages:
			if len(r) > truncate:
				r = r[:truncate] + "..."

			r = r.replace("`", "\\`").replace("*", "\\*").replace("_", "\\_")
			msg += "{}. {}\n".format(i, r)
			i += 1
		if msg != "":
			return box(msg, lang="py")
		else:
			return None
			

	def save_settings(self):
		dataIO.save_json(self.file_path, self.c_signals)


def check_folders():
	if not os.path.exists("data/signal"):
		print("Creating data/signal folder...")
		os.makedirs("data/signal")


def check_files():
	f = "data/signal/signals.json"
	if not dataIO.is_valid_json(f):
		print("Creating empty signals.json...")
		dataIO.save_json(f, {})


def setup(bot):
	check_folders()
	check_files()
	bot.add_cog(Signal((bot)))
