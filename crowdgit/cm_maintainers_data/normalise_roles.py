from cm_database import query, execute
import json
from tqdm import tqdm
import asyncio


def load_classified_roles():
    with open("classified_roles.json", "r") as f:
        return json.load(f)


async def update_roles():
    classified_roles = load_classified_roles()

    sql = """
    SELECT DISTINCT role
    FROM "maintainersInternal"
    """
    results = await query(sql)
    roles = [row["role"] for row in results]

    for role in tqdm(roles, desc="Updating roles"):
        if role in classified_roles:
            new_role = classified_roles[role]
            if new_role == "delete":
                delete_sql = """
                DELETE FROM "maintainersInternal"
                WHERE role = $1
                """
                await execute(delete_sql, (role,))
            else:
                update_sql = """
                UPDATE "maintainersInternal"
                SET role = $1
                WHERE role = $2
                """
                await execute(update_sql, (new_role, role))
        else:
            print(f"Warning: Role '{role}' not found in classified_roles.json")


if __name__ == "__main__":
    asyncio.run(update_roles())
    print("Roles have been updated in the maintainersInternal table")
