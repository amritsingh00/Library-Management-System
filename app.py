from pathlib import Path
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from flask import Flask, flash, redirect, render_template, request, url_for

app = Flask(__name__)
app.secret_key = "library-mini-project"
app.config["TEMPLATES_AUTO_RELOAD"] = True

BASE_DIR = Path(__file__).resolve().parent
BOOKS_FILE = BASE_DIR / "books.csv"
MEMBERS_FILE = BASE_DIR / "members.csv"
TRANSACTIONS_FILE = BASE_DIR / "transactions.csv"
CHARTS_DIR = BASE_DIR / "static" / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)


def initialize_data_files():
    """Create CSV files with the required columns if they do not exist."""
    book_columns = ["id", "title", "author", "category", "quantity", "available"]
    member_columns = ["id", "name", "email", "phone"]
    transaction_columns = [
        "id",
        "member_id",
        "book_id",
        "member_name",
        "book_title",
        "issue_date",
        "return_date",
        "status",
    ]

    for file_path, columns in [
        (BOOKS_FILE, book_columns),
        (MEMBERS_FILE, member_columns),
        (TRANSACTIONS_FILE, transaction_columns),
    ]:
        if not file_path.exists() or file_path.stat().st_size == 0:
            pd.DataFrame(columns=columns).to_csv(file_path, index=False)


def load_dataframe(file_path):
    """Read a CSV file with pandas and return a DataFrame."""
    return pd.read_csv(file_path)


def save_dataframe(df, file_path):
    """Write a DataFrame back to CSV using pandas."""
    df.to_csv(file_path, index=False)


def next_id(df):
    """Create the next numeric id for a DataFrame."""
    if df.empty:
        return 1
    return int(df["id"].astype(int).max()) + 1


def compute_available_stats(books_df):
    """Use NumPy to calculate statistics for available books."""
    values = books_df["available"].fillna(0).astype(int).to_numpy()
    return {
        "average": float(np.mean(values)) if values.size else 0.0,
        "maximum": int(np.max(values)) if values.size else 0,
        "minimum": int(np.min(values)) if values.size else 0,
    }


def generate_charts(books_df):
    """Create report charts and save them inside static/charts."""
    category_counts = books_df.groupby("category")["available"].sum().reset_index()

    if category_counts.empty:
        category_counts = pd.DataFrame({"category": ["No Data"], "available": [1]})

    plt.figure(figsize=(8, 4))
    plt.bar(category_counts["category"], category_counts["available"], color="#0d6efd")
    plt.title("Available Books by Category")
    plt.xlabel("Category")
    plt.ylabel("Available Copies")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    bar_path = CHARTS_DIR / "books_by_category.png"
    plt.savefig(bar_path, dpi=150)
    plt.close()

    plt.figure(figsize=(7, 7))
    plt.pie(
        category_counts["available"],
        labels=category_counts["category"],
        autopct="%1.1f%%",
        startangle=90,
        colors=["#0d6efd", "#198754", "#fd7e14", "#dc3545", "#6f42c1"],
    )
    plt.title("Availability Distribution")
    plt.tight_layout()
    pie_path = CHARTS_DIR / "availability_distribution.png"
    plt.savefig(pie_path, dpi=150)
    plt.close()

    return bar_path.name, pie_path.name


initialize_data_files()


@app.route("/")
def dashboard():
    books_df = load_dataframe(BOOKS_FILE)
    members_df = load_dataframe(MEMBERS_FILE)
    transactions_df = load_dataframe(TRANSACTIONS_FILE)

    total_books = int(len(books_df))
    issued_books = int(transactions_df[transactions_df["status"] == "Issued"].shape[0])
    available_books = int(books_df["available"].fillna(0).astype(int).sum())
    total_members = int(len(members_df))
    stats = compute_available_stats(books_df)

    return render_template(
        "index.html",
        total_books=total_books,
        issued_books=issued_books,
        available_books=available_books,
        total_members=total_members,
        available_stats=stats,
    )


@app.route("/books", methods=["GET", "POST"])
def books():
    books_df = load_dataframe(BOOKS_FILE)
    search_query = request.args.get("search", "")

    if request.method == "POST":
        action = request.form.get("action", "add")
        if action == "add":
            new_book = {
                "id": next_id(books_df),
                "title": request.form.get("title", "").strip(),
                "author": request.form.get("author", "").strip(),
                "category": request.form.get("category", "").strip(),
                "quantity": int(request.form.get("quantity", 0)),
                "available": int(request.form.get("quantity", 0)),
            }
            books_df = pd.concat([books_df, pd.DataFrame([new_book])], ignore_index=True)
            save_dataframe(books_df, BOOKS_FILE)
            flash("Book added successfully.")
        elif action == "edit":
            book_id = int(request.form.get("book_id", 0))
            index = books_df.index[books_df["id"] == book_id]
            if not index.empty:
                books_df.loc[index[0], "title"] = request.form.get("title", "").strip()
                books_df.loc[index[0], "author"] = request.form.get("author", "").strip()
                books_df.loc[index[0], "category"] = request.form.get("category", "").strip()
                quantity = int(request.form.get("quantity", 0))
                current_available = int(books_df.loc[index[0], "available"])
                delta = quantity - int(books_df.loc[index[0], "quantity"])
                books_df.loc[index[0], "quantity"] = quantity
                books_df.loc[index[0], "available"] = max(0, current_available + delta)
                save_dataframe(books_df, BOOKS_FILE)
                flash("Book updated successfully.")

    if search_query:
        search_mask = books_df["title"].str.contains(search_query, case=False, na=False) | books_df["author"].str.contains(search_query, case=False, na=False)
        books_df = books_df[search_mask]

    return render_template("books.html", books=books_df.to_dict("records"), search_query=search_query)


