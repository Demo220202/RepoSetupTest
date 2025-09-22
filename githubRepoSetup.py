import os
import subprocess
import shutil
import requests
from git import Repo
from dotenv import load_dotenv
import json

load_dotenv()

# ======== CONFIG ========
GITHUB_ORG = "Zenarate"
SONAR_ORG = "zenarate"
SONAR_HOST = "https://sonarcloud.io"
SONAR_API_TOKEN = os.environ.get("SONAR_API_TOKEN")  # Admin token to use SonarQube API
# SONAR_PROJECT_TOKEN = os.environ.get("SONAR_PROJECT_TOKEN")  # To set in GitHub Secrets
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")  # Required for GitHub CLI

# print(SONAR_API_TOKEN)
# print(GITHUB_TOKEN)

TEMPLATE_PATH = "template_github"  # 👈 Update this to your templates folder
LOCAL_CLONE_PATH = "temp_repo"  # Temporary working directory
# ========================


def create_sonar_project(repo_name):
    print(f"🔧 Creating project in SonarQube: {repo_name}")
    url = f"{SONAR_HOST}/api/projects/create"
    project_key = f"Zenarate_{repo_name}"
    params = {
        "name": repo_name,
        "project": project_key,
        "organization": SONAR_ORG
    }
    resp = requests.post(url, params=params, auth=(SONAR_API_TOKEN, ""))
    if resp.status_code != 200:
        raise Exception(f"❌ SonarQube project creation failed: {resp.text}")
    print("✅ SonarQube project created successfully")



def get_sonar_project_key(sonar_host, sonar_token, repo_name):
    url = f"{sonar_host}/api/projects/search?projects={repo_name}&organization={SONAR_ORG}"
    response = requests.get(url, auth=(sonar_token, ""))

    if response.status_code == 200:
        data = response.json()
        if data.get("components"):
            return data["components"][0]["key"]
        else:
            print(f"⚠️ No SonarCloud project found for repo: {repo_name}")
            return None
    else:
        print(f"❌ Failed to fetch SonarCloud project: {response.status_code} - {response.text}")
        return None



def set_github_secret(repo_name, secret_name, secret_value):
    print(f"🔐 Setting GitHub secret: {secret_name}")
    subprocess.run([
        "gh", "secret", "set", secret_name,
        "--repo", f"{GITHUB_ORG}/{repo_name}",
        "--body", secret_value
    ], check=True)


def clone_and_prepare_repo(repo_name):
    repo_url = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_ORG}/{repo_name}.git"
    repo_path = os.path.join(LOCAL_CLONE_PATH, repo_name)
    print(f"📥 Cloning repo to: {repo_path}")

    if os.path.exists(repo_path):
        shutil.rmtree(repo_path)
    Repo.clone_from(repo_url, repo_path)

    repo = Repo(repo_path)
    repo.git.checkout('-b', 'dev')

    return repo, repo_path


def copy_templates_and_customize(repo_path, repo_name):
    print("🧩 Copying and customizing template files...")
    workflow_dest = os.path.join(repo_path, ".github", "workflows")
    os.makedirs(workflow_dest, exist_ok=True)

    for filename in ["main.yml", "tagging.yml", "build.yml"]:
        shutil.copy(os.path.join(TEMPLATE_PATH, filename), workflow_dest)

    sonar_file_src = os.path.join(TEMPLATE_PATH, "sonar-project.properties")
    sonar_file_dest = os.path.join(repo_path, "sonar-project.properties")

    sonar_project_key = get_sonar_project_key(SONAR_HOST, SONAR_API_TOKEN, repo_name)
    print(sonar_project_key)

    if sonar_project_key is None:
        sonar_project_key = repo_name  # fallback to repo name

    with open(sonar_file_src, "r") as f:
        content = f.read().replace("sonar.projectKey=", f"sonar.projectKey={sonar_project_key}")

    with open(sonar_file_dest, "w") as f:
        f.write(content)


