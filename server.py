import logging
from flask import Flask, request, jsonify
from threading import Thread
from pilerbot.bot import main
import asyncio
import os

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/')
def home():
    return "Flask server is running!"

@app.route('/api/interactions', methods=['POST'])
def interactions():
    data = request.json
    # Handle the interaction from the bot here
    logger.info(f"Received interaction: {data}")
    return jsonify({"status": "success", "message": "Interaction received!"})

def run_discord_bot():
    logger.info("Starting Discord bot...")
    asyncio.run(main())
    logger.info("Discord bot stopped.")

def run_flask():
    # Get the port from environment variable or default to 5000
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Flask server is starting on port {port}")
    app.run(host='0.0.0.0', port=port)

# Start the Discord bot in a separate thread
flask_thread = Thread(target=run_flask)
logger.info('Starting bot thread')
flask_thread.start()
logger.info('Bot thread started')
run_discord_bot()