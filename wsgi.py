from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, request
from app import app as bolt_app, get_workspace_info, register_home_tab_handlers

# Initialize Flask app
flask_app = Flask(__name__)

# Add the app instance to make workspace_info accessible
bolt_app.get_workspace_info = get_workspace_info

# Register home tab handlers
register_home_tab_handlers(bolt_app)

# Create handler for Slack requests
handler = SlackRequestHandler(bolt_app)

@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)

# For Gunicorn
application = flask_app

if __name__ == "__main__":
    flask_app.run(port=3000)