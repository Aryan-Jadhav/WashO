from django.db import models


class DailyRevenue(models.Model):
    """Read-only model over the PostgreSQL VIEW `dashboard_daily_revenue` (see migration 0001).

    One row = money collected at one store on one day (Indian time).
    `managed = False` tells Django: don't create or change this "table" - the database
    view already exists, just let me query it like a normal table.
    """

    id = models.BigIntegerField(primary_key=True)  # row number made inside the view
    day = models.DateField()
    store = models.ForeignKey("stores.Store", on_delete=models.DO_NOTHING, related_name="+")
    orders = models.IntegerField()
    revenue = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        managed = False
        db_table = "dashboard_daily_revenue"
        ordering = ["day"]

    def __str__(self):
        return f"{self.day} {self.store_id}: ₹{self.revenue}"
