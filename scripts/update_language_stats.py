import json
import os
from collections import defaultdict
from html import escape
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

USERNAME = "Langa2007"
API_URL = "https://api.github.com"
README_PATH = "README.md"

LANGUAGES_START = "<!--START_SECTION:languages-->"
LANGUAGES_END = "<!--END_SECTION:languages-->"
BADGES_START = "<!--START_SECTION:language-badges-->"
BADGES_END = "<!--END_SECTION:language-badges-->"

TOKEN = os.environ.get("GH_STATS_TOKEN")

if not TOKEN:
    raise RuntimeError("GH_STATS_TOKEN is missing.")

# GitHub Linguist language names -> Shields.io logo identifiers and colors.
# Languages without a known logo still receive a badge using a neutral color.
LANGUAGE_BADGE_STYLES = {
    "Go": ("go", "00ADD8", "white"),
    "Rust": ("rust", "000000", "white"),
    "Python": ("python", "3776AB", "white"),
    "Java": ("openjdk", "ED8B00", "white"),
    "JavaScript": ("javascript", "F7DF1E", "black"),
    "TypeScript": ("typescript", "3178C6", "white"),
    "C": ("c", "A8B9CC", "black"),
    "C++": ("cplusplus", "00599C", "white"),
    "C#": ("csharp", "239120", "white"),
    "Kotlin": ("kotlin", "7F52FF", "white"),
    "Swift": ("swift", "F05138", "white"),
    "Dart": ("dart", "0175C2", "white"),
    "HTML": ("html5", "E34F26", "white"),
    "CSS": ("css3", "1572B6", "white"),
    "Vue": ("vuedotjs", "4FC08D", "white"),
    "Shell": ("gnubash", "4EAA25", "white"),
    "Dockerfile": ("docker", "2496ED", "white"),
    "CMake": ("cmake", "064F8C", "white"),
    "PowerShell": ("powershell", "5391FE", "white"),
    "Ruby": ("ruby", "CC342D", "white"),
    "PHP": ("php", "777BB4", "white"),
    "SQL": ("postgresql", "4169E1", "white"),
}


def github_get(endpoint):
    request = Request(
        f"{API_URL}{endpoint}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Langa2007-language-stats",
        },
    )

    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub API returned HTTP {error.code} for {endpoint}: {details}"
        ) from error
    except URLError as error:
        raise RuntimeError(
            f"Could not reach GitHub API for {endpoint}: {error}"
        ) from error


def get_repositories():
    repositories = []
    page = 1

    while True:
        data = github_get(
            f"/user/repos?visibility=all&affiliation=owner"
            f"&per_page=100&page={page}&sort=updated"
        )

        if not data:
            break

        # Only repositories whose owner is this account are included.
        owned = [
            repo for repo in data
            if repo.get("owner", {}).get("login", "").lower() == USERNAME.lower()
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
        repo_name = repo["name"]
        encoded_name = quote(repo_name, safe="")

        print(f"Scanning {owner}/{repo_name}...")
        languages = github_get(f"/repos/{owner}/{encoded_name}/languages")

        if not languages:
            print(f"  No language bytes reported for {repo_name}.")
            continue

        for language, byte_count in languages.items():
            totals[language] += byte_count
            print(f"  {language}: {byte_count:,} bytes")

    return totals


def generate_markdown(totals):
    total_bytes = sum(totals.values())

    if total_bytes == 0:
        return "No language data found yet."

    sorted_languages = sorted(
        totals.items(), key=lambda item: item[1], reverse=True
    )

    lines = [
        "| Language | Percentage | Distribution |",
        "|:---|---:|:---|",
    ]
    bar_width = 30

    for language, byte_count in sorted_languages:
        percentage = byte_count / total_bytes * 100
        filled = round(percentage / 100 * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        lines.append(
            f"| **{language}** | {percentage:.2f}% | `{bar}` |"
        )

    return "\n".join(lines)


def generate_language_badges(totals):
    if not totals:
        return '<p align="center">No language data available yet.</p>'

    badges = []
    sorted_languages = sorted(
        totals.items(), key=lambda item: item[1], reverse=True
    )

    for language, byte_count in sorted_languages:
        if byte_count <= 0:
            continue

        logo, color, logo_color = LANGUAGE_BADGE_STYLES.get(
            language, (None, "555555", "white")
        )
        label = quote(language, safe="")
        badge_url = (
            f"https://img.shields.io/badge/{label}-{color}"
            f"?style=for-the-badge"
        )
        if logo:
            badge_url += f"&logo={quote(logo, safe='')}&logoColor={logo_color}"

        badges.append(
            f'  <img src="{badge_url}" alt="{escape(language)}" />'
        )

    return '<p align="center">\n' + "\n".join(badges) + "\n</p>"


def replace_section(readme, start_marker, end_marker, content):
    if readme.count(start_marker) != 1:
        raise RuntimeError(f"Expected exactly one marker: {start_marker}")
    if readme.count(end_marker) != 1:
        raise RuntimeError(f"Expected exactly one marker: {end_marker}")

    start = readme.index(start_marker) + len(start_marker)
    end = readme.index(end_marker)

    if start > end:
        raise RuntimeError(
            f"README markers are incorrectly ordered: {start_marker}"
        )

    return readme[:start] + "\n\n" + content + "\n\n" + readme[end:]


def update_readme(language_content, badge_content):
    with open(README_PATH, "r", encoding="utf-8") as file:
        readme = file.read()

    # Update the percentage table at the bottom and the language badges above.
    readme = replace_section(
        readme, LANGUAGES_START, LANGUAGES_END, language_content
    )
    readme = replace_section(
        readme, BADGES_START, BADGES_END, badge_content
    )

    with open(README_PATH, "w", encoding="utf-8") as file:
        file.write(readme)


def main():
    print(f"Fetching repositories owned by {USERNAME}...")
    repositories = get_repositories()
    print(f"Found {len(repositories)} owned repositories.")

    totals = collect_languages(repositories)
    total_bytes = sum(totals.values())

    print(f"Detected {len(totals)} languages across {total_bytes:,} bytes.")
    print("Aggregated language totals:")
    for language, byte_count in sorted(
        totals.items(), key=lambda item: item[1], reverse=True
    ):
        percentage = byte_count / total_bytes * 100 if total_bytes else 0
        print(f"  {language}: {byte_count:,} bytes ({percentage:.2f}%)")

    language_table = generate_markdown(totals)
    language_badges = generate_language_badges(totals)
    update_readme(language_table, language_badges)

    print("README language badges and percentage table updated successfully.")


if __name__ == "__main__":
    main()
