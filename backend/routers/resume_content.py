"""Resume / portfolio content — Python mirror of frontend resumeContent.js."""

RESUME_PROFILE = {
    "name": "Naresh Vusirikayala",
    "title": "Senior Cloud DevOps Engineer · SRE · AI Platform Engineer",
    "location": "Frisco, TX",
    "email": "nareshvusiri5855@gmail.com",
    "phone": "+1 (737) 224-1812",
    "availability": "Available for SRE · Platform · DevOps roles",
    "tagline": (
        "8+ years building reliable cloud platforms on AWS & Azure — Kubernetes, GitOps, observability, "
        "and AI-assisted automation for enterprise IAM, data, and telecom workloads."
    ),
}

RESUME_CTA = {
    "introCallLabel": "Schedule 30-min intro call",
    "introCallSubject": "30-minute intro call",
    "calendlyUrl": "",
    "chatLabel": "Chat with Naresh",
    "chatHint": "Verified answers · first person · live on this profile",
}

RESUME_SUMMARY = (
    "Experienced DevOps/Cloud Engineer with 8 years of expertise in software development processes. Adept at system designing, deploying, and maintaining various applications and infrastructure solutions, both on-premises and in the cloud, using enterprise cloud services like Azure and AWS. Skilled in Infrastructure as Code (IaC) for designing robust and scalable infrastructure, including platform design. Proficient in project setup, build automation, and continuous integration/continuous deployment (CI/CD) processes. Known for quick learning pace and adaptability to emerging technologies. Dedicated to delivering high-quality solutions with a proven ability to adapt to changing environments."
)

RESUME_SUMMARY_DETAILS = [
    "Involved in Linux administration activities like troubleshooting of regular issues, configuration issues, applying patches, kernel upgrades, package management, diagnosing resource utilization and file system issues.",
    "Exposed to all aspects of the software development lifecycle (SDLC) such as Analysis, Planning, and Developing, Testing, and Implementing Post-production analysis of the projects using methodologies such as Agile, Scrum Models.",
    "Experience in the areas of DevOps, CI/CD Pipeline, Build and release management and Linux/Windows Administration. Proficient in prioritizing and completing tasks in a timely manner.",
    "Integrated Jenkins with Git, Docker, Kubernetes/EKS, and Terraform to streamline application delivery workflows.",
    "Played a pivotal role in establishing versatile CI/CD pipelines catering to diverse stacks, encompassing Java, Python, and beyond, leveraging tools such as Jenkins, Maven, Nexus, Bitbucket, JFROG Artifactory, Ansible, OpenShift, EKS, AKS, and Helm.",
    "Proficient in developing Kubernetes manifests files and Helm packages, ensuring efficient deployment and management of containerized applications.",
    "Extensive experience configuring Amazon EC2, VPC, Security Groups, IAM, Amazon S3, SNS, SQS, KMS, Secrets Manager, ACM, API Gateway, Lambda, CloudFront, CloudWatch, X-Ray, WAF, AWS PrivateLink, VPC endpoints, DynamoDB, RDS, Elastic Load Balancing in public and private subnets, and other AWS services.",
    "Experience deploying web services on Apache Tomcat, JBoss, WebSphere, NGINX, and WebLogic servers.",
    "Established CI/CD pipelines tailored for Android and iOS application development using platforms like Jenkins or GitLab CI.",
    "Implemented comprehensive security measures within CI/CD pipelines, integrating Sysdig, Fortify, Black Duck, SonarQube, JaCoCo, and OWASP ZAP for DAST, adhering to SecOps standards.",
    "Expertise deploying web apps and web APIs using Azure App Services and implementing CI/CD of web apps using Azure Pipelines.",
    "Deep understanding of IP networking technologies, troubleshooting TCP/IP networking issues, and managing networking configurations within VPCs alongside Linux network administration.",
    "Implemented robust security measures including SSL/TLS encryption, Single Sign-On (SSO) integration, and JSON Web Token (JWT) authentication for stateless and secure user authentication.",
    "Developed Terraform and CloudFormation templates, leveraging AWS CDK in Python, to automate provisioning of cloud resources across Non-prod and Prod stages.",
    "Skilled in creating and maintaining reusable components such as Jenkins shared libraries, CDK reusable modules, and Terraform reusable modules, streamlining development and promoting code consistency.",
    "Skilled in integrating Sentinel policies into Terraform CI/CD pipelines, automating policy checks before deployments, and providing continuous validation of infrastructure-as-code practices.",
    "Experienced in creating custom Terraform Sentinel policies for automated policy-as-code enforcement.",
    "Participated in migrating on-premises VM shared applications to cloud environments, including Kubernetes clusters like OpenShift, EKS, and AKS, along with virtual machine services.",
    "Proficient knowledge and hands-on experience with monitoring tools including Splunk, AppDynamics, New Relic, Grafana, Prometheus, ITRS, X-Ray, CloudWatch, and Dynatrace.",
    "Built custom observability before enterprise APM was available — shell/Python URL health checks, NGINX-hosted log browsing for ops teams, and Autosys-scheduled Python scripts for CPU and system metrics on Linux servers.",
    "Proficient administering Production, Development, and Test environments across Windows, Red Hat Linux, AWS EC2 instances, and Azure VMs.",
    "Proficient in various databases including NoSQL options like DynamoDB, Cassandra, and MongoDB, relational databases such as RDS (MySQL, PostgreSQL), and time-series databases like InfluxDB.",
    "Demonstrates effective communication and collaboration with developers, managers, and team members to coordinate tasks, fostering strong teamwork and commitment to project success.",
    "Team player with excellent interpersonal skills, self-motivated, dedicated, understanding the demands of 24/7 system maintenance, and strong customer focus.",
]

RESUME_SKILLS = {
    "sre": [
        "Kubernetes · EKS · AKS · OpenShift · Helm · Karpenter · Istio · Docker",
        "Prometheus · Grafana · Splunk · Datadog · Dynatrace · ELK · CloudWatch · AppDynamics · New Relic · ITRS",
        "Kafka · EventBridge · event streaming · ServiceNow INC automation · Netcool",
        "ArgoCD · GitOps · drift detection · rollback · blue-green deploys",
        "Incident response · SOX audit · on-call · 24/7 production · SLO/SLI",
        "Terraform · Terragrunt · CloudFormation · AWS CDK · Ansible · Sentinel policies",
        "Ping Identity · IAM · Vault · CyberArk · Checkov · SSO · JWT · SSL/TLS",
    ],
    "cloud": [
        "AWS — EC2 · EKS · ECS · Fargate · Lambda · RDS · Aurora · S3 · VPC · IAM · API Gateway · DynamoDB",
        "Azure — AKS · App Services · Databricks · Functions · Storage · hybrid cloud migration",
        "GCP · OpenStack · multi-cloud architecture · lift-and-shift · cost optimization",
        "Networking — VPC · subnets · ELB/ALB · security groups · Istio service mesh · TCP/IP",
    ],
    "cicd": [
        "Jenkins · Tekton · Harness · LightSpeed · GitHub Actions · GitLab CI · CircleCI · shared libraries",
        "ArgoCD · GitOps · Helm charts · containerization · microservices refactor",
        "Maven · Groovy pipelines · Nexus · JFROG Artifactory · Checkov · SonarQube · Fortify · OWASP ZAP gates",
        "Build & release · end-to-end automation · Agile · Scrum · Kanban · release management",
    ],
    "observability": [
        "Prometheus · Grafana · AlertManager · Splunk · Datadog · Dynatrace · AppDynamics · New Relic",
        "Elasticsearch · Netcool · event deduplication · distributed tracing · X-Ray · CloudWatch",
        "ServiceNow INC auto-creation · SOX audit trails · capacity planning · ITRS",
        "Loki · Filebeat · Blackbox Exporter · full-stack observability on EKS",
    ],
    "ai": [
        "Claude AI · Citi AI Workspaces · Generative AI for IaC & code review",
        "LangGraph multi-agent orchestration (portfolio project)",
        "RAG · ChromaDB · local LLM (Ollama) · kubectl-ai patterns",
        "Human-in-the-loop remediation · audit trails · Docker Model Runner",
        "SSE & Kafka real-time incident feeds · FastAPI · entitlement APIs",
    ],
    "languages": [
        "Python", "Java", "Go", "Shell/Bash", "Groovy", "Ruby", "Perl",
        "Terraform HCL", "YAML", "SQL", "JavaScript", "PowerShell",
    ],
}

