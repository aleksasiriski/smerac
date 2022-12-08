import os
import sys
import logging
import asyncio
import discord
import requests
import json
import numpy as np
import matplotlib.pyplot as plt
from datetime import *

log = logging.getLogger("smerac")
config = dict()

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def setup_logger(config):
    if os.getenv("DEBUG") == None:
        logging_level = logging.INFO
    else:
        logging_level = logging.DEBUG

    logging.basicConfig(
        filename=config["log_file"],
        level=logging_level,
        format="%(asctime)s - %(name)s[%(process)s] - %(levelname)s - %(message)s",
    )

def fail(msg):
    print(msg)
    exit(1)

def setup():
    config = dict()

    LOG_FILE = os.getenv("LOG_FILE")
    if LOG_FILE == None:
        LOG_FILE = "/config/logs/%s.log"%(datetime.today().strftime())
    config["log_file"] = LOG_FILE

    UNIDENTIFIED_HOURS = os.getenv("UNIDENTIFIED_HOURS")
    if UNIDENTIFIED_HOURS == None:
        UNIDENTIFIED_HOURS = 1
    config["unidentified_hours"] = UNIDENTIFIED_HOURS

    CALENDAR_HOURS = os.getenv("CALENDAR_HOURS")
    if CALENDAR_HOURS == None:
        CALENDAR_HOURS = 3
    config["calendar_hours"] = CALENDAR_HOURS

    COMMAND = os.getenv("COMMAND")
    if COMMAND == None:
        COMMAND = "/smer"
    config["command"] = COMMAND

    SAVED_PLOTS = os.getenv("SAVED_PLOTS")
    if SAVED_PLOTS == None:
        SAVED_PLOTS = "/config/savedplots"
    config["saved_plots"] = SAVED_PLOTS

    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    if DISCORD_TOKEN == None:
        fail("DISCORD_TOKEN env isn't set")
    config["discord_token"] = DISCORD_TOKEN

    NUMBER_OF_ROLES = int(os.getenv("NUMBER_OF_ROLES"))
    if NUMBER_OF_ROLES == None:
        fail("NUMBER_OF_ROLES env isn't set")

    ROLES = []
    for i in range(NUMBER_OF_ROLES):
        ROLE = os.getenv("ROLE_" + str(i+1))
        if ROLE == None:
            fail("ROLE_%s env isn't set"%(str(i+1)))
        ROLES.append(ROLE)
    config["roles"] = ROLES

    return config

@client.event
async def on_connect():
    log.info("Connected to discord!")

@client.event
async def on_ready():
    log.info("Logged in as " + client.user)
    config = setup()
    asyncio.create_task(unidentified(int(config["unidentified_hours"])*3600))
    asyncio.create_task(calendar(config, int(config["calendar_hours"])*3600))

@client.event
async def on_message(message):
    config = setup()
    user = message.author
    content = message.content

    if user == client.user:
        return

    if content.startswith(config["command"]):
        wanted_role = "null"
        discord_roles = []

        if content.endswith("none"):
            wanted_role = "none"
        for role in config["roles"]:
            discord_role = discord.utils.get(message.guild.roles, name=role)
            discord_roles.append(discord_role)
            if (wanted_role != "none") and (content.endswith(role.lower()) or content.endswith(role.upper())):
                wanted_role = discord_role

        if wanted_role != "null":
            for discord_role in discord_roles:
                await user.remove_roles(discord_role, reason="Requested removal: " + discord_role.name, atomic=True)
        
            if wanted_role != "none":
                await user.add_roles(wanted_role, reason="Requested role: " + wanted_role.name, atomic=True)
                msg = "Successfully added " + user.display_name + " to " + wanted_role.name
            else:
                msg = "Successfully removed " + user.display_name + " from all roles"
            
            log.info(msg)
            await message.channel.send(msg, delete_after=5)
            await message.delete(delay=3)

        else:
            msg = "That role doesn't exist"
            await message.channel.send(msg, delete_after=5)
            await message.delete(delay=3)

    else:
        msg = "Wrong command or trying to spam. Please write the command correctly and don't spam this channel."
        await message.channel.send(msg, delete_after=5)
        await message.delete(delay=3)

async def unidentified(delay):
    for guild in client.guilds:
        for channel in guild.channels:
            if channel.name == "unidentified":
                msg = "@everyone Idite u kanal #smerovi i odaberite smer."
                asyncio.create_task(spamToJoin(channel, msg, delay))

async def spamToJoin(channel, msg, delay):
    await channel.purge()
    while True:
        await channel.send(msg, delete_after=delay)
        await asyncio.sleep(delay)

