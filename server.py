from flask import Flask, request, jsonify
from threading import Thread
from pilerbot.bot import main
import asyncio
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "Flask server is running!"

@app.route('/api/interactions', methods=['POST'])
def interactions():
    data = request.json
    # Handle the interaction from the bot here
    print(f"Received interaction: {data}")
    return jsonify({"status": "success", "message": "Interaction received!"})

def run_discord_bot():
    asyncio.run(main())

if __name__ == "__main__":
    # Get the port from environment variable or default to 5000
    port = int(os.environ.get("PORT", 5000))
    print(port)

    # Start the Discord bot in a separate thread
    discord_thread = Thread(target=run_discord_bot)
    print('starting bot')
    discord_thread.start()
    print('bot started')

    # Start the Flask WSGI app
    app.run(host='0.0.0.0', port=port)
