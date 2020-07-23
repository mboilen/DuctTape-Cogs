import discord
from redbot.core import commands
from redbot.core import checks
from redbot.core import Config
from redbot.core.utils.predicates import MessagePredicate
from discord import utils
from discord import ChannelType
from redbot.core.utils.chat_formatting import box, pagify
import os
import random
import re

class Signal(commands.Cog):
    """Signals users to assemble"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=0x0322197802071984)
        default_guild = {
            "signals" : {}
        }
        self.config.register_guild(**default_guild)


    #the *, gameName : str allows for a multiword game name without quotes
    @commands.command(pass_context=True, no_pm=True)
    async def signal(self, ctx, *, gameName : str = None):
        """Sends up a signal"""
        server = ctx.message.guild
        game = None
        signals = await self.config.guild(ctx.guild).signals()
        if signals:
            if gameName is None:
                #game is none, so find the default game for the channel
                #since this comprehension returns a list, make sure the channel isn't ambiguous
                gameTemp = [g for g in signals.values() if g['channel'] == ctx.message.channel.id]
                if len(gameTemp) > 1:
                    await ctx.send("The channel " + ctx.message.channel.name + " is the channel for multiple games (" + (", ".join([g['game'] for g in gameTemp])) + ").  Please specify game explicitly.")
                    return
                if len(gameTemp) == 1:
                    game = gameTemp[0]
            else:
                if gameName.lower() in signals:
                    game = signals[gameName.lower()]
                if game is None:
                    #I couldn't find the game by it's primary name.  Look for aliases.
                    #(aliases might not exist)
                    gameTemp = [g for g in signals.values() if (gameName.lower() in map(lambda x : x.lower(), g.get('aliases', [])))]
                    if len(gameTemp) > 1:
                        await ctx.send("The name " + gameName + " is the alias for multiple games (" + (", ".join([g['game'] for g in gameTemp])) + ").  Please specify game by name, not alias.")
                        return
                    if len(gameTemp) == 1:
                        game = gameTemp[0]
        
        if game is None:
            if gameName is None:
                await ctx.send("No default game for #" + ctx.message.channel.name)
            else:
                await ctx.send("No game " + gameName)
            return
                

        if not game['messages']:
            await ctx.send("No messages defined for game " + game['game'])
            return
        msg = random.choice(game['messages'])
        channel = utils.get(server.channels, id=game['channel'], type=ChannelType.text)
        if channel:
            await channel.send(msg)
        else:
            await ctx.send("channel with id " + game['channel'] + " does not exist")

    @commands.group(pass_context=True, no_pm=True)
    async def sigset(self, ctx):
        """Signal management"""
        #if ctx.invoked_subcommand is None:
            #await ctx.send_help()

    @sigset.command(name="list", pass_context=True)
    async def ss_list(self, ctx):
        """Shows signal list"""
        displayedValue = False
        output = []
        signals = await self.config.guild(ctx.message.guild).signals()
        if signals:
            for game in signals.values():
                displayedValue = True

                name = game['game']
                messages = game['messages']
                aliases = ", ".join(game.get('aliases', []))
                channelObj = utils.get(ctx.message.guild.channels, id=game['channel'], type=ChannelType.text)
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
            for page in pagify("".join(output)):
                await ctx.send(box(page, lang="py"))
        else:
            await ctx.send("No games found")
        

    
    @sigset.command(name="addgame", pass_context=True)
    @checks.mod_or_permissions(administrator=True)
    async def ss_addgame(self, ctx, game : str, channel : str):
        """Adds a game to signal (and a default channel)"""
        server = ctx.message.guild
        channel = channel.lower()

        channelObj = utils.get(server.channels, name=channel, type=ChannelType.text)
        if not channelObj:
            await ctx.send(channel + " does not exist on this server.")
            return

        signals = await self.config.guild(ctx.guild).signals()

        #Search by lower case, but preserve case
        if game.lower() in signals: 
            await ctx.send(game + ' already exists')
            return

        signals[game.lower()] = {"game" : game,
                                 "channel" : channelObj.id,
                                 "messages" : []}
        await self.config.guild(ctx.guild).signals.set(signals)

        await ctx.send("Created game " + game + " with default channel " + channel)

        return

    @sigset.command(name="delgame", pass_context=True)
    @checks.mod_or_permissions(administrator=True)
    async def ss_delgame(self, ctx, game : str):
        """Deletes a game"""
        games = await self.config.guild(ctx.guild).signals()
        if games:
            try:
                del games[game.lower()]
                await self.config.guild(ctx.guild).signals.set(games)
                await ctx.send("Deleted " + game)
                return
            except:
                pass
        await ctx.send("Couldn't find " + game)

        
    @sigset.command(name="addmsg", pass_context=True)
    @checks.mod_or_permissions(administrator=True)
    async def ss_addmsg(self, ctx, gameName : str, *, response : str=None):
        """Adds a message to a signal"""
        games = await self.config.guild(ctx.guild).signals()
        game = None
        if games:
            game = games.get(gameName.lower())
        if not game:
            await ctx.send(gameName + " not defined")
            return

        game['messages'].append(response)
        await self.config.guild(ctx.guild).signals.set(games)

        await ctx.send("Response added.")

    @sigset.command(name="delmsg", pass_context=True)
    @checks.mod_or_permissions(administrator=True)
    async def ss_delmsg(self, ctx, gameName : str):
        """Let's you chose a message to remove"""
        author = ctx.message.author
        games = await self.config.guild(ctx.guild).signals()
        game = None
        if games:
            game = games.get(gameName.lower())
        if not game:
            await ctx.send(gameName + " not defined")
            return

        messages = game['messages']
        if not messages:
            await ctx.send(gameName + " has no messages to delete")
            return

        list = self.get_n_messages(messages, truncate=100)
        await ctx.send(list + "\nType 'exit' to quit removal mode")

        msg = await self.bot.wait_for("message", check=MessagePredicate.same_context(ctx), timeout=15)
        if msg is None:
            await ctx.send("Tired of waiting...")
            return
        if msg.content.lower().strip() == "exit":
            await ctx.send("Removal mode quit")
            return

        try:
            i = int(msg.content)
            del messages[i]
            await self.config.guild(ctx.guild).signals.set(games)
            await ctx.send("Removed message.")
        except:
            await ctx.send("Error removing message.")

    @sigset.command(name="aliases", pass_context=True)
    @checks.mod_or_permissions(administrator=True)
    async def ss_aliases(self, ctx, gameName : str, *, aliases : str=""):
        """Adds a comma separated list of aliases to a game"""
        games = await self.config.guild(ctx.guild).signals()
        game = None
        if games:
            game = games.get(gameName.lower())
        if not game:
            await ctx.send(gameName + " not defined")
            return

        game['aliases'] = re.split(r'\s*,\s*', aliases)
        await self.config.guild(ctx.guild).signals.set(games)

        await ctx.send("Set aliases to [" + ", ".join(game['aliases']) + "] for " + gameName)




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
            
def setup(bot):
    bot.add_cog(Signal((bot)))