def commit_and_push(repo):
    print("🚀 Committing and pushing changes...")
    repo.git.add(A=True)
    repo.index.commit("Add SonarQube config and workflows")
    origin = repo.remote(name='origin')
    origin.push(refspec='dev')


def create_pull_request(repo_name, base_branch, head_branch):
    print("🔄 Creating pull request...")
    subprocess.run([
        "gh", "pr", "create",
        "--repo", f"{GITHUB_ORG}/{repo_name}",
        "--title", f"SonarQube Integration on {base_branch}",
        "--body", "Adding SonarQube config and workflows",
        "--base", base_branch,
        "--head", head_branch
    ], check=True)


def set_branch_protection(repo_name, branch):
    print(f"🛡️ Setting branch protection for: {branch}")
    subprocess.run([
        "gh", "api", "-X", "PUT",
        f"/repos/{GITHUB_ORG}/{repo_name}/branches/{branch}/protection",
        "-f", "enforce_admins=true"
    ], check=True)


def create_branch_protection(repo_name, BRANCH_PATTERN, TEAM_SLUGS):

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    url = f"https://api.github.com/repos/{GITHUB_ORG}/{repo_name}/branches/{BRANCH_PATTERN}/protection"

    data = {
        "required_status_checks": None,
        "enforce_admins": True,
        "required_pull_request_reviews": {
            "dismiss_stale_reviews": False,
            "require_code_owner_reviews": False,
            "required_approving_review_count": 1,
        },
        "restrictions": {
            "users": [],
            "teams": TEAM_SLUGS,
            "apps": []
        },
        "allow_force_pushes": False,
        "allow_deletions": False,
        "required_linear_history": False,
        "block_creations": True,
        "require_conversation_resolution": True
    }

    response = requests.put(url, headers=headers, data=json.dumps(data))
    print("Status Code:", response.status_code)
    print("Response:", response.json())


def get_team_id(org, team_slug):
    url = f"https://api.github.com/orgs/{org}/teams/{team_slug}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()["id"]
    else:
        print(f"Error fetching team ID for {team_slug}: {response.status_code} - {response.text}")
        return None


def main():
    repo_name = input("Enter the new repo name: ").strip()
    #
    if not SONAR_API_TOKEN or not GITHUB_TOKEN:
        raise EnvironmentError("Please ensure SONAR_API_TOKEN and GITHUB_TOKEN are exported as environment variables.")

    # repo_name = "test_8Jan24"
    # Step 1: Create project in SonarCloud
    create_sonar_project(repo_name) # Tick mark

    # Step 2: Pause - Get SONAR_TOKEN from user
    print("\n🔗 Now go to SonarCloud > Analyze New Project > Select Repo > GitHub Actions.")
    print("   During the setup, a SONAR_TOKEN will be generated — copy it.")
    sonar_project_token = input("🔑 Paste the generated SONAR_TOKEN here: ").strip()
    # #
    # # # Step 3: Set secret in GitHub
    set_github_secret(repo_name, "SONAR_TOKEN", sonar_project_token) # ticket mark with update
    #
    # # Continue rest of the flow
    repo, repo_path = clone_and_prepare_repo(repo_name)
    print("Repo - ", repo, "Repo Path - ", repo_path)


    project_key_for_repo = f"Zenarate_{repo_name}" # Tick mark
    copy_templates_and_customize(repo_path, project_key_for_repo) # Tick mark

    repo = Repo(repo_path) # Tick Mark
    commit_and_push(repo) # Tick Mark
    create_pull_request(repo_name, "qa", "dev") # Tick mark
    # create_pull_request(repo_name, "main", "qa")
    #
    # create_branch_protection(repo_name, "qa", ["devops", "leads"])

    # To be added
    # create_branch_protection(repo_name, "hotfixes", ["devops", "leads"])
    # create_branch_protection(repo_name, "beta", ["devops"])
    # create_branch_protection(repo_name, "master", ["devops"])

    #
    print("\n🎉 Setup complete! Review and merge the PR to activate SonarQube analysis.")



if __name__ == "__main__":
    main()