RESUME_SKILL_MATRIX = [
    {
        "category": "Version Control",
        "proficiency": "Expert",
        "skills": [
            "Git",
            "SVN",
            "GitLab",
        ],
        "endorsed_on_linkedin": True,
    },
    {
        "category": "CI/CD",
        "proficiency": "Expert",
        "skills": [
            "Jenkins",
            "GitHub Actions",
            "Nexus",
            "JFROG Artifactory",
            "GitLab CI",
            "CircleCI",
            "Maven",
            "Azure Pipelines",
            "ArgoCD",
            "Tekton",
            "Harness",
        ],
        "endorsed_on_linkedin": True,
    },
    {
        "category": "Containerization & Orchestration",
        "proficiency": "Expert",
        "skills": [
            "Docker",
            "Kubernetes",
            "OpenShift",
            "EKS",
            "AKS",
        ],
        "endorsed_on_linkedin": True,
    },
    {
        "category": "Configuration Management",
        "proficiency": "Expert",
        "skills": [
            "Ansible",
            "Ansible Tower",
            "Chef",
            "Terraform",
        ],
        "endorsed_on_linkedin": True,
    },
    {
        "category": "Infrastructure as Code",
        "proficiency": "Expert",
        "skills": [
            "Terraform",
            "AWS CloudFormation",
            "CDK",
            "ARM",
        ],
        "endorsed_on_linkedin": True,
    },
    {
        "category": "Cloud Platforms",
        "proficiency": "Expert",
        "skills": [
            "AWS",
            "Azure",
            "Google Cloud Platform",
            "OpenStack",
        ],
        "endorsed_on_linkedin": True,
    },
    {
        "category": "Serverless",
        "proficiency": "Advanced",
        "skills": [
            "AWS Lambda",
            "Azure Functions",
            "Google Cloud Functions",
        ],
        "endorsed_on_linkedin": True,
    },
    {
        "category": "Scripting",
        "proficiency": "Advanced",
        "skills": [
            "Shell/Bash",
            "Python",
            "Ruby",
            "JavaScript (Node.js)",
        ],
        "endorsed_on_linkedin": True,
    },
    {
        "category": "Programming",
        "proficiency": "Advanced",
        "skills": [
            "Python",
            "Java",
            "Go",
        ],
        "endorsed_on_linkedin": True,
    },
    {
        "category": "Databases",
        "proficiency": "Advanced",
        "skills": [
            "MySQL",
            "PostgreSQL",
            "MongoDB",
            "RDS",
            "DynamoDB",
            "Influx",
            "Redis",
        ],
        "endorsed_on_linkedin": True,
    },
    {
        "category": "Monitoring & Logging",
        "proficiency": "Expert",
        "skills": [
            "Dynatrace",
            "AppDynamics",
            "New Relic",
            "Prometheus",
            "Grafana",
            "Splunk",
            "ELK Stack",
            "ITRS",
        ],
        "endorsed_on_linkedin": True,
    },
    {
        "category": "Networking & Security",
        "proficiency": "Advanced",
        "skills": [
            "TCP/IP",
            "SSL/TLS",
            "SSH",
            "IPsec",
            "OAuth 2.0",
            "OpenID Connect",
            "JWT",
        ],
        "endorsed_on_linkedin": True,
    },
    {
        "category": "Operating Systems",
        "proficiency": "Advanced",
        "skills": [
            "Linux (Ubuntu, Fedora, RHEL)",
            "macOS",
            "Windows Server 2019+",
        ],
        "endorsed_on_linkedin": True,
    },
    {
        "category": "Application Servers",
        "proficiency": "Advanced",
        "skills": [
            "NGINX",
            "Apache HTTP Server",
            "Tomcat",
            "Node.js",
        ],
        "endorsed_on_linkedin": True,
    },
    {
        "category": "SDLC Methodologies",
        "proficiency": "Expert",
        "skills": [
            "Agile",
            "Scrum",
            "Kanban",
            "Jira",
        ],
        "endorsed_on_linkedin": True,
    },
    {
        "category": "Security Implementation",
        "proficiency": "Advanced",
        "skills": [
            "Sysdig",
            "Fortify",
            "Black Duck",
            "SonarQube",
            "JaCoCo",
            "OWASP ZAP",
            "Checkmarx",
        ],
        "endorsed_on_linkedin": True,
    },
]


RESUME_RECOMMENDATIONS = [
    {
        "author": "Ashwin Krishnamoorthy",
        "linkedin_url": "https://www.linkedin.com/in/ashwinbk",
        "emoji": "⭐",
        "title": "Director",
        "company": "Bank of America",
        "relationship": "Former colleague (~3 years) · worked together on infrastructure and DevOps",
        "text": (
            "Naresh is a highly skilled and dependable professional. I had the opportunity to work with Naresh "
            "for around three years, and during that time, he consistently demonstrated his expertise in "
            "infrastructure and DevOps. Naresh was always proactive in taking on challenging projects. "
            "He is a fast learner, dedicated to staying updated with the latest technologies, and always "
            "approaches problems with a positive attitude. Naresh is not only technically proficient but also "
            "a great collaborator, always willing to explain his thought process and guide the team. "
            "I have no doubt Naresh would be an asset to any organization, and I highly recommend him for "
            "any role that values strong technical expertise and teamwork."
        ),
    },
    {
        "author": "Carrie Hawk",
        "linkedin_url": "https://www.linkedin.com/in/carrie-hawk-a4187b142",
        "emoji": "🤝",
        "title": "Agile Team Member",
        "company": "Pega application project",
        "relationship": "Collaborated on Agile Pega application development",
        "text": (
            "I have worked with Naresh while developing a Pega application project. This was in an Agile "
            "Methodology environment. He was very professional and willing to support any needs this role "
            "entailed. Whenever changes needed to be made, he showed flexibility to meet the needs of business "
            "and be a valued contributor to our team. If you want a great worker with excellent skills and "
            "strong work ethic, that gets it done than consider Naresh."
        ),
    },
]

RESUME_LINKEDIN = {
    "url": "https://linkedin.com/in/nareshvusiri",
    "headline": (
        "Senior DevOps Engineer | Cloud Engineer | SRE | Platform Engineer | "
        "AWS Certified DevOps Engineer | AZURE | GCP"
    ),
    "connections": "500+",
    "followers": "3,851",
    "source_note": "Skills matrix and recommendations synced from public LinkedIn profile.",
}

