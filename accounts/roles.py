"""The four user roles. Each role is a Django Group with the same name."""


class Role:
    CUSTOMER = "Customer"
    STAFF = "Store Staff"
    AGENT = "Delivery Agent"
    ADMIN = "Admin"

    ALL = [CUSTOMER, STAFF, AGENT, ADMIN]
