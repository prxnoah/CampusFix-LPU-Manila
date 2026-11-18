from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os, re
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "campusfix-demo-secret")
DB = os.path.join(os.path.dirname(__file__), "campusfix.db")

UNIVERSITY_NAME = "Lyceum of the Philippines University – Manila"
CAMPUS_ADDRESS = "Muralla cor. Real Sts., Intramuros, Manila 1002"

ROLE_LABELS = {
    "student": "Student",
    "faculty": "Faculty / Instructor",
    "maintenance": "Maintenance Personnel",
    "supervisor": "Maintenance Supervisor",
    "admin": "School Administrator",
}

STATUSES = ["Reported", "Under Review", "Assigned", "In Progress", "Resolved", "Closed"]
CATEGORIES = ["Electrical", "Plumbing", "HVAC", "Internet / Network", "Furniture",
              "Safety Hazard", "Building Damage", "Classroom Equipment", "Sanitation", "Other"]
BUILDINGS = [
    "Sotero H. Laurel Academic Resource Center (SHL-ARC)",
    "JPL Hall of Freedom",
    "Administration Building",
    "Admissions Information Center – Room 102A",
    "Office of the University Registrar – Room 104A",
    "Mini Theater",
    "Bookstore",
    "College of Technology",
    "College of Arts and Sciences",
    "College of Business Administration",
    "College of International Relations",
    "College of International Tourism and Hospitality Management",
    "College of Law",
    "Graduate School",
    "Campus Grounds / Walkways",
    "Other Campus Area"
]
SEVERITIES = ["Low", "Moderate", "High", "Critical"]

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL,
      email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
      role TEXT NOT NULL, department TEXT, user_id_code TEXT,
      contact_number TEXT, profile_photo TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS reports (
      id INTEGER PRIMARY KEY AUTOINCREMENT, report_code TEXT UNIQUE NOT NULL,
      category TEXT NOT NULL, building TEXT NOT NULL, room_area TEXT,
      severity TEXT NOT NULL, description TEXT NOT NULL, date_noticed TEXT,
      reporter_id INTEGER, assigned_to INTEGER, status TEXT DEFAULT 'Reported',
      priority TEXT DEFAULT 'Medium', duplicate_count INTEGER DEFAULT 0,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS report_updates (
      id INTEGER PRIMARY KEY AUTOINCREMENT, report_id INTEGER NOT NULL,
      user_id INTEGER, old_status TEXT, new_status TEXT, note TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS notifications (
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
      title TEXT NOT NULL, message TEXT NOT NULL, is_read INTEGER DEFAULT 0,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS announcements (
      id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
      summary TEXT, category TEXT, published_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        demos = [
            ("Alex Santos","student@campusfix.local","student","Computer Science","2026-001","09170000001"),
            ("Mia Reyes","faculty@campusfix.local","faculty","College of Engineering","EMP-1042","09170000002"),
            ("Jordan Cruz","maintenance@campusfix.local","maintenance","Facilities Management","FM-021","09170000003"),
            ("Sam Rivera","supervisor@campusfix.local","supervisor","Facilities Management","SUP-008","09170000004"),
            ("Taylor Garcia","admin@campusfix.local","admin","Office of the University Administrator","ADM-001","09170000005"),
        ]
        for name,email,role,dept,code,phone in demos:
            conn.execute("INSERT INTO users(full_name,email,password_hash,role,department,user_id_code,contact_number) VALUES(?,?,?,?,?,?,?)",
                         (name,email,generate_password_hash("password123"),role,dept,code,phone))
    if conn.execute("SELECT COUNT(*) FROM announcements").fetchone()[0] == 0:
        announcements = [
            ("LPU Manila BSIT Program Earns PICAB Accreditation", "The College of Technology celebrates the accreditation of the Bachelor of Science in Information Technology program by PICAB.", "Academic Excellence"),
            ("LPU Manila Faculty and Staff Earn Microsoft Elevate Recognition", "LPU Manila celebrates faculty and staff recognized as Microsoft Elevate for Educator Experts for AY 2026–2027.", "University News"),
            ("LPU Manila and UCSI University Explore Academic Collaboration", "The universities signed a letter of intent to explore opportunities for academic collaboration and global engagement.", "Global Engagement"),
            ("CampusFix is now live for campus maintenance reports", "Students and faculty can report facility concerns, follow status changes and receive maintenance updates through CampusFix.", "CampusFix"),
        ]
        for a in announcements:
            conn.execute("INSERT INTO announcements(title,summary,category) VALUES(?,?,?)", a)
    conn.commit()
    conn.close()

def current_user():
    uid = session.get("user_id")
    if not uid: return None
    conn=db(); u=conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone(); conn.close()
    return u

@app.context_processor
def inject_globals():
    u=current_user()
    unread=0
    if u:
        conn=db(); unread=conn.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0",(u["id"],)).fetchone()[0]; conn.close()
    return dict(current_user=u, unread_notifications=unread, role_labels=ROLE_LABELS)

def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash("Please sign in to continue.", "info")
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

def make_report_code():
    return "CF-" + datetime.now().strftime("%y%m%d%H%M%S")

def calculate_priority(severity, category, duplicate_count):
    score={"Low":1,"Moderate":2,"High":3,"Critical":5}.get(severity,2)
    if category=="Safety Hazard": score += 2
    if category in ["Electrical","Plumbing"]: score += 1
    score += min(duplicate_count,3)
    return "Urgent" if score>=7 else "High" if score>=5 else "Medium" if score>=3 else "Low"

def notify(user_id, title, message):
    if not user_id: return
    conn=db(); conn.execute("INSERT INTO notifications(user_id,title,message) VALUES(?,?,?)",(user_id,title,message)); conn.commit(); conn.close()

@app.route("/")
def home():
    conn=db()
    announcements=conn.execute("SELECT * FROM announcements ORDER BY published_at DESC LIMIT 4").fetchall()
    active=conn.execute("SELECT COUNT(*) FROM reports WHERE status NOT IN ('Resolved','Closed')").fetchone()[0]
    resolved=conn.execute("SELECT COUNT(*) FROM reports WHERE status IN ('Resolved','Closed')").fetchone()[0]
    conn.close()
    return render_template("public/home.html", announcements=announcements, active=active, resolved=resolved, university_name=UNIVERSITY_NAME, campus_address=CAMPUS_ADDRESS)

@app.route("/about")
def about(): return render_template("public/about.html")
@app.route("/admissions")
def admissions(): return render_template("public/admissions.html")
@app.route("/academics")
def academics(): return render_template("public/academics.html")
@app.route("/colleges")
def colleges(): return render_template("public/colleges.html")
@app.route("/news")
def news():
    conn=db(); items=conn.execute("SELECT * FROM announcements ORDER BY published_at DESC").fetchall(); conn.close()
    return render_template("public/news.html", announcements=items)
@app.route("/events")
def events(): return render_template("public/events.html")
@app.route("/facilities")
def facilities(): return render_template("public/facilities.html")
@app.route("/faq")
def faq(): return render_template("public/faq.html")
@app.route("/contact")
def contact(): return render_template("public/contact.html")
@app.route("/help")
def help_page(): return render_template("public/help.html")
@app.route("/resources")
def resources(): return render_template("public/resources.html")
@app.route("/faculty-directory")
def faculty_directory():
    conn=db(); faculty=conn.execute("SELECT * FROM users WHERE role='faculty' ORDER BY full_name").fetchall(); conn.close()
    return render_template("public/faculty.html", faculty=faculty)
@app.route("/campus-map")
def campus_map():
    return render_template("public/campus_map.html", university_name=UNIVERSITY_NAME, campus_address=CAMPUS_ADDRESS)

@app.route("/campus-status")
def campus_status():
    conn=db()
    rows=conn.execute("""SELECT building,
        SUM(CASE WHEN status NOT IN ('Resolved','Closed') THEN 1 ELSE 0 END) active,
        SUM(CASE WHEN status IN ('Resolved','Closed') THEN 1 ELSE 0 END) resolved
        FROM reports GROUP BY building ORDER BY active DESC""").fetchall()
    conn.close()
    return render_template("public/status.html", buildings=rows)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        email=request.form.get("email","").strip().lower()
        password=request.form.get("password","")
        conn=db(); u=conn.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone(); conn.close()
        if u and check_password_hash(u["password_hash"], password):
            session["user_id"]=u["id"]
            flash(f"Welcome back, {u['full_name'].split()[0]}!", "success")
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("The email or password is incorrect.", "error")
    return render_template("auth.html", mode="login")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        fields=[request.form.get(x,"").strip() for x in ["full_name","email","password","confirm_password","user_id_code","department","contact_number"]]
        name,email,pw,cpw,code,dept,phone=fields
        if not all(fields):
            flash("Please complete all required fields.", "error")
        elif pw != cpw:
            flash("Passwords do not match.", "error")
        elif not re.match(r"^[^@]+@[^@]+\\.[^@]+$", email):
            flash("Please use a valid university email.", "error")
        else:
            try:
                conn=db(); conn.execute("""INSERT INTO users(full_name,email,password_hash,role,department,user_id_code,contact_number)
                    VALUES(?,?,?,?,?,?,?)""",(name,email,generate_password_hash(pw),"student",dept,code,phone)); conn.commit()
                uid=conn.execute("SELECT id FROM users WHERE email=?",(email,)).fetchone()["id"]; conn.close()
                session["user_id"]=uid; flash("Account created successfully.", "success")
                return redirect(url_for("dashboard"))
            except sqlite3.IntegrityError:
                flash("That university email is already registered.", "error")
    return render_template("auth.html", mode="register")

@app.route("/logout")
def logout():
    session.clear(); flash("You have been signed out.", "info"); return redirect(url_for("home"))

@app.route("/dashboard")
@login_required
def dashboard():
    u=current_user()
    if u["role"] in ("maintenance","supervisor"): return redirect(url_for("operations"))
    if u["role"]=="admin": return redirect(url_for("admin_dashboard"))
    conn=db()
    reports=conn.execute("""SELECT r.*, u.full_name reporter, a.full_name assignee
        FROM reports r LEFT JOIN users u ON r.reporter_id=u.id LEFT JOIN users a ON r.assigned_to=a.id
        WHERE r.reporter_id=? ORDER BY r.created_at DESC""",(u["id"],)).fetchall()
    stats={
        "total":len(reports),
        "active":sum(r["status"] not in ("Resolved","Closed") for r in reports),
        "resolved":sum(r["status"] in ("Resolved","Closed") for r in reports),
        "high":sum(r["priority"] in ("High","Urgent") for r in reports)
    }
    conn.close()
    return render_template("dashboard/user.html", reports=reports, stats=stats)

@app.route("/operations")
@login_required
def operations():
    u=current_user()
    if u["role"] not in ("maintenance","supervisor","admin"):
        return redirect(url_for("dashboard"))
    conn=db()
    where="" if u["role"] in ("supervisor","admin") else "WHERE r.assigned_to=?"
    args=() if where=="" else (u["id"],)
    reports=conn.execute(f"""SELECT r.*, p.full_name reporter, a.full_name assignee FROM reports r
        LEFT JOIN users p ON r.reporter_id=p.id LEFT JOIN users a ON r.assigned_to=a.id
        {where} ORDER BY CASE r.priority WHEN 'Urgent' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END, r.created_at DESC""",args).fetchall()
    counts={
        "open":conn.execute("SELECT COUNT(*) FROM reports WHERE status NOT IN ('Resolved','Closed')").fetchone()[0],
        "assigned":conn.execute("SELECT COUNT(*) FROM reports WHERE assigned_to IS NOT NULL AND status NOT IN ('Resolved','Closed')").fetchone()[0],
        "urgent":conn.execute("SELECT COUNT(*) FROM reports WHERE priority='Urgent' AND status NOT IN ('Resolved','Closed')").fetchone()[0],
        "done":conn.execute("SELECT COUNT(*) FROM reports WHERE status IN ('Resolved','Closed')").fetchone()[0],
    }
    staff=conn.execute("SELECT id,full_name FROM users WHERE role='maintenance'").fetchall()
    conn.close()
    return render_template("dashboard/operations.html", reports=reports, counts=counts, staff=staff)

@app.route("/admin")
@login_required
def admin_dashboard():
    if current_user()["role"]!="admin": return redirect(url_for("dashboard"))
    conn=db()
    total=conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    open_count=conn.execute("SELECT COUNT(*) FROM reports WHERE status NOT IN ('Resolved','Closed')").fetchone()[0]
    resolved=conn.execute("SELECT COUNT(*) FROM reports WHERE status IN ('Resolved','Closed')").fetchone()[0]
    users=conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    by_cat=conn.execute("SELECT category,COUNT(*) c FROM reports GROUP BY category ORDER BY c DESC").fetchall()
    by_build=conn.execute("SELECT building,COUNT(*) c FROM reports GROUP BY building ORDER BY c DESC").fetchall()
    recent=conn.execute("SELECT r.*,u.full_name reporter FROM reports r LEFT JOIN users u ON r.reporter_id=u.id ORDER BY r.created_at DESC LIMIT 8").fetchall()
    conn.close()
    rate=round((resolved/total*100),1) if total else 0
    return render_template("dashboard/admin.html", total=total,open_count=open_count,resolved=resolved,users=users,rate=rate,by_cat=by_cat,by_build=by_build,recent=recent)

@app.route("/reports/new", methods=["GET","POST"])
@login_required
def new_report():
    if request.method=="POST":
        u=current_user()
        category=request.form.get("category"); building=request.form.get("building"); room=request.form.get("room_area")
        severity=request.form.get("severity"); desc=request.form.get("description","").strip(); noticed=request.form.get("date_noticed")
        conn=db()
        duplicate=conn.execute("""SELECT COUNT(*) c FROM reports WHERE building=? AND category=? AND status NOT IN ('Resolved','Closed')""",(building,category)).fetchone()["c"]
        priority=calculate_priority(severity,category,duplicate)
        code=make_report_code()
        conn.execute("""INSERT INTO reports(report_code,category,building,room_area,severity,description,date_noticed,reporter_id,priority,duplicate_count)
                        VALUES(?,?,?,?,?,?,?,?,?,?)""",(code,category,building,room,severity,desc,noticed,u["id"],priority,duplicate))
        rid=conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO report_updates(report_id,user_id,new_status,note) VALUES(?,?,?,?,?)",(rid,u["id"],"Reported","Report submitted by campus user."))
        conn.commit(); conn.close()
        flash(f"Report {code} submitted successfully.", "success")
        return redirect(url_for("report_detail", report_id=rid))
    return render_template("dashboard/report_form.html", categories=CATEGORIES, buildings=BUILDINGS, severities=SEVERITIES)

@app.route("/reports/<int:report_id>")
@login_required
def report_detail(report_id):
    conn=db()
    r=conn.execute("""SELECT r.*,p.full_name reporter,p.email reporter_email,a.full_name assignee
                      FROM reports r LEFT JOIN users p ON r.reporter_id=p.id LEFT JOIN users a ON r.assigned_to=a.id
                      WHERE r.id=?""",(report_id,)).fetchone()
    if not r: conn.close(); return "Report not found",404
    u=current_user()
    if u["role"] in ("student","faculty") and r["reporter_id"]!=u["id"]:
        conn.close(); return "Access denied",403
    timeline=conn.execute("""SELECT ru.*,u.full_name FROM report_updates ru LEFT JOIN users u ON ru.user_id=u.id
                             WHERE report_id=? ORDER BY created_at""",(report_id,)).fetchall()
    staff=conn.execute("SELECT id,full_name FROM users WHERE role='maintenance' ORDER BY full_name").fetchall()
    conn.close()
    return render_template("dashboard/report_detail.html",report=r,timeline=timeline,staff=staff,statuses=STATUSES)

@app.route("/reports/<int:report_id>/update", methods=["POST"])
@login_required
def update_report(report_id):
    u=current_user()
    if u["role"] not in ("maintenance","supervisor","admin"): return "Forbidden",403
    new_status=request.form.get("status"); note=request.form.get("note","").strip()
    assignee=request.form.get("assigned_to") or None
    conn=db(); r=conn.execute("SELECT * FROM reports WHERE id=?",(report_id,)).fetchone()
    if not r: conn.close(); return "Not found",404
    old=r["status"]
    if new_status not in STATUSES: new_status=old
    conn.execute("UPDATE reports SET status=?,assigned_to=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(new_status,assignee,report_id))
    conn.execute("INSERT INTO report_updates(report_id,user_id,old_status,new_status,note) VALUES(?,?,?,?,?)",(report_id,u["id"],old,new_status,note or f"Status changed to {new_status}."))
    if r["reporter_id"]:
        notify(r["reporter_id"],f"CampusFix {r['report_code']} updated",f"Your report is now {new_status}.")
    conn.commit(); conn.close()
    flash("Report updated successfully.", "success")
    return redirect(url_for("report_detail", report_id=report_id))

@app.route("/notifications")
@login_required
def notifications():
    u=current_user(); conn=db()
    items=conn.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC",(u["id"],)).fetchall()
    conn.execute("UPDATE notifications SET is_read=1 WHERE user_id=?",(u["id"],)); conn.commit(); conn.close()
    return render_template("dashboard/notifications.html",items=items)

@app.route("/profile")
@login_required
def profile(): return render_template("dashboard/profile.html", user=current_user())

@app.route("/api/stats")
def api_stats():
    conn=db()
    by_cat=conn.execute("SELECT category,COUNT(*) count FROM reports GROUP BY category").fetchall()
    by_build=conn.execute("SELECT building,COUNT(*) count FROM reports GROUP BY building").fetchall()
    conn.close()
    return jsonify({"categories":[dict(x) for x in by_cat],"buildings":[dict(x) for x in by_build]})

@app.errorhandler(404)
def not_found(e): return render_template("error.html", code=404, message="The page you are looking for could not be found."),404

init_db()
if __name__=="__main__":
    app.run(debug=True)