FEATURED_PROJECT = {
    "name": "SRE AI Copilot",
    "badge": "Personal SRE bot · R&D project",
    "role": "Independent portfolio build — not employer production work",
    "period": "2025 – Present",
    "architecture_link": "/docs",
    "repo_label": "github.com/nareshram5855/sre-ai-copilot",
    "repo_url": "https://github.com/nareshram5855/sre-ai-copilot",
    "summary": (
        "Personal R&D project I built to explore AI-assisted incident response: AlertManager triage, "
        "unified observability across Prometheus, Loki, and OTEL, RAG-backed runbooks, and "
        "human-gated Kubernetes remediation — validating SRE + AI platform patterns outside my "
        "Fortune-scale client engagements at Citi, BofA, Verizon, and Toyota."
    ),
    "highlights": [
        {"label": "Multi-agent LangGraph", "detail": "Seven specialist agents (Triage, Chat, Runbook, RCA, Executor, Supervisor, Learning) with LangGraph checkpointing and Redis/SQLite persistence fallbacks."},
        {"label": "Observability pipeline", "detail": "Prometheus + Loki + 7 synthetic microservices on Minikube; anomaly watcher; Command Center with live SSE fleet health."},
        {"label": "Event-driven architecture", "detail": "Kafka (aiokafka) for durable incident/anomaly fan-out with SSE fallback; Redis for sessions, dedup, and LangGraph checkpoints."},
        {"label": "Autonomous remediation", "detail": "ExecutorAgent: parallel K8s gather → LLM plan → write actions gated by human approval; append-only audit trail; ServiceNow & PagerDuty integration hooks."},
        {"label": "Enterprise patterns", "detail": "API-key auth, GitOps-ready manifests, GitHub Actions CD to Minikube, architecture docs at /docs, app profiler at /profiler."},
        {"label": "Operator dashboard", "detail": "Command Center, Observe, Incident Analysis, Playbooks, Audit log, and Resume — enterprise-grade SRE workspace with live SSE fleet health."},
    ],
    "tech_stack": [
        "React 18 · Vite · TailwindCSS",
        "FastAPI · Python 3.11+",
        "LangGraph · LangChain · Ollama",
        "ChromaDB · Redis · SQLite · Kafka",
        "Prometheus · Loki · AlertManager · OTel",
        "Kubernetes · Minikube · GitHub Actions · SSE",
    ],
    "tech_stack_categories": [
        {"category": "Frontend", "tools": ["React 18", "Vite", "TailwindCSS"]},
        {"category": "Backend", "tools": ["FastAPI", "Python 3.11+", "Gunicorn"]},
        {"category": "AI / agents", "tools": ["LangGraph", "LangChain", "Ollama", "ChromaDB"]},
        {"category": "Observability", "tools": ["Prometheus", "Loki", "AlertManager", "OTel"]},
        {"category": "Platform", "tools": ["Kubernetes", "Minikube", "Kafka", "Redis", "SQLite"]},
        {"category": "Delivery", "tools": ["GitHub Actions", "Docker", "SSE", "Make"]},
    ],
}

