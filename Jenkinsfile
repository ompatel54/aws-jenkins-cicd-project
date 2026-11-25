pipeline {

    agent any

    environment {
        AWS_REGION     = 'ap-south-1'
        ECR_REPOSITORY = 'cicd-demo'
        APP_HOST       = '172.31.14.218'
        APP_CONTAINER  = 'cicd-demo'
    }

    stages {

        // ==========================================
        // STAGE 1: GET SOURCE CODE FROM GITHUB
        // ==========================================
        stage('Checkout Code') {
            steps {
                checkout scm
            }
        }

        // ==========================================
        // STAGE 2: CHECK REQUIRED TOOLS
        // ==========================================
        stage('Check Tools') {
            steps {
                sh '''
                    set -e
                    echo "Checking installed tools..."
                    git --version
                    docker --version
                    aws --version
                '''
            }
        }

        // ==========================================
        // STAGE 3: BUILD DOCKER IMAGE
        // ==========================================
        stage('Build Docker Image') {
            steps {
                sh '''
                    set -e
                    echo "Building Docker image..."
                    docker build -t cicd-demo:${BUILD_NUMBER} .
                '''
            }
        }

        // ==========================================
        // STAGE 4: AUTHENTICATE WITH AMAZON ECR
        // ==========================================
        stage('Login to ECR') {
            steps {
                script {
                    env.AWS_ACCOUNT_ID = sh(
                        script: 'aws sts get-caller-identity --query Account --output text',
                        returnStdout: true
                    ).trim()

                    env.ECR_REGISTRY = "${env.AWS_ACCOUNT_ID}.dkr.ecr.${env.AWS_REGION}.amazonaws.com"
                    env.ECR_URI      = "${env.ECR_REGISTRY}/${env.ECR_REPOSITORY}"
                }

                sh '''
                    set -e
                    echo "Logging into Amazon ECR..."
                    aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}
                '''
            }
        }

        // ==========================================
        // STAGE 5: PUSH IMAGE TO AMAZON ECR
        // ==========================================
        stage('Push Docker Image') {
            steps {
                sh '''
                    set -e
                    echo "Tagging Docker image..."
                    docker tag cicd-demo:${BUILD_NUMBER} ${ECR_URI}:${BUILD_NUMBER}

                    echo "Pushing image to Amazon ECR..."
                    docker push ${ECR_URI}:${BUILD_NUMBER}
                '''
            }
        }

        // ==========================================
        // STAGE 6: DEPLOY TO APPLICATION EC2
        // ==========================================
        stage('Deploy to Application EC2') {
            steps {
                withCredentials([
                    sshUserPrivateKey(
                        credentialsId: 'app-ec2-ssh',
                        keyFileVariable: 'SSH_KEY',
                        usernameVariable: 'SSH_USER'
                    )
                ]) {
                    sh '''
                        set -e

                        echo "Preparing remote deployment script..."

                        cat > deploy-remote.sh <<'DEPLOY_SCRIPT'
#!/bin/bash
set -e

NEW_IMAGE="${ECR_URI}:${IMAGE_TAG}"
ECR_REGISTRY="$(echo "$ECR_URI" | cut -d/ -f1)"

echo "================================"
echo "Starting Application Deployment"
echo "================================"

# STEP 1: Login to Amazon ECR
echo "Logging into Amazon ECR..."
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"

# STEP 2: Pull the new Docker image
echo "Pulling new Docker image..."
docker pull "$NEW_IMAGE"

# STEP 3: Identify the currently running image
OLD_IMAGE=""
if docker container inspect "$APP_CONTAINER" >/dev/null 2>&1; then
    OLD_IMAGE=$(docker inspect --format='{{.Config.Image}}' "$APP_CONTAINER")
    echo "Previous image: $OLD_IMAGE"
    echo "Stopping previous container..."
    docker stop "$APP_CONTAINER" || true
    docker rm "$APP_CONTAINER" || true
else
    echo "No previous container found. First deployment."
fi

# STEP 4: Start the new container
echo "Starting new application container..."
if ! docker run -d --name "$APP_CONTAINER" --restart unless-stopped -p 5000:5000 "$NEW_IMAGE"; then
    echo "New container failed. Starting rollback..."
    if [ -n "$OLD_IMAGE" ]; then
        docker rm -f "$APP_CONTAINER" || true
        docker run -d --name "$APP_CONTAINER" --restart unless-stopped -p 5000:5000 "$OLD_IMAGE"
        echo "Previous version restored."
    fi
    exit 1
fi

# STEP 5: Application health check
echo "Checking application health..."
HEALTHY=0
for i in $(seq 1 12); do
    if curl -fsS http://localhost:5000/health; then
        HEALTHY=1
        echo "Application health check passed!"
        break
    fi
    echo "Health check attempt $i failed. Retrying..."
    sleep 5
done

# STEP 6: Rollback if health check fails
if [ "$HEALTHY" -eq 1 ]; then
    echo "================================"
    echo "DEPLOYMENT SUCCESSFUL"
    echo "================================"
else
    echo "Health check failed. Rolling back..."
    docker stop "$APP_CONTAINER" || true
    docker rm "$APP_CONTAINER" || true
    if [ -n "$OLD_IMAGE" ]; then
        docker run -d --name "$APP_CONTAINER" --restart unless-stopped -p 5000:5000 "$OLD_IMAGE"
        echo "Previous version restored successfully."
    else
        echo "No previous version available for rollback."
    fi
    exit 1
fi
DEPLOY_SCRIPT

                        echo "Transferring and running deployment script on Application EC2..."

                        ssh -i "$SSH_KEY" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new "${SSH_USER}@${APP_HOST}" "AWS_REGION='${AWS_REGION}' ECR_URI='${ECR_URI}' IMAGE_TAG='${BUILD_NUMBER}' APP_CONTAINER='${APP_CONTAINER}' bash -s" < deploy-remote.sh

                        echo "Removing temporary deployment script..."
                        rm -f deploy-remote.sh

                        echo "Application deployment stage completed."
                    '''
                }
            }
        }

    }

    // ==========================================
    // POST-BUILD RESULTS
    // ==========================================
    post {

        success {
            echo '''
====================================
CI/CD PIPELINE COMPLETED SUCCESSFULLY
====================================
Docker image built.
Image pushed to Amazon ECR.
Application deployment completed.
Health check passed.
'''
        }

        failure {
            echo '''
====================================
CI/CD PIPELINE FAILED
====================================
Check the Jenkins Console Output.
If deployment failed, check rollback logs.
'''
        }

    }

}