@app.route("/books/delete/<int:book_id>", methods=["POST"])
def delete_book(book_id):
    books_df = load_dataframe(BOOKS_FILE)
    books_df = books_df[books_df["id"] != book_id]
    save_dataframe(books_df, BOOKS_FILE)
    flash("Book deleted successfully.")
    return redirect(url_for("books"))


@app.route("/members", methods=["GET", "POST"])
def members():
    members_df = load_dataframe(MEMBERS_FILE)

    if request.method == "POST":
        new_member = {
            "id": next_id(members_df),
            "name": request.form.get("name", "").strip(),
            "email": request.form.get("email", "").strip(),
            "phone": request.form.get("phone", "").strip(),
        }
        members_df = pd.concat([members_df, pd.DataFrame([new_member])], ignore_index=True)
        save_dataframe(members_df, MEMBERS_FILE)
        flash("Member added successfully.")

    return render_template("members.html", members=members_df.to_dict("records"))


@app.route("/members/delete/<int:member_id>", methods=["POST"])
def delete_member(member_id):
    members_df = load_dataframe(MEMBERS_FILE)
    members_df = members_df[members_df["id"] != member_id]
    save_dataframe(members_df, MEMBERS_FILE)
    flash("Member deleted successfully.")
    return redirect(url_for("members"))


@app.route("/issue", methods=["GET", "POST"])
def issue_book():
    books_df = load_dataframe(BOOKS_FILE)
    members_df = load_dataframe(MEMBERS_FILE)

    if request.method == "POST":
        book_id = int(request.form.get("book_id", 0))
        member_id = int(request.form.get("member_id", 0))

        book_row = books_df[books_df["id"] == book_id]
        member_row = members_df[members_df["id"] == member_id]

        if book_row.empty or member_row.empty:
            flash("Please choose a valid member and book.")
        else:
            book_index = book_row.index[0]
            available = int(books_df.loc[book_index, "available"])
            if available <= 0:
                flash("This book is currently unavailable.")
            else:
                transactions_df = load_dataframe(TRANSACTIONS_FILE)
                new_transaction = {
                    "id": next_id(transactions_df),
                    "member_id": member_id,
                    "book_id": book_id,
                    "member_name": member_row.iloc[0]["name"],
                    "book_title": book_row.iloc[0]["title"],
                    "issue_date": pd.Timestamp.today().strftime("%Y-%m-%d"),
                    "return_date": "",
                    "status": "Issued",
                }
                transactions_df = pd.concat([transactions_df, pd.DataFrame([new_transaction])], ignore_index=True)
                books_df.loc[book_index, "available"] = available - 1
                save_dataframe(books_df, BOOKS_FILE)
                save_dataframe(transactions_df, TRANSACTIONS_FILE)
                flash("Book issued successfully.")
                return redirect(url_for("issue_book"))

    return render_template("issue_book.html", books=books_df.to_dict("records"), members=members_df.to_dict("records"))


@app.route("/return", methods=["GET", "POST"])
def return_book():
    transactions_df = load_dataframe(TRANSACTIONS_FILE)
    issued_transactions = transactions_df[transactions_df["status"] == "Issued"]

    if request.method == "POST":
        transaction_id = int(request.form.get("transaction_id", 0))
        transaction_row = transactions_df[transactions_df["id"] == transaction_id]
        if transaction_row.empty:
            flash("Please choose a valid transaction.")
        else:
            books_df = load_dataframe(BOOKS_FILE)
            book_row = books_df[books_df["id"] == int(transaction_row.iloc[0]["book_id"])]
            if not book_row.empty:
                book_index = book_row.index[0]
                books_df.loc[book_index, "available"] = int(books_df.loc[book_index, "available"]) + 1
                transactions_df.loc[transaction_row.index[0], "status"] = "Returned"
                transactions_df.loc[transaction_row.index[0], "return_date"] = pd.Timestamp.today().strftime("%Y-%m-%d")
                save_dataframe(books_df, BOOKS_FILE)
                save_dataframe(transactions_df, TRANSACTIONS_FILE)
                flash("Book returned successfully.")
                return redirect(url_for("return_book"))

    return render_template("return_book.html", transactions=issued_transactions.to_dict("records"))


@app.route("/reports")
def reports():
    books_df = load_dataframe(BOOKS_FILE)
    chart_bar, chart_pie = generate_charts(books_df)
    return render_template("reports.html", chart_bar=chart_bar, chart_pie=chart_pie)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