RESUME_EXPERIENCE = [
    {
        "company": "Citigroup (CISO Organization)",
        "role": "Senior Cloud DevOps Engineer / SRE",
        "period": "Apr 2025 – Present",
        "location": "Irving, TX",
        "description": (
            "At Citigroup, supporting the CISO organization, responsible for migrating critical identity and access management services to the AWS cloud, ensuring compliance, scalability, and operational resilience. Modernizing legacy on-prem IAM solutions, including Ping Identity products, and transitioning them to a secure, containerized platform on Amazon."
        ),
        "bullets": [
            "Built and maintained CI/CD workflows using Tekton, LightSpeed, and Harness for containerized microservice deployments across dev, staging, and production environments.",
            "Migrated critical identity services, including PingFederate, PingAccess, and PingDirectory, from on-premises infrastructure to AWS cloud using EKS, Terraform, and containerization best practices.",
            "Led the modernization of legacy monolithic applications by refactoring them into microservices, deploying on Amazon EKS and ECS using scalable CI/CD practices.",
            "Configured and managed ArgoCD for GitOps-based continuous delivery of microservices to EKS clusters, enabling automated sync, drift detection, and rollback capabilities across multiple environments.",
            "Led the migration of on-premises IAM applications and vendor services to AWS EKS and EC2, ensuring minimal downtime, compliance with CISO security standards, and optimizing cloud resources for performance and cost-efficiency.",
            "Developed and maintained a Python FastAPI-based Entitlement Service for SafeWord to generate and manage user entitlements efficiently.",
            "Built scalable REST APIs in Python to handle entitlement validation, access management, and user authorization workflows.",
            "Wrote complex SQL queries, stored procedures, and optimized database operations for reporting applications.",
            "Developed and maintained IAM audit tools for SOX compliance reporting, building entitlement services using Shell scripts, SQL queries, and Python to automate access review and certification workflows.",
            "Built Elasticsearch queries for EKS workload application monitoring and integrated with Netcool for centralized event deduplication, which triggers ServiceNow to automatically create INC tickets for production incidents.",
            "Configured Prometheus and Grafana for infrastructure and application monitoring across EKS clusters, and integrated alerting workflows with ServiceNow to automatically create INC tickets for proactive incident resolution.",
            "Automated infrastructure provisioning and configuration management using Terraform, reducing manual setup time.",
            "Provided production support for IAM PingDirectory and Apigee API gateway services, ensuring high availability, troubleshooting authentication issues, and performing configuration updates across environments.",
            "Deployed and configured SiteMinder and Ping Identity SSO services on IIS web servers running on Windows, managing agent configurations, policy bindings, and session management for enterprise web application authentication.",
            "Developed custom Ansible roles for automated deployment and configuration of SiteMinder Admin Server and Policy Server on both Linux and Windows platforms, streamlining provisioning and ensuring consistent configurations across environments.",
            "Implemented Karpenter for automated node provisioning and scaling of SSO Ping services in EKS, optimizing cluster resource utilization and reducing infrastructure costs through right-sized node pools.",
            "Proficient in leveraging AI-powered tools such as Claude AI and Citi AI Workspaces to accelerate development workflows, automate code reviews, generate infrastructure-as-code templates, and streamline documentation processes.",
            "Actively involved in exploring and adopting next-generation Generative AI projects within the organization, evaluating AI-driven solutions for DevOps automation, intelligent monitoring, and operational efficiency improvements.",
        ],
        "environment": (
            "AWS, Terraform, LightSpeed, Tekton, OpenShift, Harness, IaC, GitHub Actions, Oracle, Jenkins, Splunk, CLI, GitHub, Maven, Docker, EKS, ECS, Fargate, Unix/Linux, EC2, VPC, Security Groups, IAM, Amazon S3, SNS, SQS, KMS, NACL, Secrets Manager, Ping, PingDirectory, Apigee, Elasticsearch, Prometheus, Grafana, Netcool, ServiceNow, Karpenter, ArgoCD, Ansible, IIS, Windows Server, Claude AI, Generative AI, SiteMinder"
        ),
    },
    {
        "company": "Toyota Motors North America",
        "role": "Senior Cloud DevOps Engineer / Infrastructure Engineer",
        "period": "Nov 2024 – Mar 2025",
        "location": "Plano, TX",
        "description": (
            "Supported Data Platform Teams in managing AWS infrastructure and ensuring high availability of critical data platforms, including RDS Postgres, Aurora, and vendor-integrated solutions. Delivered scalable, resilient cloud platforms for data transformations and advanced analytics."
        ),
        "bullets": [
            "Proficient in leveraging AWS services for product user onboarding, including setting up baseline services and configuring AWS accounts for application onboarding using Terragrunt and Terraform blueprints.",
            "Designed and implemented scalable CI/CD pipelines using Jenkins and GitHub Actions to automate build, test, and deployment processes, ensuring high-quality and efficient application delivery.",
            "Managed large-scale infrastructure deployments, including VPCs, EC2 instances, RDS/Aurora databases, and EKS clusters, using Terraform and Terragrunt.",
            "Built infrastructure as code (IaC) solutions with Terraform and Terragrunt to provision and manage cloud resources across AWS and Azure environments.",
            "Deployed and managed vendor-based applications on Amazon ECS using Fargate, ensuring high availability and scalability for critical workloads.",
            "Designed and implemented a Terraform blueprint for automating the deployment of Informatica in cluster mode on cloud infrastructure, ensuring high availability and scalability.",
            "Crafted user-data scripts within Terraform modules to configure Informatica services automatically upon instance initialization, optimizing setup time and reducing manual configuration errors.",
            "Automated ECS service provisioning and deployment pipelines using Terraform and CI/CD tools.",
            "Automated data ingestion from various sources into Databricks using AWS Lambda, S3, and EventBridge, enabling real-time processing and transformation.",
            "Architected a production RAG (Retrieval-Augmented Generation) pipeline for the data analytics team — AWS Glue jobs for ETL and structured metadata extraction from Aurora/RDS schemas, Amazon Titan Text Embeddings v2 for semantic vectorization, and Amazon Bedrock (Llama 3 70B) for LLM-powered inference — enabling analysts to query operational runbooks and data catalog in plain English without writing SQL.",
            "Led lift-and-shift migrations of legacy applications and vendor applications from on-premises data centers to AWS EC2 and EKS, ensuring minimal downtime and optimizing cloud resources for performance, scalability, and cost-efficiency.",
            "Developed extensive Terraform blueprints for provisioning AWS services such as EC2, EKS, API Gateway, Lambda, IAM, Security Groups, CloudWatch, ASG, SES, SQS, SNS, AMI, VPC Endpoints, ATF, S3, EBS, EFS, KMS, Secrets Manager, and RDS/Aurora databases.",
            "Developed Terraform modules to automate the creation, retention, and deletion of EC2 snapshots, ensuring data durability and rapid recovery options for critical EC2 instances.",
            "Created Terraform modules for automated backups of Elastic File System (EFS), integrating with AWS Backup services to provide consistent, point-in-time backups.",
            "Automated EBS snapshot management using AWS DLM (Data Lifecycle Manager) to enforce backup policies, retain critical data for compliance, and enable seamless disaster recovery.",
            "Integrated S3 as a cost-effective archival solution for storing large application logs and data backups, leveraging lifecycle policies for automated data tiering between Standard, Infrequent Access, and Glacier storage classes.",
            "Developed and maintained Helm charts for packaging and deploying complex applications to Kubernetes, simplifying application updates and lifecycle management.",
            "Monitored application health, logs, and infrastructure metrics using Datadog to improve observability and incident response.",
            "Integrated Datadog, Prometheus, and Grafana with application services deployed on AWS EC2, ECS, and EKS (Kubernetes), providing comprehensive monitoring and observability solutions.",
            "Collaborated closely with business users and stakeholders to understand their specific requirements and objectives, ensuring solutions developed were aligned with business needs.",
            "Supported critical production deployments, ensuring smooth rollouts of new features and updates with minimal downtime and disruption to business operations.",
        ],
        "environment": (
            "AWS, Terraform, Terragrunt, CFN, IaC, GitHub Actions, Aurora, RDS, Oracle, Jenkins, Splunk, CLI, GitHub, Auto Scaling, Maven, Docker, EKS, ECS, Fargate, Unix/Linux, EC2, VPC, Security Groups, IAM, Amazon S3, SNS, SQS, KMS, NACL, Secrets Manager, ACM, API Gateway, Lambda, CloudFront, CloudWatch, X-Ray, WAF, AWS PrivateLink, VPC endpoints, DynamoDB, Elastic Load Balancing, Amazon Bedrock, AWS Glue, Llama 3 70B, Amazon Titan Embeddings, RAG"
        ),
    },
    {
        "company": "Verizon",
        "role": "Senior Cloud DevOps Engineer / SRE",
        "period": "Sep 2023 – Oct 2024",
        "location": "Atlanta, GA",
        "description": (
            "Managed AWS account provisioning and infrastructure setup for Verizon Smart Family (VSF) products, ensuring scalable, secure cloud platforms supporting innovative family safety solutions."
        ),
        "bullets": [
            "Proficient in leveraging AWS services for product user onboarding, including setting up baseline services and configuring AWS accounts for application onboarding.",
            "Engaged in supporting cloud instances on AWS, managing Linux and Windows environments, with expertise in Elastic IP, Security Groups, and Virtual Private Cloud configurations.",
            "Demonstrated extensive experience configuring various AWS services, including EC2, VPC, Security Groups, Lambda, SNS, SQS, API Gateway, EBS, EFS, IAM, S3, RDS, DynamoDB, and Elastic Load Balancing across public and private subnets.",
            "Developed Jenkins shared libraries using Groovy scripts to support application and infrastructure deployments.",
            "Utilized CloudFormation for infrastructure as code, ensuring scalable and reliable AWS deployments.",
            "Developed Terraform modules and scripts to automate the creation and configuration of cloud infrastructure components, reducing manual intervention and minimizing errors.",
            "Proficient in using AWS CDK to define cloud infrastructure and applications using Python programming language.",
            "Developed universal CDK modules in Python to simplify managing AWS CDK updates, reducing the need for frequent manual adjustments.",
            "Orchestrated complex CI/CD workflows to automate builds, testing, and deployments across multiple environments.",
            "Led lift-and-shift migrations of legacy applications from on-premises data centers to AWS EC2 and EKS, ensuring minimal downtime and optimizing cloud resources for performance, scalability, and cost-efficiency.",
            "Integrated Jenkins with Git and GitLab CI/CD with repositories for automated CI/CD, improving development speed and efficiency.",
            "Led end-to-end setup of Amazon EKS clusters, including node group configuration, networking setup, and security policies.",
            "Automated the provisioning of worker nodes using Ansible, ensuring consistency and scalability.",
            "Managed node configurations, such as instance types, IAM roles, and auto-scaling groups, for efficient cluster management.",
            "Designed and deployed scalable big data processing pipelines on Amazon EMR, utilizing frameworks like Apache Spark and Hadoop to process large volumes of data efficiently.",
            "Deployed Ingress controllers for efficient and automated management of incoming traffic.",
            "Integrated Amazon API Gateway with various AWS services to host and manage APIs, enabling seamless communication and interaction between services.",
            "Developed a Lambda authorizer to validate JWT claims, ensuring secure authentication and authorization for API requests.",
            "Developed and maintained Docker images and containerized Go applications for deployment on cloud platforms such as AWS and Kubernetes.",
            "Involved in gathering requirements for application and system design as part of the DevOps process, working closely with development, operations, and business teams.",
            "Implemented enforcement of security scans as part of the CI/CD pipeline, ensuring mandatory security scans with gateway blocking non-compliant deployments.",
            "Designed and implemented custom Ansible roles to automate infrastructure provisioning, configuration management, and continuous integration workflows.",
            "Developed reusable Ansible roles for managing application deployments, environment setup, and system monitoring across Dev, QA, and Prod environments.",
            "Integrated Checkov scans into Jenkins and GitLab CI/CD pipelines for automatic pre-deployment checks, ensuring infrastructure changes adhere to security best practices and compliance standards.",
            "Leveraged Istio observability tools, such as distributed tracing, monitoring, and logging, integrated with Prometheus and Grafana, for deep visibility into service interactions.",
            "Configured Istio sidecar proxy to handle load balancing and automated scaling, ensuring consistent performance as demand fluctuates across the application.",
            "Implemented installation of infrastructure security tools such as Tenable and CrowdStrike on Amazon Machine Images (AMIs) to scan for vulnerabilities and enhance system security.",
            "Collaborated with cross-functional teams to integrate Artifactory, JIRA, and ServiceNow, enhancing artifact management, issue tracking, and service management.",
        ],
        "environment": (
            "AWS, Terraform, CFN, CDK, IaC, Bitbucket, Jenkins, Splunk, CLI, GitHub, Auto Scaling, Maven, Docker, EKS, OpenShift, Kubernetes, Unix/Linux, Django, Flask, EC2, VPC, Security Groups, IAM, Amazon S3, SNS, SQS, KMS, Secrets Manager, ACM, API Gateway, Lambda, CloudFront, CloudWatch, X-Ray, WAF, AWS PrivateLink, VPC endpoints, DynamoDB, RDS, Elastic Load Balancing"
        ),
    },
    {
        "company": "Bank of America",
        "role": "Senior DevOps Engineer / Platform Engineer",
        "period": "Oct 2020 – Sep 2023",
        "location": "Plano, TX",
        "description": (
            "GRA team platform and CI/CD support for regulatory workflows, enabling users to efficiently manage and execute compliance processes with robust, scalable infrastructure and seamless automation."
        ),
        "bullets": [
            "Engaged in all stages of the software development lifecycle (SDLC) including analysis, planning, development, testing, and post-production analysis using Agile and Scrum methodologies.",
            "Implemented multiple CI/CD pipelines using Jenkins and Ansible Tower for both on-premises and cloud-based software.",
            "Proficient in troubleshooting and automating deployments to web-based application servers like WebLogic and Apache Tomcat.",
            "Deployed and managed Kafka clusters with automated scaling, monitoring, and alerting, using Prometheus and Grafana to ensure high availability and quick issue resolution in production environments.",
            "Implemented CI/CD pipelines for Kafka deployments, automating configuration management, partitioning, and topic replication across multiple environments for consistent and reliable data streaming.",
            "Implemented real-time event streaming and messaging solutions using Kafka for distributed systems integration.",
            "Involved in identifying and mitigating continuous vulnerabilities across infrastructure and applications, working closely with security teams to implement automated security scans in CI/CD pipelines.",
            "Migrated on-premise application services to Azure Cloud with hands-on experience deploying, configuring, and managing infrastructure on Azure including Virtual Machines, Azure App Services, AKS, Azure Storage, and Azure Functions.",
            "Experienced in migrating non-containerized applications to containerized environments like Apache Airflow, Spring Boot, React, NodeJS, Flask, and Django apps.",
            "Managed UNIX environments on RHEL platforms, implementing security protocols including SUDO and Kerberos.",
            "Created and optimized CI/CD pipelines for automated build, test, and deployment in OpenShift, utilizing Jenkins and GitLab for efficient delivery.",
            "Provisioned and managed OpenShift namespaces and Persistent Volume Claims (PVCs) to organize and allocate storage dynamically for various workloads.",
            "Skilled in full setup and configuration of Linux environments, including NGINX, developer tools, uWSGI, Autosys, and SMTP services, optimizing system performance through ulimit adjustments.",
            "Led the migration of on-premises applications and databases to Azure, leveraging Azure Migrate to assess dependencies, plan capacity, and streamline transition with minimal downtime.",
            "Optimized application performance and monitoring using Azure Monitor, Application Insights, and Log Analytics, creating real-time dashboards and alerting systems.",
            "Implemented Azure Databricks for migrating on-premises data workflows to the cloud, replacing Hadoop clusters with scalable Spark-based data lakes.",
            "Developed Helm charts and Kubernetes manifest files to streamline deployment processes, enhance application scalability, and ensure high availability across multiple environments.",
            "Supported production releases through effective release management and implemented branching strategies, ensuring seamless integration and deployment workflows.",
            "Automated database deployment using Radical, Datical tools and Ansible playbooks.",
            "Proficient in shell scripting, Python, PowerShell, and YAML for automation and monitoring.",
            "Integrated Jenkins with SonarQube for code analysis and maintained CloudBees Jenkins pipelines for deployment.",
            "Utilized Ansible playbooks to automate the migration of batch processing and other jobs from cron to AutoSys, enhancing efficiency, reliability, and scalability.",
            "Utilized HashiCorp Vault and CyberArk services for secrets management.",
            "Experienced in debugging Hadoop-based applications and developing automation scripts for monitoring services health check.",
            "When enterprise observability platforms were not yet available on the engagement, built custom shell and Python monitoring: iterated application URLs for HTTP status-code health checks, hosted log directories behind NGINX so operators could browse logs in the browser, and scheduled Python CPU/system-metric collectors as Autosys jobs — before adopting Dynatrace, Prometheus, Grafana, and Splunk at scale.",
            "Supported and optimized Big Data platforms, managing and deploying Apache Spark clusters to enhance scalability and reliability for data processing pipelines.",
            "Automated deployment and monitoring of PySpark workflows, ensuring efficient resource utilization and minimizing downtime for critical Big Data applications.",
            "Integrated Dynatrace, Prometheus, and Grafana for comprehensive monitoring, alongside implementing Splunk logging across all services and establishing server monitoring via Splunk Dashboard.",
            "Facilitated daily scrum sessions to track ticket progress and resolve blockers, ensuring adherence to agile principles and timely delivery.",
            "Engaged with adoption customers to provide on-call support, swiftly addressing and resolving blockers, ensuring smooth transition and high satisfaction.",
        ],
        "environment": (
            "uWSGI, NGINX, Linux, Bitbucket, Git version control, IAM, Jenkins, Dynatrace, Splunk, CLI, GitHub, Auto Scaling, Maven, Docker, OpenShift, Kubernetes, Unix/Linux, Django, Flask, Toad, MySQL, Autosys"
        ),
    },
    {
        "company": "Anthem",
        "role": "DevOps Engineer",
        "period": "Feb 2020 – Aug 2020",
        "location": "Norfolk, VA",
        "description": (
            "Established scalable platform solutions enabling insurance teams to efficiently manage and maintain critical data, supporting delivery of superior healthcare services."
        ),
        "bullets": [
            "Supported cloud instances on AWS, managing Linux and Windows environments, and configuring services like EC2, S3, and Elastic Load Balancing.",
            "Troubleshot EC2 instances, S3 buckets, VPC, and Elastic Load Balancer, ensuring system integrity and reliability.",
            "Built automation scripts for scheduling Auto Scaling load balancer and conducted Jenkins CI/CD pipeline jobs for end-to-end automation.",
            "Implemented continuous integration web hooks and workflows around Jenkins to automate development and test environments.",
            "Collaborated in automating AWS infrastructure via Terraform and Jenkins, and software configuration using Ansible playbook.",
            "Orchestrated containerization of multiple apps using Docker engines in virtualized platforms.",
            "Utilized Kubernetes and Helm charts for deploying, scaling, and managing Docker containers in a fault-tolerant infrastructure.",
            "Engineered Splunk for log analysis and maintained heterogeneous environments.",
            "Provided 24/7 major incident management and supported change management for network infrastructure.",
            "Configured Cisco and F5 load balancers and utilized logging/monitoring tools like CloudWatch and Nagios for system monitoring.",
        ],
        "environment": (
            "AWS, Apache Tomcat, Linux, Git version control, VPC, EC2, ELK, S3, Route53, EBS, IAM, ELB, Jenkins, CloudFormation, AppDynamics, Helm charts, CLI, GitHub, Auto Scaling, Maven, Docker, Kubernetes, Unix/Linux, Nagios"
        ),
    },
    {
        "company": "Inovus IT Services",
        "role": "Build & Release Engineer",
        "period": "May 2017 – Jul 2018",
        "location": "India",
        "description": (
            "Inovus IT Services integrated IT-backed multi-modal network allows end-to-end supply chain solutions specific to varied business requirements."
        ),
        "bullets": [
            "Set up an automation environment for the Application team and facilitated build and release automation.",
            "Deployed Java/J2EE applications to web servers in Agile CI environments, automating the entire process.",
            "Implemented CI/CD pipelines using Jenkins and Ansible for on-premises and cloud-based software.",
            "Deployed Java applications on Kubernetes Clusters via Jenkins CI/CD integration and resolved deployment issues.",
            "Utilized Maven for building Java projects and managing build artifacts.",
            "Managed release cycles across Development, Integration, QA, UAT, and Production environments.",
            "Built and deployed artifacts to Development, Integration, and QA Environments.",
            "Supported Linux Containers and WebSphere applications for middleware integration.",
            "Provisioned multi-tier applications in OpenStack cloud using Ansible.",
            "Administered Jenkins for managing Build, Test, and Deploy processes, utilizing SVN/GIT for version control.",
            "Migrated applications to Microsoft Azure Cloud Platform, implementing IaaS and PaaS solutions.",
            "Implemented network traffic rules and Access Control Lists (ACL) in Azure Virtual Network.",
            "Developed UNIX and Perl scripts for manual code deployment and notification.",
            "Executed DB Scripts (DMLs) with dependencies on Oracle DB.",
        ],
        "environment": (
            "Java, Maven, GIT, Jenkins, Linux, Solaris, WebSphere, Shell scripting, Nexus, Tomcat, Confluence, JIRA, ANT, Azure, Perl, Oracle DB"
        ),
    },
]


RESUME_EDUCATION = [
    {
        "institution": "Southern Arkansas University",
        "degree": "Master of Science, Computer Information Science",
        "period": "Aug 2018 – Dec 2019",
        "detail": "Arkansas, USA",
    },
]

RESUME_CERTIFICATIONS = [
    {"name": "AWS Certified DevOps Engineer — Professional", "issuer": "Amazon Web Services", "year": "Professional"},
]

RESUME_STATS = [
    {"label": "Experience", "value": "8+", "sub": "Production SRE & DevOps"},
    {"label": "Enterprise", "value": "6", "sub": "Fortune-scale clients"},
    {"label": "Certification", "value": "AWS", "sub": "DevOps Engineer — Pro"},
    {"label": "Portfolio", "value": "Live", "sub": "Personal SRE bot · R&D"},
]

# Observability career arc — lead with DIY tooling when recruiters ask about monitoring/APM/logging.
RESUME_OBSERVABILITY_JOURNEY = {
    "title": "Observability journey — custom shell/Python tooling to enterprise platforms",
    "lead": (
        "When I started on early enterprise platform work, we often did not have access to full commercial "
        "observability suites — so my observability background began by building monitoring myself."
    ),
    "diy_phase": [
        "Shell and Python health checks: iterated through application URL endpoints and used HTTP status codes "
        "to determine whether services were healthy — lightweight, repeatable checks before APM was in place.",
        "Log visibility via NGINX: hosted application log directories behind NGINX so operators and support teams "
        "could browse and tail logs directly in the browser when centralized log platforms were not available.",
        "Infrastructure metrics with Python + Autosys: wrote Python scripts to collect CPU, memory, and system "
        "metrics on RHEL/Linux servers and scheduled them as Autosys batch jobs for recurring infra observability.",
    ],
    "enterprise_phase": [
        "Bank of America: Dynatrace, Prometheus, and Grafana; Splunk logging and dashboards; Kafka monitoring; "
        "Autosys automation for batch and monitoring jobs.",
        "Anthem: Splunk log analysis; CloudWatch and Nagios; ELK in the environment stack.",
        "Verizon: Istio observability with Prometheus and Grafana; distributed tracing for service interactions.",
        "Toyota: Datadog, Prometheus, and Grafana across EC2, ECS, and EKS workloads.",
        "Citigroup: Prometheus and Grafana on EKS; Elasticsearch with Netcool deduplication feeding ServiceNow INC auto-creation.",
    ],
    "recruiter_hook": (
        "For hiring managers: I did not inherit observability — I built it from shell scripts, NGINX log access, "
        "and Autosys-scheduled Python metrics, then scaled into Prometheus, Dynatrace, Splunk, and ELK at "
        "Fortune-scale clients. That builder mindset helps me design monitoring that works in constrained "
        "environments, not just operate someone else's dashboard."
    ),
    "primary_employer": "Bank of America",
    "skills": [
        "observability",
        "monitoring",
        "health checks",
        "shell scripting",
        "python",
        "nginx",
        "autosys",
        "prometheus",
        "grafana",
        "splunk",
        "dynatrace",
        "elk",
        "logging",
        "metrics",
        "apm",
    ],
}

