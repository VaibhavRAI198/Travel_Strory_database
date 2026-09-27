from flask import Flask, render_template, request, redirect, url_for, session
app = Flask(__name__)

app.secret_key = "travel_story_database"


USERNAME = "raiv"
PASSWORD = "64843810"

if __name__ == "__main__":
    app.run(debug=True)
