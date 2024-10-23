from urllib.parse import urlparse
from crowdgit.cm_maintainers_data.scraper import scrape, check_for_updates
from crowdgit.cm_maintainers_data.cm_database import query, execute
import os
from datetime import datetime
from crowdgit.cm_maintainers_data.process_maintainers import process_maintainers
import csv
import asyncio
from crowdgit.logger import get_logger
from crowdgit import LOCAL_DIR
from datetime import datetime, timedelta
import base64

logger = get_logger(__name__)

GET_COST = True


def update_cost_csv(url, total_cost):
    csv_file = LOCAL_DIR / "repo_costs.csv"
    file_exists = os.path.isfile(csv_file)

    with open(csv_file, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow(["Repo URL", "Total Cost"])
        writer.writerow([url, total_cost])


def write_failed_repo(url, owner, repo_name, error):
    csv_file = LOCAL_DIR / "failed_repos.csv"
    file_exists = os.path.isfile(csv_file)

    with open(csv_file, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow(["repo_url", "owner", "repo", "error"])
        writer.writerow([url, owner, repo_name, str(error)])


def is_repo_failed(url):
    if not os.path.isfile(LOCAL_DIR / "failed_repos.csv"):
        return False

    with open(LOCAL_DIR / "failed_repos.csv", "r") as csvfile:
        reader = csv.DictReader(csvfile)
        return any(row["repo_url"] == url for row in reader)


async def parse_not_parsed():
    try:
        # Query to get repos that haven't been processed recently
        repos = await query(
            """
            SELECT id, url 
            FROM "githubRepos" 
            WHERE "lastMaintainerRunAt" IS NULL 
        """
        )

        logger.info("Processing repos")
        for repo in repos:
            try:
                url = repo["url"]
                repo_id = repo["id"]

                if is_repo_failed(url):
                    logger.info(f"Skipping failed repo: {url}")
                    continue

                parsed_url = urlparse(url)
                path_parts = parsed_url.path.strip("/").split("/")

                if len(path_parts) >= 2:
                    owner, repo_name = path_parts[:2]
                    if owner == "envoyproxy":
                        raise Exception("envoy later")

                    logger.info(f"\nProcessing repo: github.com/{owner}/{repo_name}")
                    result = scrape(owner, repo_name)

                    if (
                        isinstance(result, dict)
                        and "maintainer_file" in result
                        and "maintainer_info" in result
                    ):
                        maintainer_file = result["maintainer_file"]
                        maintainer_info = result["maintainer_info"]

                        await process_maintainers(repo_id, url, maintainer_info)

                        # Update githubRepos table
                        await execute(
                            """
                            UPDATE "githubRepos"
                            SET "maintainerFile" = %s, "lastMaintainerRunAt" = %s
                            WHERE id = %s
                        """,
                            (maintainer_file, datetime.now(), repo_id),
                        )

                        logger.info(f"Successfully processed maintainers for {owner}/{repo_name}")

                        if GET_COST:
                            update_cost_csv(url, result["total_cost"])
                    else:
                        await execute(
                            """
                            UPDATE "githubRepos"
                            SET "lastMaintainerRunAt" = %s
                            WHERE id = %s
                        """,
                            (datetime.now(), repo_id),
                        )
                        logger.warning(
                            f"Failed to scrape maintainers for {owner}/{repo_name}: {result.get('reason', 'Unknown error')}"
                        )

                        if GET_COST and "total_cost" in result:
                            update_cost_csv(url, result["total_cost"])
                else:
                    logger.error(f"Invalid GitHub URL format: {url}")
                    write_failed_repo(url, "", "", "Invalid GitHub URL format")

            except Exception as error:
                logger.error(f"Error processing repo {url}: {error}")
                write_failed_repo(url, owner, repo_name, error)

    except Exception as error:
        logger.error(f"Error while processing repos: {error}")
        raise error


async def parse_already_parsed():
    repos = await query(
        """
            SELECT id, url , "lastMaintainerRunAt", "maintainerFile"
            FROM "githubRepos" 
            WHERE "lastMaintainerRunAt" IS NOT NULL
            and "maintainerFile" is not null
        """
    )

    # here we will need to check if there are updates to the maintainer file since the last run
    for repo in repos:
        repo_id = repo["id"]
        url = repo["url"]
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.strip("/").split("/")

        if len(path_parts) >= 2:
            owner, repo_name = path_parts[:2]
            if owner == "envoyproxy":
                continue  # Skip envoyproxy repos for now

            logger.info(f"\nProcessing repo: github.com/{owner}/{repo_name}")
            try:
                result = check_for_updates(
                    repo["maintainerFile"], owner, repo_name, repo["lastMaintainerRunAt"]
                )

                if result is not None:
                    if isinstance(result, dict) and "maintainer_info" in result:
                        maintainer_info = result["maintainer_info"]

                        await process_maintainers(repo_id, url, maintainer_info)

                        # Update githubRepos table
                        await execute(
                            """
                            UPDATE "githubRepos"
                            SET  "lastMaintainerRunAt" = %s
                            WHERE id = %s
                            """,
                            (datetime.now(), repo_id),
                        )

                        logger.info(f"Successfully processed maintainers for {owner}/{repo_name}")

                        if GET_COST:
                            update_cost_csv(url, result["total_cost"])
                    else:
                        await execute(
                            """
                            UPDATE "githubRepos"
                            SET "lastMaintainerRunAt" = %s
                            WHERE id = %s
                            """,
                            (datetime.now(), repo_id),
                        )
                        logger.warning(
                            f"Failed to re-scrape maintainers for {owner}/{repo_name}: {result.get('reason', 'Unknown error')}"
                        )

                        if GET_COST and "total_cost" in result:
                            update_cost_csv(url, result["total_cost"])
                else:
                    logger.info(f"No updates found for {owner}/{repo_name}")
            except Exception as error:
                logger.error(f"Error processing repo {url}: {error}")
                write_failed_repo(url, owner, repo_name, str(error))
        else:
            logger.error(f"Invalid GitHub URL format: {url}")
            write_failed_repo(url, "", "", "Invalid GitHub URL format")


async def reidentify_repos_with_no_maintainer_file():
    repos = await query(
        """
            SELECT id, url, "lastMaintainerRunAt", "maintainerFile"
            FROM "githubRepos" 
            WHERE "lastMaintainerRunAt" IS NOT NULL
            AND "maintainerFile" IS NULL
        """
    )

    for repo in repos:
        url = repo["url"]
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.strip("/").split("/")

        if len(path_parts) >= 2:
            owner, repo_name = path_parts[:2]
            if owner == "envoyproxy":
                continue  # Skip envoyproxy repos for now

            logger.info(f"\nProcessing repo: github.com/{owner}/{repo_name}")

            # Here we will need to rerun search for the maintainer file
            # TODO: Implement the search for maintainer file


async def main():
    async with asyncio.TaskGroup() as tg:
        tg.create_task(parse_not_parsed())
        tg.create_task(parse_already_parsed())
        tg.create_task(reidentify_repos_with_no_maintainer_file())


if __name__ == "__main__":
    asyncio.run(main())