# SRE behavioral interview stories — STAR format for recruiter RAG (verified Naresh narratives).
RESUME_BEHAVIORAL_STORIES = [
    {
        "question": "Tell me about a time you dealt with a major production incident.",
        "theme": "production_incident",
        "skills": [
            "incident response",
            "performance troubleshooting",
            "nginx",
            "load balancer",
            "flask",
            "tcp",
            "vendor escalation",
            "firmware",
            "production support",
        ],
        "title": "File upload performance degradation — Broadcom load balancer TCP bug",
        "situation": (
            "Critical production incident: file upload performance degradation impacting nearly 50% of users. "
            "Uploads were significantly slower in production than in lower environments, with repeated escalations."
        ),
        "action": (
            "Could not reproduce in lower environments. Built a lightweight Flask test service mirroring production "
            "architecture — Nginx, Broadcom load balancer, and NAS mount. Systematically removed one network hop at a "
            "time to isolate the Broadcom load balancer as the source of delay. Collected clear performance data and "
            "shared with the vendor."
        ),
        "result": (
            "Vendor confirmed a recent patch introduced a TCP performance bug visible only under production traffic "
            "patterns; lower environments ran older firmware. After the fix, upload performance returned to normal. "
            "Implemented quarterly firmware refresh cycles across environments to prevent version drift."
        ),
    },
    {
        "question": "Tell me about a time when your monitoring/alerting failed to catch a production issue.",
        "theme": "observability_gap",
        "skills": [
            "observability",
            "monitoring",
            "alerting",
            "grafana",
            "prometheus",
            "micrometer",
            "java",
            "memory leak",
            "heap",
            "gc",
            "soak testing",
        ],
        "title": "Undetected Java memory leak — improved heap and GC alerting",
        "situation": (
            "Slow memory leak in a Java Spring Boot service went undetected for several days. Monitoring focused on "
            "CPU, error rates, and disk — not heap memory trending or saturation alerts."
        ),
        "action": (
            "Issue surfaced when customers reported gradual performance degradation; service was heavily impacted "
            "with frequent Full GCs. Took ownership and improved observability: heap usage trends, GC frequency, and "
            "old-generation memory alerts in Grafana using Micrometer + Prometheus. Introduced regular soak tests."
        ),
        "result": (
            "Caught similar memory leaks early before customer impact. Lesson: good observability means monitoring "
            "the right signals, not just having many alerts."
        ),
    },
    {
        "question": "Tell me about a time you had a conflict with the development team.",
        "theme": "cross_team_collaboration",
        "skills": [
            "hashicorp vault",
            "secrets management",
            "security",
            "devops collaboration",
            "deployment pipeline",
            "container startup",
            "credentials",
        ],
        "title": "Hardcoded credentials vs Vault — pragmatic security win without dev rework",
        "situation": (
            "Sensitive credentials (database passwords and API keys) were hardcoded in application.properties and "
            "committed to Git. Recommended moving secrets to HashiCorp Vault and reading via environment variables."
        ),
        "action": (
            "Development team disagreed — no bandwidth for code changes. Instead of pushing harder, created a shell "
            "script that fetches secrets from Vault during container startup and injects them as environment variables. "
            "Updated the deployment pipeline to use this script."
        ),
        "result": (
            "Significantly improved security without requiring immediate dev code changes. Team appreciated the "
            "approach; migrated to a cleaner Vault integration later."
        ),
    },
    {
        "question": "Tell me about a challenge involving network isolation or cloud security architecture.",
        "theme": "network_isolation",
        "skills": [
            "aws privatelink",
            "kubernetes networkpolicies",
            "eks",
            "mongodb atlas",
            "network isolation",
            "multi-tenant",
            "jenkins",
            "cloud security",
            "vpc",
        ],
        "title": "Multi-tenant Jenkins on EKS — MongoDB Atlas isolation via AWS PrivateLink",
        "situation": (
            "Multiple teams shared a Jenkins platform running on AWS EKS, each with their own dedicated "
            "Jenkins controller deployed via Jenkins Operator in separate namespaces. Each controller needed "
            "to connect to its own MongoDB Atlas cluster. The hard requirement was strict network isolation — "
            "no controller should be able to reach another team's database."
        ),
        "action": (
            "Evaluated VPC peering but ruled it out because it would expose entire VPC CIDRs. Chose AWS "
            "PrivateLink (Private Endpoints) instead — created separate PrivateLink endpoints for each "
            "MongoDB Atlas cluster and applied Kubernetes NetworkPolicies in each namespace to restrict "
            "outbound traffic so only the respective Jenkins controller could reach its own Atlas endpoint. "
            "This enforced isolation at both the network layer (PrivateLink) and the Kubernetes layer (NetworkPolicies)."
        ),
        "result": (
            "Successfully achieved strict network isolation between teams — no cross-team database access was "
            "possible. Trade-off: managing multiple PrivateLink endpoints increased operational overhead and cost. "
            "The experience reinforced my understanding of the balance between security, isolation, and operational "
            "complexity in multi-tenant cloud environments."
        ),
    },
    {
        "question": "Tell me about a time you improved secret management or eliminated application downtime during secret rotation.",
        "theme": "secrets_management",
        "skills": [
            "hashicorp vault",
            "vault agent injector",
            "openshift",
            "kubernetes",
            "secrets management",
            "secret rotation",
            "sidecar injector",
            "vm to container migration",
            "zero downtime",
        ],
        "title": "Vault Agent Sidecar Injector — zero-downtime secret rotation during OpenShift migration",
        "situation": (
            "During a migration of applications from VMs to OpenShift, we hit a recurring problem with secret "
            "management. The applications relied on a custom HashiCorp Vault shell script to fetch secrets at "
            "startup — it frequently failed due to network timeouts and token expiry. Worse, every time secrets "
            "were rotated, we had to restart the application pods to pick up new values, causing unnecessary downtime."
        ),
        "action": (
            "I implemented the Vault Agent Injector (Sidecar Injector pattern) in OpenShift. The Vault Agent "
            "sidecar container was injected automatically into each pod via annotations, fetching and renewing "
            "secrets directly from Vault and writing them as environment variables or files into a shared volume. "
            "This replaced the brittle custom script entirely and enabled dynamic secret rotation — the sidecar "
            "handled lease renewal transparently without any application restarts."
        ),
        "result": (
            "Eliminated the unreliable custom script, removed all application downtime caused by secret rotation, "
            "and made secret management fully automated and auditable. Teams no longer needed manual intervention "
            "during rotation cycles. The pattern became the standard approach for all subsequent VM-to-OpenShift "
            "migrations in the engagement."
        ),
    },
]

