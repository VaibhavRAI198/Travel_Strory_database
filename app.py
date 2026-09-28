from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
import os

app = Flask(__name__)
app.secret_key = "travel_story_database"

USERNAME = "raiv"
PASSWORD = "64843810"

def get_db_connection():
    return psycopg2.connect(os.environ["DATABASE_URL"])
    
@app.route("/")
def home():
    return redirect(url_for("database"))

@app.route("/database", methods=["GET", "POST"])
def database():
    error = None
    tables = []
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if username == USERNAME and password == PASSWORD:
            session["database_authorized"] = True
            return redirect(url_for("database"))
        error = "Unauthorized: Invalid username or password."
    authorized = session.get("database_authorized", False)
    if authorized:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """)
            table_rows = cursor.fetchall()
            for row in table_rows:
                table_name = row[0]
                cursor.execute("""
                    SELECT
                        column_name,
                        data_type,
                        is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = %s
                    ORDER BY ordinal_position;
                """, (table_name,))
                columns = cursor.fetchall()
                cursor.execute(
                    f'SELECT * FROM "{table_name}"'
                )
                data = cursor.fetchall()
                column_names = [desc[0] for desc in cursor.description]
                tables.append({
                    "name": table_name,
                    "columns": columns,
                    "column_names": column_names,
                    "data": data
                })
            cursor.close()
            conn.close()
        except Exception as e:
            error = f"Database error: {e}"
    return render_template( "index.html", authorized=authorized, error=error, tables=tables)


@app.route("/delete_table", methods=["POST"])
def delete_table():
    if not session.get("database_authorized", False):
        return redirect(url_for("database"))
    table_name = request.form.get("table_name", "").strip()
    if not table_name:
        return redirect(url_for("database"))
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = %s
            );
        """, (table_name,))
        exists = cursor.fetchone()[0]
        if not exists:
            cursor.close()
            conn.close()
            return redirect(url_for("database"))
        cursor.execute('DROP TABLE public."' + table_name.replace('"', '""') + '" CASCADE')
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for("database"))
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return render_template("index.html",authorized=True,error=f"Unable to delete table: {e}",tables=[])

@app.route("/database_logout")
def database_logout():
    session.pop("database_authorized", None)
    return redirect(url_for("database"))

@app.route("/edit_table", methods=["GET", "POST"])
def edit_table():
    if not session.get("database_authorized", False):
        return redirect(url_for("database"))
    if request.method == "GET":
        return render_template("edit_table.html")
    return render_template("edit_table.html")


@app.route("/create_table", methods=["GET", "POST"])
def create_table():
    if not session.get("database_authorized", False):
        return redirect(url_for("database"))
    if request.method == "GET":
        return render_template("create_table.html")
    return render_template("create_table.html")

@app.route("/create_table", methods=["GET", "POST"])
def create_table():

    # Check authorization
    if not session.get("database_authorized", False):
        return redirect(url_for("database"))

    if request.method == "GET":
        return render_template("createtable.html")

    # Get table name from HTML
    table_name = request.form.get("table_name", "").strip()

    # Get columns from HTML
    column_names = request.form.getlist("column_name")
    data_types = request.form.getlist("data_type")

    if not table_name:
        return render_template(
            "createtable.html",
            error="Table name is required."
        )

    if not column_names:
        return render_template(
            "createtable.html",
            error="At least one column is required."
        )

    # Validate table name
    if not table_name.replace("_", "").isalnum():
        return render_template(
            "createtable.html",
            error="Invalid table name."
        )

    allowed_types = {
        "INTEGER",
        "BIGINT",
        "SERIAL",
        "BIGSERIAL",
        "VARCHAR(255)",
        "TEXT",
        "BOOLEAN",
        "DATE",
        "TIMESTAMP",
        "NUMERIC",
        "REAL",
        "DOUBLE PRECISION"
    }

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check table already exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = %s
            )
        """, (table_name,))

        if cursor.fetchone()[0]:

            cursor.close()
            conn.close()

            return render_template(
                "createtable.html",
                error=f"Table '{table_name}' already exists."
            )

        # Build columns
        column_definitions = []

        for column_name, data_type in zip(
            column_names,
            data_types
        ):

            column_name = column_name.strip()
            data_type = data_type.strip().upper()

            if not column_name:
                raise ValueError(
                    "Column name cannot be empty."
                )

            if not column_name.replace("_", "").isalnum():
                raise ValueError(
                    f"Invalid column name: {column_name}"
                )

            if data_type not in allowed_types:
                raise ValueError(
                    f"Invalid data type: {data_type}"
                )

            column_definitions.append(
                f'"{column_name}" {data_type}'
            )

        # Create table
        sql = f'''
            CREATE TABLE public."{table_name}" (
                {", ".join(column_definitions)}
            )
        '''

        cursor.execute(sql)

        conn.commit()

        cursor.close()
        conn.close()

        return redirect(url_for("database"))

    except Exception as e:

        if "conn" in locals():
            conn.rollback()
            conn.close()

        return render_template(
            "createtable.html",
            error=f"Database error: {e}"
        )


if __name__ == "__main__":
    app.run(debug=True)
