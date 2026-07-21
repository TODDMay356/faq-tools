pipeline {
    agent {
        node {
            label 'k8s-test-jenkins-slave-python3'
        }
    }
    parameters {
        choice(name: 'Build_Action', choices: ['YES', 'NO'], description: '本次构建是否进行代码编译？')
        choice(name: 'Deploy_Action', choices: ['YES', 'NO'], description: '本次构建是否部署至相应环境？')
        choice(name: 'UnitTest_Action', choices: ['NO', 'YES'], description: '是否进行UnitTest单元测试？')
    }
    options {
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '20'))
        disableConcurrentBuilds()
        timeout(time: 20, unit: 'MINUTES')
        gitLabConnection('gitlab')
    }
    environment {
        IMAGE_REPO = "harbor.inflyway.com"
        HARBOR = credentials('harbor')
        GIT_CONFIG_URL = "gitlab.kamelnet.com/kustomize/faq-tools.git"
        GIT = credentials('git-jenkins')
        PROJECT_NAME = "faq-tools"
        IMAGE_VERSION = "${GIT_COMMIT}-${BUILD_NUMBER}"
        FEISHU_TOKEN = "8d17910e-c5eb-4ee4-b254-7471aaf94afa"
        CHECK_RL = "未做代码扫描"
        CHECK_CODE_FLAG = "False"
    }
    stages {
        stage('Printenv') {
            steps {
                container('jenkins-slave-python3') {
                    script {
                        def specificCause = currentBuild.getBuildCauses('hudson.model.Cause$UserIdCause')
                        env.CAUSE = "${specificCause.shortDescription}"
                        echo 'printenv'
                        echo "'${BUILD_URL}'"
                        echo "'${HOSTNAME}'"
                        echo "'${RUN_CHANGES_DISPLAY_URL}'"
                        echo "'${PATH}'"
                        echo "'${CAUSE}'"
                    }
                }
            }
        }
        stage('Checkout代码') {
            steps {
                container('jenkins-slave-python3') {
                    checkout scm
                    script {
                        sh "git log --oneline -n 1 > gitlog.file"
                        env.commitlog = readFile("gitlog.file").trim()
                        updateGitlabCommitStatus(name: env.STAGE_NAME, state: 'success')
                        env.git_commit_name = sh (script: "git --no-pager show -s --format='%an' ${GIT_COMMIT}",returnStdout: true).trim()
                    }
                }
            }
        }
        stage('Docker_Build构建容器镜像') {
            when {
                environment name: 'Build_Action', value: 'YES'
            }
            steps {
                container('jenkins-slave-python3') {
                    script {
                        if (BRANCH_NAME =~ "develop" || BRANCH_NAME =~ "dev" || BRANCH_NAME =~ "feature") {
                            retry(2) { sh 'docker build . -t ${IMAGE_REPO}/kamelnet-dev/${PROJECT_NAME}:${IMAGE_VERSION}' }
                        }
                        else if ( BRANCH_NAME =~ "test" || BRANCH_NAME =~ "release") {
                            retry(2) { sh 'docker build . -t ${IMAGE_REPO}/kamelnet-test/${PROJECT_NAME}:${IMAGE_VERSION}' }
                        }
                        else if ( BRANCH_NAME =~ "uat") {
                            retry(2) { sh 'docker build . -t ${IMAGE_REPO}/kamelnet-uat/${PROJECT_NAME}:${IMAGE_VERSION}' }
                        }
                        else if (BRANCH_NAME =~ "master" || BRANCH_NAME =~ "hotfix" ) {
                            retry(2) { sh 'docker build . -t ${IMAGE_REPO}/kamelnet-master/${PROJECT_NAME}:${IMAGE_VERSION}' }
                        }
                    }
                }
            }
        }
        stage('Push_Image推送镜像') {
            when {
                environment name: 'Build_Action', value: 'YES'
            }
            steps {
                container('jenkins-slave-python3') {
                    script {
                        if (BRANCH_NAME =~ "develop" || BRANCH_NAME =~ "dev" || BRANCH_NAME =~ "feature") {
                            retry(2) {
                                sh 'docker login --username ${HARBOR_USR} --password ${HARBOR_PSW} ${IMAGE_REPO}/kamelnet-dev'
                                sh 'docker push ${IMAGE_REPO}/kamelnet-dev/${PROJECT_NAME}:${IMAGE_VERSION}'
                                updateGitlabCommitStatus(name: env.STAGE_NAME, state: 'success')
                            }
                            sh 'docker rmi ${IMAGE_REPO}/kamelnet-dev/${PROJECT_NAME}:${IMAGE_VERSION}'
                            image="${IMAGE_REPO}/kamelnet-dev/${PROJECT_NAME}"
                            imageTag="${IMAGE_VERSION}"
                        }
                        else if (BRANCH_NAME =~ "test" || BRANCH_NAME =~ "release") {
                            retry(2) {
                                sh 'docker login --username ${HARBOR_USR} --password ${HARBOR_PSW} ${IMAGE_REPO}/kamelnet-test'
                                sh 'docker push ${IMAGE_REPO}/kamelnet-test/${PROJECT_NAME}:${IMAGE_VERSION}'
                                updateGitlabCommitStatus(name: env.STAGE_NAME, state: 'success')
                            }
                            sh 'docker rmi ${IMAGE_REPO}/kamelnet-test/${PROJECT_NAME}:${IMAGE_VERSION}'
                            image="${IMAGE_REPO}/kamelnet-test/${PROJECT_NAME}"
                            imageTag="${IMAGE_VERSION}"
                        }
                        else if (BRANCH_NAME =~ "uat") {
                            retry(2) {
                                sh 'docker login --username ${HARBOR_USR} --password ${HARBOR_PSW} ${IMAGE_REPO}/kamelnet-uat'
                                sh 'docker push ${IMAGE_REPO}/kamelnet-uat/${PROJECT_NAME}:${IMAGE_VERSION}'
                                updateGitlabCommitStatus(name: env.STAGE_NAME, state: 'success')
                            }
                            sh 'docker rmi ${IMAGE_REPO}/kamelnet-uat/${PROJECT_NAME}:${IMAGE_VERSION}'
                            image="${IMAGE_REPO}/kamelnet-uat/${PROJECT_NAME}"
                            imageTag="${IMAGE_VERSION}"
                        }
                        else if (BRANCH_NAME =~ "master" || BRANCH_NAME =~ "hotfix") {
                            retry(2) {
                                sh 'docker login --username ${HARBOR_USR} --password ${HARBOR_PSW} ${IMAGE_REPO}/kamelnet-master'
                                sh 'docker push ${IMAGE_REPO}/kamelnet-master/${PROJECT_NAME}:${IMAGE_VERSION}'
                                updateGitlabCommitStatus(name: env.STAGE_NAME, state: 'success')
                            }
                            sh 'docker rmi ${IMAGE_REPO}/kamelnet-master/${PROJECT_NAME}:${IMAGE_VERSION}'
                            image="${IMAGE_REPO}/kamelnet-master/${PROJECT_NAME}"
                            imageTag="${IMAGE_VERSION}"
                        }
                    }
                }
            }
        }
        stage('Commit_YAML提交YAML配置') {
            when {
                environment name: 'Deploy_Action', value: 'YES'
            }
            steps {
                container('jenkins-slave-python3') {
                    script {
                        APP_DIR="${JOB_NAME}".split("/")[0]
                        sh """
                            echo $APP_DIR $image $imageTag
                            git config --global user.email "jenkins@camelfin.com"
                            git config --global user.name "jenkins"
                            mkdir -p /opt/devops-cd/
                            cd /opt/devops-cd/
                            git clone http://${GIT_USR}:${GIT_PSW}@${GIT_CONFIG_URL}
                        """
                        if (BRANCH_NAME =~ "master"){
                            sh """
                            cd /opt/devops-cd/${APP_DIR}
                            kustomize edit set image ${image}:${imageTag}
                            """
                        }
                        if (BRANCH_NAME =~ "develop" || BRANCH_NAME =~ "dev" || BRANCH_NAME =~ "feature") {
                            sh """
                                cd /opt/devops-cd/${APP_DIR}
                                git checkout -b develop origin/develop
                                kustomize edit set image ${image}:${imageTag}
                            """
                        }
                        if (BRANCH_NAME =~ "uat") {
                            sh """
                                cd /opt/devops-cd/${APP_DIR}
                                git checkout -b uat origin/uat
                                kustomize edit set image ${image}:${imageTag}
                            """
                        }
                        else if (BRANCH_NAME =~ "release" || BRANCH_NAME =~ "test") {
                            sh """
                                cd /opt/devops-cd/${APP_DIR}
                                git checkout -b test origin/test
                                kustomize edit set image ${image}:${imageTag}
                            """
                        }
                        sh """
                            cd /opt/devops-cd/${APP_DIR}
                            git add .
                            git commit -m '${IMAGE_VERSION}'
                            git push
                        """
                        updateGitlabCommitStatus(name: env.STAGE_NAME, state: 'success')
                    }
                }
            }
        }
    }
    post {
        success {
        echo "恭喜你"
        sh """
            curl -X POST -H "Content-Type: application/json" \
              -d '{
                "msg_type": "interactive",
                "card": {
                  "config": {
                    "wide_screen_mode": true,
                    "enable_forward": true
                  },
                  "header": {
                    "title": {
                      "tag": "plain_text",
                      "content": "构建通知-${JOB_NAME}"
                    },
                    "template": "Green"
                  },
                  "elements": [
                    {
                      "tag": "div",
                      "text": {
                        "tag": "lark_md",
                        "content": "**构建结果：** 构建成功 \\n**项目名称：** ${JOB_NAME} \\n**构建分支：** ${JOB_BASE_NAME} \\n**构建原因：** ${CAUSE} \\n**提交者：** ${git_commit_name} \\n**版本号：** ${IMAGE_VERSION} \\n**提交日志：** ${commitlog} \\n**扫描结果：** ${CHECK_RL}\\n**[点我查看构建日志](${RUN_DISPLAY_URL})** \\n**[点我查看变更记录](${RUN_CHANGES_DISPLAY_URL})**"
                      }
                    }
                  ]
                }
              }'  https://open.feishu.cn/open-apis/bot/v2/hook/${FEISHU_TOKEN}
        """
        }
        failure {
        echo "oh NO!"
        sh """
            curl -X POST -H "Content-Type: application/json" \
              -d '{
                "msg_type": "interactive",
                "card": {
                  "config": {
                    "wide_screen_mode": true,
                    "enable_forward": true
                  },
                  "header": {
                    "title": {
                      "tag": "plain_text",
                      "content": "构建通知-${JOB_NAME}"
                    },
                    "template": "Red"
                  },
                  "elements": [
                    {
                      "tag": "div",
                      "text": {
                        "tag": "lark_md",
                        "content": "**构建结果：** 构建失败 \\n**项目名称：** ${JOB_NAME} \\n**构建分支：** ${JOB_BASE_NAME} \\n**构建原因：** ${CAUSE} \\n**提交者：** ${git_commit_name} \\n**版本号：** ${IMAGE_VERSION} \\n**提交日志：** ${commitlog} \\n**扫描结果：** ${CHECK_RL}\\n**[点我查看构建日志](${RUN_DISPLAY_URL})** \\n**[点我查看变更记录](${RUN_CHANGES_DISPLAY_URL})**"
                      }
                    }
                  ]
                }
              }' \
        https://open.feishu.cn/open-apis/bot/v2/hook/${FEISHU_TOKEN}
        """
        }
        always {
            echo '构建完成'
        }
    }
}