from urllib.parse import urlparse
from crowdgit.cm_maintainers_data.scraper import scrape
from crowdgit.cm_maintainers_data.cm_database import query, execute
import os
from datetime import datetime
from crowdgit.cm_maintainers_data.process_maintainers import process_maintainers
import csv
import asyncio
from crowdgit.logger import get_logger
from crowdgit import LOCAL_DIR

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
    pass


async def reidentify_repos_with_no_maintainers():
    pass


async def main():
    async with asyncio.TaskGroup() as tg:
        tg.create_task(parse_not_parsed())
        tg.create_task(parse_already_parsed())
        tg.create_task(reidentify_repos_with_no_maintainers())


if __name__ == "__main__":
    asyncio.run(main())
