from datetime import datetime

import github
import requests
from environs import Env
from github import Github

env = Env()
env.read_env()  # Read .env into os.environ

BOT_NAME = "nano-continuous-testing-bot"
LABEL_NAME = "continuous-testing"

APP_ID = env("APP_ID")
PRIVATE_KEY = env("PRIVATE_KEY")


def get_test_results(commit):
    url = "https://raw.githubusercontent.com/gr0vity-dev/nano-node-builder/main/continuous_testing/dcf214c9580ee9212f6dd72678056c24b08f4298.json"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        return None


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


def format_comment_body(results):
    # Use emojis for visual feedback
    status_emoji = {"PASS": "✅", "FAIL": "❌", "ERROR": "⚠️"}

    # Start with a bold title
    body = "### 🧪 Automated Test Results:\n\n"

    # Overall status with color emphasis
    overall_status = results["overall_status"]
    overall_status_str = f"**Overall Status:** {status_emoji.get(overall_status, '❓')} {overall_status}"
    if overall_status == "PASS":
        overall_status_str = f"<span style='color:green;'>{overall_status_str}</span>"
    elif overall_status in ["FAIL", "ERROR"]:
        overall_status_str = f"<span style='color:red;'>{overall_status_str}</span>"

    body += overall_status_str + "\n\n"

    # Table headers
    body += "| Testcase | Status | Time |\n"
    body += "|----------|--------|------|\n"
    for testcase in results["testcases"]:
        # Parse the start and end times
        start_time = datetime.fromisoformat(testcase["started_at"].replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(testcase["completed_at"].replace("Z", "+00:00"))
        # Calculate the duration
        duration = end_time - start_time
        # Convert duration to a formatted string (e.g., "1m 33s")
        duration_str = f"{duration.seconds//60}m {duration.seconds%60}s"

        # Emoji and color for status
        test_status = testcase["status"]
        test_status_emoji = status_emoji.get(test_status, "❓")
        if test_status == "PASS":
            test_status_str = f"<span style='color:green;'>{test_status_emoji} {test_status}</span>"
        elif test_status in ["FAIL", "ERROR"]:
            test_status_str = f"<span style='color:red;'>{test_status_emoji} {test_status}</span>"
        else:
            test_status_str = f"{test_status_emoji} {test_status}"

        body += f"| {testcase['testcase']} | {test_status_str} | {duration_str} |\n"
    return body


def update_or_create_comment(g: Github, pr: github.PullRequest.PullRequest, body: str):
    comments = pr.get_issue_comments()
    for comment in comments:
        if comment.user.login == f"{BOT_NAME}[bot]":
            print("Updating existing comment")
            comment.edit(body)
            return

    print("Creating new comment")
    pr.create_issue_comment(body)


def update_pr(g: Github, pr: github.PullRequest.PullRequest, results: dict):
    comment_body = format_comment_body(results)
    update_or_create_comment(g, pr, comment_body)
    pass


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
    commit = pr.get_commits().reversed[0]
    print("Latest commit:", commit.sha)

    results = get_test_results(commit)
    if results:
        print("Found test results, updating PR...")
        update_pr(g, pr, results)
    else:
        print("Test results not found")


def process_repo(g: Github, repo: github.Repository.Repository):
    pull_requests = repo.get_pulls(state="open")
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
    main()

    pass
