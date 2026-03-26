pipeline {
    agent { label 'zos-cust-test' }

    triggers {
        cron('0 9 30 3 *')
        pollSCM('H/10 * * * *')     
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Detect Trigger Type') {
            steps {
                script {
                    def causes = currentBuild.getBuildCauses()
                    echo "Build causes: ${causes}"

                    env.IS_SCM_TRIGGER = causes.toString().contains('SCMTrigger') ? 'true' : 'false'
                }
            }
        }

        stage('Create Virtual Environment') {
            when {
                expression { env.IS_SCM_TRIGGER != 'true' }
            }
            steps {
                sh '''
                    python3 -m venv venv
                    . venv/bin/activate
                    pip install --upgrade pip
                '''
            }
        }

        stage('Install Dependencies and Artifactory Check') {
            when {
                expression { env.IS_SCM_TRIGGER != 'true' }
            }
            steps {
                withCredentials([
                    string(credentialsId: 'artifactory-access-token', variable: 'ACCESS_TOKEN')
                ]) {
                    sh '''
                        # Activate virtual environment
                        . venv/bin/activate
                        
                        echo "Installing dependencies from requirements.txt"
                        pip install -r requirements.txt
                        
                        # Check if ibm_saturn_client is already installed
                        if pip show ibm_saturn_client > /dev/null 2>&1; then
                            echo "ibm_saturn_client is already installed in the virtual environment"
                        else
                            echo "ibm_saturn_client not found, proceeding with installation from Artifactory"
                            
                            echo "Checking Artifactory access"
                            curl -I -u "Shivaraman.S@ibm.com:${ACCESS_TOKEN}" \
                            "https://na.artifactory.swg-devops.com/artifactory/api/pypi/sys-stg-team-pypi-local/simple/"
                            
                            echo "Checking ibm-saturn-client package versions"
                            python -m pip index versions ibm-saturn-client -i \
                            https://na.artifactory.swg-devops.com/artifactory/api/pypi/sys-stg-team-pypi-local/simple
                            
                            echo "Installing ibm_saturn_client from Artifactory"
                            pip install ibm_saturn_client --extra-index-url='https://na.artifactory.swg-devops.com/artifactory/api/pypi/sys-stg-team-pypi-local/simple'
                        fi
                    '''
                }
            }
        }

        stage('Run Script with Credentials') {
            when {
                expression { env.IS_SCM_TRIGGER != 'true' }
            }
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'ecobuild-trial-1',
                        usernameVariable: 'USER',
                        passwordVariable: 'PASS'
                    ),
                    // string(credentialsId: 'ecobuild_slack_key', variable: 'SLACK_KEY')
                ]) {
                    sh '''
                        python3 fetch_build_details.py
                    '''
                }
            }
        }

        stage('Cron Update Commit') {
            when {
                expression { env.IS_SCM_TRIGGER != 'true' }
            }
            steps {
                sh '''
                    echo "Preparing to push Jenkinsfile to Git"

                    git config user.name "Meghana-Anand"
                    git config user.email "Meghana-Anand@ibm.com"

                    git add Jenkinsfile4 || true

                    if ! git diff --cached --quiet; then
                        git commit -m "Auto update Jenkins cron"
                        git push origin HEAD:main
                    else
                        echo "No changes to commit"
                    fi
                '''
            }
        }

        stage('SCM Reload Run (No-op)') {
            when {
                expression { env.IS_SCM_TRIGGER == 'true' }
            }
            steps {
                echo "SCM-triggered build -> only reloading Jenkinsfile (no execution)"
            }
        }
    }

    post {
        always {
            echo 'Pipeline finished. Check console output for script results.'
        }
    }
}
