from flask import Flask, render_template, request, redirect, url_for, jsonify, Response, session, flash
import sqlite3, os, csv, io
from datetime import date, datetime
from zoneinfo import ZoneInfo

APP_DIR=os.path.dirname(os.path.abspath(__file__))
DB=os.path.join(APP_DIR,"familykitty.db")
app=Flask(__name__)
app.secret_key=os.environ.get("SECRET_KEY","dev-only-change-me")
IST=ZoneInfo("Asia/Kolkata")

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init():
    c=db()
    c.executescript("""
    PRAGMA foreign_keys=ON;
    CREATE TABLE IF NOT EXISTS members(id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT, monthly INTEGER NOT NULL DEFAULT 0, role TEXT DEFAULT 'Member', active INTEGER DEFAULT 1, tracked_only INTEGER DEFAULT 0, joined TEXT);
    CREATE TABLE IF NOT EXISTS dues(id INTEGER PRIMARY KEY, member_id INTEGER, month TEXT, due INTEGER, paid INTEGER DEFAULT 0, status TEXT DEFAULT 'Pending', UNIQUE(member_id,month), FOREIGN KEY(member_id) REFERENCES members(id));
    CREATE TABLE IF NOT EXISTS transactions(id INTEGER PRIMARY KEY, member_id INTEGER, type TEXT, amount INTEGER, date TEXT, mode TEXT, note TEXT, status TEXT DEFAULT 'active', created_by TEXT DEFAULT 'Admin', void_reason TEXT, FOREIGN KEY(member_id) REFERENCES members(id));
    CREATE TABLE IF NOT EXISTS loans(id INTEGER PRIMARY KEY, member_id INTEGER, principal INTEGER, outstanding INTEGER, repaid INTEGER DEFAULT 0, interest INTEGER DEFAULT 0, purpose TEXT, status TEXT DEFAULT 'Active', issued TEXT, FOREIGN KEY(member_id) REFERENCES members(id));
    CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, action TEXT, detail TEXT, actor TEXT, created TEXT);
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
    """)
    if c.execute("SELECT COUNT(*) FROM members").fetchone()[0]==0:
        c.executemany("INSERT INTO members(name,phone,monthly,role,joined) VALUES(?,?,?,?,?)",[
            ("Vaibhav","",5000,"Member","2026-05-01"),("Aniket","",3000,"Admin","2026-05-01"),("Bhushan","",2000,"Member","2026-05-01")])
        ids=[r["id"] for r in c.execute("SELECT id FROM members ORDER BY id")]
        for m in range(5,11):
            month=f"2026-{m:02d}"
            for i,mid in enumerate(ids):
                due=[5000,3000,2000][i]
                paid=due if not (m==7 and i==0) else 2500
                status="Paid" if paid==due else "Partial"
                c.execute("INSERT OR IGNORE INTO dues(member_id,month,due,paid,status) VALUES(?,?,?,?,?)",(mid,month,due,paid,status))
                if paid:
                    c.execute("INSERT INTO transactions(member_id,type,amount,date,mode,note) VALUES(?,?,?,?,?,?)",(mid,"deposit",paid,f"{month}-28","UPI","Seed contribution"))
        c.execute("INSERT INTO loans(member_id,principal,outstanding,repaid,interest,purpose,status,issued) VALUES(?,?,?,?,?,?,?,?)",(ids[0],10000,6000,4000,0,"Home repair","Active","2026-08-12"))
        c.execute("INSERT INTO transactions(member_id,type,amount,date,mode,note) VALUES(?,?,?,?,?,?)",(ids[0],"loan_disbursal",10000,"2026-08-12","Other","Home repair loan"))
        c.execute("INSERT INTO transactions(member_id,type,amount,date,mode,note) VALUES(?,?,?,?,?,?)",(ids[0],"loan_repayment",4000,"2026-09-12","UPI","Partial repayment"))
        c.execute("INSERT INTO settings(key,value) VALUES('group_name','Bhushan Family')")
        c.execute("INSERT INTO settings(key,value) VALUES('deadline_day','30')")
        c.execute("INSERT INTO settings(key,value) VALUES('savings_interest','0')")
        c.execute("INSERT INTO settings(key,value) VALUES('loan_interest','0')")
        c.execute("INSERT INTO settings(key,value) VALUES('visibility','Everyone')")
        c.execute("INSERT INTO audit(action,detail,actor,created) VALUES('Demo created','Seeded Bhushan Family','System',?)",(datetime.now(IST).isoformat(),))
    c.commit(); c.close()

