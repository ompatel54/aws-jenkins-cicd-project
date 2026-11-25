pipeline {

    agent any

    environment {
        AWS_REGION = 'ap-south-1'
        ECR_REPOSITORY = 'cicd-demo'
        APP_HOST = '172.31.14.218'
        APP_CONTAINER = 'cicd-demo'
    }

    stages {

        stage('Checkout Code') {
            steps {
                checkout scm
            }
        }

        stage('Check Tools') {
            steps {
                sh '''
                    git --version
                    docker --version
                    aws --version
                '''
            }
        }

        stage('Build Docker Image') {
            steps {
                sh '''
                    docker build -t cicd-demo:${BUILD_NUMBER} .
                '''
            }
        }

        stage('Login to ECR') {
            steps {
                script {
                    env.AWS_ACCOUNT_ID = sh(
                        script: 'aws sts get-caller-identity --query Account --output text',
                        returnStdout: true
                    ).trim()

                    env.ECR_REGISTRY =
                        "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

                    env.ECR_URI =
                        "${ECR_REGISTRY}/${ECR_REPOSITORY}"
                }

                sh '''
                    aws ecr get-login-password --region ${AWS_REGION} |
                    docker login --username AWS --password-stdin ${ECR_REGISTRY}
                '''
            }
        }

        stage('Push Docker Image') {
            steps {
                sh '''
                    docker tag cicd-demo:${BUILD_NUMBER} ${ECR_URI}:${BUILD_NUMBER}
                    docker push ${ECR_URI}:${BUILD_NUMBER}
                '''
            }
        }

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

                        ssh -i "$SSH_KEY" \
                            -o IdentitiesOnly=yes \
                            -o StrictHostKeyChecking=accept-new \
                            "${SSH_USER}@${APP_HOST}" \
                            "AWS_REGION='${AWS_REGION}' ECR_URI='${ECR_URI}' IMAGE_TAG='${BUILD_NUMBER}' APP_CONTAINER='${APP_CONTAINER}' bash -s" <<'REMOTE'

set -e

NEW_IMAGE="${ECR_URI}:${IMAGE_TAG}"

echo "Logging into Amazon ECR..."

aws ecr get-login-password --region "$AWS_REGION" |
docker login --username AWS --password-stdin "$(echo "$ECR_URI" | cut -d/ -f1)"

echo "Pulling new Docker image..."

docker pull "$NEW_IMAGE"

OLD_IMAGE=""

if docker container inspect "$APP_CONTAINER" >/dev/null 2>&1
then
    OLD_IMAGE=$(docker inspect --format='{{.Config.Image}}' "$APP_CONTAINER")
    echo "Previous image: $OLD_IMAGE"

    docker stop "$APP_CONTAINER" || true
    docker rm "$APP_CONTAINER" || true
fi

echo "Starting new application..."

if ! docker run -d 
    --name "$APP_CONTAINER" 
    --restart unless-stopped 
    -p 5000:5000 
    "$NEW_IMAGE"
then
    echo "New container failed. Rolling back..."

    if [ -n "$OLD_IMAGE" ]; then
        docker run -d \
            --name "$APP_CONTAINER" \
            --restart unless-stopped \
            -p 5000:5000 \
            "$OLD_IMAGE"
    fi

    exit 1
fi

echo "Checking application health..."

HEALTHY=0

for i in $(seq 1 12)
do
    if curl -fsS http://localhost:5000/health
    then
        HEALTHY=1
        break
    fi

    sleep 5
done

if [ "$HEALTHY" -eq 1 ]; then
    echo "Deployment successful!"
else
    echo "Health check failed. Rolling back..."

    docker stop "$APP_CONTAINER" || true
    docker rm "$APP_CONTAINER" || true

    if [ -n "$OLD_IMAGE" ]; then
        docker run -d \
            --name "$APP_CONTAINER" \
            --restart unless-stopped \
            -p 5000:5000 \
            "$OLD_IMAGE"

        echo "Previous version restored."
    else
        echo "No previous version available."
    fi

    exit 1
fi

REMOTE
                    '''
                }
            }
        }
    }

    post {
        success {
            echo 'CI/CD pipeline completed successfully!'
        }

        failure {
            echo 'Pipeline failed. Check the Console Output.'
        }
    }
}
