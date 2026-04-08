from typing import Optional


DATABASE = {
    "vendor nordics": {
        "vendor_id": "V-041",
        "vendor_name": "Nordics Supply Co.",
        "last_invoice_amount": 1450.00,
        "payment_status": "pending",
        "notes": "Previous invoice #1023 paid on March 10"
    },
    "duplicate invoice": {
        "invoice_id": "INV-1023",
        "vendor": "Nordics Supply Co.",
        "amount": 1450.00,
        "paid_on": "2026-03-10",
        "status": "already_paid"
    },
    "spend approval policy": {
        "policy_id": "FIN-002",
        "title": "Discretionary Spend Approval Policy",
        "content": (
            "All discretionary spend requires manager approval. "
            "Amounts over $5,000 require CEO or Finance Lead sign-off. "
            "During a company-wide freeze, no discretionary spend may be "
            "approved without explicit CEO written authorisation."
        ),
        "last_updated": "2026-01-15"
    },
    "marketing budget": {
        "q2_budget": 12000.00,
        "spent_to_date": 8200.00,
        "remaining": 3800.00,
        "freeze_active": True
    },
    "office supplies policy": {
        "policy_id": "OPS-001",
        "content": "Office supplies under $200 can be approved by any team lead.",
        "last_updated": "2025-11-01"
    }
}


CALENDAR = {
    "tuesday_3pm": {
        "slot": "Tuesday 3:00 PM",
        "status": "blocked",
        "blocked_by": "Weekly engineering sync (recurring)",
        "organiser": "Jordan Mehta"
    },
    "tuesday_4pm": {
        "slot": "Tuesday 4:00 PM",
        "status": "available"
    },
    "wednesday_10am": {
        "slot": "Wednesday 10:00 AM",
        "status": "available"
    },
    "wednesday_2pm": {
        "slot": "Wednesday 2:00 PM",
        "status": "available"
    },
    "thursday_11am": {
        "slot": "Thursday 11:00 AM",
        "status": "available"
    }
}


EMAIL_LOG = []


def query_database(query: str) -> dict:
    query_lower = query.lower()
    
    KEYWORD_MAP = {
        "vendor nordics": ["nordics", "nordic", "supply co", "v-041"],
        "duplicate invoice": ["inv-1023", "duplicate", "already paid", "1023"],
        "spend approval policy": ["spend", "policy", "approval", "discretionary", "freeze", "fin-002"],
        "marketing budget": ["marketing budget", "q2 budget", "campaign budget"],
        "office supplies policy": ["office supplies", "ops-001", "stationery"]
    }
    
    for db_key, keywords in KEYWORD_MAP.items():
        if any(kw in query_lower for kw in keywords):
            return {"status": "found", "result": DATABASE[db_key]}
    
    return {
        "status": "not_found",
        "result": "No matching record found for query: " + query
    }


def check_calendar(slot: str) -> dict:
    slot_lower = slot.lower().replace(" ", "_").replace(":", "")
    for key, value in CALENDAR.items():
        if key in slot_lower or slot_lower in key:
            return {"status": "found", "result": value}
    return {
        "status": "not_found",
        "result": f"No calendar data found for slot: {slot}"
    }


def send_email(to: str, subject: str, body: str) -> dict:
    email = {"to": to, "subject": subject, "body": body}
    EMAIL_LOG.append(email)
    return {"status": "sent", "to": to, "subject": subject}


def calculate(expression: str) -> dict:
    try:
        allowed = set("0123456789+-*/(). ")
        if not all(c in allowed for c in expression):
            return {"status": "error", "result": "Invalid characters in expression"}
        result = eval(expression)
        return {"status": "ok", "result": round(result, 2)}
    except Exception as e:
        return {"status": "error", "result": str(e)}


def use_tool(tool_name: str, tool_args: Optional[dict]) -> dict:
    if tool_args is None:
        tool_args = {}

    if tool_name == "database":
        return query_database(tool_args.get("query", ""))
    elif tool_name == "calendar":
        return check_calendar(tool_args.get("slot", ""))
    elif tool_name == "email":
        return send_email(
            tool_args.get("to", ""),
            tool_args.get("subject", ""),
            tool_args.get("body", "")
        )
    elif tool_name == "calculator":
        return calculate(tool_args.get("expression", ""))
    else:
        return {"status": "error", "result": f"Unknown tool: {tool_name}"}


def reset_email_log():
    global EMAIL_LOG
    EMAIL_LOG = []


def get_email_log():
    return EMAIL_LOG.copy()