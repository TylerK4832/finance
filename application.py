import os
import csv

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    user_stocks=db.execute("SELECT * FROM stocks WHERE user_id= :user_id", user_id=session["user_id"])
    stock_names=[]
    stock_prices=[]
    stock_prices_usd=[]
    stock_prices_total=[]
    grand_total=0
    user_cash=db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])[0]['cash']
    cash_total=usd(user_cash)
    length= len(user_stocks)
    for i in range(length):
        stock_names.append(lookup(user_stocks[i]['symbol'])['name'])
        stock_prices.append(usd(lookup(user_stocks[i]['symbol'])['price']))
        stock_prices_usd.append(usd(lookup(user_stocks[i]['symbol'])['price']*user_stocks[i]['shares']))
        stock_prices_total.append(lookup(user_stocks[i]['symbol'])['price']*user_stocks[i]['shares'])
    grand_total=usd(sum(stock_prices_total)+user_cash)
    return render_template("index.html", user_stocks=user_stocks, stock_names=stock_names, length=length, stock_prices=stock_prices, stock_prices_usd=stock_prices_usd, grand_total=grand_total, cash_total=cash_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    
    if request.method == "GET":
        return render_template("buy.html")
        
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        if symbol == "" or lookup(symbol) == None:
            return apology("Please enter a valid symbol")
        user_cash=db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])[0]['cash']
        total_cost=float(shares)*lookup(symbol)["price"]
        if user_cash < total_cost:
            return apology("You can't afford to purchase those shares!")
        db.execute("UPDATE users SET cash = :nettotal WHERE id = :user_id", user_id=session["user_id"], nettotal=user_cash-total_cost)
        db.execute("INSERT INTO stocks (user_id, symbol, shares) VALUES(:user_id, :symbol, :shares)", user_id=session["user_id"], symbol=symbol, shares=shares)
        return redirect("/")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    
    if request.method == "GET":
        return render_template("quote.html")
    
    if request.method == "POST":
        stockinfo = lookup(request.form.get("symbol"))
        stockinfo["price"] = usd(stockinfo["price"])
        return render_template("quoted.html", stockinfo=stockinfo)

@app.route("/register", methods=["GET", "POST"])
def register():
    
    if request.method == "GET":
        return render_template("register.html")
    
    if request.method == "POST":
        if not request.form.get("username") or not request.form.get("password") or not request.form.get("confirmation"):
            return apology("Please complete all sections.")
        if not request.form.get("password") == request.form.get("confirmation"):
            return apology("Are you silly? Those passwords don't match!")
        if db.execute("SELECT username FROM users WHERE username = :name LIMIT 1", name=request.form.get("username")):
            return apology("That username is taken! Please choose another.")
        else:
            db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)", username=request.form.get("username"), hash=(generate_password_hash(request.form.get("password"))))
            return redirect("/")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    user_stocks=db.execute("SELECT * FROM stocks WHERE user_id= :user_id", user_id=session["user_id"])
    length= len(user_stocks)
    if request.method == "GET":
        return render_template("sell.html", user_stocks=user_stocks, length=length)
        
    if request.method == "POST":
        user_shares=db.execute("SELECT shares FROM stocks WHERE user_id = :user_id AND symbol = :symbol", user_id=session["user_id"], symbol=request.form.get("symbol"))[0]["shares"]
        if int(request.form.get("shares"),10) > user_shares:
            return apology("You don't own that many shares!")
        total_cost = int(request.form.get("shares"),10)*lookup(request.form.get("symbol"))
        db.execute("UPDATE users SET cash = :nettotal WHERE id = :user_id", user_id=session["user_id"], nettotal=user_cash-total_cost)
        if user_shares == int(request.form.get("shares"),10):
            db.execute("DELETE FROM stocks WHERE user_id = :user_id AND symbol = :symbol", user_id=session["user_id"], symbol=request.form.get("symbol"))
                       
        if user_shares > int(request.form.get("shares"),10):
            db.execute("UPDATE stocks SET shares = :netshares WHERE user_id = :user_id AND symbol = :symbol", netshares=user_shares-int(request.form.get("shares"),10), user_id=session["user_id"], symbol=request.form.get("symbol"))
                       
        return redirect("/")

@app.route("/addcash", methods=["GET", "POST"])
def addcash():

    if request.method == "GET":
        return render_template("addcash.html")
    
    
    if request.method == "POST":
        return apology("TODO")
    
def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
