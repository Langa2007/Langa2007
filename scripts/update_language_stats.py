
import json
import os
from collections import defaultdict
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

USERNAME = "Langa2007"
API_URL = "https://api.github.com"

START_MARKER = "<!--START_SECTION:languages-->"
END_MARKER = "<!--END_SECTION:languages-->"

TOKEN = os.environ.get("GH_STATS_TOKEN")

if not TOKEN:
    raise RuntimeError("GH_STATS_TOKEN is missing.")


def github_get(endpoint):
    request = Request(
        f"{API_URL}{endpoint}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    except (HTTPError, URLError) as error:
        raise RuntimeError(
            f"GitHub API request failed: {endpoint}: {error}"
        ) from error


def get_repositories():
    repositories = []
    page = 1

    while True:
        data = github_get(
            f"/user/repos?visibility=all"
            f"&affiliation=owner&per_page=100&page={page}"
        )

        if not data:
            break

        # Only repositories owned by this account.
        owned = [
            repo for repo in data
            if repo["owner"]["login"].lower() == USERNAME.lower()
        ]

        repositories.extend(owned)

        if len(data) < 100:
            break

        page += 1

    return repositories


def collect_languages(repositories):
    totals = defaultdict(int)

    for repo in repositories:
        owner = repo["owner"]["login"]
        name = quote(repo["name"], safe="")

        print(f"Scanning {owner}/{repo['name']}")

        languages = github_get(
            f"/repos/{owner}/{name}/languages"
        )

        for language, byte_count in languages.items():
            totals[language] += byte_count

    return totals


def generate_markdown(totals):
    total_bytes = sum(totals.values())

    if not total_bytes:
        return "No language data found yet."

    sorted_languages = sorted(
        totals.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    lines = [
        "| Language | Percentage | Distribution |",
        "|:---|---:|:---|",
    ]

    bar_width = 30

    for language, byte_count in sorted_languages:
        percentage = (byte_count / total_bytes) * 100

        filled = round(percentage / 100 * bar_width)

        bar = (
            "█" * filled
            + "░" * (bar_width - filled)
        )

        lines.append(
            f"| **{language}** "
            f"| {percentage:.2f}% "
            f"| `{bar}` |"
        )

    return "\n".join(lines)


def update_readme(content):
    readme_path = "README.md"

    with open(readme_path, "r", encoding="utf-8") as file:
        readme = file.read()

    if readme.count(START_MARKER) != 1:
        raise RuntimeError("Invalid or missing start marker.")

    if readme.count(END_MARKER) != 1:
        raise RuntimeError("Invalid or missing end marker.")

    start = readme.index(START_MARKER) + len(START_MARKER)
    end = readme.index(END_MARKER)

    if start > end:
        raise RuntimeError("README markers are incorrectly ordered.")

    updated_readme = (
        readme[:start]
        + "\n\n"
        + content
        + "\n\n"
        + readme[end:]
    )

    with open(readme_path, "w", encoding="utf-8") as file:
        file.write(updated_readme)


def main():
    print("Fetching owned repositories...")

    repositories = get_repositories()

    print(f"Found {len(repositories)} owned repositories.")

    totals = collect_languages(repositories)

    print(f"Detected {len(totals)} languages.")

    markdown = generate_markdown(totals)

    update_readme(markdown)

    print("README language statistics updated successfully.")


if __name__ == "__main__":
    main()
