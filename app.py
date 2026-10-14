import os
import psycopg
from flask import Flask, request, redirect, render_template_string

app = Flask(__name__)
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")
    return psycopg.connect(DATABASE_URL)

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS medicines (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                batch TEXT DEFAULT '',
                expiry DATE,
                quantity INTEGER NOT NULL DEFAULT 0,
                min_stock INTEGER NOT NULL DEFAULT 10,
                cost_price NUMERIC(12,2) NOT NULL DEFAULT 0,
                selling_price NUMERIC(12,2) NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS movements (
                id SERIAL PRIMARY KEY,
                medicine_id INTEGER REFERENCES medicines(id),
                movement_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MELKA DRUG STORE</title>
<style>
body{font-family:Arial;margin:0;background:#f1f6fb;color:#17365d}
header{background:#0756a5;color:white;padding:20px;text-align:center}
main{padding:15px;max-width:1000px;margin:auto}
.card{background:white;padding:15px;margin:12px 0;border-radius:10px}
input,button{padding:10px;margin:5px 0;max-width:100%;box-sizing:border-box}
input{width:100%;border:1px solid #bbb;border-radius:5px}
button{background:#0756a5;color:white;border:0;border-radius:5px}
table{width:100%;border-collapse:collapse;background:white}
th,td{padding:8px;border:1px solid #ddd;text-align:left}
.low{color:#c00;font-weight:bold}
.small{font-size:13px}
</style>
</head>
<body>
<header>
<h1>MELKA DRUG STORE</h1>
<p>KUSAA QORICHA MALKAA</p>
</header>
<main>
{% if error %}
<div class="card" style="color:#b00020">{{ error }}</div>
{% endif %}
<div class="card">
<h2>Stock Dashboard</h2>
<p>Medicine types: <b>{{ count }}</b></p>
<p>Total units in stock: <b>{{ units }}</b></p>
<p>Estimated stock cost: <b>{{ "%.2f"|format(value) }} ETB</b></p>
</div>
<div class="card">
<h2>Add New Medicine</h2>
<form method="post" action="/add">
<label>Medicine name</label>
<input name="name" required>
<label>Batch number</label>
<input name="batch">
<label>Expiry date</label>
<input type="date" name="expiry">
<label>Opening quantity</label>
<input type="number" name="quantity" min="0" value="0" required>
<label>Minimum stock alert</label>
<input type="number" name="min_stock" min="0" value="10" required>
<label>Purchase cost per unit (ETB)</label>
<input type="number" name="cost_price" min="0" step="0.01" value="0" required>
<label>Selling price per unit (ETB)</label>
<input type="number" name="selling_price" min="0" step="0.01" value="0" required>
<button type="submit">Save Medicine</button>
</form>
</div>
<div class="card">
<h2>Stock In / Stock Out</h2>
<form method="post" action="/move">
<label>Medicine</label>
<select name="medicine_id" required>
{% for m in medicines %}
<option value="{{ m['id'] }}">{{ m['name'] }} — {{ m['batch'] }}</option>
{% endfor %}
</select>
<label>Quantity</label>
<input type="number" name="quantity" min="1" required>
<label>Movement</label>
<select name="movement_type">
<option value="IN">Stock In</option>
<option value="OUT">Stock Out</option>
</select>
<button type="submit">Record Movement</button>
</form>
</div>
<div class="card">
<h2>Medicine Inventory</h2>
<div style="overflow-x:auto">
<table>
<tr><th>Name</th><th>Batch</th><th>Expiry</th><th>Qty</th>
<th>Cost</th><th>Sell price</th><th>Status</th></tr>
{% for m in medicines %}
<tr>
<td>{{ m['name'] }}</td><td>{{ m['batch'] }}</td>
<td>{{ m['expiry'] or '' }}</td><td>{{ m['quantity'] }}</td>
<td>{{ m['cost_price'] }}</td><td>{{ m['selling_price'] }}</td>
<td>{% if m['quantity'] <= m['min_stock'] %}
<span class="low">LOW STOCK</span>{% else %}OK{% endif %}</td>
</tr>
{% endfor %}
</table>
</div>
<p class="small">Prototype: verify all records and workflows before real pharmacy use.</p>
</div>
</main>
</body>
</html>
"""

def dashboard(error=None):
    init_db()
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id,name,batch,expiry,quantity,min_stock,
                   cost_price,selling_price
            FROM medicines ORDER BY name
        """).fetchall()
        medicines = [dict(r) for r in rows]
    count = len(medicines)
    units = sum(m["quantity"] for m in medicines)
    value = sum(float(m["quantity"] * m["cost_price"]) for m in medicines)
    return render_template_string(
        PAGE, medicines=medicines, count=count,
        units=units, value=value, error=error
    )

@app.route("/")
def home():
    try:
        return dashboard()
    except Exception:
        app.logger.exception("Dashboard failed")
        return "Database setup failed. Check DATABASE_URL in Render and its logs.", 500

@app.route("/add", methods=["POST"])
def add():
    try:
        name = request.form["name"].strip()
        batch = request.form.get("batch", "").strip()
        expiry = request.form.get("expiry") or None
        quantity = int(request.form["quantity"])
        min_stock = int(request.form["min_stock"])
        cost = float(request.form["cost_price"])
        selling = float(request.form["selling_price"])

        if not name or min(quantity, min_stock) < 0 or min(cost, selling) < 0:
            return dashboard("Please check the medicine details.")

        init_db()
        with get_db() as conn:
            row = conn.execute("""
                INSERT INTO medicines
                (name,batch,expiry,quantity,min_stock,cost_price,selling_price)
                VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id
            """, (name,batch,expiry,quantity,min_stock,cost,selling)).fetchone()
            if quantity > 0:
                conn.execute("""
                    INSERT INTO movements
                    (medicine_id,movement_type,quantity)
                    VALUES (%s,'IN',%s)
                """, (row[0], quantity))
        return redirect("/")
    except Exception:
        app.logger.exception("Adding medicine failed")
        return "Could not save medicine. Check the Render logs.", 500

@app.route("/move", methods=["POST"])
def move():
    try:
        medicine_id = int(request.form["medicine_id"])
        quantity = int(request.form["quantity"])
        movement_type = request.form["movement_type"]

        if quantity < 1 or movement_type not in ("IN", "OUT"):
            return dashboard("Invalid stock movement.")

        init_db()
        with get_db() as conn:
            row = conn.execute("""
                SELECT quantity FROM medicines WHERE id=%s FOR UPDATE
            """, (medicine_id,)).fetchone()

            if row is None:
                return dashboard("Medicine not found.")

            current = row[0]
            if movement_type == "OUT" and quantity > current:
                return dashboard("Not enough stock for this movement.")

            change = quantity if movement_type == "IN" else -quantity
            conn.execute("""
                UPDATE medicines SET quantity=quantity+%s WHERE id=%s
            """, (change, medicine_id))
            conn.execute("""
                INSERT INTO movements
                (medicine_id,movement_type,quantity)
                VALUES (%s,%s,%s)
            """, (medicine_id,movement_type,quantity))

        return redirect("/")
    except Exception:
        app.logger.exception("Stock movement failed")
        return "Could not record stock movement. Check the Render logs.", 500

if __name__ == "__main__":
    app.run()
