from crowdgit.cm_maintainers_data.cm_database import query, execute
from tqdm import tqdm
from slugify import slugify
import asyncio


async def compare_maintainers(repo_id: str, repo_url: str, maintainers: list[dict]):
    current_maintainers = await query(
        """
        SELECT mi.role, mi."repoUrl", mi."repoId", mi."identityId", mem.value as github_username
        FROM "maintainersInternal" mi
        JOIN "memberIdentities" mem ON mi."identityId" = mem.id
        WHERE mi."repoId" = %s AND mem.platform = 'github' AND mem.type = 'username' and mem.verified = True
        """,
        (repo_id,),
    )


async def process_maintainers(repo_id: str, repo_url: str, maintainers: list[dict]):
    async def process_maintainer(maintainer):
        title = maintainer["title"].lower()
        title = (
            title.replace("repository", "").replace("active", "").replace("project", "").strip()
        )
        role = slugify(title)
        # Find the identity in the database
        github_username = maintainer["github_username"]
        if github_username == "unknown":
            return
        identity = await query(
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
            await execute(
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

    semaphore = asyncio.Semaphore(3)

    async def process_with_semaphore(maintainer):
        async with semaphore:
            await process_maintainer(maintainer)

    await asyncio.gather(*[process_with_semaphore(maintainer) for maintainer in maintainers])
