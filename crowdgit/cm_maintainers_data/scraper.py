import os
import base64
from dotenv import load_dotenv
from crowdgit.cm_maintainers_data.bedrock import invoke_bedrock
from crowdgit.cm_maintainers_data.enums import ScraperError
import json
from tqdm import tqdm
from prettytable import PrettyTable
from crowdgit import LOCAL_DIR
from crowdgit.repo import get_local_repo, REPOS_DIR
from crowdgit.logger import get_logger

logger = get_logger(__name__)

load_dotenv()

# List of common maintainer file names
maintainer_files = [
    "MAINTAINERS",
    "MAINTAINERS.md",
    "MAINTAINER.md",
    "CODEOWNERS.md",
    "CONTRIBUTORS",
    "CONTRIBUTORS.md",
    "docs/MAINTAINERS.md",
    "OWNERS",
    "CODEOWNERS",
    ".github/MAINTAINERS.md",
    ".github/CONTRIBUTORS.md",
]


# Function to check for maintainer files
def find_maintainer_file(owner: str, repo: str):
    remote_url = f"https://github.com/{owner}/{repo}.git"
    local_repo = "./" + get_local_repo(remote_url, REPOS_DIR)

    if not os.path.exists(local_repo):
        print(f"Local repo {local_repo} does not exist")
        return None, None, 0

    logger.info(f"\nChecking for maintainer files in {owner}/{repo}...")

    file_names = os.listdir(local_repo)

    for file in maintainer_files:
        file_path = os.path.join(local_repo, file)
        if os.path.isfile(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return file, base64.b64encode(content.encode()).decode(), 0

    logger.info("\nNo maintainer files found using the known file names.")

    logger.info("\nUsing AI to find maintainer files...")
    file_name, ai_cost = find_maintainer_file_with_ai(file_names, owner, repo)

    if file_name:
        file_path = os.path.join(local_repo, file_name)
        if os.path.isfile(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            logger.info(f"\nMaintainer file found: {file_name}")
            return file_name, base64.b64encode(content.encode()).decode(), ai_cost

    return None, None, ai_cost


def update_stats(file_name, owner, repo):
    stats_file = os.path.join(LOCAL_DIR, "ai-found-file-stats.json")
    if os.path.exists(stats_file):
        with open(stats_file, "r") as f:
            stats = json.load(f)
    else:
        stats = {}

    if file_name not in stats:
        stats[file_name] = []
    repo_identifier = f"{owner}/{repo}"
    if repo_identifier not in stats[file_name]:
        stats[file_name].append(repo_identifier)

    with open(stats_file, "w") as f:
        json.dump(stats, f, indent=2)


def find_maintainer_file_with_ai(file_names, owner, repo):
    instructions = (
        "You are a helpful assistant.",
        "You are given a list of file names from a GitHub repository.",
        "Your task is to determine if any of these files are a maintainer file.",
        "If a maintainer file is found, return the file name as {file_name: <file_name>}",
        "If no maintainer file is found, return {error: 'not_found'}.",
        "If the list of files is empty, return {error: 'not_found'}.",
        "The file is never CONTRIBUTING.md"
        "As an example, this is the kind of files you are looking for:",
        "{EXAMPLE_FILES}" "Here is the list of file names and their contents:",
        "{FILE_NAMES}",
    )
    replacements = {"EXAMPLE_FILES": maintainer_files, "FILE_NAMES": file_names}
    result = invoke_bedrock(instructions, replacements=replacements)

    if "file_name" in result["output"]:
        file_name = result["output"]["file_name"]
        update_stats(file_name, owner, repo)
        return file_name, result["cost"]
    else:
        return None, result["cost"]


def analyze_file_content(content):
    instructions = (
        "Analyze the following content from a GitHub repository file and extract maintainer information.",
        "The information should include GitHub usernames, names, and their titles or roles if available.",
        "If GitHub usernames are not explicitly mentioned, try to infer them from the names or any links provided.",
        "Present the information as a list of JSON objects.",
        "Each JSON object should have 'github_username', 'name', and 'title' fields.",
        "The title field should be a string that describes the maintainer's role or title,",
        "it should have a maximum of two words,",
        "and it should not contain words that do not add information, like 'repository', 'active', or 'project'.",
        "The title has to be related to ownershop, maintainership, review, governance, or similar. It cannot be Software Engineer, for example.",
        "If a GitHub username can't be determined, use 'unknown' as the value.",
        "If you canot find any maintainer information, return {error: 'not_found'}",
        "If the content is not talking about a person, rather a group or team (for example config.yaml @LFDT-Hiero/lf-staff), return {error: 'not_found'}",
        "Here is the content to analyze:",
        "{CONTENT}."
        "Present the information as a list of JSON object in the following format:{info: <list of maintainer info>}, or {error: 'not_found'}",
        "The output should be a valid JSON array, directly parseable by Python.",
    )

    if len(content) > 5000:
        chunks = []
        while content:
            split_index = content.rfind("\n", 0, 5000)
            if split_index == -1:
                split_index = 5000
            chunks.append(content[:split_index])
            content = content[split_index:].lstrip()

        aggregated_info = {"output": {"info": []}, "cost": 0}
        for i, chunk in enumerate(chunks, 1):
            chunk_info = invoke_bedrock(instructions, replacements={"CONTENT": chunk})
            if "info" in chunk_info["output"]:
                aggregated_info["output"]["info"].extend(chunk_info["output"]["info"])
            aggregated_info["cost"] += chunk_info["cost"]
        maintainer_info = aggregated_info
    else:
        maintainer_info = invoke_bedrock(instructions, replacements={"CONTENT": content})

    try:
        if "info" in maintainer_info["output"]:
            return maintainer_info
        elif maintainer_info["output"].get("error", None) == "not_found":
            return {"output": {"info": None}, "cost": maintainer_info["cost"]}
        else:
            raise ValueError(
                "Expected a list of maintainer info or an error message, got: "
                + str(maintainer_info)
            )
    except ValueError:
        raise ValueError("Failed to analyze the maintainer file content.")


# Function to display maintainer info in a table
def display_maintainer_info(info):
    table = PrettyTable()
    table.field_names = ["GitHub Username", "Name", "Title/Role"]
    table.align = "l"
    for item in info:
        username = item.get("github_username", "unknown")
        name = item.get("name", "N/A")
        role = item.get("title", item.get("role", "N/A"))
        table.add_row([username if username != "unknown" else "N/A", name, role])
    logger.info("\n%s", table)


# Main logic
def scrape(owner: str, repo: str):
    total_cost = 0

    file_name, file_content, ai_cost = find_maintainer_file(owner, repo)
    total_cost += ai_cost
    if not file_name or not file_content:
        return {
            "failed": True,
            "reason": ScraperError.NO_MAINTAINER_FILE,
            "total_cost": total_cost,
        }

    decoded_content = base64.b64decode(file_content).decode("utf-8")

    logger.info(f"\nAnalyzing maintainer file: {file_name}")
    result = analyze_file_content(decoded_content)
    maintainer_info = result["output"].get("info", None)
    total_cost += result["cost"]

    if not maintainer_info:
        logger.error("Failed to analyze the maintainer file content.")
        return {"failed": True, "reason": ScraperError.ANALYSIS_FAILED, "total_cost": total_cost}

    return {
        "maintainer_file": file_name,
        "maintainer_info": maintainer_info,
        "total_cost": total_cost,
    }


if __name__ == "__main__":
    owner = "serverlessworkflow"
    repo = "synapse"

    result = scrape(owner, repo)
    if "maintainer_info" in result:
        display_maintainer_info(result["maintainer_info"])
    elif "failed" in result:
        logger.error(f"Failed to scrape {owner}/{repo}: {result['reason']}")
    if "total_cost" in result:
        logger.info(f"Total cost: ${result['total_cost']:.6f}")
