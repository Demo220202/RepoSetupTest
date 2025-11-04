pipeline {
    agent any

    environment {
        SONAR_API_TOKEN = credentials('sonar-api-token')
//         GITHUB_TOKEN    = credentials('github-token')
        PATH = "/opt/homebrew/bin:/usr/local/bin:${env.PATH}"
    }

    stages {

        stage('Check gh') {
            steps {
                sh '''
                    echo "PATH is: $PATH"
                    which gh || echo "gh not found"
                    gh --version || echo "gh command failed"
                '''
            }
        }

        stage('Install GitHub CLI if missing') {
            steps {
                sh '''
                    if ! command -v gh >/dev/null 2>&1; then
                        echo "Installing GitHub CLI..."
                        if [[ "$OSTYPE" == "darwin"* ]]; then
                            # Detect Homebrew path
                            if [ -x "/opt/homebrew/bin/brew" ]; then
                                /opt/homebrew/bin/brew install gh
                            elif [ -x "/usr/local/bin/brew" ]; then
                                /usr/local/bin/brew install gh
                            else
                                echo "Homebrew not found. Please install Homebrew first."
                                exit 1
                            fi
                        else
                            curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | \
                                sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
                            sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg
                            echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | \
                                sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
                            sudo apt update
                            sudo apt install -y gh
                        fi
                    else
                        echo "GitHub CLI already installed at $(which gh)"
                    fi
                '''
            }
        }

        stage('Step 1: Repo Name & Create Sonar Project') {
            steps {
                def userGitHubToken = input(
                        id: 'firstInput',
                        message: 'Paste the user GitHub token',
                        parameters: [
                            password(name: 'GITHUB_TOKEN', description: 'Enter user GitHub Token')
                        ]
                    )

                    env.GITHUB_TOKEN = userGitHubToken.toString()

                sh """
                    python3 -m venv venvrepo
                    . venvrepo/bin/activate
                    pip install -r requirements.txt
                    python githubRepoSetup.py --repo-name "$REPO_NAME" --phase create_project
                """
            }
        }

        stage('Step 2: Paste Sonar Project Token') {
            steps {
                script {
                    def sonarTokenInput = input(
                        id: 'secondInput',
                        message: 'Paste the SonarCloud project token',
                        parameters: [
                            password(name: 'SONAR_PROJECT_TOKEN', description: 'Enter Sonar project token from SonarCloud')
                        ]
                    )

                    env.SONAR_PROJECT_TOKEN = sonarTokenInput.toString()
                }

                sh """
                    . venvrepo/bin/activate
                    python githubRepoSetup.py \
                        --repo-name "$REPO_NAME" \
                        --phase finalize
                """
            }
        }

        stage('Step 3: Approval for Branch Protection') {
            steps {
                script {
                    // Only waits for human approval
                    def approval = input(
                        id: 'approvalInput',
                        message: 'Do you want to proceed with branch protection setup?',
                        parameters: [
                            choice(name: 'PROCEED', choices: ['Yes', 'No'], description: 'Select Yes to continue')
                        ]
                    )

                    if (approval == 'No') {
                        error "Branch protection setup aborted by user."
                    }
                }

                sh """
                    . venvrepo/bin/activate
                    python githubRepoSetup.py \
                        --repo-name "$REPO_NAME" \
                        --phase finalize_branch_protection
                """
            }
        }

    }
}
