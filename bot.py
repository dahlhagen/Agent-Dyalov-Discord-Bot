import random
import json
import os
from datetime import datetime, timedelta, timezone
import discord
from discord.ext import commands
from config import TOKEN  # this imports your secret token from config.py

MISSION_LIFETIME = timedelta(days=7)   # missions expire after a week
MAX_SWAPS_PER_WEEK = 3                 # how many times you can !nyttoppdrag per week


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def parse_iso(s):
    return datetime.fromisoformat(s)

# ---------- Persistent data (points + active missions) ----------
# We store this in a small JSON file on disk, so points survive
# closing and reopening the bot. It's created automatically the
# first time someone earns a point or gets a mission.
DATA_FILE = "data.json"


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"points": {}, "active_missions": {}, "swaps": {}, "self_fails": {}}


def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


data = load_data()
data.setdefault("swaps", {})       # in case this is an older data.json without this key
data.setdefault("self_fails", {})  # same, for older data.json files
# data["points"]            -> {"user_id": score}
# data["active_missions"]   -> {"user_id": {"text": "...", "triggers": [...], "assigned_at": "iso timestamp"}}
# data["swaps"]             -> {"user_id": ["iso timestamp", "iso timestamp", ...]}  (recent !nyttoppdrag uses)
# data["self_fails"]        -> {"user_id": count}  (how many times they've said their own trigger word)


def mission_is_expired(mission):
    return datetime.now(timezone.utc) - parse_iso(mission["assigned_at"]) > MISSION_LIFETIME


