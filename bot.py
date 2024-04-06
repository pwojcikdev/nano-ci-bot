import argparse
import time
from datetime import datetime

import github
import requests
from environs import Env
from github import Github

env = Env()
env.read_env()  # Read .env into os.environ

BOT_NAME = "nano-continuous-testing-bot"
LABEL_NAME = "continuous-testing"
MAX_PRS = 40  # Maximum number of PRs to scan

APP_ID = env("APP_ID")
PRIVATE_KEY = env("PRIVATE_KEY")

print("Starting the bot...")
print("APP_ID:", APP_ID)
print("PRIVATE_KEY:", PRIVATE_KEY)


def get_test_results(commit):
    url = f"https://raw.githubusercontent.com/gr0vity-dev/nano-node-builder/main/continuous_testing/{commit}.json"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json(), url
    else:
        return None, None


# Example test results JSON:
# {
#   "hash": "dcf214c9580ee9212f6dd72678056c24b08f4298",
#   "run_id": "8575942365",
#   "type": "pull_request",
#   "pull_request": "4536",
#   "started_at": "2024-04-05T21:31:17Z",
#   "completed_at": "2024-04-05T21:35:28Z",
#   "testcases": [
#     {
#       "testcase": "5n4pr_conf_10k_bintree",
#       "status": "PASS",
#       "started_at": "2024-04-05T21:32:25Z",
#       "completed_at": "2024-04-05T21:33:58Z"
#     },
#     {
#       "testcase": "5n4pr_conf_send_independant",
#       "status": "PASS",
#       "started_at": "2024-04-05T21:32:19Z",
#       "completed_at": "2024-04-05T21:34:06Z"
#     },
#     {
#       "testcase": "5n4pr_conf_change_dependant",
#       "status": "PASS",
#       "started_at": "2024-04-05T21:32:22Z",
#       "completed_at": "2024-04-05T21:34:33Z"
#     },
#     {
#       "testcase": "5n4pr_conf_change_independant",
#       "status": "PASS",
#       "started_at": "2024-04-05T21:32:38Z",
#       "completed_at": "2024-04-05T21:34:57Z"
#     },
#     {
#       "testcase": "5n4pr_conf_send_dependant",
#       "status": "PASS",
#       "started_at": "2024-04-05T21:32:26Z",
#       "completed_at": "2024-04-05T21:35:08Z"
#     }
#   ],
#   "overall_status": "PASS"
# }


def calculate_duration(started_at: str, completed_at: str) -> str:
    start_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    end_time = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
    duration = end_time - start_time
    duration_str = f"{duration.seconds // 60}m {duration.seconds % 60}s"
    return duration_str


FOOTER = "\n---\n\n_Test results provided by [nano-node-builder](https://github.com/gr0vity-dev/nano-node-builder)_\n"


def format_comment_body(results: dict, details_url: str) -> str:
    status_emoji = {"PASS": "✅", "FAIL": "❌", "ERROR": "⚠️"}

    # Start with a title and overall status
    body = f"#### 🧪 Network simulation test results for commit: `{results['hash']}`\n"
    body += f"Overall status: {status_emoji.get(results['overall_status'], '❓')} **{results['overall_status']}** ([details]({details_url}))\n\n"

    body += f"---\n\n"

    # Testcases table
    body += "| Testcase | Status | Duration | Log |\n"
    body += "|----------|--------|----------|-----|\n"
    for testcase in results["testcases"]:
        duration_str = calculate_duration(testcase["started_at"], testcase["completed_at"])
        status_str = f"{status_emoji.get(testcase['status'], '❓')} **{testcase['status']}**"
        log_file_url = details_url.replace(".json", f"_{testcase['testcase']}.txt")
        body += f"| `{testcase['testcase']}` | {status_str} | {duration_str} | [Log]({log_file_url}) |\n"

    body += FOOTER

    return body


def in_progress_comment_body(commit_hash: str) -> str:
    status_emoji = "⏳"

    # Formatting the comment body
    body = f"#### 🧪 Network simulation test results for commit: `{commit_hash}`\n"
    body += f"Overall status: {status_emoji} **TESTING**\n\n"

    body += FOOTER

    return body


def update_or_create_comment(g: Github, pr: github.PullRequest.PullRequest, body: str):
    comments = pr.get_issue_comments()
    for comment in comments:
        if comment.user.login == f"{BOT_NAME}[bot]":
            if comment.body != body:
                print("Updating existing comment")
                comment.edit(body)
            else:
                print("Comment already up-to-date")

            return

    print("Creating new comment")
    pr.create_issue_comment(body)


def check_label(pr: github.PullRequest.PullRequest, label_name: str):
    """Check if a PR has a specific label."""
    labels = pr.get_labels()
    for label in labels:
        if label.name == label_name:
            return True
    return False


def process_pr(g: Github, repo: github.Repository.Repository, pr: github.PullRequest.PullRequest):
    print("Processing PR:", pr.number)

    # Check if the PR has proper label
    if not check_label(pr, LABEL_NAME):
        print("Skipping PR as it doesn't have the required label:", LABEL_NAME)
        return

    # Get the latest commit in the PR
    commit = pr.get_commits().reversed[0].sha
    print("Latest commit:", commit)

    results, details_url = get_test_results(commit)
    if results:
        print("Found test results, updating PR...")

        comment_body = format_comment_body(results, details_url)
        update_or_create_comment(g, pr, comment_body)
    else:
        print("Test results not found")

        comment_body = in_progress_comment_body(commit)
        update_or_create_comment(g, pr, comment_body)


def process_repo(g: Github, repo: github.Repository.Repository):
    pull_requests = repo.get_pulls(state="open")[:MAX_PRS]
    for pr in pull_requests:
        print("Found PR:", pr.number)
        process_pr(g, repo, pr)


def main():
    auth = github.Auth.AppAuth(APP_ID, PRIVATE_KEY)

    gi = github.GithubIntegration(auth=auth)

    for installation in gi.get_installations():
        print("Found installation ID:", installation.id)

        g = installation.get_github_for_installation()

        # Now, iterate over all repositories accessible to this installation
        for repo in installation.get_repos():
            print("Found repository:", repo.full_name)
            process_repo(g, repo)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--interval", type=int, default=60, help="Interval between runs in seconds. Default is 60 seconds."
    )
    args = parser.parse_args()

    while True:
        main()

        print(f"Waiting for {args.interval} seconds before the next run...")
        time.sleep(args.interval)

    pass
