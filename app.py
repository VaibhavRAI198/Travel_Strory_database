from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
from psycopg2 import sql
import os
import re

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "travel_story_database")

USERNAME = "raiv"
PASSWORD = "64843810"

ALLOWED_COLUMN_TYPES = {
    "VARCHAR(255)",
    "TEXT",
    "INTEGER",
    "BIGINT",
    "BOOLEAN",
    "DATE",
    "TIMESTAMP",
    "NUMERIC"
}


def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set.")

    return psycopg2.connect(database_url)


def valid_identifier(name):
    """
    Allow PostgreSQL table/column names containing:
    letters, numbers and underscore.
    Must start with a letter or underscore.
    """
    return bool(
        re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name or "")
    )


def get_tables():
    tables = []

    conn = None
    cursor = None

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

        for (table_name,) in table_rows:

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

            column_names = [
                column[0]
                for column in columns
            ]

            cursor.execute(
                sql.SQL("SELECT * FROM {}").format(
                    sql.Identifier(table_name)
                )
            )

            data = cursor.fetchall()

            tables.append({
                "name": table_name,
                "columns": columns,
                "column_names": column_names,
                "data": data
            })

    finally:
        if cursor:
            cursor.close()

        if conn:
            conn.close()

    return tables


@app.route("/")
def home():
    return redirect(url_for("database"))


@app.route("/database", methods=["GET", "POST"])
def database():

    error = None

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if username == USERNAME and password == PASSWORD:

            session["database_authorized"] = True

            return redirect(
                url_for("database")
            )

        error = "Unauthorized: Invalid username or password."

    authorized = session.get(
        "database_authorized",
        False
    )

    tables = []

    if authorized:

        try:

            tables = get_tables()

        except Exception as e:

            error = f"Database error: {e}"

    return render_template(
        "index.html",
        authorized=authorized,
        error=error,
        success=None,
        tables=tables
    )