RESUME_ACHIEVEMENTS = [
    {
        "title": "IAM & zero-trust at Citigroup",
        "detail": (
            "Migrating Ping Identity stack to AWS EKS with ArgoCD GitOps, Karpenter scaling, "
            "and SOX-compliant audit tooling."
        ),
    },
    {
        "title": "RAG pipeline & data platform at Toyota TMNA",
        "detail": (
            "Architected a production RAG pipeline for the data analytics team — AWS Glue ETL for Aurora/RDS metadata ingestion, "
            "Amazon Titan Text Embeddings v2 for semantic search, and Amazon Bedrock (Llama 3 70B) for LLM inference. "
            "Built reusable Terraform blueprints for Informatica cluster deployments, ECS/Fargate ETL pipelines, "
            "Aurora/RDS provisioning, and Datadog observability."
        ),
    },
    {
        "title": "Observability & incident automation",
        "detail": (
            "Started with DIY shell/Python monitoring (URL health checks, NGINX log browsing, Autosys metrics) "
            "before scaling to Prometheus, Grafana, Splunk, Dynatrace, and ELK at Fortune-scale clients."
        ),
    },
    {
        "title": "AI-enabled SRE (this demo)",
        "detail": (
            "Built SRE AI Copilot — LangGraph agents, RAG runbooks, Kafka/SSE feeds, "
            "human-gated kubectl remediation, audit trail."
        ),
    },
]

TECHNICAL_HIGHLIGHTS = [
    {
        "title": "8+ years · AWS DevOps Pro · multi-cloud SRE",
        "detail": (
            "8+ years across Citi, BofA, Verizon, Toyota, and Anthem — AWS DevOps Engineer Professional certified. "
            "Production Kubernetes on EKS, AKS, and OpenShift; Terraform, CDK, and Terragrunt at Fortune-scale regulated workloads."
        ),
    },
    {
        "title": "EKS + ArgoCD GitOps at Citigroup (CISO org)",
        "detail": (
            "Migrating Ping Identity IAM stack (PingFederate, PingAccess, PingDirectory) to AWS EKS with Terraform. "
            "ArgoCD GitOps CD with automated sync, drift detection, and rollback; Karpenter node scaling; Tekton/Harness CI/CD."
        ),
    },
    {
        "title": "Kafka event streaming at Bank of America",
        "detail": (
            "Deployed and operated Kafka clusters with CI/CD automation, topic replication, and Prometheus/Grafana monitoring. "
            "Platform engineering for regulatory (GRA) workflows on OpenShift and Azure AKS."
        ),
    },
    {
        "title": "Observability at enterprise scale",
        "detail": (
            "Prometheus, Grafana, Splunk, Datadog, Dynatrace across Citi, BofA, Verizon, and Toyota. "
            "ServiceNow INC automation, Elasticsearch + Netcool event deduplication, SOX-compliant audit trails."
        ),
    },
    {
        "title": "SRE AI Copilot — production-grade AI ops demo",
        "detail": (
            "LangGraph 7-agent orchestration (Triage, Chat, Runbook, RCA, Executor, Supervisor, Learning) with Redis/SQLite checkpointing. "
            "Kafka durable fan-out + SSE real-time feeds; ChromaDB RAG runbooks; human-gated kubectl remediation; append-only audit trail."
        ),
    },
    {
        "title": "245 automated tests · GitHub Actions CD",
        "detail": (
            "Full test suite covering agents, RAG, observability API, audit, and security middleware. "
            "GitOps-ready K8s manifests; GitHub Actions CD to Minikube; architecture docs at /docs."
        ),
    },
]

