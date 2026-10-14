from flask import Flask, render_template_string, request, redirect, session
import sqlite3
import os
from datetime import date

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "melka-change-this-key")
DB = os.environ.get("DB_PATH", "melka_stock.db")
PASSWORD = os.environ.get("ADMIN_PASSWORD", "Melka@123")

def connect():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

with connect() as con:
    con.execute("""
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            batch TEXT,
            expiry TEXT,
            quantity INTEGER NOT NULL DEFAULT 0,
            cost REAL NOT NULL DEFAULT 0,
            price REAL NOT NULL DEFAULT 0,
            minimum INTEGER NOT NULL DEFAULT 10
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_id INTEGER,
            name TEXT,
            quantity INTEGER,
            cost REAL,
            price REAL,
            sold_at TEXT
        )
    """)

PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MELKA DRUG STORE</title>
<style>
body{font-family:Arial;background:#f1f5f9;margin:0;color:#123}
header{background:#075985;color:white;padding:20px}
main{max-width:1000px;margin:auto;padding:15px}
.card{background:white;padding:16px;margin:12px 0;border-radius:12px;box-shadow:0 2px 8px #ddd}
input,button{padding:11px;margin:4px;border:1px solid #bbb;border-radius:6px}
button{background:#075985;color:white;cursor:pointer}
table{width:100%;border-collapse:collapse;background:white}
td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}
a{color:#075985}
.alert{color:#b91c1c;font-weight:bold}
</style>
</head>
<body>
<header><h1>💊 MELKA DRUG STORE</h1><p>Medicine Stock Control System</p></header>
<main>
{% if not logged %}
<div class="card"><h2>Admin Login</h2>
<form method="post"><input type="password" name="password" placeholder="Admin password" required>
<button>Login</button></form><p>Set a secure ADMIN_PASSWORD before public deployment.</p></div>
{% else %}
<p><a href="/logout">Logout</a></p>
<div class="card"><h2>Dashboard</h2>
<p>Total medicine types: <b>{{count}}</b></p>
<p>Total units in stock: <b>{{units}}</b></p>
<p>Estimated stock value: <b>{{'%.2f'|format(value)}} ETB</b></p>
<p>Sales revenue: <b>{{'%.2f'|format(revenue)}} ETB</b></p>
<p>Gross profit from recorded sales: <b>{{'%.2f'|format(profit)}} ETB</b></p>
</div>
<div class="card"><h2>Add Medicine / Stock</h2>
<form method="post" action="/add">
<input name="name" placeholder="Medicine name" required>
<input name="batch" placeholder="Batch number">
<input name="expiry" type="date" title="Expiry date">
<input name="quantity" type="number" min="0" placeholder="Quantity" required>
<input name="cost" type="number" step="0.01" min="0" placeholder="Unit cost" required>
<input name="price" type="number" step="0.01" min="0" placeholder="Selling price" required>
<input name="minimum" type="number" min="0" value="10" placeholder="Low-stock limit">
<button>Add stock</button></form></div>
<div class="card"><h2>Record Sale</h2>
<form method="post" action="/sell">
<select name="id" required>{% for m in meds %}<option value="{{m.id}}">{{m.name}} (stock {{m.quantity}})</option>{% endfor %}</select>
<input name="quantity" type="number" min="1" placeholder="Quantity sold" required>
<button>Record sale</button></form></div>
<div class="card"><h2>Search Inventory</h2>
<form method="get"><input name="q" value="{{q}}" placeholder="Medicine name or batch"><button>Search</button></form>
<div style="overflow-x:auto"><table><tr><th>Medicine</th><th>Batch</th><th>Expiry</th><th>Stock</th><th>Cost</th><th>Price</th><th>Status</th></tr>
{% for m in meds %}<tr><td>{{m.name}}</td><td>{{m.batch or ''}}</td><td>{{m.expiry or ''}}</td><td>{{m.quantity}}</td><td>{{m.cost}}</td><td>{{m.price}}</td><td>{% if m.quantity <= m.minimum %}<span class="alert">LOW STOCK</span>{% endif %}{% if m.expiry and m.expiry <= today %}<span class="alert"> EXPIRED/DUE</span>{% endif %}</td></tr>{% endfor %}
</table></div></div>
<div class="card"><h2>Recent Sales</h2><div style="overflow-x:auto"><table>
<tr><th>Date</th><th>Medicine</th><th>Quantity</th><th>Revenue</th><th>Gross profit</th></tr>
{% for s in sales %}<tr><td>{{s.sold_at}}</td><td>{{s.name}}</td><td>{{s.quantity}}</td><td>{{'%.2f'|format(s.price*s.quantity)}}</td><td>{{'%.2f'|format((s.price-s.cost)*s.quantity)}}</td></tr>{% endfor %}
</table></div></div>
{% endif %}
</main></body></html>
"""

@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST" and request.form.get("password") == PASSWORD:
        session["logged"] = True
        return redirect("/")
    if not session.get("logged"):
        return render_template_string(PAGE, logged=False)
    q = request.args.get("q", "").strip()
    with connect() as con:
        meds = con.execute(
            "SELECT * FROM medicines WHERE name LIKE ? OR batch LIKE ? ORDER BY name",
            (f"%{q}%", f"%{q}%")
        ).fetchall()
        count = con.execute("SELECT COUNT(*) FROM medicines").fetchone()[0]
        units = con.execute("SELECT COALESCE(SUM(quantity),0) FROM medicines").fetchone()[0]
        value = con.execute("SELECT COALESCE(SUM(quantity*cost),0) FROM medicines").fetchone()[0]
        revenue = con.execute("SELECT COALESCE(SUM(quantity*price),0) FROM sales").fetchone()[0]
        profit = con.execute("SELECT COALESCE(SUM(quantity*(price-cost)),0) FROM sales").fetchone()[0]
        sales = con.execute("SELECT * FROM sales ORDER BY id DESC LIMIT 30").fetchall()
    return render_template_string(PAGE, logged=True, meds=meds, count=count,
        units=units, value=value, revenue=revenue, profit=profit,
        sales=sales, q=q, today=date.today().isoformat())

@app.route("/add", methods=["POST"])
def add():
    if not session.get("logged"):
        return redirect("/")
    name = request.form["name"].strip()
    batch = request.form.get("batch", "").strip()
    expiry = request.form.get("expiry", "")
    quantity = max(0, int(request.form["quantity"]))
    cost = max(0, float(request.form["cost"]))
    price = max(0, float(request.form["price"]))
    minimum = max(0, int(request.form.get("minimum", 10)))
    with connect() as con:
        con.execute("""INSERT INTO medicines
            (name,batch,expiry,quantity,cost,price,minimum)
            VALUES (?,?,?,?,?,?,?)""",
            (name,batch,expiry,quantity,cost,price,minimum))
    return redirect("/")

@app.route("/sell", methods=["POST"])
def sell():
    if not session.get("logged"):
        return redirect("/")
    mid = int(request.form["id"])
    qty = int(request.form["quantity"])
    with connect() as con:
        med = con.execute("SELECT * FROM medicines WHERE id=?", (mid,)).fetchone()
        if med and qty > 0 and med["quantity"] >= qty:
            con.execute("UPDATE medicines SET quantity=quantity-? WHERE id=?", (qty,mid))
            con.execute("""INSERT INTO sales
                (medicine_id,name,quantity,cost,price,sold_at)
                VALUES (?,?,?,?,?,?)""",
                (mid,med["name"],qty,med["cost"],med["price"],date.today().isoformat()))
    return redirect("/")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
