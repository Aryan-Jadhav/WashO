from django.shortcuts import render

from accounts.permissions import role_required
from accounts.roles import Role
from stores.models import Store
from tagging.models import MismatchAlert

from .services import dashboard_data, store_summary


@role_required(Role.ADMIN)
def dashboard(request):
    stores = Store.objects.filter(is_active=True)
    store = stores.filter(slug=request.GET.get("store", "")).first()
    data = dashboard_data(store=store)
    data.update({
        "stores": stores,
        "store": store,
        "store_rows": None if store else store_summary(),
        "latest_alerts": MismatchAlert.objects.filter(status=MismatchAlert.Status.OPEN)
        .select_related("order__store").order_by("-created_at")[:5],
        # Data for the charts, passed safely to JavaScript with |json_script.
        "chart_data": {k: data[k] for k in ("daily", "monthly", "by_status")}
        | {"top_services": [{"label": r["name"], "value": r["garments"]} for r in data["top_services"]]},
    })
    return render(request, "dashboard/dashboard.html", data)
