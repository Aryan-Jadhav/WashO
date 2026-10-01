# PostgreSQL feature for the viva: a PL/pgSQL TRIGGER that writes the order status history.
#
# In simple words:
#   - A trigger is a small program stored INSIDE the database that runs automatically
#     when a table changes.
#   - Ours runs after a new order is inserted, and after an order's status is updated.
#   - It inserts one row into orders_orderstatushistory: old status, new status, time, who.
#   - "Who" comes from a per-transaction setting (washo.changed_by) that the Django code
#     sets just before saving (orders/services.py -> _set_audit_context). If someone changes
#     a status directly in the database, the change is STILL recorded (with changed_by empty).
#
# WHY in the database and not only in Python: the audit trail cannot be skipped by any
# program, script or manual SQL - it is enforced at the lowest level.

from django.db import migrations

CREATE_SQL = r"""
CREATE OR REPLACE FUNCTION washo_log_order_status() RETURNS trigger AS $$
DECLARE
    -- current_setting(name, true) returns NULL instead of an error when the setting is missing.
    v_user_id bigint := NULLIF(current_setting('washo.changed_by', true), '')::bigint;
    v_note    text   := COALESCE(current_setting('washo.status_note', true), '');
    v_from    text   := '';
BEGIN
    IF TG_OP = 'UPDATE' THEN
        v_from := OLD.status;
    END IF;

    INSERT INTO orders_orderstatushistory (order_id, from_status, to_status, changed_by_id, note, changed_at)
    VALUES (NEW.id, v_from, NEW.status, v_user_id, LEFT(v_note, 300), now());

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Fires once for every new order (history starts with "Booked").
CREATE TRIGGER trg_order_status_on_insert
    AFTER INSERT ON orders_order
    FOR EACH ROW
    EXECUTE FUNCTION washo_log_order_status();

-- Fires only when the status column really changes (not on other edits).
CREATE TRIGGER trg_order_status_on_update
    AFTER UPDATE OF status ON orders_order
    FOR EACH ROW
    WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION washo_log_order_status();
"""

DROP_SQL = r"""
DROP TRIGGER IF EXISTS trg_order_status_on_update ON orders_order;
DROP TRIGGER IF EXISTS trg_order_status_on_insert ON orders_order;
DROP FUNCTION IF EXISTS washo_log_order_status();
"""


class Migration(migrations.Migration):

    dependencies = [("orders", "0001_initial")]

    operations = [migrations.RunSQL(CREATE_SQL, reverse_sql=DROP_SQL)]
