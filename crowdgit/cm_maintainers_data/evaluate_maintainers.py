from urllib.parse import urlparse
from scraper import scrape
from cm_database import query
from tqdm import tqdm
import csv
import os


def get_repos_and_scrape():
    try:
        # Query to get the first 100 repos
        repos = query('SELECT url FROM "githubRepos" ORDER BY RANDOM() LIMIT 100')

        # Check if the CSV file already exists
        file_exists = os.path.isfile("maintainer_results.csv")

        # Open CSV file for appending
        with open("maintainer_results.csv", "a", newline="", encoding="utf-8") as csvfile:
            fieldnames = ["repo_url", "maintainer_file", "maintainer_data", "error"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            # Write header only if the file is newly created
            if not file_exists:
                writer.writeheader()

            for repo in tqdm(repos, desc="Processing repos", unit="repo"):
                url = repo["url"]
                parsed_url = urlparse(url)
                path_parts = parsed_url.path.strip("/").split("/")

                if len(path_parts) >= 2:
                    owner, repo_name = path_parts[:2]
                    tqdm.write(f"\nProcessing repo: github.com/{owner}/{repo_name}")
                    result = scrape(owner, repo_name)

                    # Prepare row data
                    row = {
                        "repo_url": url,
                        "maintainer_file": "",
                        "maintainer_data": "",
                        "error": "",
                    }

                    if (
                        isinstance(result, dict)
                        and "maintainer_file" in result
                        and "maintainer_info" in result
                    ):
                        row["maintainer_file"] = result["maintainer_file"]
                        row["maintainer_data"] = str(result["maintainer_info"])
                        tqdm.write(f"Successfully scraped maintainers for {owner}/{repo_name}")
                    else:
                        row["error"] = result["reason"].value
                        tqdm.write(
                            f"Failed to scrape maintainers for {owner}/{repo_name}: {row['error']}"
                        )

                    # Write row to CSV
                    writer.writerow(row)
                else:
                    tqdm.write(f"Invalid GitHub URL format: {url}")
                    writer.writerow({"repo_url": url, "error": "Invalid GitHub URL format"})

    except Exception as error:
        print(f"Error while processing repos: {error}")


if __name__ == "__main__":
    get_repos_and_scrape()
