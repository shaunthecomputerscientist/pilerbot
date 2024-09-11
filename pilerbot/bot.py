import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from discord.ext.commands import has_permissions
import sqlite3
from dotenv import load_dotenv
import os
from typing import List
from pilerbot.llms.llms import GenerativeModel
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, PromptTemplate, SystemMessagePromptTemplate
from pilerbot.tools.tools import Vision_Model
from pilerbot.langgraphworkflow import langgraph_agent,agent_utilities
from pilerbot.tools.tools import wikipedia,arxiv,search_tool, Calculator,retriever_on_web_data,current_time
import logging
# Load environment variables from a .env file
load_dotenv()

# # Database setup
# conn = sqlite3.connect('discord_users.db')
# c = conn.cursor()

# # Create the users table if it doesn't exist, including the last_online column
# c.execute('''CREATE TABLE IF NOT EXISTS users (
#              username TEXT PRIMARY KEY,
#              points INTEGER,
#              level TEXT,
#              last_online TIMESTAMP
#              )''')
# conn.commit()






import psycopg2
from psycopg2 import sql

# Database setup
conn = psycopg2.connect(
    host=os.getenv("DB_HOSTNAME", "localhost"),
    port=os.getenv("DB_PORT", "5432"),
    database=os.getenv("DB_NAME", "discord_users"),
    user=os.getenv("DB_USERNAME", "piler2024"),
    password=os.getenv("DB_PASSWORD", "12345678")
)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users (
             username TEXT PRIMARY KEY,
             points INTEGER,
             level TEXT,
             last_online TIMESTAMP
             )''')
conn.commit()

# Define constants
QUIZ_POINTS = {
    'hard': [10000, 5000, 2500],
    'medium': [1000, 500, 250],
    'easy': [100, 50, 25]
}

HELP_POINTS = 100

ROLE_THRESHOLDS = {
    "Novice": 0,
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



class PilerBot(commands.Cog):
    def __init__(self, bot,tools):
        self.bot = bot
        self.recent_users = set()  # Set to keep track of recent users
        self.clear_recent_users_loop.start()  # Start the task loop
        self.tools=tools
        self.llm_evaluate, self.llm_router, self.AnswerFormat, self.tool_mapping = agent_utilities(self.tools,"Given a user <query> use tool to answer. If you know the answer directly return the answer with no useless characters that invalidate json structure. Enclose property names/values of dictionary in quotes.","Given user query and other constraints, generate answer or use tool according to the given answer_schema with no useless characters that invalidate json structure. Enclose property names/values of dictionary in quotes.")
        self.agent = langgraph_agent(llm_evaluate=self.llm_evaluate, llm_router=self.llm_router, tool_mapping=self.tool_mapping, AnswerFormat=self.AnswerFormat)


    @commands.Cog.listener()
    async def on_ready(self):
        print(f"Logged in as {self.bot.user}")
        self.check_monthly_activity.start()  # Start the background task here

    def get_user(self, username):
        # Try to fetch the user from the database
        c.execute("SELECT * FROM users WHERE username = %s;", (username,))
        user = c.fetchone()

        # If the user does not exist, add them with default values
        if user is None:
            # Default points and level for new users
            default_points = 0
            default_level = "Novice"
            default_last_online = datetime.utcnow()
            c.execute("INSERT INTO users (username, points, level, last_online) VALUES (%s, %s, %s, %s);",
                    (username, default_points, default_level, default_last_online))
            conn.commit()
            # Fetch the newly added user
            c.execute("SELECT * FROM users WHERE username = %s;", (username,))
            user = c.fetchone()

        return user

    def askagent(self, query: str):
        try:
            response = self.agent.initiate_agent(query)
            return response
        except Exception as e:
            print(e)
            return e

    
    @commands.command(name='askpileragent')
    async def askpileragent(self, ctx, *, query: str):
        # Replace 'langgraph_agent' with your actual agent logic
        try:
            response = self.askagent(query=query)
            
            # Send the response back to Discord channel
            await ctx.send(f"{response}")
        except Exception as e:
            await ctx.send(f"Error: {e}")

    def askpileragentforimage(self,query):
        response = self.askagent(query=query)
        return response




    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        

        username = message.author.name
        
        if username not in self.recent_users:
            
            try:
                # Update last online time in the database if the difference is more than 2 days
                self.update_last_online(message.author.name)
                self.recent_users.add(username)
            except Exception as e:
                print(f"Error updating last online time: {e}")
        
        # Process commands
        # await self.bot.process_commands(message)

    def update_last_online(self, username):
        current_time = datetime.utcnow()
        c.execute("SELECT last_online FROM users WHERE username = %s;", (username,))
        result = c.fetchone()
        print(result) 
        if result:
            last_online = result[0]
            if last_online:
                last_online_time = datetime.fromisoformat([last_online.isoformat() if isinstance(last_online,datetime) else last_online][0])
                # last_online_time = last_online
                # Check if the difference is more than 2 days
                
                if current_time - last_online_time > timedelta(days=1):
                    print(f'last online {last_online_time}. Updating to current time.')
                    self._update_last_online(username, current_time)
                else:
                    print('User was online in last 1 days')
            else:
                # If last_online is None, perform the update
                self._update_last_online(username, current_time)
        else:
            self.get_user(username=username)

    def _update_last_online(self, username, current_time):
        try:
            c.execute("UPDATE users SET last_online = %s WHERE username = %s;",
                      (current_time.isoformat(), username))
            conn.commit()
        except Exception as e:
            print(f"Error updating last online in database: {e}")


    @tasks.loop(hours=30)  # Runs every 24 hours
    async def clear_recent_users_loop(self):
        self.recent_users.clear()  # Empty the set of recent users
        print("Cleared the recent users set.")

    @clear_recent_users_loop.before_loop
    async def before_clear_recent_users_loop(self):
        await self.bot.wait_until_ready()  # Wait until the bot is ready
    

    def calculate_level(self, points):
        for level, threshold in sorted(ROLE_THRESHOLDS.items(), key=lambda x: x[1], reverse=True):
            if points >= threshold:
                return level
        return "Novice"
    def subtract_points(self, username, points_to_subtract):
        # Fetch the user from the database
        user = self.get_user(username)
        
        if user:
            # Calculate the new points, ensuring it does not go below zero
            new_points = max(user[1] - points_to_subtract, 0)
            new_level = self.calculate_level(new_points)
            
            # Update the user in the database
            c.execute("UPDATE users SET points = %s, level = %s WHERE username = %s;",
                    (new_points, new_level, username))
            conn.commit()
            
            return new_points, new_level
        return None
    @commands.command(name="subtractpilerpoints")
    @commands.has_permissions(administrator=True)
    async def subtract_points_command(self, ctx, points: int, *members: discord.Member):
        # Ensure points are positive
        if points <= 0:
            await ctx.send("Points must be a positive integer.")
            return

        if not members:
            await ctx.send("Please specify at least one user.")
            return

        for member in members:
            # Call the function to subtract points
            new_points, new_level = self.subtract_points(member.name, points)
            
            if new_points is not None:
                await ctx.send(f"{member.mention} has had {points} points subtracted. They now have {new_points} points and their new level is {new_level}.")
                await self.assign_role(member=member)
            else:
                await ctx.send(f"Could not find user {member.mention}.")

        print('subtracting points from users')        
    @commands.command(name='recentusers')
    async def show_recent_users(self,ctx):

        await ctx.send(f"These are recent users : {self.recent_users}")
    def update_user_points(self, username, points):
        user = self.get_user(username)
        if user:
            new_points = max(user[1] + points, 0)
            new_level = self.calculate_level(new_points)
            last_online = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            c.execute("UPDATE users SET points = %s, level = %s, last_online = %s WHERE username = %s;",
                      (new_points, new_level, last_online, username))
            conn.commit()
            return new_points, new_level
        return None


    @tasks.loop(hours=720)
    async def check_monthly_activity(self):
        c.execute("SELECT username, points, last_online FROM users;")
        users = c.fetchall()
        for username, points, last_online in users:
            if not isinstance(last_online, str):
                last_online = str(last_online)
            try:
                # Adjust the format to include fractional seconds
                last_online_date = datetime.strptime(last_online, '%Y-%m-%d %H:%M:%S.%f')
            except ValueError as e:
                # Handle the case where the fractional seconds might not be present
                try:
                    last_online_date = datetime.strptime(last_online, '%Y-%m-%d %H:%M:%S')
                except ValueError as e:
                    print(f"Error parsing date for {username}: {e}")
                    continue

            if points > 0 and (datetime.utcnow() - last_online_date).days >= 30:
                new_points, new_level = self.update_user_points(username, -100)
                print(f"{username} has been deducted 100 points. New points: {new_points}, New level: {new_level}")


    @commands.command(name="checklevels")
    async def check_levels(self, ctx, *members: discord.Member):
        if not members:
            members = [ctx.message.author]

        results = []

        for member in members:
            user = self.get_user(member.name)
            if user:
                results.append(f"{member.mention}, you have {user[1]} points and your level is {user[2]}.")
            else:
                results.append(f"{member.mention}, you have no points yet.")

        await ctx.send("\n".join(results))

    @commands.command(name="lastonline")
    async def check_last_online(self, ctx, member: discord.Member = None):
        member = member or ctx.message.author
        user = self.get_user(member.name)
        if user:
            await ctx.send(f"{member.mention}, your last online time was {user[3]}.")
        else:
            await ctx.send(f"{member.mention}, no last online time found.")

    @commands.command(name="quizpoints")
    @commands.has_permissions(administrator=True)
    async def quiz(self, ctx, difficulty: str, first_place: discord.Member, second_place: discord.Member = None, third_place: discord.Member = None):
        if difficulty.lower() in QUIZ_POINTS:
            print('Updating quiz points for top three quizzers.')
            points = QUIZ_POINTS[difficulty.lower()]
            participants = [first_place, second_place, third_place]
            print(participants)

            for i, participant in enumerate(participants):
                if participant:
                    self.update_user_points(participant.name, points[i])

            for participant in participants:
                if participant:
                    print('Updating roles')
                    await self.assign_role(participant)
                print('Roles updated')


            await ctx.send(f"Points awarded to quiz participants based on {difficulty} difficulty.")

    @commands.command(name="helpeduser")
    @commands.has_permissions(administrator=True)
    async def help_command(self, ctx, helper: discord.Member):
        self.update_user_points(helper.name, HELP_POINTS)
        await ctx.send(f"{helper.display_name} has been awarded {HELP_POINTS} points for helping!")
        await self.assign_role(helper)
        # print(discord.utils.get(helper.guild.roles, name=[self.calculate_level(self.get_user(helper.name)[1])][0]))
        # await helper.add_roles(discord.utils.get(helper.guild.roles, name=[self.calculate_level(self.get_user(helper.name)[1])][0]))
        # print('helped someone')
        # await ctx.send(f"{helper.display_name} has been awarded {HELP_POINTS} points for helping!")
    
    @commands.command(name="addpilerpoints")
    @commands.has_permissions(administrator=True)
    async def add_points(self, ctx, points: int, *members: discord.Member):
        print('inside addpoints')
        if points <= 0:
            await ctx.send("Points must be a positive integer.")
            return

        if not members:
            await ctx.send("Please specify at least one user.")
            return

        for member in members:
            # Update points using the helper function
            new_points, new_level = self.update_user_points(member.name, points)

            # Confirm the update
            await ctx.send(f"{member.mention} has been awarded {points} points. New total: {new_points} points, level: {new_level}.")
            await self.assign_role(member=member)

        print('adding points to users')
    async def assign_role(self,member: discord.Member):
        """Assigns a role to the member based on their points."""
        user = self.get_user(member.name)
        if user:
            points, level = user[1], user[2]
            print(f'User {member.name} has {points} points and level {level}')
            for role_name, threshold in ROLE_THRESHOLDS.items():
                role = discord.utils.get(member.guild.roles, name=role_name)
                print(role)
                if role:
                    if points >= threshold:
                        print("points > = threshold")
                        print(f"{self.calculate_level(points)}")
                        if role not in member.roles:
                            await member.add_roles(role)
                            # await member.send(f"Congratulations! You have been awarded the {role_name} role for earning {points} points.")
                            await member.send(f"Congratulations! You have been awarded the {role_name} role for earning {points} points.")

                    else:
                        print("points < threshold")
                        if role in member.roles:
                            await member.remove_roles(role)
                            await member.add_roles(self.calculate_level(points))
                            # await member.send(f"Your {role_name} role has been removed as your points dropped below {threshold}.")
                            await member.send(f"Your {role_name} role has been removed as your points dropped below {threshold}.")

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You do not have permission to use this command.")
        elif isinstance(error, commands.CommandNotFound):
            await ctx.send("This command does not exist.")
        # else:
        #     await ctx.send(f"An error occurred: {error}")
    @commands.command(name='pileraskimage')
    async def pileraskimage(self,ctx,*, prompt: str):
    # Ensure the message has an attachment
        print('1')
        print(ctx.message.attachments)
        if not ctx.message.attachments:
            print('2')
            await ctx.send("Please attach an image with your prompt.")
            return
        print('3')
        # Get the first attachment (you can modify to handle multiple attachments)
        attachment = ctx.message.attachments[0]
        print(attachment)

        valid_image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']
        if not any(attachment.filename.lower().endswith(ext) for ext in valid_image_extensions):
            await ctx.send("The attached file is not a valid image type. Please attach a valid image (jpg, png, etc.).")
            return

        # Save the image locally
        save_path = os.path.join('pilerbot', 'Database', 'images', attachment.filename)
        print(save_path)
        await attachment.save(save_path)
        
        try:
            # Process the image and prompt using the Vision class
            input_data={
                "model":None,
                "query":prompt+"describe the entire image for a blind person",
            }
            result = Vision_Model(
                **input_data
            )
            # result = vision_model.vision(query=prompt)

            await ctx.send(f"Image analysis result: {result}")

            prompt= f"Here is a description of the image/problem\n {result}\n find the answer of the problem."
            # Send the prompt to the model
            answer=self.askpileragentforimage(prompt)
            await ctx.send(f"{answer}")
        except Exception as e:
            await ctx.send(f"Error processing image: {str(e)}")
        
        # Clean up by deleting the saved image
        if os.path.exists(save_path):
            os.remove(save_path)


# Instantiate the bot
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)
async def main():
    print("PILER BOT INITIALIZED")
    await bot.add_cog(PilerBot(bot, tools = [wikipedia,arxiv,search_tool, Calculator,retriever_on_web_data,current_time] ))  # Await the add_cog call
    print("Calling PILER BOT")
    await bot.start(os.getenv('DISCORD_API_KEY'))