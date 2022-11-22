import os

UNIDENTIFIED_HOURS = os.getenv("UNIDENTIFIED_HOURS")
CALENDAR_HOURS = os.getenv("CALENDAR_HOURS")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
NUMBER_OF_ROLES = int(os.getenv("NUMBER_OF_ROLES"))
roles = []
for i in range(NUMBER_OF_ROLES):
    role = os.getenv("ROLE_%s"%(str(i+1)))
    roles.append(role)

import asyncio, discord

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_connect():
    print(f"Connected to discord!")

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    asyncio.create_task(unidentified(UNIDENTIFIED_HOURS*3600))
    asyncio.create_task(calendar(CALENDAR_HOURS*3600))

@client.event
async def on_message(message):
    user = message.author
    content = message.content

    if user == client.user:
        return

    if content.startswith("!smer"):
        wanted_role = "null"
        discord_roles = []

        if content.endswith("none"):
            wanted_role = "none"
        for role in roles:
            discord_role = discord.utils.get(message.guild.roles, name=role)
            discord_roles.append(discord_role)
            if (wanted_role != "none") and (content.endswith(role.lower()) or content.endswith(role.upper())):
                wanted_role = discord_role

        if wanted_role != "null":
            for discord_role in discord_roles:
                await user.remove_roles(discord_role, reason="Requested removal: " + discord_role.name, atomic=True)
        
            log = ""
            if wanted_role != "none":
                await user.add_roles(wanted_role, reason="Requested role: " + wanted_role.name, atomic=True)
                log = "Successfully added " + user.display_name + " to " + wanted_role.name
            else:
                log = "Successfully removed " + user.display_name + " from all roles"
            print(log)
            await message.channel.send(log, delete_after=5)
            await message.delete(delay=3)

        else:
            log = "That role doesn't exist"
            await message.channel.send(log, delete_after=5)
            await message.delete(delay=3)

    else:
        log = "Wrong command or trying to spam. Please write the command correctly and don't spam this channel."
        await message.channel.send(log, delete_after=5)
        await message.delete(delay=3)

async def unidentified(delay):
    for guild in client.guilds:
        for channel in guild.channels:
            if channel.name == "unidentified":
                asyncio.create_task(spamToJoin(channel, "@everyone Idite u kanal #smerovi i odaberite smer.", delay))

async def spamToJoin(channel, msg, delay):
    await channel.purge()
    while True:
        await channel.send(msg, delete_after=delay)
        await asyncio.sleep(delay)

import requests, json
from datetime import *

async def calendar(delay):
    for guild in client.guilds:
        for category in guild.categories:
            if category.name == "calendar":
                for channel in category.channels:
                    for role in roles:
                        if role.lower() == channel.name.lower():
                            calendar_url = os.getenv("CALENDAR_URL_" + role)
                            asyncio.create_task(updateCalendar(channel, calendar_url, delay))

def dayInWeek(dayInt):
    switcher = {
        0: "mon",
        1: "tue",
        2: "wed",
        3: "thu",
        4: "fri",
        5: "sat",
        6: "sun"
    }
    return switcher.get(dayInt, "Error!")

def dayInWeekSrpski(day):
    switcher = {
        "mon": "Ponedeljak",
        "tue": "Utorak",
        "wed": "Sreda",
        "thu": "Četvrtak",
        "fri": "Petak",
        "sat": "Subota",
        "sun": "Nedelja"
    }
    return switcher.get(day, "Error!")

def sortByDateTime(event):
    return datetime.fromisoformat(event["start"]["dateTime"])

def isSameWeek(week, week_old):
    for weekday in week:
        if week[weekday] != week_old[weekday]:
            if len(week[weekday]) != len(week_old[weekday]):
                return False

            for i in range(len(week[weekday])):
                event = week[weekday][dayInWeek(i)]
                event_old = week_old[weekday][dayInWeek(i)]

                if event != event_old:
                    if event.summary != event_old.summary:
                        return False

                    start_datetime = datetime.fromisoformat(event["start"]["dateTime"])
                    start_datetime_old = datetime.fromisoformat(event_old["start"]["dateTime"])
                    start_time = start_datetime.time()
                    start_time_old = start_datetime_old.time()

                    if start_time != start_time_old:
                        return False

                    end_datetime = datetime.fromisoformat(event["end"]["dateTime"])
                    end_datetime_old = datetime.fromisoformat(event_old["end"]["dateTime"])
                    end_time = end_datetime.time()
                    end_time_old = end_datetime_old.time()

                    if end_time != end_time_old:
                        return False
    return True

async def updateCalendar(channel, calendar_url, delay):
    await channel.purge()
    spacer = "-------------------------"
    week_old = dict()

    while True:
        current_date = date.today()
        calendar = json.loads(requests.get(calendar_url).text)

        week = {"mon": [],"tue": [],"wed": [],"thu": [],"fri": [],"sat": [],"sun": []}
        for event in calendar["items"]:
            start_datetime = datetime.fromisoformat(event["start"]["dateTime"])
            start_date = start_datetime.date()
            if (start_date >= current_date) and (start_date < current_date + timedelta(days=7)):
                if dayInWeek(start_date.weekday()) == "mon":
                    week["mon"].append(event)
                elif dayInWeek(start_date.weekday()) == "tue":
                    week["tue"].append(event)
                elif dayInWeek(start_date.weekday()) == "wed":
                    week["wed"].append(event)
                elif dayInWeek(start_date.weekday()) == "thu":
                    week["thu"].append(event)
                elif dayInWeek(start_date.weekday()) == "fri":
                    week["fri"].append(event)
                elif dayInWeek(start_date.weekday()) == "sat":
                    week["sat"].append(event)
                elif dayInWeek(start_date.weekday()) == "sun":
                    week["sun"].append(event)
        
        for weekday in week:
            if week[weekday] != []:
                week[weekday].sort(key=sortByDateTime)

        if week_old == dict() or not isSameWeek(week, week_old):
            week_old = week
            await channel.purge()
            for weekday in week:
                if week[weekday] != []:
                    day_output = spacer
                    day_output += "\n\n**" + dayInWeekSrpski(weekday) + ":**\n\n"
                    for event in week[weekday]:
                        summary = event["summary"]
                        start_datetime = datetime.fromisoformat(event["start"]["dateTime"])
                        start_time = start_datetime.strftime("%H:%M")
                        end_datetime = datetime.fromisoformat(event["end"]["dateTime"])
                        end_time = end_datetime.strftime("%H:%M")
                        day_output += summary + "\n"
                        day_output += "**" + start_time + "** - " + end_time + "\n"
                    day_output += "\n" + spacer
                    await channel.send(day_output)

        await asyncio.sleep(delay)

if __name__ == "__main__":
    client.run(DISCORD_TOKEN)