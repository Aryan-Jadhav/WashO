# PostgreSQL feature for the viva (2 of 2): a database VIEW for the revenue report.
#
# In simple words:
#   - A view is a SAVED QUERY that behaves like a read-only table.
#   - Ours joins payments with orders and adds up the money collected per store per day.
#   - The dashboard just reads "SELECT ... FROM dashboard_daily_revenue" - the joining,
#     grouping and time-zone conversion live in ONE place, inside the database.
#   - It is always up to date: a view stores no data of its own, it runs the query when read.
#
# Revenue = cash/UPI actually collected (Cash on Delivery), counted on the day it was
# collected, in Indian time (payments are stored in UTC).

from django.db import migrations, models

CREATE_VIEW = r"""
CREATE OR REPLACE VIEW dashboard_daily_revenue AS
SELECT
    row_number() OVER (ORDER BY t.day, t.store_id) AS id,
    t.day,
    t.store_id,
    count(*)            AS orders,
    sum(t.amount)       AS revenue
FROM (
    SELECT (p.collected_at AT TIME ZONE 'Asia/Kolkata')::date AS day,
           o.store_id,
           p.amount
    FROM payments_payment AS p
    JOIN orders_order     AS o ON o.id = p.order_id
) AS t
GROUP BY t.day, t.store_id;
"""

DROP_VIEW = "DROP VIEW IF EXISTS dashboard_daily_revenue;"


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("payments", "0001_initial"),
        ("orders", "0004_order_delivery_agent_order_delivery_date_and_more"),
        ("stores", "0002_pune_stores"),
    ]

    operations = [
        migrations.RunSQL(CREATE_VIEW, reverse_sql=DROP_VIEW),
        # Tell Django's migration state about the unmanaged model (no SQL is run for it).
        migrations.CreateModel(
            name="DailyRevenue",
            fields=[
                ("id", models.BigIntegerField(primary_key=True, serialize=False)),
                ("day", models.DateField()),
                ("orders", models.IntegerField()),
                ("revenue", models.DecimalField(decimal_places=2, max_digits=12)),
                ("store", models.ForeignKey(on_delete=models.DO_NOTHING, related_name="+", to="stores.store")),
            ],
            options={"db_table": "dashboard_daily_revenue", "ordering": ["day"], "managed": False},
        ),
    ]
