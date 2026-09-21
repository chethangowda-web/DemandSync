"""
RBAC — centralized permission matrix. No scattered if role == checks.
"""
from enum import Enum

class Role(str, Enum):
    BENEFICIARY = "BENEFICIARY"
    DSO = "DSO"
    FIELD_FOOD_INSPECTOR = "FIELD_FOOD_INSPECTOR"
    FPS_OWNER = "FPS_OWNER"
    AUDITOR = "AUDITOR"
    SYSTEM_ADMIN = "SYSTEM_ADMIN"
    # legacy aliases for existing DB
    DISTRICT_OFFICER = "DSO"
    ADMIN = "SYSTEM_ADMIN"

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

# Centralized mapping ROLE -> PERMISSIONS
ROLE_PERMISSIONS = {
    Role.BENEFICIARY: {
        Permission.AUTH_LOGIN, Permission.AUTH_LOGOUT,
        Permission.VIEW_OWN_PROFILE, Permission.VIEW_OWN_ENTITLEMENT,
        Permission.SUBMIT_INTENT, Permission.VIEW_OWN_HISTORY,
        Permission.VIEW_CYCLE, Permission.VIEW_FPS,
    },
    Role.DSO: {
        Permission.AUTH_LOGIN, Permission.AUTH_LOGOUT,
        Permission.VIEW_CYCLE, Permission.VIEW_DEMAND, Permission.VIEW_FPS, Permission.VIEW_WAREHOUSE,
        Permission.MANAGE_CYCLE, Permission.VIEW_MANIFEST, Permission.VIEW_AUDIT,
        Permission.VIEW_INSPECTIONS,
    },
    Role.FIELD_FOOD_INSPECTOR: {
        Permission.AUTH_LOGIN, Permission.AUTH_LOGOUT,
        Permission.VIEW_CYCLE, Permission.VIEW_FPS,
        Permission.VIEW_INSPECTIONS, Permission.CREATE_INSPECTION_ORDER, Permission.SUBMIT_INSPECTION,
    },
    Role.FPS_OWNER: {
        Permission.AUTH_LOGIN, Permission.AUTH_LOGOUT,
        Permission.VIEW_CYCLE, Permission.VIEW_FPS,
        Permission.VIEW_FPS_INVENTORY, Permission.VIEW_FPS_TRANSACTIONS, Permission.PROCESS_EPOS, Permission.VIEW_MANIFEST,
    },
    Role.AUDITOR: {
        Permission.AUTH_LOGIN, Permission.AUTH_LOGOUT,
        Permission.VIEW_CYCLE, Permission.VIEW_DEMAND, Permission.VIEW_FPS, Permission.VIEW_WAREHOUSE,
        Permission.VIEW_AUDIT, Permission.VIEW_MANIFEST, Permission.VIEW_INSPECTIONS,
    },
    Role.SYSTEM_ADMIN: {
        Permission.AUTH_LOGIN, Permission.AUTH_LOGOUT,
        Permission.MANAGE_USERS, Permission.MANAGE_ROLES, Permission.MANAGE_DATASETS, Permission.VIEW_SYSTEM_HEALTH,
        Permission.VIEW_AUDIT, Permission.VIEW_CYCLE, Permission.VIEW_DEMAND,
    },
}

# Officer role aliases
ROLE_PERMISSIONS[Role.DISTRICT_OFFICER] = ROLE_PERMISSIONS[Role.DSO]
ROLE_PERMISSIONS[Role.ADMIN] = ROLE_PERMISSIONS[Role.SYSTEM_ADMIN]

def get_permissions(role: str) -> set:
    try: return ROLE_PERMISSIONS[Role(role)]
    except: return set()

def has_permission(role: str, perm: Permission) -> bool:
    return perm in get_permissions(role)
