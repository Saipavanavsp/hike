"""Generate the labelled training set for the role-category classifier.

The texts are synthetic resume summaries built from per-category templates with a fixed
random seed, plus cross-category "noise" skills so the task is not trivially separable
(full-stack in particular overlaps heavily with frontend and backend).

Run from backend/:  python -m seed.build_classifier_data
Output: app/ml/data/classifier_train.json (committed).
"""

import json
import random
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "app" / "ml" / "data" / "classifier_train.json"
PER_CATEGORY = 40

COMMON = ["Git", "Agile", "Jira", "SQL", "Docker", "Linux", "Scrum", "Code Review", "REST APIs"]

CATS = {
    "backend": {
        "titles": [
            "Backend Engineer",
            "Software Engineer - Backend",
            "Python Developer",
            "Java Developer",
            "Golang Engineer",
            "API Developer",
            "Platform Engineer (APIs)",
        ],
        "skills": [
            "Python",
            "Django",
            "FastAPI",
            "Flask",
            "Java",
            "Spring Boot",
            "Go",
            "Node.js",
            "PostgreSQL",
            "MySQL",
            "Redis",
            "Kafka",
            "RabbitMQ",
            "Celery",
            "gRPC",
            "Microservices",
            "Hibernate",
            "MongoDB",
            "System Design",
            "GraphQL",
        ],
        "phrases": [
            "designed and scaled REST and gRPC services",
            "owned payment and ledger APIs",
            "optimised slow SQL queries and added indexes",
            "built event-driven microservices",
            "reduced API p95 latency",
            "wrote background workers and job queues",
            "designed database schemas and migrations",
            "implemented caching with Redis",
        ],
    },
    "frontend": {
        "titles": [
            "Frontend Engineer",
            "UI Developer",
            "React Developer",
            "Frontend Developer",
            "Software Engineer - Web UI",
            "Angular Developer",
        ],
        "skills": [
            "React",
            "TypeScript",
            "JavaScript",
            "Next.js",
            "Redux",
            "Vue.js",
            "Angular",
            "HTML",
            "CSS",
            "Tailwind CSS",
            "Sass",
            "Webpack",
            "Vite",
            "Storybook",
            "Jest",
            "Figma",
            "Web Accessibility",
            "Responsive Design",
            "Material UI",
        ],
        "phrases": [
            "built a component library and design system",
            "improved Core Web Vitals",
            "implemented pixel-perfect responsive layouts from Figma",
            "migrated a large codebase to TypeScript",
            "built accessible forms and tables",
            "managed client state with Redux",
            "worked closely with designers on UI",
        ],
    },
    "fullstack": {
        "titles": [
            "Full Stack Developer",
            "Full-Stack Engineer",
            "Software Engineer (Full Stack)",
            "MERN Stack Developer",
            "Product Engineer",
        ],
        "skills": [
            "React",
            "Node.js",
            "Express",
            "MongoDB",
            "TypeScript",
            "Next.js",
            "PostgreSQL",
            "Django",
            "JavaScript",
            "GraphQL",
            "Redux",
            "AWS",
            "Tailwind CSS",
            "Prisma",
            "FastAPI",
            "Vue.js",
        ],
        "phrases": [
            "shipped end-to-end features across frontend and backend",
            "built both the React client and the Node.js API",
            "owned features from database schema to UI",
            "built MERN stack applications",
            "developed dashboards and the APIs behind them",
            "deployed full stack apps on AWS and Vercel",
        ],
    },
    "data_ml": {
        "titles": [
            "Data Scientist",
            "Machine Learning Engineer",
            "ML Engineer",
            "Data Analyst",
            "Data Engineer",
            "NLP Engineer",
            "AI Engineer",
        ],
        "skills": [
            "Python",
            "Pandas",
            "NumPy",
            "scikit-learn",
            "PyTorch",
            "TensorFlow",
            "NLP",
            "Machine Learning",
            "Deep Learning",
            "Apache Spark",
            "Airflow",
            "Tableau",
            "Power BI",
            "Statistics",
            "XGBoost",
            "Hugging Face",
            "LLMs",
            "MLflow",
            "Computer Vision",
            "dbt",
            "BigQuery",
        ],
        "phrases": [
            "trained and deployed classification models",
            "built feature pipelines in Spark",
            "ran A/B tests and statistical analysis",
            "fine-tuned transformer models",
            "built ETL pipelines and data warehouses",
            "created dashboards for business teams",
            "improved model accuracy with feature engineering",
            "built a RAG prototype with LLMs",
        ],
    },
    "devops": {
        "titles": [
            "DevOps Engineer",
            "Site Reliability Engineer",
            "Cloud Engineer",
            "Platform Engineer",
            "Infrastructure Engineer",
            "SRE",
        ],
        "skills": [
            "Kubernetes",
            "Docker",
            "Terraform",
            "AWS",
            "Azure",
            "Google Cloud",
            "Jenkins",
            "GitHub Actions",
            "Ansible",
            "Prometheus",
            "Grafana",
            "Helm",
            "Linux",
            "Bash",
            "CI/CD",
            "Argo CD",
            "Nginx",
            "Datadog",
            "Python",
        ],
        "phrases": [
            "managed Kubernetes clusters in production",
            "wrote Terraform modules for AWS",
            "built CI/CD pipelines",
            "set up monitoring and alerting with Prometheus",
            "reduced cloud costs",
            "handled on-call and incident response",
            "automated server configuration with Ansible",
            "improved deployment reliability",
        ],
    },
    "mobile": {
        "titles": [
            "Android Developer",
            "iOS Developer",
            "Mobile Engineer",
            "Flutter Developer",
            "React Native Developer",
            "Mobile App Developer",
        ],
        "skills": [
            "Kotlin",
            "Android",
            "Jetpack Compose",
            "Swift",
            "iOS",
            "SwiftUI",
            "Flutter",
            "Dart",
            "React Native",
            "Firebase",
            "Retrofit",
            "Xcode",
            "MVVM",
            "Kotlin Coroutines",
            "Gradle",
            "UIKit",
            "Core Data",
        ],
        "phrases": [
            "published apps on the Play Store and App Store",
            "built offline-first mobile apps",
            "reduced app crash rate",
            "implemented push notifications",
            "built screens in Jetpack Compose",
            "optimised app startup time",
            "shipped a cross-platform Flutter app",
        ],
    },
    "qa": {
        "titles": [
            "QA Engineer",
            "SDET",
            "Test Automation Engineer",
            "Quality Analyst",
            "QA Automation Engineer",
            "Software Test Engineer",
        ],
        "skills": [
            "Selenium",
            "Cypress",
            "Playwright",
            "TestNG",
            "JUnit",
            "Postman",
            "JMeter",
            "Appium",
            "Test Automation",
            "Manual Testing",
            "API Testing",
            "Cucumber",
            "Java",
            "Python",
            "Regression Testing",
            "Performance Testing",
            "Jira",
        ],
        "phrases": [
            "wrote automated regression suites",
            "built API test frameworks",
            "performed load testing with JMeter",
            "maintained test plans and test cases",
            "reported and tracked defects in Jira",
            "set up tests in the CI pipeline",
            "automated mobile tests with Appium",
        ],
    },
}


def make_sample(rng: random.Random, cat: str) -> str:
    c = CATS[cat]
    title = rng.choice(c["titles"])
    years = rng.choice([1, 2, 2, 3, 3, 4, 5, 6, 8])
    skills = rng.sample(c["skills"], k=rng.randint(4, 8))
    skills += rng.sample(COMMON, k=rng.randint(1, 3))
    # Noise: a skill from another category, as real resumes often have.
    other = rng.choice([k for k in CATS if k != cat])
    skills.append(rng.choice(CATS[other]["skills"]))
    rng.shuffle(skills)
    phrases = rng.sample(c["phrases"], k=rng.randint(2, 3))
    return (
        f"{title} with {years} years of experience. "
        f"{phrases[0].capitalize()}; {'; '.join(phrases[1:])}. "
        f"Skills: {', '.join(skills)}."
    )


def main() -> None:
    rng = random.Random(2026)
    rows = [
        {"text": make_sample(rng, cat), "label": cat} for cat in CATS for _ in range(PER_CATEGORY)
    ]
    rng.shuffle(rows)
    OUT.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"wrote {len(rows)} samples to {OUT}")


if __name__ == "__main__":
    main()
