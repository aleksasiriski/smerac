import os
import sys
import logging

import asyncio
import interactions

import requests
import json

import numpy as np
import matplotlib.pyplot as plt

from datetime import *

# Setup

def fail(msg):
    print(msg)
    exit(1)

def setup_config():
    config = dict()

    LOG_FILE = os.getenv("LOG_FILE")
    if LOG_FILE == None:
        LOG_FILE = "/config/logs/%s.log"%(datetime.today().strftime("%Y-%m-%d-%H-%M-%S"))
    config["log_file"] = LOG_FILE

    CALENDAR_HOURS = os.getenv("CALENDAR_HOURS")
    if CALENDAR_HOURS == None:
        CALENDAR_HOURS = 3
    config["calendar_hours"] = int(CALENDAR_HOURS)*3600

    COMMAND = os.getenv("COMMAND")
    if COMMAND == None:
        COMMAND = "smer"
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

# Global variables

log = logging.getLogger("smerac")
config = setup_config()
bot = interactions.Client(token=config["discord_token"])

# Used by both Commands and Calendar

def check_pinned(message):
    return not message.pinned

# Commands

@bot.command(
    name="smer",
    description="Choose your role!",
    scope=1026925641708339301,
    options = [
        interactions.Option(
            name="wanted_role",
            description="The role you want.",
            type=interactions.OptionType.STRING,
            required=True,
        ),
    ],
)
async def choose_role(ctx: interactions.CommandContext, wanted_role: str):
    author = ctx.author

    log.debug(f"Started choosing role for {author.nick}")

    guild = await ctx.get_guild()
    discord_roles = await guild.get_all_roles()

    for author_role_id in author.roles:
        author_role = await guild.get_role(author_role_id)
        for role in config["roles"]:
            if role.upper() == author_role.name.upper():
                await author.remove_role(author_role_id)
                log.debug(f"Removed {author.nick} from {role}")
            else:
                log.debug(f"Role {role} isn't {author_role.name}")
    
    if wanted_role != "none":
        for role in config["roles"]:
            if wanted_role.upper() == role.upper():
                for discord_role in discord_roles:
                    if wanted_role.upper() == discord_role.name.upper():
                        await author.add_role(discord_role.id)
                        break
                break
        log.info(f"Added {author.nick} to {wanted_role}.")
        message = await ctx.send(f"Succesfully added {author.nick} to {wanted_role.upper()}!")
        await asyncio.sleep(5)
        await message.delete()
    else:
        log.info(f"Removed {author.nick} from all roles.")
        message = await ctx.send(f"Succesfully removed {author.nick} from all roles!")
        await asyncio.sleep(5)
        await message.delete()

# Calendar

async def calendar(delay):
    log.debug("Calendar")

    for guild in bot.guilds:
        channels = await guild.get_all_channels()
        for category in channels:
            if category.type == interactions.ChannelType.GUILD_CATEGORY and category.name.upper() == "calendar":
                for role in config["roles"]:
                    for channel in channels:
                        if channel.parent_id == category.id and role.upper() == channel.name.upper():
                            CALENDAR_URL = os.getenv("CALENDAR_URL_" + role)
                            if CALENDAR_URL == None:
                                log.info("CALENDAR_URL_%s env isn't set, skipping."%(role))
                            else:
                                asyncio.create_task(updateCalendar(channel, CALENDAR_URL, delay))
                            break
                break

def dayInWeek(dayInt):
    switcher = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}
    return switcher.get(dayInt, "Error!")

def dayInWeekSrpski(day):
    switcher = {"mon": "Ponedeljak", "tue": "Utorak", "wed": "Sreda", "thu": "Četvrtak", "fri": "Petak", "sat": "Subota", "sun": "Nedelja"}
    return switcher.get(day, "Error!")

async def generateWeek(events):
    log.debug("Generating week")

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
    log.debug("Parsing week")

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

                        if name.upper().replace(" ", "") == event_old["name"].upper().replace(" ", ""):

                            foundInfo = False
                            for info_old in event_old["info"]:
                                if info.upper().replace(" ", "") == info_old["name"].upper().replace(" ", ""):
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

async def updateCalendar(channel, calendar_url, delay):
    log.debug("Updating calendar for " + channel.name)

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

            await channel.purge(8, check=check_pinned)

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

                    await channel.send(content=day_output)

            await channel.send(files = await classesPerDayGraph(channel.name, week))

        await asyncio.sleep(delay)

async def classesPerDayGraph(channel_name, week):
    log.debug("Plotting graph for " + channel_name)

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

    return interactions.File(filename=filename)

# Startup

@bot.event(name="on_start")
async def on_start():
    await bot.wait_until_ready()

    log.info("Started Smerac!")

    await calendar(config["calendar_hours"])

if __name__ == "__main__":
    log.info("Starting Smerac!")
    setup_logger(config)
    bot.start()