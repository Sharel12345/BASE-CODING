# Daily Status Workflow

Trigger: manual (`project-manager` agent). No schedule is created during setup.

## Steps
1. **Connect/verify** – per `config/sources.json`. Report actual status (`connected` only after a real read).
2. **Retrieve** – clients, projects, users, statuses, open tasks (read-only). Note timestamps.
3. **Map** – by actual IDs; list ambiguous matches under "Decisions needed".
4. **Analyze** – overdue, upcoming (≤3 days), explicit blockers, no owner, awaiting approval/material. Tag `עובדה`/`הסקה`.
5. **Dedupe** – compare proposals with existing tasks per project.
6. **Report** – Hebrew, per template below. Not committed to Git.

## Report template (Hebrew)
```
דוח סטטוס יומי – THE CENTER
תאריך: <DD.MM.YYYY HH:mm, Asia/Jerusalem> | חיבור TaskFlow: <מחובר/לא מחובר>
1. עד 5 עדיפויות
2. משימות באיחור  (task_id | לקוח › פרויקט | יעד | אחראי)
3. חסמים ואישורים חסרים  (עובדה / הסקה)
4. החלטות נדרשות
5. הצעות למשימות (טיוטה – לא נוצרו ב-TaskFlow)
6. מקורות: חותמות זמן, מזהי/קישורי משימות
```

## Disconnected mode
Report only: connection not established, what was checked, and the single input needed (TaskFlow API documentation or connection method).