def log(c,action,detail):
    c.execute("INSERT INTO audit(action,detail,actor,created) VALUES(?,?,?,?)",(action,detail,session.get("actor","Aniket"),datetime.now(IST).isoformat()))

def balances(c):
    members=c.execute("SELECT * FROM members WHERE active=1 ORDER BY name").fetchall()
    out=[]
    for m in members:
        tx=c.execute("SELECT type,COALESCE(SUM(amount),0) amount FROM transactions WHERE member_id=? AND status='active' GROUP BY type",(m["id"],)).fetchall()
        sums={r["type"]:r["amount"] for r in tx}
        savings=sums.get("deposit",0)+sums.get("interest_credit",0)-sums.get("withdrawal",0)-sums.get("penalty",0)
        loan=c.execute("SELECT COALESCE(SUM(outstanding+interest),0) n FROM loans WHERE member_id=? AND status IN ('Active','Partially Repaid')",(m["id"],)).fetchone()["n"]
        out.append(dict(member=m,savings=savings,loan=loan,net=savings-loan))
    return out

@app.route("/")
def home():
    c=db(); rows=balances(c)
    pool=sum(x["savings"] for x in rows); loans=sum(x["loan"] for x in rows); available=pool-sum(c.execute("SELECT COALESCE(SUM(outstanding),0) FROM loans").fetchone())
    month=date.today().strftime("%Y-%m")
    due=c.execute("SELECT d.*,m.name FROM dues d JOIN members m ON m.id=d.member_id WHERE d.month=? AND m.active=1",(month,)).fetchall()
    paid=sum(1 for d in due if d["status"]=="Paid"); expected=sum(d["due"] for d in due); collected=sum(d["paid"] for d in due)
    activity=c.execute("SELECT t.*,m.name FROM transactions t LEFT JOIN members m ON m.id=t.member_id ORDER BY t.id DESC LIMIT 7").fetchall()
    group=c.execute("SELECT value FROM settings WHERE key='group_name'").fetchone()
    c.close()
    return render_template("index.html",rows=rows,pool=pool,loans=loans,available=available,due=due,paid=paid,expected=expected,collected=collected,activity=activity,group=group["value"] if group else "FamilyKitty",month=month)

@app.route("/members")
def members():
    c=db(); rows=balances(c); c.close(); return render_template("members.html",rows=rows)

@app.route("/deposit",methods=["POST"])
def deposit():
    c=db(); mid=int(request.form["member_id"]); amount=int(request.form["amount"]); d=request.form.get("date") or date.today().isoformat()
    mode=request.form.get("mode","UPI"); note=request.form.get("note","")
    c.execute("INSERT INTO transactions(member_id,type,amount,date,mode,note) VALUES(?,?,?,?,?,?)",(mid,"deposit",amount,d,mode,note))
    month=d[:7]
    due=c.execute("SELECT * FROM dues WHERE member_id=? AND month=?",(mid,month)).fetchone()
    if due:
        paid=due["paid"]+amount; status="Paid" if paid>=due["due"] else "Partial"
        c.execute("UPDATE dues SET paid=?,status=? WHERE id=?",(paid,status,due["id"]))
    log(c,"Deposit recorded",f"Member #{mid}: ₹{amount:,} via {mode}")
    c.commit(); c.close(); flash("Deposit recorded and ledger updated.","success"); return redirect(url_for("home"))

