# AWS CI/CD Pipeline Using Jenkins, Docker and Amazon ECR

An automated CI/CD pipeline that takes a Python Flask application from GitHub, builds a Docker image, pushes it to Amazon ECR and deploys it to an EC2 instance, with health checks and automatic rollback.

**Flow:** GitHub → Jenkins → Docker Build → Amazon ECR → Application EC2 → Health Check

![Architecture diagram](docs/architecture.svg)

---

## Table of Contents

- [Overview](#overview)
- [Technologies](#technologies)
- [Features](#features)
- [Repository Structure](#repository-structure)
- [The Application](#the-application)
- [Docker Configuration](#docker-configuration)
- [Pipeline Stages](#pipeline-stages)
- [Deployment and Rollback](#deployment-and-rollback)
- [AWS Infrastructure](#aws-infrastructure)
- [Getting Started](#getting-started)
- [Screenshots](#screenshots)
- [Troubleshooting and Lessons Learned](#troubleshooting-and-lessons-learned)
- [Future Improvements](#future-improvements)
- [Summary](#summary)

---

## Overview

Every build in Jenkins runs the following steps automatically:

1. Check out the latest code from GitHub
2. Build a Docker image tagged with the Jenkins build number (for example `cicd-demo:11`)
3. Log in to Amazon ECR using the Jenkins server's IAM role and push the image
4. Connect to the application EC2 instance over SSH, pull the new image and replace the running container
5. Verify the application with a health check
6. Restore the previous version automatically if the deployment fails

No AWS access keys are stored anywhere. Both servers use IAM roles, and the SSH key for deployment is kept in Jenkins credentials.

---

## Technologies

| Area | Tools |
|------|-------|
| Source control | Git, GitHub |
| CI/CD | Jenkins (declarative pipeline) |
| Application | Python 3.12, Flask |
| Containers | Docker |
| Registry | Amazon ECR (private repository, AES-256 encryption) |
| Compute | Amazon EC2 on Ubuntu 24.04 (Jenkins server and application server) |
| Security | AWS IAM roles, security groups, SSH key credentials in Jenkins |
| Scripting and tooling | Bash, Groovy (Jenkinsfile), AWS CLI, SSH |

---

## Features

- **Fully automated pipeline:** from checkout to a running container without manual steps
- **Versioned images:** every build produces a separate image tagged with `BUILD_NUMBER`
- **Secure authentication:** IAM roles for ECR access, SSH key stored in Jenkins credentials
- **Remote deployment:** a Bash script is sent to the application server over SSH and executed there
- **Health checks:** up to 12 attempts, 5 seconds apart, against the `/health` endpoint
- **Automatic rollback:** the previous image is restored if the new container fails to start or fails the health check
- **Auto-restart:** the container runs with `--restart unless-stopped`
- **Fail-fast scripts:** `set -e` in every shell block stops the build at the first error

---

## Repository Structure

```
.
├── app.py                   # Flask application (/ and /health endpoints)
├── requirements.txt         # Python dependencies
├── Dockerfile               # Container image definition
├── .dockerignore            # Files excluded from the Docker build context
├── Jenkinsfile              # Pipeline definition
├── docs/
│   ├── architecture.svg     # Architecture diagram
│   ├── setup-guide.md       # AWS, IAM and Jenkins setup guide
│   └── screenshots/         # Project screenshots
└── README.md
```

---

## The Application

A small Flask application that returns JSON. The version is defined in `app.py` as `APP_VERSION`, which makes it easy to see which release is running after a deployment.

| Endpoint | Description | Example response |
|----------|-------------|------------------|
| `/` | Homepage showing the application message and version | `{"message": "AWS CI/CD Pipeline Application", "version": "v1"}` |
| `/health` | Health check, returns HTTP 200 when the app is working | `{"status": "healthy", "version": "v1"}` |

The app listens on `0.0.0.0:5000` so it is reachable from outside the container.

---

## Docker Configuration

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 5000
CMD ["python", "app.py"]
```

- **Slim base image:** `python:3.12-slim` keeps the image small
- **Layer caching:** `requirements.txt` is copied and installed before the application code, so dependencies are only reinstalled when they change
- **`.dockerignore`:** excludes `.git`, `.gitignore`, `__pycache__`, `*.pyc` and `.env` from the build context

---

## Pipeline Stages

The `Jenkinsfile` defines six stages.

| # | Stage | What it does |
|---|-------|--------------|
| 1 | Checkout Code | Pulls the latest code from GitHub (`checkout scm`) |
| 2 | Check Tools | Confirms `git`, `docker` and `aws` are installed on the Jenkins server |
| 3 | Build Docker Image | Builds `cicd-demo:<build-number>` |
| 4 | Login to ECR | Gets the AWS account ID, builds the ECR URI and logs Docker in using the IAM role |
| 5 | Push Docker Image | Tags the image with the ECR URI and pushes it |
| 6 | Deploy to Application EC2 | Sends the deployment script over SSH and runs it on the application server |

### Pipeline configuration

| Variable | Value | Purpose |
|----------|-------|---------|
| `AWS_REGION` | `ap-south-1` | AWS region for ECR |
| `ECR_REPOSITORY` | `cicd-demo` | ECR repository name |
| `APP_HOST` | Private IP of the application server | Deployment target |
| `APP_CONTAINER` | `cicd-demo` | Name of the running container |

Jenkins credential required: **`app-ec2-ssh`** (SSH username with private key) for deploying to the application server.

---

## Deployment and Rollback

The deployment script runs on the application server and performs these steps:

1. Log in to Amazon ECR
2. Pull the new image
3. Record the image of the currently running container, then stop and remove that container
4. Start the new container on port 5000
5. Call `http://localhost:5000/health` up to 12 times, waiting 5 seconds between failed attempts
6. If healthy, report **DEPLOYMENT SUCCESSFUL**

**Rollback happens in two cases:**
- The new container fails to start: the failed container is removed and the previous image is started again
- The health check never passes: the new container is stopped and removed, and the previous image is started again

In both cases the build ends with a failure status, so the problem is visible in Jenkins.

> **Note:** rollback needs a previously deployed working image, so the very first deployment has no version to roll back to.

---

## AWS Infrastructure

| Component | Configuration |
|-----------|---------------|
| Amazon ECR | Private repository `cicd-demo`, images tagged by Jenkins build number, AES-256 encryption |
| Jenkins EC2 role | `Jenkins-ECR-Push-Role` with `AmazonEC2ContainerRegistryPowerUser`, so Jenkins can push images |
| Application EC2 role | `EC2-ECR-Pull-Role` with `AmazonEC2ContainerRegistryReadOnly`, so the app server can pull images |
| Application EC2 | Ubuntu 24.04, t3.micro, Docker installed, IAM role attached |
| Security group | SSH (22) allowed from the Jenkins security group, TCP 5000 allowed from the tester's IP |

Full instructions are in the **[Project Setup Guide](docs/setup-guide.md)**.

---

## Getting Started

1. Clone the repository: `git clone https://github.com/ompatel54/aws-jenkins-cicd-project.git`
2. Create a private ECR repository (`cicd-demo`) and two EC2 instances (Jenkins and application)
3. Create the IAM roles `Jenkins-ECR-Push-Role` and `EC2-ECR-Pull-Role` and attach them to the instances
4. Install Jenkins, Docker and the AWS CLI on the Jenkins server, and Docker and the AWS CLI on the application server
5. Add the SSH credential `app-ec2-ssh` in Jenkins
6. Create a Pipeline job using **Pipeline script from SCM** that points to this repository and the `main` branch
7. Click **Build Now** or push a commit
8. Open `http://<APP-EC2-PUBLIC-IP>:5000/` and `http://<APP-EC2-PUBLIC-IP>:5000/health`

---

## Screenshots

### AWS infrastructure
| EC2 instances | IAM roles |
|---|---|
| ![EC2 dashboard](docs/screenshots/01-ec2-dashboard.png) | ![IAM roles](docs/screenshots/02-iam-roles.png) |

### Amazon ECR repository
![ECR repository](docs/screenshots/03-ecr-repository.png)

### Jenkins pipeline (all six stages)
![Jenkins pipeline success](docs/screenshots/04-jenkins-pipeline-success.png)

### Jenkins console output
![Jenkins console output](docs/screenshots/05-jenkins-console-output.png)

### Running application and health check
| Homepage | Health check |
|---|---|
| ![Application homepage](docs/screenshots/06-application-homepage.png) | ![Health check](docs/screenshots/07-health-check.png) |

### Docker containers on the application server
![Docker containers](docs/screenshots/08-docker-containers.png)

### Rollback after a failed deployment
![Rollback console output](docs/screenshots/09-rollback-console-output.png)

---

## Troubleshooting and Lessons Learned

**`bash: line N: REMOTE: command not found` and exit code 127**
- *Cause:* a heredoc closing marker was indented, so the remote shell treated it as a command. Multi-line commands were also missing trailing backslashes.
- *Fix:* put the heredoc marker at the very start of the line and write long commands on single lines.
- *Lesson:* the line number in a Jenkins `sh` error refers to the generated script for that step, not to the Jenkinsfile.

**`curl: (56) Connection reset by peer` during the health check**
- *Cause:* the container was still starting.
- *Fix:* the health check retries every 5 seconds, so it passes once the app is ready.

**Jenkins ran an old version of the pipeline**
- *Cause:* the job was not using the latest commit on `main`.
- *Fix:* compare the `Checking out Revision` hash in the console log with the latest commit, and make sure the job uses **Pipeline script from SCM**.

---

## Future Improvements

- Pin the Flask version in `requirements.txt` for reproducible builds
- Run the container as a non-root user
- Serve the app with Gunicorn instead of Flask's built-in development server
- Trigger builds automatically with a GitHub webhook
- Add automated tests and an image vulnerability scan (for example Trivy) before pushing
- Add an ECR lifecycle policy to remove old images
- Put the application behind an Application Load Balancer with HTTPS
- Define the infrastructure with Terraform
- Add Slack or email notifications for build results

---

## Summary

Built an AWS-based CI/CD pipeline using Jenkins, Docker, Amazon ECR and EC2 to automate application building, container image publishing, remote deployment, health verification and rollback. Used IAM roles for secure AWS authentication and Bash scripting for deployment automation.

## Author

**Om Patel**: [GitHub](https://github.com/ompatel54)
