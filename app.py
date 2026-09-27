from flask import Flask, render_template, request, redirect, url_for, session
app = Flask(__name__)

app.secret_key = "travel_story_database"

USERNAME = "raiv"
PASSWORD = "64843810"

@app.route("/")
def home():
    if "database_authorized" in session:
        return redirect(url_for("database"))
    return redirect(url_for("database"))
    
@app.route("/database", methods=["GET", "POST"])
def database():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if username == USERNAME and password == PASSWORD:
            session["database_authorized"] = True
            return redirect(url_for("database"))
        else:
            error = "Unauthorized: Invalid username or password."
    authorized = session.get("database_authorized", False)
    return render_template( "database.html", authorized=authorized,error=error)

@app.route("/database/logout")
def database_logout():
    session.pop("database_authorized", None)
    return redirect(url_for("database"))

if __name__ == "__main__":
    app.run(debug=True)
