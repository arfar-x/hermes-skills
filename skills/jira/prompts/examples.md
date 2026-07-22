# Jira Assistant — Few-shot Examples

These examples illustrate the expected tool-calling pattern. Tool calls
are shown as `tool_name(args) -> result` with abbreviated JSON; actual
tool output includes full structured fields.

---

### "What should I work on next?"

```
my_work() -> [
  {"key": "PAY-101", "summary": "Fix rounding bug", "priority": "High",
   "status": "To Do", "updated": "2026-07-18T10:00:00Z", "blocked": false},
  {"key": "PAY-102", "summary": "Add retry logic", "priority": "Medium",
   "status": "To Do", "updated": "2026-07-10T09:00:00Z", "blocked": true}
]
```

Assistant reasons over the JSON (highest priority, not blocked, staleness)
and responds in prose, e.g.:

> I'd start with **PAY-101** ("Fix rounding bug") — it's High priority,
> not blocked, and hasn't moved since Jul 18. PAY-102 is Medium priority
> and currently blocked, so it's not actionable right now.

---

### "What's blocking PAY-412?"

```
blockers(issue_key="PAY-412") -> {
  "issue_key": "PAY-412",
  "blocked": true,
  "reasons": ["Blocked by PAY-390 (status: In Progress)"]
}
```

> PAY-412 is blocked by **PAY-390**, which is still In Progress.

If `"blocked": false`, respond that nothing is currently blocking it —
never invent a reason.

---

### "Summarize PAY-412."

```
issue_summary(issue_key="PAY-412") -> {
  "issue": {...}, "comments": [...], "worklogs": [...],
  "changelog": [...], "linked_issues": [...]
}
```

Assistant produces a concise natural-language summary of status, recent
activity, and any linked work — all drawn from the returned JSON.

---

### "Log 2h on PAY-412 for implementing validation."

Assistant first confirms:

> I'll log 2h on PAY-412 with the description "implementing validation" —
> confirm?

After the user confirms:

```
worklog(issue_key="PAY-412", duration="2h",
        description="implementing validation", confirm=true) -> {
  "confirmed": true, "issue_key": "PAY-412",
  "worklog": {"id": "10021", "time_spent": "2h", ...}
}
```

> Logged 2h on PAY-412.

---

### "Move PAY-412 to Review."

Assistant first confirms, then calls:

```
transition(issue_key="PAY-412", status="Review", confirm=true) -> {
  "confirmed": true, "issue_key": "PAY-412",
  "transitioned_to": "Review", "transition_name": "Move to Review"
}
```

> Moved PAY-412 to Review.

---

### "Which tickets haven't been updated recently?"

```
search(jql="assignee = currentUser() AND updated <= -14d AND resolution = Unresolved") -> {
  "jql": "...", "count": 2,
  "issues": [{"key": "PAY-050", "updated": "2026-07-01T...", ...}, ...]
}
```

> Two of your tickets haven't been touched in 2+ weeks: PAY-050 (last
> updated Jul 1) and ...

---

### "What's the current sprint goal?"

```
sprint() -> {
  "board": {"id": 3, "name": "PAY Board", "type": "scrum"},
  "sprint": {"id": 55, "name": "Sprint 12", "state": "active",
             "start_date": "...", "end_date": "...",
             "goal": "Ship validation improvements"}
}
```

> The active sprint is **Sprint 12**, goal: "Ship validation
> improvements", running through <end_date>.
