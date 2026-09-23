"""RBAC: one centralized role -> permission matrix. No scattered `if role ==` checks."""
from enum import Enum


class Role(str, Enum):
    BENEFICIARY = "BENEFICIARY"
    DSO = "DSO"
    FIELD_FOOD_INSPECTOR = "FIELD_FOOD_INSPECTOR"
    FPS_OWNER = "FPS_OWNER"
    AUDITOR = "AUDITOR"
    SYSTEM_ADMIN = "SYSTEM_ADMIN"


# officers.role values in the dataset -> canonical roles used in tokens and permission checks
OFFICER_ROLE_MAP = {
    "DISTRICT_OFFICER": Role.DSO,
    "FIELD_FOOD_INSPECTOR": Role.FIELD_FOOD_INSPECTOR,
    "FPS_OWNER": Role.FPS_OWNER,
    "AUDITOR": Role.AUDITOR,
    "ADMIN": Role.SYSTEM_ADMIN,
}

# where the client should send a user after login (role routing)
PORTALS = {
    Role.BENEFICIARY: "/beneficiary",
    Role.DSO: "/dso",
    Role.FIELD_FOOD_INSPECTOR: "/inspector",
    Role.FPS_OWNER: "/fps",
    Role.AUDITOR: "/auditor",
    Role.SYSTEM_ADMIN: "/admin",
}


class Permission(str, Enum):
    AUTH_LOGIN = "AUTH_LOGIN"
    AUTH_LOGOUT = "AUTH_LOGOUT"
    VIEW_OWN_PROFILE = "VIEW_OWN_PROFILE"
    VIEW_OWN_ENTITLEMENT = "VIEW_OWN_ENTITLEMENT"
    SUBMIT_INTENT = "SUBMIT_INTENT"
    VIEW_OWN_HISTORY = "VIEW_OWN_HISTORY"
    VIEW_CYCLE = "VIEW_CYCLE"
    VIEW_DEMAND = "VIEW_DEMAND"
    VIEW_FPS = "VIEW_FPS"
    VIEW_WAREHOUSE = "VIEW_WAREHOUSE"
    MANAGE_CYCLE = "MANAGE_CYCLE"
    VIEW_INSPECTIONS = "VIEW_INSPECTIONS"
    CREATE_INSPECTION_ORDER = "CREATE_INSPECTION_ORDER"
    SUBMIT_INSPECTION = "SUBMIT_INSPECTION"
    VIEW_FPS_INVENTORY = "VIEW_FPS_INVENTORY"
    VIEW_FPS_TRANSACTIONS = "VIEW_FPS_TRANSACTIONS"
    PROCESS_EPOS = "PROCESS_EPOS"
    VIEW_AUDIT = "VIEW_AUDIT"
    VIEW_MANIFEST = "VIEW_MANIFEST"
    MANAGE_USERS = "MANAGE_USERS"
    MANAGE_ROLES = "MANAGE_ROLES"
    MANAGE_DATASETS = "MANAGE_DATASETS"
    VIEW_SYSTEM_HEALTH = "VIEW_SYSTEM_HEALTH"
    VERIFY_DISPATCH = "VERIFY_DISPATCH"
    REVIEW_AUDIT = "REVIEW_AUDIT"
    VIEW_ACTIONS = "VIEW_ACTIONS"


P = Permission
_COMMON = {P.AUTH_LOGIN, P.AUTH_LOGOUT}

ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.BENEFICIARY: _COMMON | {P.VIEW_OWN_PROFILE, P.VIEW_OWN_ENTITLEMENT, P.SUBMIT_INTENT,
                                 P.VIEW_OWN_HISTORY, P.VIEW_CYCLE, P.VIEW_FPS},
    Role.DSO: _COMMON | {P.VIEW_CYCLE, P.VIEW_DEMAND, P.VIEW_FPS, P.VIEW_WAREHOUSE, P.MANAGE_CYCLE,
                         P.VIEW_MANIFEST, P.VIEW_AUDIT, P.VIEW_INSPECTIONS, P.CREATE_INSPECTION_ORDER,
                         P.VIEW_ACTIONS},
    Role.FIELD_FOOD_INSPECTOR: _COMMON | {P.VIEW_CYCLE, P.VIEW_FPS, P.VIEW_INSPECTIONS, P.SUBMIT_INSPECTION,
                                          P.VERIFY_DISPATCH, P.VIEW_ACTIONS},
    Role.FPS_OWNER: _COMMON | {P.VIEW_CYCLE, P.VIEW_FPS, P.VIEW_FPS_INVENTORY, P.VIEW_FPS_TRANSACTIONS,
                               P.PROCESS_EPOS, P.VIEW_MANIFEST, P.VIEW_ACTIONS},
    Role.AUDITOR: _COMMON | {P.VIEW_CYCLE, P.VIEW_DEMAND, P.VIEW_FPS, P.VIEW_WAREHOUSE, P.VIEW_AUDIT,
                             P.VIEW_MANIFEST, P.VIEW_INSPECTIONS, P.REVIEW_AUDIT, P.VIEW_ACTIONS},
    Role.SYSTEM_ADMIN: _COMMON | {P.MANAGE_USERS, P.MANAGE_ROLES, P.MANAGE_DATASETS, P.VIEW_SYSTEM_HEALTH,
                                   P.VIEW_AUDIT, P.VIEW_CYCLE, P.VIEW_DEMAND, P.VIEW_ACTIONS},
}


def canonical_officer_role(db_role: str) -> Role | None:
    return OFFICER_ROLE_MAP.get(db_role)


def get_permissions(role: str) -> set[Permission]:
    try:
        return ROLE_PERMISSIONS[Role(role)]
    except (ValueError, KeyError):
        return set()


def has_permission(role: str, perm: Permission) -> bool:
    return perm in get_permissions(role)


def portal_for(role: str) -> str | None:
    try:
        return PORTALS[Role(role)]
    except (ValueError, KeyError):
        return None