TECH_STACK_COMPARISON = {
    "enterprise": [
        {"category": "Kubernetes", "tools": "EKS · AKS · OpenShift · Helm · Karpenter · Istio"},
        {"category": "GitOps / CI/CD", "tools": "ArgoCD · Tekton · Harness · Jenkins · GitHub Actions"},
        {"category": "IaC", "tools": "Terraform · Terragrunt · AWS CDK · CloudFormation"},
        {"category": "Observability", "tools": "Prometheus · Grafana · Splunk · Datadog · Dynatrace · ELK"},
        {"category": "Event streaming", "tools": "Kafka · ServiceNow INC · Elasticsearch · Netcool"},
        {"category": "Secrets / compliance", "tools": "Vault · CyberArk · Checkov · SOX audit"},
    ],
    "demo": [
        {"category": "Kubernetes", "tools": "Minikube · 7 synthetic microservices · kubectl remediation"},
        {"category": "GitOps / CI/CD", "tools": "GitHub Actions CD · K8s manifests · drift-ready ArgoCD patterns"},
        {"category": "IaC", "tools": "Terraform-style K8s YAML · docker-compose · Makefile automation"},
        {"category": "Observability", "tools": "Prometheus · Loki · AlertManager · anomaly watcher · SSE fleet health"},
        {"category": "Event streaming", "tools": "Kafka (aiokafka) · SSE fallback · Redis dedup · live events API"},
        {"category": "AI / agents", "tools": "LangGraph 7 agents · Ollama · ChromaDB RAG · FastAPI · audit trail"},
    ],
}

RECRUITER_SUGGESTED_QUESTIONS = [
    "Walk me through your observability journey — from DIY scripts to Prometheus and Splunk",
    "Walk me through BofA like I'm your hiring manager with coffee",
    "If I'm hiring for Citi-like IAM work, why you and not the next resume?",
    "Okay but seriously — what broke in prod and how did you fix it?",
    "Tell me about your SRE AI Copilot (portfolio project)",
    "What's the most 'only an SRE would care' thing you've automated?",
    "Be honest: Ansible or Terraform — which one saved you at 2 AM?",
    "No jargon — explain EKS like I'm on LinkedIn scrolling fast",
    "What's one thing on your resume you're most proud of?",
    "I'd love to hear more about your Citi IAM work",
    "Compare your observability stack experience vs this demo platform",
    "Summarize your Kafka and event-streaming experience at BofA",
    "What do colleagues say about working with you?",
    "How do GitOps and IaC show up across your client engagements?",
    "What's your on-call war story — the one that actually taught you something?",
    "Why are you a strong SRE + AI candidate?",
    "What did you do at Bank of America and Verizon?",
    "Which cloud and Kubernetes skills are you strongest in?",
]

RECRUITER_FOLLOW_UP_POOLS = {
    "employer": [
        "What was your biggest win at {employer}?",
        "How did {employer} compare to your other clients?",
        "What would your {employer} manager say you brought to the team?",
        "Walk me through a typical week on the {employer} platform team",
        "What production headaches did you solve at {employer}?",
        "I'd love a deeper dive — what made {employer} work unique?",
    ],
    "employerCompare": [
        "How does Citi IAM work compare to what you did at BofA?",
        "Verizon vs Citi — where did you lean harder into Kubernetes?",
        "Which client taught you the most about on-call discipline?",
        "If you had to pick one employer to repeat, which and why?",
    ],
    "compareEmployers": [
        "Compare your Verizon and BofA platform work side by side",
        "Which employer had the gnarliest incident culture?",
        "Where did you ship the most meaningful automation?",
    ],
    "skill": [
        "Walk me through your observability journey — how did you start before Prometheus?",
        "Where have you actually used that in a client environment?",
        "No jargon — explain that skill like I'm on LinkedIn scrolling fast",
        "Be honest: Ansible or Terraform — which one saved you at 2 AM?",
        "What's the most 'only an SRE would care' thing you've automated?",
        "How does your enterprise experience compare to this demo platform?",
        "Which client engagement best showcases that skill?",
    ],
    "skillAtClient": [
        "Show me that skill in action at Citi or BofA",
        "Did you use that more at Verizon or Toyota?",
        "What's one metric or outcome that skill improved?",
    ],
    "incident": [
        "Okay but seriously — what broke in prod and how did you fix it?",
        "Walk me through a ServiceNow INC you actually owned",
        "What's your on-call war story — the one that actually taught you something?",
        "How did observability help you catch something before users noticed?",
        "What would you do differently on that incident today?",
        "How do you balance speed vs safety during a production fire?",
    ],
    "portfolio": [
        "How is LangGraph used in your SRE AI Copilot?",
        "Walk me through the Command Center live triage flow",
        "What's human-gated vs fully automated in the demo?",
        "How does this portfolio project map to enterprise SRE work?",
    ],
    "portfolioDemo": [
        "Want to see the architecture docs for this project?",
        "What would you demo in a 10-minute interview loop?",
        "How many agents are in the LangGraph orchestration?",
    ],
    "recommendation": [
        "What do colleagues say about working with you?",
        "How do you collaborate when prod is on fire?",
        "What's your reputation on-call — calm or caffeinated?",
        "Tell me about a time you mentored someone through a tough deploy",
    ],
    "generic": [
        "What's one thing on your resume you're most proud of?",
        "Why are you a strong SRE + AI candidate?",
        "Which cloud and Kubernetes skills are you strongest in?",
        "How do GitOps and IaC show up across your client engagements?",
        "What should I ask next that most recruiters miss?",
    ],
    "icebreaker": [
        "If I'm hiring for Citi-like IAM work, why you and not the next resume?",
        "Walk me through BofA like I'm your hiring manager with coffee",
        "What's the most underrated tool on your resume?",
        "Convince me you'd survive a 3 AM Sev-1 with grace",
    ],
}

DEMO_METRICS = [
    {"label": "LangGraph agents", "value": "7"},
    {"label": "Synthetic microservices", "value": "7"},
    {"label": "Automated tests", "value": "245+"},
]

RESUME_LINKS = [
    {"label": "LinkedIn", "url": "https://linkedin.com/in/nareshvusiri", "icon": "linkedin"},
    {"label": "GitHub — SRE AI Copilot", "url": "https://github.com/nareshram5855/sre-ai-copilot", "icon": "github"},
    {"label": "Architecture Docs", "url": "/docs", "icon": "docs", "internal": True},
    {"label": "Live Demo", "url": "/", "icon": "link", "internal": True},
    {"label": "App Profiler", "url": "/profiler", "icon": "link", "internal": True},
]
