from flask import Flask, request, jsonify
from threading import Thread

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

def run():
    app.run(host='0.0.0.0', port=5000)
def keep_alive():
    t=Thread(target=run)
    t.start()

# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=5000)
