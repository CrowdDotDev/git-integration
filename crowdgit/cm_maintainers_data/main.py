from urllib.parse import urlparse
from scraper import scrape
from cm_database import query, execute
from tqdm import tqdm
import os
from datetime import datetime
from process_maintainers import process_maintainers
import csv

GET_COST = True


def update_cost_csv(url, total_cost):
    csv_file = "repo_costs.csv"
    file_exists = os.path.isfile(csv_file)

    with open(csv_file, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow(["Repo URL", "Total Cost"])
        writer.writerow([url, total_cost])


def write_failed_repo(url, owner, repo_name, error):
    csv_file = "failed_repos.csv"
    file_exists = os.path.isfile(csv_file)

    with open(csv_file, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow(["repo_url", "owner", "repo", "error"])
        writer.writerow([url, owner, repo_name, str(error)])


def is_repo_failed(url):
    if not os.path.isfile("failed_repos.csv"):
        return False

    with open("failed_repos.csv", "r") as csvfile:
        reader = csv.DictReader(csvfile)
        return any(row["repo_url"] == url for row in reader)


def main():
    try:
        # Query to get repos that haven't been processed recently
        repos = query(
            """
            SELECT id, url 
            FROM "githubRepos" 
            WHERE "lastMaintainerRunAt" IS NULL 
        """
        )

        for repo in tqdm(repos, desc="Processing repos", unit="repo"):
            try:
                url = repo["url"]
                repo_id = repo["id"]

                if is_repo_failed(url):
                    tqdm.write(f"Skipping failed repo: {url}")
                    continue

                parsed_url = urlparse(url)
                path_parts = parsed_url.path.strip("/").split("/")

                if len(path_parts) >= 2:
                    owner, repo_name = path_parts[:2]
                    if owner == "envoyproxy":
                        raise Exception("envoy later")
                    tqdm.write(f"\nProcessing repo: github.com/{owner}/{repo_name}")
                    result = scrape(owner, repo_name)

                    if (
                        isinstance(result, dict)
                        and "maintainer_file" in result
                        and "maintainer_info" in result
                    ):
                        maintainer_file = result["maintainer_file"]
                        maintainer_info = result["maintainer_info"]

                        process_maintainers(repo_id, url, maintainer_info)

                        # Update githubRepos table
                        execute(
                            """
                            UPDATE "githubRepos"
                            SET "maintainerFile" = %s, "lastMaintainerRunAt" = %s
                            WHERE id = %s
                        """,
                            (maintainer_file, datetime.now(), repo_id),
                        )

                        tqdm.write(f"Successfully processed maintainers for {owner}/{repo_name}")

                        if GET_COST:
                            update_cost_csv(url, result["total_cost"])
                    else:
                        execute(
                            """
                            UPDATE "githubRepos"
                            SET "lastMaintainerRunAt" = %s
                            WHERE id = %s
                        """,
                            (datetime.now(), repo_id),
                        )
                        tqdm.write(
                            f"Failed to scrape maintainers for {owner}/{repo_name}: {result.get('reason', 'Unknown error')}"
                        )

                        if GET_COST and "total_cost" in result:
                            update_cost_csv(url, result["total_cost"])
                else:
                    tqdm.write(f"Invalid GitHub URL format: {url}")
                    write_failed_repo(url, "", "", "Invalid GitHub URL format")

            except Exception as error:
                tqdm.write(f"Error processing repo {url}: {error}")
                write_failed_repo(url, owner, repo_name, error)

    except Exception as error:
        print(f"Error while processing repos: {error}")
        raise error


if __name__ == "__main__":
    main()
