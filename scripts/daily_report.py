"""End-to-end read-only run: paginated live read -> analysis -> Hebrew summary on stdout.
Nothing is written to disk. Usage: python3 scripts/daily_report.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import taskflow_client as tf
from analyze import analyze, israel_today


def line(x):
    return f'  #{x["task_id"]} {(x["title"] or "")[:40]} | {x["client"]}›{x["project"]} | {x["url"]}'


def main():
    meta = {}
    for a, k in (("users.list", "users"), ("clients.list", "clients"), ("projects.list", "projects")):
        d = tf.call(a); meta[k] = (len(d[k]), d.get("count"))
    r = tf.paginate("tasks.list", "tasks")
    print("חיבור: אומת (קריאה בלבד)  |  " + "  ".join(f"{k}={n}/{c}" for k, (n, c) in meta.items()))
    print(f'משימות: נקראו {len(r["records"])} מתוך {r["reported_count"]} ב-{r["requests"]} בקשות; שלמות: {"כן" if r["complete"] else "לא"}')
    if not r["complete"]:
        print("  בעיות:", "; ".join(r["issues"]))
        return 2
    o = analyze(r["records"], [], israel_today())
    t = o["totals"]
    print(f'נכון ל-{o["as_of"]} (Asia/Jerusalem) | סה"כ {t["all"]}, פתוחות {t["open"]}, הושלמו {t["done"]}')
    for k, h in (("overdue", "באיחור"), ("due_today", "יעד היום"), ("upcoming", "יעד עד 3 ימים"),
                 ("no_owner", "ללא אחראי"), ("awaiting_client_approval", "ממתין לאישור לקוח"),
                 ("awaiting_manager_approval", "ממתין לאישור מנהל"), ("approval_untyped", "אישור ללא סוג"),
                 ("revision", "הערות לקוח"), ("no_due_date", "ללא תאריך יעד (פתוחות)"), ("blocked", "חסמים מפורשים")):
        print(f"{h}: {len(o[k])}")
        if k in ("overdue", "due_today", "upcoming", "no_owner"):
            for x in o[k][:10]: print(line(x))
    print("זמן המתנה באישור: לא ידוע (אין חותמת שינוי סטטוס)  |  מיפוי לקוח/פרויקט: לפי שם, לא מאומת")
    if o["ambiguous_names"]: print("שמות דו-משמעיים:", o["ambiguous_names"])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except tf.TaskFlowError as e:
        print(f"FAILED: {e}"); sys.exit(1)
