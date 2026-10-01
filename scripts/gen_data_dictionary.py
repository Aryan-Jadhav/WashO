"""Generate docs/04_data_dictionary.md from the real Django models.

Run:  venv\\Scripts\\python scripts\\gen_data_dictionary.py
WHY generated: the dictionary then always matches the database exactly.
"""
import inspect
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "washo.settings")

import django  # noqa: E402

django.setup()

from django.apps import apps  # noqa: E402
from django.db import connection, models  # noqa: E402

OUR_APPS = ["accounts", "stores", "catalog", "orders", "tagging", "payments", "dashboard", "core"]
EXTRA = [("auth", "Group")]  # roles


def purpose(model):
    doc = inspect.getdoc(model) or ""
    if doc.startswith(model.__name__ + "("):  # Django's automatic signature docstring
        doc = ""
    first = doc.split("\n\n")[0].replace("\n", " ").strip()
    return first or f"Stores {model._meta.verbose_name_plural}."


def col_type(f):
    t = f.db_type(connection) or ""
    if isinstance(f, models.ForeignKey):
        t = f.target_field.rel_db_type(connection)
    return t.replace("character varying", "varchar")


def constraints_for(f, model):
    c = []
    if f.primary_key:
        c.append("PK")
    if isinstance(f, models.ForeignKey):
        c.append(f"FK → {f.related_model._meta.db_table} ({f.remote_field.on_delete.__name__})")
    if f.unique and not f.primary_key:
        c.append("UNIQUE")
    c.append("NULL" if f.null else "NOT NULL")
    if f.has_default() and not callable(f.default):
        c.append(f"DEFAULT {f.default!r}")
    if getattr(f, "db_default", models.NOT_PROVIDED) is not models.NOT_PROVIDED:
        c.append("DB DEFAULT")
    if f.db_index and not f.unique and not f.primary_key and not isinstance(f, models.ForeignKey):
        c.append("INDEX")
    if f.choices:
        c.append("CHOICES: " + ", ".join(str(k) for k, _ in f.flatchoices[:12]))
    return "; ".join(c)


def description(f):
    text = str(f.help_text or "").strip() or str(f.verbose_name).capitalize()
    return text.replace("|", "/")


OPS = {"exact": "=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<=", "in": "IN", "regex": "matches regex",
       "isnull": "IS NULL"}


def readable(q):
    """Turn a Django Q() condition into SQL-like text, e.g. "total = subtotal + express_charge - discount"."""
    if isinstance(q, models.Q):
        parts = [readable(child) for child in q.children]
        text = f" {q.connector} ".join(parts)
        if len(parts) > 1:
            text = f"({text})"
        return f"NOT {text}" if q.negated else text
    lookup, value = q
    field, _, op = lookup.partition("__")
    if op not in OPS:
        field, op = lookup, "exact"
    if isinstance(value, (models.F, models.Expression)):
        val = str(value).replace("F(", "").replace(")", "").replace("Upper(", "UPPER(")
        if "UPPER" in val:
            val += ")"
    elif isinstance(value, (list, tuple)):
        val = "(" + ", ".join(repr(v) for v in value) + ")"
    elif isinstance(value, str):
        val = f"'{value}'"  # shown as SQL text, not Python repr (no doubled backslashes)
    else:
        val = repr(value)
    if op == "isnull":
        return f"{field} IS {'NULL' if value else 'NOT NULL'}"
    return f"{field} {OPS[op]} {val}"


def table(model):
    meta = model._meta
    out = [f"### `{meta.db_table}` — {meta.verbose_name.title()}", "", purpose(model), ""]
    if not meta.managed:
        out += ["*Read-only: this is a **PostgreSQL VIEW**, not a table.*", ""]
    out += ["| Field | Type | Constraint | Description |", "|---|---|---|---|"]
    for f in meta.concrete_fields:
        out.append(f"| `{f.column}` | {col_type(f)} | {constraints_for(f, model)} | {description(f)} |")
    for f in meta.many_to_many:
        out.append(f"| `{f.name}` | (link table `{f.m2m_db_table()}`) | M2M → {f.related_model._meta.db_table} | "
                   f"{description(f)} |")
    extra = []
    for c in meta.constraints:
        kind = "CHECK" if isinstance(c, models.CheckConstraint) else "UNIQUE"
        detail = ""
        if isinstance(c, models.UniqueConstraint):
            detail = "(" + ", ".join(c.fields) + ")" + (f" WHERE {readable(c.condition)}" if c.condition else "")
        else:
            detail = readable(c.condition)
        extra.append(f"- **{kind}** `{c.name}`: {detail}")
    for idx in meta.indexes:
        extra.append(f"- **INDEX** `{idx.name}`: (" + ", ".join(idx.fields) + ")")
    if extra:
        out += ["", "Table-level constraints and indexes:", ""] + extra
    return "\n".join(out) + "\n"


def main():
    parts = [
        "# Data Dictionary",
        "",
        "Generated from the Django models by `scripts/gen_data_dictionary.py` (do not edit by hand).",
        "Every table has an auto-increment primary key `id` (bigint) unless shown otherwise.",
        "Types are the PostgreSQL column types. FK rules: CASCADE = delete children too, "
        "PROTECT = refuse to delete while referenced, SET_NULL = keep the row and clear the link.",
        "",
    ]
    models_list = []
    for label in OUR_APPS:
        models_list += [m for m in apps.get_app_config(label).get_models()]
    models_list += [apps.get_model(a, m) for a, m in EXTRA]
    parts.append("## Tables\n")
    for i, m in enumerate(models_list, 1):
        parts.append(f"{i}. [`{m._meta.db_table}`](#{m._meta.db_table.replace('_', '')}) — {m._meta.verbose_name.title()}")
    parts.append("")
    for m in models_list:
        parts.append(table(m))
    parts.append("## PostgreSQL trigger\n")
    parts.append("| Object | Type | Fires | Action |\n|---|---|---|---|\n"
                 "| `washo_log_order_status()` | PL/pgSQL function | — | Inserts a row in `orders_orderstatushistory` "
                 "(old status, new status, user from setting `washo.changed_by`, note, time). |\n"
                 "| `trg_order_status_on_insert` | AFTER INSERT trigger on `orders_order` | every new order | "
                 "calls the function (history starts with Booked) |\n"
                 "| `trg_order_status_on_update` | AFTER UPDATE OF status trigger on `orders_order` | only when "
                 "status really changes | calls the function |\n")
    out = ROOT / "docs" / "04_data_dictionary.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote {out} ({len(models_list)} tables)")


if __name__ == "__main__":
    main()