@app.route("/create_table", methods=["POST"])
def create_table():

    if not session.get(
        "database_authorized",
        False
    ):
        return redirect(
            url_for("database")
        )

    table_name = request.form.get(
        "table_name",
        ""
    ).strip()

    column_names = request.form.getlist(
        "column_name[]"
    )

    column_types = request.form.getlist(
        "column_type[]"
    )

    table_name = table_name.strip()

    column_names = [
        name.strip()
        for name in column_names
    ]

    # -----------------------------
    # VALIDATE TABLE NAME
    # -----------------------------

    if not table_name:

        return render_database_error(
            "Table name is required."
        )

    if not valid_identifier(table_name):

        return render_database_error(
            "Invalid table name. Use only letters, numbers and underscore."
        )

    # -----------------------------
    # VALIDATE COLUMNS
    # -----------------------------

    if not column_names:

        return render_database_error(
            "At least one column is required."
        )

    if len(column_names) != len(column_types):

        return render_database_error(
            "Column information is invalid."
        )

    cleaned_columns = []

    for name, column_type in zip(
        column_names,
        column_types
    ):

        if not name:

            return render_database_error(
                "Column name cannot be empty."
            )

        if not valid_identifier(name):

            return render_database_error(
                f"Invalid column name: {name}"
            )

        if column_type not in ALLOWED_COLUMN_TYPES:

            return render_database_error(
                f"Invalid column type for column: {name}"
            )

        cleaned_columns.append(
            (name, column_type)
        )

    # -----------------------------
    # CHECK DUPLICATE COLUMNS
    # -----------------------------

    names = [
        name.lower()
        for name, _ in cleaned_columns
    ]

    if len(names) != len(set(names)):

        return render_database_error(
            "Duplicate column names are not allowed."
        )

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        # -----------------------------
        # CHECK TABLE EXISTS
        # -----------------------------

        cursor.execute("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = %s
            );
        """, (table_name,))

        exists = cursor.fetchone()[0]

        if exists:

            return render_database_error(
                f"Table '{table_name}' already exists."
            )

        # -----------------------------
        # BUILD CREATE TABLE
        # -----------------------------

        column_definitions = []

        for name, column_type in cleaned_columns:

            column_definitions.append(
                sql.SQL("{} {}").format(
                    sql.Identifier(name),
                    sql.SQL(column_type)
                )
            )

        query = sql.SQL(
            "CREATE TABLE {} ({})"
        ).format(
            sql.Identifier(table_name),
            sql.SQL(", ").join(
                column_definitions
            )
        )

        cursor.execute(query)

        conn.commit()

        return render_database_success(
            f"Table '{table_name}' created successfully."
        )

    except Exception as e:

        if conn:
            conn.rollback()

        return render_database_error(
            f"Unable to create table: {e}"
        )

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


@app.route("/edit_table", methods=["POST"])
def edit_table():

    if not session.get(
        "database_authorized",
        False
    ):
        return redirect(
            url_for("database")
        )

    old_table_name = request.form.get(
        "old_table_name",
        ""
    ).strip()

    table_name = request.form.get(
        "table_name",
        ""
    ).strip()

    column_names = request.form.getlist(
        "column_name[]"
    )

    column_types = request.form.getlist(
        "column_type[]"
    )

    # -----------------------------
    # VALIDATE TABLE NAMES
    # -----------------------------

    if not old_table_name:

        return render_database_error(
            "Original table name is missing."
        )

    if not valid_identifier(old_table_name):

        return render_database_error(
            "Invalid original table name."
        )

    if not table_name:

        return render_database_error(
            "Table name is required."
        )

    if not valid_identifier(table_name):

        return render_database_error(
            "Invalid table name."
        )

    # -----------------------------
    # VALIDATE COLUMNS
    # -----------------------------

    if not column_names:

        return render_database_error(
            "At least one column is required."
        )

    if len(column_names) != len(column_types):

        return render_database_error(
            "Column information is invalid."
        )

    cleaned_columns = []

    for name, column_type in zip(
        column_names,
        column_types
    ):

        name = name.strip()

        if not name:

            return render_database_error(
                "Column name cannot be empty."
            )

        if not valid_identifier(name):

            return render_database_error(
                f"Invalid column name: {name}"
            )

        if column_type not in ALLOWED_COLUMN_TYPES:

            return render_database_error(
                f"Invalid column type: {column_type}"
            )

        cleaned_columns.append(
            (name, column_type)
        )

    # -----------------------------
    # DUPLICATE COLUMNS
    # -----------------------------

    names = [
        name.lower()
        for name, _ in cleaned_columns
    ]

    if len(names) != len(set(names)):

        return render_database_error(
            "Duplicate column names are not allowed."
        )

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        # -----------------------------
        # CHECK ORIGINAL TABLE
        # -----------------------------

        cursor.execute("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = %s
            );
        """, (old_table_name,))

        old_exists = cursor.fetchone()[0]

        if not old_exists:

            return render_database_error(
                f"Table '{old_table_name}' does not exist."
            )

        # -----------------------------
        # CHECK NEW TABLE NAME
        # -----------------------------

        if old_table_name != table_name:

            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = %s
                );
            """, (table_name,))

            new_exists = cursor.fetchone()[0]

            if new_exists:

                return render_database_error(
                    f"Table '{table_name}' already exists."
                )

            # Rename table

            cursor.execute(
                sql.SQL(
                    "ALTER TABLE {} RENAME TO {}"
                ).format(
                    sql.Identifier(old_table_name),
                    sql.Identifier(table_name)
                )
            )

        # -----------------------------
        # GET EXISTING COLUMNS
        # -----------------------------

        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
            ORDER BY ordinal_position;
        """, (table_name,))

        existing_columns = [
            row[0]
            for row in cursor.fetchall()
        ]

        new_columns = [
            name
            for name, _ in cleaned_columns
        ]

        # -----------------------------
        # REMOVE COLUMNS
        # -----------------------------

        for old_column in existing_columns:

            if old_column not in new_columns:

                cursor.execute(
                    sql.SQL(
                        "ALTER TABLE {} DROP COLUMN {} CASCADE"
                    ).format(
                        sql.Identifier(table_name),
                        sql.Identifier(old_column)
                    )
                )

        # -----------------------------
        # ADD / ALTER COLUMNS
        # -----------------------------

        for name, column_type in cleaned_columns:

            if name in existing_columns:

                cursor.execute(
                    sql.SQL(
                        "ALTER TABLE {} ALTER COLUMN {} TYPE {} USING {}::{}"
                    ).format(
                        sql.Identifier(table_name),
                        sql.Identifier(name),
                        sql.SQL(column_type),
                        sql.Identifier(name),
                        sql.SQL(column_type)
                    )
                )

            else:

                cursor.execute(
                    sql.SQL(
                        "ALTER TABLE {} ADD COLUMN {} {}"
                    ).format(
                        sql.Identifier(table_name),
                        sql.Identifier(name),
                        sql.SQL(column_type)
                    )
                )

        conn.commit()

        return render_database_success(
            f"Table '{table_name}' updated successfully."
        )

    except Exception as e:

        if conn:
            conn.rollback()

        return render_database_error(
            f"Unable to edit table: {e}"
        )

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


@app.route("/delete_table", methods=["POST"])
def delete_table():

    if not session.get(
        "database_authorized",
        False
    ):
        return redirect(
            url_for("database")
        )

    table_name = request.form.get(
        "table_name",
        ""
    ).strip()

    if not table_name:

        return render_database_error(
            "Table name is required."
        )

    if not valid_identifier(table_name):

        return render_database_error(
            "Invalid table name."
        )

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        # -----------------------------
        # CHECK TABLE
        # -----------------------------

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

            return render_database_error(
                f"Table '{table_name}' does not exist."
            )

        # -----------------------------
        # DELETE TABLE
        # -----------------------------

        cursor.execute(
            sql.SQL(
                "DROP TABLE {} CASCADE"
            ).format(
                sql.Identifier(table_name)
            )
        )

        conn.commit()

        return render_database_success(
            f"Table '{table_name}' deleted successfully."
        )

    except Exception as e:

        if conn:
            conn.rollback()

        return render_database_error(
            f"Unable to delete table: {e}"
        )

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


@app.route("/database_logout")
def database_logout():

    session.pop(
        "database_authorized",
        None
    )

    return redirect(
        url_for("database")
    )


def render_database_error(message):

    try:
        tables = get_tables()
    except Exception:
        tables = []

    return render_template(
        "index.html",
        authorized=True,
        error=message,
        success=None,
        tables=tables
    )


def render_database_success(message):

    try:
        tables = get_tables()
    except Exception:
        tables = []

    return render_template(
        "index.html",
        authorized=True,
        error=None,
        success=message,
        tables=tables
    )


if __name__ == "__main__":
    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )
