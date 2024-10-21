from cm_database import query, execute
from tqdm import tqdm
from slugify import slugify


def process_maintainers(repo_id, repo_url, maintainers):
    for maintainer in maintainers:
        title = maintainer["title"].lower()
        title = (
            title.replace("repository", "").replace("active", "").replace("project", "").strip()
        )
        role = slugify(title)
        # Find the identity in the database
        github_username = maintainer["github_username"]
        if github_username == "unknown":
            continue
        identity = query(
            """
            SELECT id 
            FROM "memberIdentities" 
            WHERE platform = 'github' AND value = %s
            LIMIT 1
        """,
            (github_username,),
        )
        if identity:
            identity_id = identity[0]["id"]
            # Insert maintainer data
            execute(
                """
                INSERT INTO "maintainersInternal" 
                (role, "repoUrl", "repoId", "identityId")
                VALUES (%s, %s, %s, %s)
                ON CONFLICT ("repoId", "identityId") DO UPDATE
                SET role = EXCLUDED.role, "updatedAt" = NOW()
            """,
                (role, repo_url, repo_id, identity_id),
            )
        else:
            tqdm.write(f"Identity not found for GitHub user: {maintainer}")
