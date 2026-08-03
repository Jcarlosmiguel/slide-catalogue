"""Backing logic for the sysadmin-only raw SQL console (POST /api/admin/sql
in main.py). Scope, as agreed: SELECT/UPDATE/DELETE/INSERT plus schema
statements like ALTER/CREATE - everything except DROP and TRUNCATE, which
stay blocked by name since they're the two statement types that can destroy
data with no smaller-blast-radius equivalent (an accidental bad UPDATE/DELETE
is at least recoverable from the backups created via
POST /api/admin/backup / backup_catalogue.sh - a dropped table isn't
meaningfully different from that, but blocking it by name costs nothing and
matches what the user explicitly asked to keep off the table).

Only ever executes exactly one statement per call: get_db_connection() never
sets CLIENT.MULTI_STATEMENTS, so the server itself won't run a second
stacked statement, and _split_statements() below is a second, independent
check so a chained "UPDATE x; DROP TABLE y;" is rejected before it ever
reaches the server, not just silently truncated.
"""

BLOCKED_KEYWORDS = {"DROP", "TRUNCATE"}


def _strip_leading_comments(sql):
    """Repeatedly strips leading whitespace and -- / # line comments and
    /* */ block comments, so the real first keyword can be found even when
    a submission starts with an explanatory comment."""
    while True:
        stripped = sql.lstrip()
        if stripped.startswith("--") or stripped.startswith("#"):
            newline = stripped.find("\n")
            sql = stripped[newline + 1:] if newline != -1 else ""
            continue
        if stripped.startswith("/*"):
            end = stripped.find("*/")
            sql = stripped[end + 2:] if end != -1 else ""
            continue
        return stripped


def _leading_keyword(sql):
    sql = _strip_leading_comments(sql)
    word = []
    for ch in sql:
        if ch.isalpha():
            word.append(ch)
        else:
            break
    return "".join(word).upper()


def _split_statements(sql):
    """Splits on ';' that isn't inside a '...'/"..."/`...` literal or a
    comment, so a semicolon embedded in a string value doesn't get mistaken
    for a second statement."""
    statements = []
    current = []
    quote = None
    i = 0
    n = len(sql)
    while i < n:
        ch = sql[i]

        if quote:
            current.append(ch)
            if ch == "\\" and quote != "`":
                # Escaped character - consume it verbatim (doesn't close the
                # quote), same handling MariaDB itself uses inside strings.
                if i + 1 < n:
                    current.append(sql[i + 1])
                    i += 2
                    continue
            elif ch == quote:
                quote = None
            i += 1
            continue

        if ch in ("'", '"', "`"):
            quote = ch
            current.append(ch)
            i += 1
            continue

        if sql[i:i + 2] == "--" or ch == "#":
            newline = sql.find("\n", i)
            current.append(sql[i:newline] if newline != -1 else sql[i:])
            i = newline if newline != -1 else n
            continue

        if sql[i:i + 2] == "/*":
            end = sql.find("*/", i + 2)
            current.append(sql[i:end + 2] if end != -1 else sql[i:])
            i = end + 2 if end != -1 else n
            continue

        if ch == ";":
            statements.append("".join(current))
            current = []
            i += 1
            continue

        current.append(ch)
        i += 1

    tail = "".join(current)
    if tail.strip():
        statements.append(tail)

    return statements


def validate_statement(sql):
    """Raises ValueError with a user-facing message if the submission isn't
    exactly one allowed statement. Returns nothing on success."""
    if not sql or not sql.strip():
        raise ValueError("Empty query")

    statements = _split_statements(sql)
    if len(statements) != 1:
        raise ValueError(
            "Only a single statement is allowed per execution - "
            f"found {len(statements)}"
        )

    keyword = _leading_keyword(statements[0])
    if not keyword:
        raise ValueError("Could not determine statement type")

    if keyword in BLOCKED_KEYWORDS:
        raise ValueError(f"{keyword} is not permitted through this console")
