pipeline {
    agent any

    environment {
        SONAR_API_TOKEN = credentials('sonar-api-token')
        GITHUB_TOKEN    = credentials('github-token')
    }

    stages {
        stage('Step 1: Repo Name & Create Sonar Project') {
            steps {
//                 script {
//                     def userInput = input(
//                         id: 'firstInput',
//                         message: 'Provide repo details',
//                         parameters: [
//                             string(name: 'REPO_NAME', description: 'Enter the new GitHub repository name')
//                         ]
//                     )
//                     env.REPO_NAME = userInput['REPO_NAME']
//                 }

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
                    // Ask user for Sonar Project Token securely
                    def userInput = input(
                        id: 'secondInput',
                        message: 'Paste the SonarCloud project token',
                        parameters: [
                            password(name: 'SONAR_PROJECT_TOKEN', description: 'Enter Sonar project token from SonarCloud')
                        ]
                    )
                    env.SONAR_PROJECT_TOKEN = userInput['SONAR_PROJECT_TOKEN']
                }

                sh """
                    . venvrepo/bin/activate
                    python githubRepoSetup.py \
                        --repo-name "$REPO_NAME" \
                        --sonar-token "$SONAR_PROJECT_TOKEN" \
                        --phase finalize
                """
            }
        }
    }
}
