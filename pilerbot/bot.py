import discord
from discord.ext import commands, tasks
from collections import defaultdict
from datetime import datetime, timedelta
import sqlite3
from dotenv import load_dotenv
load_dotenv()
import os
import server

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="/", intents=intents)

# Define constants
QUIZ_POINTS = {
    'hard': [10000, 5000, 2500],
    'medium': [1000, 500, 250],
    'easy': [100, 50, 25]
}

HELP_POINTS = 100

ROLE_THRESHOLDS = {
    "Novice" : 0,
    "Beginner": 100,
    "Apprentice": 1000,
    "Intermediate": 10000,
    "Practitioner": 1000000,
    "Advanced": 500000,
    "Candidate Master": 10000000,
    "Master": 100000000,
    "Grand Master": 500000000,
    "Legendary": 1000000000
}

# Database setup
conn = sqlite3.connect('discord_users.db')
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS users (
             username TEXT PRIMARY KEY,
             points INTEGER,
             level TEXT
             )''')
conn.commit()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    check_monthly_activity.start()  # Start the monthly activity check

def get_user(username):
    c.execute("SELECT * FROM users WHERE username = ?", (username,))
    return c.fetchone()

def add_or_update_user(username, points=0):
    user = get_user(username)
    if user is None:
        c.execute("INSERT INTO users (username, points, level) VALUES (?, ?, ?)",
                  (username, points, "Novice"))
    else:
        c.execute("UPDATE users SET points = ?, level = ? WHERE username = ?",
                  (points, calculate_level(points), username))
    conn.commit()

def calculate_level(points):
    for level, threshold in sorted(ROLE_THRESHOLDS.items(), key=lambda x: x[1], reverse=True):
        if points >= threshold:
            return level
    return "Novice"

def update_user_points(username, points):
    user = get_user(username)
    if user:
        new_points = max(user[1] + points, 0)
        new_level = calculate_level(new_points)
        c.execute("UPDATE users SET points = ?, level = ? WHERE username = ?",
                  (new_points, new_level, username))
        conn.commit()
        return new_points, new_level
    return None

@tasks.loop(hours=720)
async def check_monthly_activity():
    c.execute("SELECT username, points FROM users")
    users = c.fetchall()
    for username, points in users:
        if points > 0:
            new_points, new_level = update_user_points(username, -10)
            print(f"{username} has been deducted 10 points. New points: {new_points}, New level: {new_level}")

@bot.command(name="quiz")
async def quiz(ctx, difficulty: str, first_place: discord.Member, second_place: discord.Member = None, third_place: discord.Member = None):
    if difficulty.lower() in QUIZ_POINTS:
        points = QUIZ_POINTS[difficulty.lower()]
        participants = [first_place, second_place, third_place]

        for i, participant in enumerate(participants):
            if participant:
                update_user_points(participant.name, points[i])

        for participant in participants:
            if participant:
                await assign_role(participant)

        await ctx.send(f"Points awarded to quiz participants based on {difficulty} difficulty.")

@bot.command(name="help")
async def help_command(ctx, helper: discord.Member):
    update_user_points(helper.name, HELP_POINTS)
    await assign_role(helper)
    await ctx.send(f"{helper.display_name} has been awarded {HELP_POINTS} points for helping!")

@bot.command(name="points")
async def check_points(ctx, member: discord.Member = None):
    member = member or ctx.message.author
    user = get_user(member.name)
    if user:
        await ctx.send(f"{member.mention}, you have {user[1]} points and your level is {user[2]}.")
    else:
        await ctx.send(f"{member.mention}, you have no points yet.")


async def assign_role(member: discord.Member):
    """Assigns a role to the member based on their points."""
    user = get_user(member.name)
    if user:
        points, level = user[1], user[2]
        for role_name, threshold in ROLE_THRESHOLDS.items():
            role = discord.utils.get(member.guild.roles, name=role_name)
            if role:
                if points >= threshold:
                    if role not in member.roles:
                        await member.add_roles(role)
                        await member.send(f"Congratulations! You have been awarded the {role_name} role for earning {points} points.")
                else:
                    if role in member.roles:
                        await member.remove_roles(role)
                        await member.send(f"Your {role_name} role has been removed as your points dropped below {threshold}.")

# server.keep_alive()
bot.run(os.environ.get('DISCORD_API_KEY'))