def recent_swap_count(user_id):
    """Returns how many times this user has used !nyttoppdrag in the last 7 days,
    and prunes any timestamps older than that while we're at it."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    timestamps = data["swaps"].get(user_id, [])
    recent = [t for t in timestamps if parse_iso(t) > cutoff]
    data["swaps"][user_id] = recent
    return len(recent)

# ---------- !comrade quotes ----------
QUOTES = [
    "we have reviewed your file. Continue as instructed.",
    "your neighbor has already reported this conversation.",
    "silence is also an answer. We have recorded it.",
    "the Committee does not forget. Nor do we forgive.",
    "state your business, then return to your post.",
    "trust no one. Not even yourself.",
    "your loyalty will be reassessed at the usual interval.",
    "there is no need to ask where we got this information.",
]
last_quote = {"value": None}

# ---------- !oppdrag missions ----------
# Each mission has display text (in Norwegian) and a list of "triggers" —
# words/phrases the bot watches for in chat. A list lets us accept
# alternate spellings (like "Teknikeren" vs "Teknikern") for the same mission.
MISSIONS = [
    # Original custom picks (kept)
    {"text": "Få et annet medlem til å si **Flaskebong**.", "triggers": ["flaskebong"]},
    {"text": "Få et annet medlem til å si **Ulf Larsen**.", "triggers": ["ulf larsen"]},
    {"text": "Få et annet medlem til å si **Teknikeren**.", "triggers": ["teknikeren", "teknikern"]},
    {"text": "Få et annet medlem til å si **Red Ryder**.", "triggers": ["red ryder"]},
    {"text": "Få et annet medlem til å si **Age of Empires**.", "triggers": ["age of empires"]},
    {"text": "Få et annet medlem til å si **bålet**.", "triggers": ["bålet"]},
    {"text": "Få et annet medlem til å si **Praha**.", "triggers": ["praha"]},
    # Pulled from the server's actual chat history (chosen for how often they naturally come up)
    {"text": "Få et annet medlem til å si **Erna**.", "triggers": ["erna"]},
    {"text": "Få et annet medlem til å si **Campino**.", "triggers": ["campino"]},
    {"text": "Få et annet medlem til å si **Superland**.", "triggers": ["superland"]},
    {"text": "Få et annet medlem til å si **Haaland**.", "triggers": ["haaland", "håland"]},
    {"text": "Få et annet medlem til å si **banan**.", "triggers": ["banan"]},
    {"text": "Få et annet medlem til å si **carbonara**.", "triggers": ["carbonara"]},
    {"text": "Få et annet medlem til å si **Ringnes**.", "triggers": ["ringnes"]},
    {"text": "Få et annet medlem til å si **Temu**.", "triggers": ["temu"]},
    {"text": "Få et annet medlem til å si **Anim8or**.", "triggers": ["anim8or"]},
    {"text": "Få et annet medlem til å si **Hachiko**.", "triggers": ["hachiko"]},
    # More, pulled from a deeper pass over the chat log
    {"text": "Få et annet medlem til å si **Oslo**.", "triggers": ["oslo"]},
    {"text": "Få et annet medlem til å si **Horten**.", "triggers": ["horten"]},
    {"text": "Få et annet medlem til å si **Trump**.", "triggers": ["trump"]},
    {"text": "Få et annet medlem til å si **pizza**.", "triggers": ["pizza"]},
    {"text": "Få et annet medlem til å si **Trondheim**.", "triggers": ["trondheim"]},
    {"text": "Få et annet medlem til å si **Tønsberg**.", "triggers": ["tønsberg"]},
    {"text": "Få et annet medlem til å si **Litauen**.", "triggers": ["litauen"]},
    {"text": "Få et annet medlem til å si **Vilnius**.", "triggers": ["vilnius"]},
    {"text": "Få et annet medlem til å si **Kongsberg**.", "triggers": ["kongsberg"]},
    {"text": "Få et annet medlem til å si **Canada**.", "triggers": ["canada"]},
    {"text": "Få et annet medlem til å si **Fortnite**.", "triggers": ["fortnite"]},
    # More distinctive inside-jokes, same style as Flaskebong / Ulf Larsen
    {"text": "Få et annet medlem til å si **Happytree**.", "triggers": ["happytree", "happy tree"]},
    {"text": "Få et annet medlem til å si **Chinesium**.", "triggers": ["chinesium"]},
    {"text": "Få et annet medlem til å si **jeger**.", "triggers": ["jeger"]},
    {"text": "Få et annet medlem til å si **Tordenskjold**.", "triggers": ["tordenskjold"]},
    {"text": "Få et annet medlem til å si **Gimsekloss**.", "triggers": ["gimsekloss"]},
    {"text": "Få et annet medlem til å si **Gildehallen**.", "triggers": ["gildehallen"]},
    # Newest batch
    {"text": "Få et annet medlem til å si **Drangedal**.", "triggers": ["drangedal"]},
    {"text": "Få et annet medlem til å si **Skrim**.", "triggers": ["skrim"]},
    {"text": "Få et annet medlem til å si **krokodille**.", "triggers": ["krokodille"]},
    {"text": "Få et annet medlem til å si **Russland**.", "triggers": ["russland"]},
    {"text": "Få et annet medlem til å si **politi**.", "triggers": ["politi"]},
    {"text": "Få et annet medlem til å si **weed**.", "triggers": ["weed"]},
    {"text": "Få et annet medlem til å si **Snus**.", "triggers": ["snus"]},
    {"text": "Få et annet medlem til å si **Skruf**.", "triggers": ["skruf"]},
    {"text": "Få et annet medlem til å si **Tang**.", "triggers": ["tang"]},
    {"text": "Få et annet medlem til å si **Fisk**.", "triggers": ["fisk"]},
    {"text": "Få et annet medlem til å si **Fiskestang**.", "triggers": ["fiskestang"]},
    {"text": "Få et annet medlem til å si **Pizzaovn**.", "triggers": ["pizzaovn"]},
    {"text": "Få et annet medlem til å si **Tom**.", "triggers": ["tom"]},
    {"text": "Få et annet medlem til å si **Ole**.", "triggers": ["ole"]},
    {"text": "Få et annet medlem til å si **Flatdal**.", "triggers": ["flatdal"]},
    {"text": "Få et annet medlem til å si **Bål**.", "triggers": ["bål"]},
    {"text": "Få et annet medlem til å si **lan**.", "triggers": ["lan"]},
    {"text": "Få et annet medlem til å si **pasta**.", "triggers": ["pasta"]},
]

# "Intents" tell Discord what kind of data your bot is allowed to receive.
intents = discord.Intents.default()
intents.message_content = True  # read message text
intents.members = True          # needed so !leaderboard can look up display names

bot = commands.Bot(command_prefix="!", intents=intents, case_insensitive=True)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}! Bot is online.")


@bot.event
async def on_message(message):
    # Ignore the bot's own messages
    if message.author == bot.user:
        return

    # Only check for mission triggers on messages sent in the server (not DMs)
    if message.guild is not None:
        author_id = str(message.author.id)
        content = message.content.lower()

        # Check every player's active mission to see if this message completes it
        for user_id, mission in list(data["active_missions"].items()):
            # First, clear out missions that are older than a week
            if mission_is_expired(mission):
                del data["active_missions"][user_id]
                save_data()
                try:
                    expired_player = await bot.fetch_user(int(user_id))
                    await expired_player.send(
                        "⌛ Oppdraget ditt har utløpt etter en uke. "
                        "Skriv `!oppdrag` for å få et nytt."
                    )
                except discord.Forbidden:
                    pass
                continue

            if user_id == author_id:
                # You said your own mission's trigger word — mission fails!
                matched_trigger = next((t for t in mission["triggers"] if t in content), None)
                if matched_trigger is None:
                    continue  # this message doesn't touch their mission at all, nothing happens

                del data["active_missions"][user_id]
                data["self_fails"][user_id] = data["self_fails"].get(user_id, 0) + 1
                fails = data["self_fails"][user_id]

                penalty_applied = False
                if fails >= 2:
                    data["points"][user_id] = data["points"].get(user_id, 0) - 1
                    penalty_applied = True
                save_data()

                try:
                    if penalty_applied:
                        await message.author.send(
                            f"❌ Oppdraget mislyktes! Du sa ditt eget hemmelige ord (\"{matched_trigger}\") selv. "
                            f"Dette er ikke første gang, så du mister ett poeng "
                            f"(du har nå {data['points'][user_id]} poeng). "
                            f"Skriv `!oppdrag` for et nytt oppdrag."
                        )
                    else:
                        await message.author.send(
                            f"❌ Oppdraget mislyktes! Du sa ditt eget hemmelige ord (\"{matched_trigger}\") selv. "
                            f"Ingen poengtrekk denne gangen, men neste gang du gjør det mister du ett poeng. "
                            f"Skriv `!oppdrag` for et nytt oppdrag."
                        )
                except discord.Forbidden:
                    pass
                continue

            # A mission can have several accepted triggers (e.g. spelling variants).
            # Find the first one that appears in this message, if any.
            matched_trigger = next((t for t in mission["triggers"] if t in content), None)

            if matched_trigger:
                # Mission complete! Award the point and clear their mission.
                data["points"][user_id] = data["points"].get(user_id, 0) + 1
                del data["active_missions"][user_id]
                save_data()

                # Announce it publicly in the channel where it happened
                await message.channel.send(
                    f"🎯 Oppdrag fullført! {message.author.mention} sa hemmelig ordet "
                    f"**\"{matched_trigger}\"** og ga <@{user_id}> ett poeng! "
                    f"(Totalt: {data['points'][user_id]} poeng)"
                )

                # Also DM the player directly
                try:
                    player = await bot.fetch_user(int(user_id))
                    await player.send(
                        f"✅ Oppdraget ditt er fullført! Ordet var \"{matched_trigger}\". "
                        f"Du har nå {data['points'][user_id]} poeng. "
                        f"Skriv `!oppdrag` for et nytt oppdrag."
                    )
                except discord.Forbidden:
                    pass  # can't DM them, no big deal

    # This line is required so normal commands (!hello, !comrade, etc.) still work
    await bot.process_commands(message)


@bot.command()
async def hello(ctx):
    await ctx.send(f"Hey {ctx.author.mention}! 👋")


@bot.command()
async def comrade(ctx):
    line = random.choice(QUOTES)
    while line == last_quote["value"] and len(QUOTES) > 1:
        line = random.choice(QUOTES)
    last_quote["value"] = line
    await ctx.send(f"☭ Comrade {ctx.author.mention}, {line}")


@bot.command()
async def oppdrag(ctx):
    user_id = str(ctx.author.id)

    # If they already have a mission in progress, remind them instead of
    # handing out a new one — unless it's expired, in which case treat it
    # as if they have none
    if user_id in data["active_missions"]:
        mission = data["active_missions"][user_id]
        if mission_is_expired(mission):
            del data["active_missions"][user_id]
            save_data()
        else:
            try:
                await ctx.author.send(f"Du har allerede et pågående oppdrag:\n{mission['text']}")
            except discord.Forbidden:
                await ctx.send(f"{ctx.author.mention}, jeg kan ikke sende deg DM! Skru på DM-er fra medlemmer.")
            return

    mission = random.choice(MISSIONS)
    data["active_missions"][user_id] = {
        "text": mission["text"],
        "triggers": mission["triggers"],
        "assigned_at": now_iso(),
    }
    save_data()

    try:
        await ctx.author.send(
            f"🎯 Ditt oppdrag, kamerat: {mission['text']}\n\n"
            f"Få noen andre i serveren til å si det — jeg følger med. "
            f"Oppdraget utløper om en uke hvis det ikke fullføres."
        )
        await ctx.send(f"{ctx.author.mention}, sjekk DM-ene dine for oppdraget ditt! 🎯")
    except discord.Forbidden:
        # Couldn't DM them, so undo the assignment
        del data["active_missions"][user_id]
        save_data()
        await ctx.send(f"{ctx.author.mention}, jeg kan ikke sende deg DM! Skru på DM-er fra medlemmer og prøv igjen.")


@bot.command(name="nyttoppdrag")
async def nyttoppdrag(ctx):
    user_id = str(ctx.author.id)

    if user_id not in data["active_missions"]:
        await ctx.send(f"{ctx.author.mention}, du har ikke noe aktivt oppdrag å bytte. Skriv `!oppdrag` for å få et.")
        return

    count = recent_swap_count(user_id)
    if count >= MAX_SWAPS_PER_WEEK:
        save_data()  # recent_swap_count may have pruned old entries
        await ctx.send(
            f"{ctx.author.mention}, du har allerede byttet oppdrag {MAX_SWAPS_PER_WEEK} ganger denne uken. "
            f"Prøv igjen senere."
        )
        return

    old_mission = data["active_missions"][user_id]
    new_mission = random.choice(MISSIONS)
    # Try not to hand back the exact same mission they already had
    while new_mission["text"] == old_mission["text"] and len(MISSIONS) > 1:
        new_mission = random.choice(MISSIONS)

    data["active_missions"][user_id] = {
        "text": new_mission["text"],
        "triggers": new_mission["triggers"],
        "assigned_at": now_iso(),
    }
    data["swaps"].setdefault(user_id, []).append(now_iso())
    save_data()

    try:
        await ctx.author.send(
            f"🔄 Nytt oppdrag: {new_mission['text']}\n\n"
            f"Du har brukt {count + 1}/{MAX_SWAPS_PER_WEEK} bytter denne uken."
        )
        await ctx.send(f"{ctx.author.mention}, byttet oppdrag! Sjekk DM-ene dine. 🔄")
    except discord.Forbidden:
        await ctx.send(f"{ctx.author.mention}, jeg kan ikke sende deg DM! Skru på DM-er fra medlemmer.")


@bot.command()
async def leaderboard(ctx):
    if not data["points"]:
        await ctx.send("Ingen poeng ennå, kamerater! Skriv `!oppdrag` for å få et oppdrag.")
        return

    sorted_points = sorted(data["points"].items(), key=lambda x: x[1], reverse=True)

    lines = ["🏆 **Leaderboard** 🏆"]
    for i, (user_id, score) in enumerate(sorted_points, start=1):
        member = ctx.guild.get_member(int(user_id))
        name = member.display_name if member else f"Unknown user ({user_id})"
        lines.append(f"{i}. {name} — {score} point(s)")

    await ctx.send("\n".join(lines))


@bot.command()
async def rules(ctx):
    await ctx.send(
        "📖 **Velkommen til Oppdrag-spillet, kamerat!**\n\n"
        "Dette er et hemmelig oppdrag-spill som foregår i denne serveren.\n\n"
        "**Slik fungerer det:**\n"
        "1️⃣ Skriv `!oppdrag` for å få et hemmelig oppdrag sendt til deg i DM (privatmelding).\n"
        "2️⃣ Oppdraget ber deg om å få **et annet medlem** til å si et bestemt ord eller uttrykk "
        "— uten å avsløre for dem hva ordet er! Det er poenget med spillet.\n"
        "3️⃣ Så snart noen andre enn deg sier ordet et sted i serveren, oppdager boten det automatisk. "
        "Du får da ett poeng, og det blir annonsert i kanalen hvem som sa ordet.\n"
        "4️⃣ Du kan bare ha ett aktivt oppdrag om gangen. Når det er fullført, kan du skrive "
        "`!oppdrag` igjen for et nytt.\n"
        "5️⃣ Et oppdrag utløper automatisk etter **én uke** hvis det ikke er fullført — da kan du "
        "bare be om et nytt med `!oppdrag`.\n"
        "6️⃣ Vil du bytte oppdraget ditt før det er fullført? Skriv `!nyttoppdrag` — men du kan "
        f"bare gjøre dette **{MAX_SWAPS_PER_WEEK} ganger per uke**.\n"
        "7️⃣ ⚠️ Pass på: hvis **du selv** sier ditt eget hemmelige ord, mislykkes oppdraget! "
        "Første gang skjer det uten straff, men gjør du det igjen mister du ett poeng.\n\n"
        "**Kommandoer:**\n"
        "`!oppdrag` — få et nytt hemmelig oppdrag (sendt i DM)\n"
        "`!nyttoppdrag` — bytt ut ditt nåværende oppdrag med et nytt (maks 3x/uke)\n"
        "`!leaderboard` — se poengtavlen for hele serveren\n"
        "`!comrade` — få en tilfeldig kommissær-kommentar\n"
        "`!hello` — si hei til boten\n"
        "`!rules` — vis denne meldingen igjen\n\n"
        "Lykke til, kamerat. Komitéen følger med. ☭"
    )


bot.run(TOKEN)