async def calendar(config, delay):
    for guild in client.guilds:
        for category in guild.categories:
            if category.name == "calendar":
                for channel in category.channels:
                    for role in config["roles"]:
                        if role.lower() == channel.name.lower():
                            CALENDAR_URL = os.getenv("CALENDAR_URL_" + role)
                            if CALENDAR_URL == None:
                                log.info("CALENDAR_URL_%s env isn't set, skipping."%(role))
                            else:
                                asyncio.create_task(updateCalendar(config, channel, CALENDAR_URL, delay))

def dayInWeek(dayInt):
    switcher = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}
    return switcher.get(dayInt, "Error!")

def dayInWeekSrpski(day):
    switcher = {"mon": "Ponedeljak", "tue": "Utorak", "wed": "Sreda", "thu": "Četvrtak", "fri": "Petak", "sat": "Subota", "sun": "Nedelja"}
    return switcher.get(day, "Error!")

async def generateWeek(events):
    current_date = date.today()
    week = {"mon": [], "tue": [], "wed": [], "thu": [], "fri": [], "sat": [], "sun": []}

    for event in events:
        start_date = datetime.fromisoformat(event["start"]["dateTime"]).date()
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
        week[weekday].sort(key = lambda event : datetime.fromisoformat(event["start"]["dateTime"]))

    return week

async def parseWeek(week_data):
    week = {"mon": [], "tue": [], "wed": [], "thu": [], "fri": [], "sat": [], "sun": []}

    for weekday in week_data:
        if week_data[weekday] != []:
            for event in week_data[weekday]:
                name, info = event["summary"].split(",", 1)
                start_time = datetime.fromisoformat(event["start"]["dateTime"]).strftime("%H:%M")
                end_time = datetime.fromisoformat(event["end"]["dateTime"]).strftime("%H:%M")

                foundEvent = False
                if week[weekday] != []:
                    for event_old in week[weekday]:

                        if name.lower().replace(" ", "") == event_old["name"].lower().replace(" ", ""):

                            foundInfo = False
                            for info_old in event_old["info"]:
                                if info.lower().replace(" ", "") == info_old["name"].lower().replace(" ", ""):
                                    info_old["start_times"].append(start_time)
                                    info_old["end_times"].append(end_time)
                                    foundInfo = True
                                    break
                            if not foundInfo:
                                new_info = {"name": info, "start_times": [], "end_times": []}
                                new_info["start_times"].append(start_time)
                                new_info["end_times"].append(end_time)
                                event_old["info"].append(new_info)

                            foundEvent = True
                            break

                if not foundEvent:
                    new_event = {"name": name, "info": []}
                    new_info = {"name": info, "start_times": [], "end_times": []}
                    new_info["start_times"].append(start_time)
                    new_info["end_times"].append(end_time)
                    new_event["info"].append(new_info)
                    week[weekday].append(new_event)
    
    return week

async def updateCalendar(config, channel, calendar_url, delay):
    spacer = "-------------------------"
    week_old = dict()

    while True:
        calendar = json.loads(requests.get(calendar_url).text)

        week_data = await generateWeek(calendar["items"])
        week = await parseWeek(week_data)

        if week_old != week:
            log.debug(str(week_old))
            log.debug("----- week_old != week -----")
            log.debug(str(week))

            week_old = week

            await channel.purge()

            for weekday in week:
                if week[weekday] != []:
                    day_output = spacer
                    day_output += "\n\n**" + dayInWeekSrpski(weekday) + ":**\n\n"

                    for event in week[weekday]:
                        day_output += "--- " + event["name"] + " ---\n"

                        for info in event["info"]:
                            day_output += info["name"] + "\n"

                            for i in range(len(info["start_times"])):
                                day_output += "**" + info["start_times"][i] + "** - " + info["end_times"][i] + "\n"

                        day_output += "\n"
                    day_output += spacer

                    await channel.send(day_output)

            await channel.send(file = await classesPerDayGraph(config, channel.name, week))

        await asyncio.sleep(delay)

async def classesPerDayGraph(channel_name, week):
    filename = config["saved_plots"] + "/" + channel_name + ".png"
    data = dict()

    for weekday in week:
        data[dayInWeekSrpski(weekday)] = len(week[weekday])

    keys = list(data.keys())
    values = list(data.values())

    fig = plt.figure(figsize = (10, 5))

    plt.bar(keys, values, color ='maroon', width = 0.2)

    plt.xlabel("Dani")
    plt.ylabel("Broj časova")
    plt.title("Broj časova po danu.")

    plt.savefig(filename)
    plt.close()

    return discord.File(filename)

if __name__ == "__main__":
    log.info("Starting Smerac!")

    config = setup()
    setup_logger(config)

    client.run(config["discord_token"])