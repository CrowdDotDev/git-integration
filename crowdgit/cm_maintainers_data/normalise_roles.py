from cm_database import query, execute
from bedrock import invoke_bedrock
import json
from tqdm import tqdm


def load_classified_roles():
    with open("classified_roles.json", "r") as f:
        return json.load(f)


def update_roles():
    classified_roles = load_classified_roles()

    sql = """
    SELECT DISTINCT role
    FROM "maintainersInternal"
    """
    roles = [row["role"] for row in query(sql)]

    for role in tqdm(roles, desc="Updating roles"):
        if role in classified_roles:
            new_role = classified_roles[role]
            if new_role == "delete":
                delete_sql = """
                DELETE FROM "maintainersInternal"
                WHERE role = %s
                """
                execute(delete_sql, (role,))
            else:
                update_sql = """
                UPDATE "maintainersInternal"
                SET role = %s
                WHERE role = %s
                """
                execute(update_sql, (new_role, role))
        else:
            print(f"Warning: Role '{role}' not found in classified_roles.json")


if __name__ == "__main__":
    update_roles()
    print("Roles have been updated in the maintainersInternal table")