@app.route("/loans",methods=["GET","POST"])
def loans():
    c=db()
    if request.method=="POST":
        mid=int(request.form["member_id"]); amount=int(request.form["amount"]); pool=sum(x["savings"] for x in balances(c))
        outstanding=c.execute("SELECT COALESCE(SUM(outstanding),0) n FROM loans WHERE status IN ('Active','Partially Repaid')").fetchone()["n"]
        if amount>pool-outstanding:
            flash("Cannot approve: amount exceeds available pool.","error")
        else:
            c.execute("INSERT INTO loans(member_id,principal,outstanding,purpose,issued) VALUES(?,?,?,?,?)",(mid,amount,amount,request.form.get("purpose",""),date.today().isoformat()))
            c.execute("INSERT INTO transactions(member_id,type,amount,date,mode,note) VALUES(?,?,?,?,?,?)",(mid,"loan_disbursal",amount,date.today().isoformat(),"Other",request.form.get("purpose","Loan disbursed")))
            log(c,"Loan approved",f"Member #{mid}: ₹{amount:,}")
            c.commit(); flash("Loan approved and recorded.","success")
    loanrows=c.execute("SELECT l.*,m.name FROM loans l JOIN members m ON m.id=l.member_id ORDER BY l.id DESC").fetchall()
    mem=c.execute("SELECT * FROM members WHERE active=1").fetchall(); c.close()
    return render_template("loans.html",loans=loanrows,members=mem)

@app.route("/repay/<int:loan_id>",methods=["POST"])
def repay(loan_id):
    c=db(); l=c.execute("SELECT * FROM loans WHERE id=?",(loan_id,)).fetchone()
    amount=int(request.form["amount"]); applied=min(amount,l["interest"]); principal=min(amount-applied,l["outstanding"])
    c.execute("UPDATE loans SET interest=interest-?,outstanding=outstanding-?,repaid=repaid+? WHERE id=?",(applied,principal,principal,loan_id))
    c.execute("INSERT INTO transactions(member_id,type,amount,date,mode,note) VALUES(?,?,?,?,?,?)",(l["member_id"],"loan_repayment",amount,date.today().isoformat(),request.form.get("mode","UPI"),f"Interest ₹{applied:,}; principal ₹{principal:,}"))
    if l["outstanding"]-principal==0 and l["interest"]-applied==0: c.execute("UPDATE loans SET status='Closed' WHERE id=?",(loan_id,))
    log(c,"Loan repayment",f"Loan #{loan_id}: ₹{amount:,} (interest ₹{applied:,}, principal ₹{principal:,})")
    c.commit(); c.close(); flash("Repayment recorded.","success"); return redirect(url_for("loans"))

@app.route("/member/add",methods=["POST"])
def add_member():
    c=db(); c.execute("INSERT INTO members(name,phone,monthly,role,tracked_only,joined) VALUES(?,?,?,?,?,?)",(request.form["name"],request.form.get("phone",""),int(request.form["monthly"]),"Member",1 if request.form.get("tracked") else 0,date.today().isoformat()))
    log(c,"Member added",request.form["name"]); c.commit(); c.close(); flash("Member added.","success"); return redirect(url_for("members"))

@app.route("/export.csv")
def export():
    c=db(); rows=c.execute("SELECT t.date,m.name,t.type,t.amount,t.mode,t.note,t.status FROM transactions t LEFT JOIN members m ON m.id=t.member_id ORDER BY t.date,t.id").fetchall(); c.close()
    s=io.StringIO(); w=csv.writer(s); w.writerow(["Date","Member","Type","Amount (INR)","Mode","Note","Status"])
    for r in rows: w.writerow(list(r))
    return Response("\ufeff"+s.getvalue(),mimetype="text/csv",headers={"Content-Disposition":"attachment; filename=familykitty-ledger.csv"})

@app.route("/settings",methods=["GET","POST"])
def settings():
    c=db()
    if request.method=="POST":
        for k in ["group_name","deadline_day","savings_interest","loan_interest","visibility"]:
            c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(k,request.form.get(k,"")))
        log(c,"Settings updated","Group settings changed"); c.commit(); flash("Settings saved.","success")
    data={r["key"]:r["value"] for r in c.execute("SELECT * FROM settings")}; audit=c.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 30").fetchall(); c.close()
    return render_template("settings.html",data=data,audit=audit)

@app.route("/manifest.json")
def manifest():
    return jsonify({"name":"FamilyKitty","short_name":"FamilyKitty","start_url":"/","display":"standalone","background_color":"#f6f7f4","theme_color":"#176b53","icons":[]})

@app.route("/sw.js")
def sw():
    return Response("const CACHE='familykitty-v1'; self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(['/','/static/app.css'])))); self.addEventListener('fetch',e=>{if(e.request.method==='GET')e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request)));});",mimetype="application/javascript")

@app.route("/health")
def health(): return jsonify({"ok":True,"app":"FamilyKitty"})

if __name__=="__main__":
    init()
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=True)
