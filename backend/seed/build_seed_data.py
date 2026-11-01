"""Build the seed dataset: 20 fictional companies, 50 jobs, 20 resumes and eval labels.

All companies and people are invented. Output (committed):
  seed/data/companies.json, jobs.json, resumes.json, eval_pairs.json
  seed/resumes/*.pdf  (rendered with reportlab)

Run from backend/:  python -m seed.build_seed_data
"""

import json
import random
from pathlib import Path

from seed.render import render_pdf

HERE = Path(__file__).parent
DATA = HERE / "data"
PDF_DIR = HERE / "resumes"

COMPANIES = [
    (
        "Nimbus Ledger",
        "Fintech",
        "201-500",
        "Bengaluru",
        "Nimbus Ledger makes accounting and GST compliance software for 40,000 small businesses.",
    ),
    (
        "Tidepool Labs",
        "Developer tools",
        "51-200",
        "Pune",
        "Tidepool Labs builds API monitoring and usage-based billing tools for engineering teams.",
    ),
    (
        "Kestrel Systems",
        "Logistics software",
        "201-500",
        "Hyderabad",
        "Kestrel Systems plans delivery routes for grocery and pharmacy fleets in 30 cities.",
    ),
    (
        "Orchid Analytics",
        "Analytics consulting",
        "51-200",
        "Pune",
        "Orchid Analytics builds forecasting and reporting systems for retail and FMCG clients.",
    ),
    (
        "Banyan Cloud",
        "Cloud infrastructure",
        "501-1000",
        "Bengaluru",
        "Banyan Cloud runs managed Kubernetes and databases for Indian startups.",
    ),
    (
        "Saffron Pay",
        "Payments",
        "501-1000",
        "Bengaluru",
        "Saffron Pay processes UPI and card payments for 2 lakh merchants.",
    ),
    (
        "Monsoon Mobility",
        "Mobility",
        "1001-5000",
        "Hyderabad",
        "Monsoon Mobility operates an electric ride-hailing fleet across South India.",
    ),
    (
        "Ironwood Health",
        "Healthtech",
        "201-500",
        "Chennai",
        "Ironwood Health builds clinic management and e-prescription software for 6,000 clinics.",
    ),
    (
        "Quillstack",
        "Publishing SaaS",
        "51-200",
        "Bengaluru",
        "Quillstack is a remote-first company that builds a publishing platform for newsrooms.",
    ),
    (
        "Peregrine Freight",
        "Freight marketplace",
        "201-500",
        "Chennai",
        "Peregrine Freight matches shippers with truck carriers and handles tracking and payments.",
    ),
    (
        "Kiln Energy",
        "Energy analytics",
        "51-200",
        "Pune",
        "Kiln Energy helps factories cut power bills using smart meter data.",
    ),
    (
        "Cobalt Harbor",
        "Cybersecurity",
        "201-500",
        "Hyderabad",
        "Cobalt Harbor sells threat detection for mid-size banks and insurers.",
    ),
    (
        "Jamun Retail Tech",
        "Retail software",
        "501-1000",
        "Bengaluru",
        "Jamun Retail Tech makes point-of-sale and inventory software used by 4,000 stores.",
    ),
    (
        "Vantage Agro",
        "Agritech",
        "51-200",
        "Hyderabad",
        "Vantage Agro gives farmers crop advisories and market prices in nine languages.",
    ),
    (
        "Granite Byte",
        "Product engineering services",
        "1001-5000",
        "Chennai",
        "Granite Byte builds and tests software for banking and retail clients.",
    ),
    (
        "Halcyon Learning",
        "Edtech",
        "201-500",
        "Bengaluru",
        "Halcyon Learning runs live and recorded courses for 3 million school students.",
    ),
    (
        "Neem Insure",
        "Insurtech",
        "201-500",
        "Pune",
        "Neem Insure sells health and motor insurance online and through 8,000 agents.",
    ),
    (
        "Sandal Studio",
        "E-commerce platform",
        "51-200",
        "Bengaluru",
        "Sandal Studio lets small brands build online stores without code.",
    ),
    (
        "Tarang Media",
        "Streaming",
        "501-1000",
        "Hyderabad",
        "Tarang Media streams regional films, series and live cricket to 12 million users.",
    ),
    (
        "Zephyr Grid",
        "IoT / smart buildings",
        "201-500",
        "Chennai",
        "Zephyr Grid connects HVAC, lighting and meters in 900 commercial buildings.",
    ),
]

# (company, title, category, location, remote, exp_min, exp_max, skills, focus)
JOBS = [
    (
        0,
        "Backend Engineer (Python)",
        "backend",
        "Bengaluru",
        "hybrid",
        2,
        4,
        ["Python", "Django", "PostgreSQL", "Redis", "Celery", "Docker", "REST APIs"],
        "the invoicing and bank reconciliation APIs",
    ),
    (
        5,
        "Senior Backend Engineer, Payments",
        "backend",
        "Bengaluru",
        "hybrid",
        5,
        8,
        ["Java", "Spring Boot", "PostgreSQL", "Apache Kafka", "Microservices", "AWS"],
        "the payment authorisation and settlement services",
    ),
    (
        2,
        "Golang Engineer, Routing APIs",
        "backend",
        "Hyderabad",
        "onsite",
        3,
        6,
        ["Go", "gRPC", "PostgreSQL", "Redis", "Kubernetes"],
        "the route optimisation and dispatch APIs",
    ),
    (
        8,
        "Backend Engineer - Node.js",
        "backend",
        "Remote",
        "remote",
        2,
        5,
        ["Node.js", "TypeScript", "Express", "MongoDB", "Redis", "AWS"],
        "the publishing and webhook delivery pipeline",
    ),
    (
        14,
        "Associate Software Engineer (Backend)",
        "backend",
        "Chennai",
        "onsite",
        0,
        2,
        ["Java", "Spring Boot", "MySQL", "REST APIs", "Git"],
        "order management services for retail clients",
    ),
    (
        16,
        "Backend Developer - Django",
        "backend",
        "Pune",
        "hybrid",
        1,
        3,
        ["Python", "Django", "PostgreSQL", "Celery", "REST APIs", "Docker"],
        "policy issuance and claims workflows",
    ),
    (
        12,
        "Senior Java Engineer, Order Management",
        "backend",
        "Bengaluru",
        "onsite",
        6,
        10,
        ["Java", "Spring Boot", "Hibernate", "MySQL", "RabbitMQ", "Microservices"],
        "the order and inventory platform used by 4,000 stores",
    ),
    (
        11,
        "Backend Engineer, Threat Intel APIs",
        "backend",
        "Hyderabad",
        "hybrid",
        2,
        5,
        ["Python", "FastAPI", "Elasticsearch", "PostgreSQL", "Docker", "Kubernetes"],
        "APIs that serve threat indicators to customer SIEMs",
    ),
    (
        6,
        "Staff Backend Engineer",
        "backend",
        "Hyderabad",
        "hybrid",
        8,
        12,
        ["Go", "Java", "Distributed Systems", "Apache Kafka", "PostgreSQL", "System Design"],
        "the trip and pricing platform",
    ),
    (
        7,
        "Backend Engineer (FastAPI)",
        "backend",
        "Chennai",
        "hybrid",
        1,
        3,
        ["Python", "FastAPI", "PostgreSQL", "SQLAlchemy", "Docker", "AWS"],
        "appointment booking and e-prescription APIs",
    ),
    (
        17,
        "Frontend Engineer (React)",
        "frontend",
        "Bengaluru",
        "hybrid",
        2,
        4,
        ["React", "TypeScript", "Redux", "CSS", "Jest"],
        "the drag-and-drop storefront builder",
    ),
    (
        0,
        "Senior Frontend Engineer",
        "frontend",
        "Bengaluru",
        "hybrid",
        5,
        8,
        ["React", "TypeScript", "Next.js", "Tailwind CSS", "Storybook", "Web Accessibility"],
        "dense accounting dashboards and the shared design system",
    ),
    (
        15,
        "UI Developer",
        "frontend",
        "Remote",
        "remote",
        1,
        3,
        ["JavaScript", "HTML", "CSS", "React", "Responsive Design"],
        "the student video player and practice screens",
    ),
    (
        18,
        "Frontend Engineer - Video Platform",
        "frontend",
        "Hyderabad",
        "onsite",
        3,
        6,
        ["React", "TypeScript", "Next.js", "Web Performance", "Webpack"],
        "the web video player and watch pages",
    ),
    (
        10,
        "Frontend Developer (Angular)",
        "frontend",
        "Pune",
        "hybrid",
        2,
        5,
        ["Angular", "TypeScript", "D3.js", "Sass", "Jest"],
        "energy monitoring dashboards for plant managers",
    ),
    (
        5,
        "Frontend Engineer, Merchant Dashboard",
        "frontend",
        "Bengaluru",
        "hybrid",
        2,
        5,
        ["React", "TypeScript", "TanStack Query", "Tailwind CSS", "Cypress"],
        "the merchant dashboard for settlements and refunds",
    ),
    (
        13,
        "Junior Frontend Developer",
        "frontend",
        "Hyderabad",
        "onsite",
        0,
        2,
        ["JavaScript", "React", "HTML", "CSS", "Git"],
        "the farmer advisory web app",
    ),
    (
        8,
        "Senior Frontend Engineer (Vue)",
        "frontend",
        "Remote",
        "remote",
        4,
        7,
        ["Vue.js", "Nuxt.js", "TypeScript", "Tailwind CSS", "Vitest"],
        "the rich-text editor and publishing UI",
    ),
    (
        1,
        "Full Stack Engineer",
        "fullstack",
        "Pune",
        "hybrid",
        2,
        5,
        ["TypeScript", "React", "Node.js", "PostgreSQL", "Prisma", "Docker"],
        "the developer portal and usage billing",
    ),
    (
        15,
        "Full Stack Developer (MERN)",
        "fullstack",
        "Bengaluru",
        "hybrid",
        1,
        3,
        ["MongoDB", "Express", "React", "Node.js", "JavaScript"],
        "course authoring tools for teachers",
    ),
    (
        9,
        "Senior Full Stack Engineer",
        "fullstack",
        "Chennai",
        "hybrid",
        5,
        9,
        ["React", "TypeScript", "Python", "Django", "PostgreSQL", "AWS"],
        "the shipper and carrier portals",
    ),
    (
        19,
        "Full Stack Engineer, IoT Console",
        "fullstack",
        "Chennai",
        "onsite",
        2,
        4,
        ["React", "Node.js", "TypeScript", "PostgreSQL", "WebSockets", "Docker"],
        "the building operations console",
    ),
    (
        16,
        "Full Stack Developer",
        "fullstack",
        "Pune",
        "hybrid",
        3,
        6,
        ["Next.js", "React", "Node.js", "GraphQL", "PostgreSQL"],
        "the agent and customer self-service portals",
    ),
    (
        3,
        "Full Stack Engineer, Analytics Apps",
        "fullstack",
        "Pune",
        "hybrid",
        2,
        5,
        ["React", "Python", "FastAPI", "PostgreSQL", "Docker", "D3.js"],
        "internal analytics apps for client teams",
    ),
    (
        12,
        "Product Engineer (Full Stack)",
        "fullstack",
        "Bengaluru",
        "hybrid",
        1,
        3,
        ["React", "TypeScript", "Node.js", "MySQL", "REST APIs"],
        "store onboarding and billing flows",
    ),
    (
        1,
        "Lead Full Stack Engineer",
        "fullstack",
        "Remote",
        "remote",
        8,
        12,
        ["TypeScript", "React", "Node.js", "PostgreSQL", "AWS", "System Design", "Mentoring"],
        "the core product team",
    ),
    (
        3,
        "Data Scientist",
        "data_ml",
        "Pune",
        "hybrid",
        2,
        4,
        ["Python", "Pandas", "scikit-learn", "SQL", "Statistics", "Tableau"],
        "churn and demand forecasting models for retail clients",
    ),
    (
        6,
        "Machine Learning Engineer, Pricing",
        "data_ml",
        "Hyderabad",
        "hybrid",
        3,
        6,
        ["Python", "PyTorch", "XGBoost", "MLflow", "Apache Spark", "Docker"],
        "surge pricing and ETA prediction",
    ),
    (
        10,
        "Data Engineer",
        "data_ml",
        "Pune",
        "hybrid",
        2,
        5,
        ["Python", "Apache Spark", "Apache Airflow", "SQL", "dbt", "AWS"],
        "pipelines that ingest 50 million smart meter readings a day",
    ),
    (
        18,
        "Senior ML Engineer, Recommendations",
        "data_ml",
        "Hyderabad",
        "hybrid",
        5,
        9,
        ["Python", "PyTorch", "Recommender Systems", "Apache Spark", "Kubernetes", "MLOps"],
        "the home feed recommendation system",
    ),
    (
        7,
        "NLP Engineer",
        "data_ml",
        "Chennai",
        "hybrid",
        2,
        5,
        ["Python", "NLP", "Hugging Face", "PyTorch", "FastAPI"],
        "clinical note summarisation and medical coding",
    ),
    (
        13,
        "Junior Data Analyst",
        "data_ml",
        "Hyderabad",
        "onsite",
        0,
        2,
        ["SQL", "Excel", "Power BI", "Python", "Statistics"],
        "crop yield and mandi price reporting",
    ),
    (
        11,
        "ML Engineer, Anomaly Detection",
        "data_ml",
        "Hyderabad",
        "hybrid",
        3,
        6,
        ["Python", "scikit-learn", "Time Series", "Apache Kafka", "Docker"],
        "anomaly detection on network telemetry",
    ),
    (
        5,
        "Data Scientist, Risk",
        "data_ml",
        "Bengaluru",
        "hybrid",
        3,
        6,
        ["Python", "XGBoost", "SQL", "Feature Engineering", "Statistics", "A/B Testing"],
        "fraud and credit risk models",
    ),
    (
        8,
        "AI Engineer (LLMs)",
        "data_ml",
        "Remote",
        "remote",
        2,
        5,
        ["Python", "LLMs", "RAG", "LangChain", "Vector Databases", "FastAPI"],
        "writing assistant features built on LLMs",
    ),
    (
        4,
        "DevOps Engineer",
        "devops",
        "Bengaluru",
        "hybrid",
        2,
        5,
        ["Kubernetes", "Docker", "Terraform", "AWS", "GitHub Actions", "Prometheus"],
        "the managed Kubernetes offering",
    ),
    (
        4,
        "Senior Site Reliability Engineer",
        "devops",
        "Bengaluru",
        "hybrid",
        5,
        9,
        ["Kubernetes", "Linux", "Prometheus", "Grafana", "Go", "Incident Management"],
        "reliability for 1,200 customer clusters",
    ),
    (
        9,
        "Cloud Engineer (Azure)",
        "devops",
        "Chennai",
        "onsite",
        2,
        4,
        ["Azure", "Terraform", "AKS", "CI/CD", "Bash", "Docker"],
        "the migration of the carrier platform to Azure",
    ),
    (
        2,
        "Platform Engineer",
        "devops",
        "Hyderabad",
        "hybrid",
        3,
        6,
        ["Kubernetes", "Helm", "Argo CD", "Terraform", "Google Cloud", "Python"],
        "the internal developer platform",
    ),
    (
        14,
        "Junior DevOps Engineer",
        "devops",
        "Chennai",
        "onsite",
        0,
        2,
        ["Linux", "Docker", "Jenkins", "Bash", "Git", "AWS"],
        "CI/CD pipelines for client projects",
    ),
    (
        19,
        "SRE, Edge Infrastructure",
        "devops",
        "Chennai",
        "hybrid",
        4,
        7,
        ["Linux", "Ansible", "Prometheus", "Grafana", "Kubernetes", "Networking"],
        "a fleet of 30,000 edge gateways",
    ),
    (
        6,
        "Android Engineer",
        "mobile",
        "Hyderabad",
        "hybrid",
        2,
        5,
        ["Kotlin", "Android", "Jetpack Compose", "Kotlin Coroutines", "Retrofit", "MVVM"],
        "the rider app",
    ),
    (
        15,
        "iOS Developer",
        "mobile",
        "Bengaluru",
        "hybrid",
        2,
        4,
        ["Swift", "iOS", "SwiftUI", "UIKit", "Xcode"],
        "the offline-first learning app",
    ),
    (
        13,
        "Flutter Developer",
        "mobile",
        "Hyderabad",
        "onsite",
        1,
        3,
        ["Flutter", "Dart", "Firebase", "REST APIs", "Git"],
        "the farmer advisory app",
    ),
    (
        5,
        "Senior React Native Engineer",
        "mobile",
        "Bengaluru",
        "hybrid",
        5,
        8,
        ["React Native", "TypeScript", "Redux", "iOS", "Android"],
        "the merchant point-of-sale app",
    ),
    (
        7,
        "Mobile Engineer (Android)",
        "mobile",
        "Chennai",
        "onsite",
        1,
        3,
        ["Kotlin", "Android", "Room Database", "Firebase Cloud Messaging", "Dagger Hilt"],
        "the patient app for bookings and reports",
    ),
    (
        14,
        "QA Automation Engineer",
        "qa",
        "Chennai",
        "onsite",
        2,
        5,
        ["Selenium", "Java", "TestNG", "API Testing", "Jenkins"],
        "regression suites for banking clients",
    ),
    (
        0,
        "SDET",
        "qa",
        "Bengaluru",
        "hybrid",
        3,
        6,
        ["Playwright", "TypeScript", "API Testing", "Postman", "CI/CD"],
        "end-to-end coverage for the accounting web app",
    ),
    (
        16,
        "QA Engineer (Manual + Automation)",
        "qa",
        "Pune",
        "onsite",
        1,
        3,
        ["Manual Testing", "Selenium", "Jira", "SQL", "Test Planning"],
        "policy purchase and claims journeys",
    ),
    (
        18,
        "Performance Test Engineer",
        "qa",
        "Hyderabad",
        "hybrid",
        3,
        6,
        ["JMeter", "k6", "Performance Testing", "Grafana", "Linux"],
        "load testing for live cricket streams",
    ),
]

RESPONSIBILITIES = {
    "backend": [
        "Design, build and own services and APIs end to end, from schema to production.",
        "Write clear technical designs and review them with the team before building.",
        "Profile slow endpoints and queries; add indexes, caching or batching where it helps.",
        "Keep services observable with structured logs, metrics and useful alerts.",
        "Take part in a fair on-call rotation and write blameless postmortems.",
        "Review pull requests and help keep the codebase easy to change.",
    ],
    "frontend": [
        "Build fast, accessible screens from Figma designs with the design team.",
        "Own UI state, data fetching and error handling for your features.",
        "Contribute components to the shared design system and document them.",
        "Measure and improve load time and interaction latency on low-end devices.",
        "Write component and end-to-end tests for critical flows.",
        "Review pull requests and pair with backend engineers on API contracts.",
    ],
    "fullstack": [
        "Ship features end to end: database changes, APIs and the UI that uses them.",
        "Talk to users and support teams to understand problems before building.",
        "Keep the frontend and backend codebases tested and easy to change.",
        "Own deployments and monitoring for the services you build.",
        "Break large projects into small, safe releases behind feature flags.",
        "Review code and help newer engineers on the team.",
    ],
    "data_ml": [
        "Frame business problems as measurable modelling tasks with clear baselines.",
        "Build features and training datasets from raw event and transaction data.",
        "Train, evaluate and compare models; report results honestly, including failures.",
        "Work with engineers to deploy models and monitor drift in production.",
        "Write clear analyses and present findings to product and business teams.",
        "Keep pipelines and experiments reproducible.",
    ],
    "devops": [
        "Run and improve production infrastructure with infrastructure as code.",
        "Build CI/CD pipelines that let teams deploy safely many times a day.",
        "Define SLOs, dashboards and alerts that catch real problems early.",
        "Lead incident response and drive follow-up fixes to completion.",
        "Reduce cloud spend without hurting reliability.",
        "Write runbooks and help product teams own their services in production.",
    ],
    "mobile": [
        "Build and ship features in the app on a two-week release train.",
        "Keep the app fast to start and smooth to scroll on budget phones.",
        "Handle offline use, flaky networks and background sync carefully.",
        "Track crashes and ANRs and fix the top issues every sprint.",
        "Work with designers on interactions and with backend engineers on APIs.",
        "Write unit and UI tests for important flows.",
    ],
    "qa": [
        "Plan test coverage for new features with product managers and developers.",
        "Build and maintain automated test suites that run in CI on every change.",
        "Find, reproduce and clearly report defects with steps and evidence.",
        "Keep flaky tests under control and test runs fast.",
        "Test APIs and data, not only the UI.",
        "Share release quality reports with the team.",
    ],
}

REQUIREMENT_EXTRA = {
    "backend": "Solid understanding of relational databases, transactions and indexing.",
    "frontend": "Strong JavaScript fundamentals, semantic HTML and modern CSS.",
    "fullstack": "Comfortable working across the stack and picking up new tools quickly.",
    "data_ml": "Good grasp of statistics, model evaluation and experiment design.",
    "devops": "Strong Linux and networking fundamentals.",
    "mobile": "Experience publishing and maintaining an app on the stores.",
    "qa": "An eye for edge cases and the patience to chase intermittent bugs.",
}

NICE_TO_HAVE = {
    "backend": ["Experience with event-driven systems.", "Open-source contributions."],
    "frontend": ["Experience building data-heavy tables or charts.", "Accessibility audits."],
    "fullstack": ["Experience with a B2B SaaS product.", "Infrastructure basics (Docker, CI)."],
    "data_ml": ["Experience deploying models behind an API.", "Published papers or Kaggle work."],
    "devops": ["Kubernetes operator or controller experience.", "Security hardening."],
    "mobile": [
        "Experience with accessibility on mobile.",
        "Kotlin Multiplatform or Swift packages.",
    ],
    "qa": ["Performance or security testing exposure.", "ISTQB certification."],
}

BENEFITS = [
    "Health insurance for you, your spouse, children and parents (Rs 5 lakh cover).",
    "24 days of paid leave plus public holidays.",
    "Annual learning budget of Rs 50,000 for courses, books and conferences.",
    "Laptop of your choice and a home office allowance.",
    "ESOPs that vest over four years.",
    "Flexible hours with core collaboration time of 11:00 to 16:00 IST.",
    "Meal card and quarterly team offsites.",
    "Paid parental leave of 26 weeks (birthing parent) and 6 weeks (other parent).",
]

CATEGORY_PAY = {
    "backend": 1.05,
    "frontend": 0.95,
    "fullstack": 1.0,
    "data_ml": 1.1,
    "devops": 1.05,
    "mobile": 1.0,
    "qa": 0.85,
}


def salary_band(category: str, lo: int, hi: int, rng: random.Random) -> tuple[int, int]:
    mid_years = (lo + hi) / 2
    base_lpa = (4.5 + 3.2 * mid_years) * CATEGORY_PAY[category] * rng.uniform(0.93, 1.07)
    smin = round(base_lpa * 0.85 * 2) / 2  # nearest 0.5 lakh
    smax = round(base_lpa * 1.25 * 2) / 2
    return int(smin * 100_000), int(smax * 100_000)


def describe(company: tuple, job: tuple, rng: random.Random) -> str:
    _, title, cat, _, remote, lo, hi, skills, focus = job
    about = company[4]
    work = {
        "remote": "This is a fully remote role within India.",
        "hybrid": "This is a hybrid role: three days a week in our office.",
        "onsite": "This role is based in our office five days a week.",
    }[remote]
    years = f"{lo}-{hi} years" if lo > 0 else f"0-{hi} years (internships count)"
    resp = rng.sample(RESPONSIBILITIES[cat], k=4)
    core, rest = skills[:3], skills[3:]
    reqs = [
        f"{years} of professional experience in a similar role.",
        f"Hands-on experience with {', '.join(core)}.",
    ]
    if rest:
        reqs.append(f"Working knowledge of {', '.join(rest)}.")
    reqs.append(REQUIREMENT_EXTRA[cat])
    reqs.append("Clear written communication in English.")
    benefits = rng.sample(BENEFITS, k=4)
    lines = [
        "## About the role",
        f"{about} As a {title} you will work on {focus}. {work}",
        "",
        "## Responsibilities",
        *[f"- {r}" for r in resp],
        "",
        "## Requirements",
        *[f"- {r}" for r in reqs],
        "",
        "## Nice to have",
        *[f"- {n}" for n in NICE_TO_HAVE[cat]],
        "",
        "## Benefits",
        *[f"- {b}" for b in benefits],
    ]
    return "\n".join(lines)


# ---------- resumes ----------

# Bullet banks are worded independently of the classifier's training templates.
RESUME_BULLETS = {
    "backend": [
        "Built a {s0} service handling 1.5M requests per day with p95 under 120 ms.",
        "Designed {s2} schemas and migrations for billing data; added indexes that cut report time from 40s to 2s.",
        "Introduced {s3} for caching hot reads and background job queues.",
        "Wrote integration tests and set up Docker-based local environments for the team.",
        "Split a monolith module into two {s1} services with clear API contracts.",
        "Investigated production incidents and wrote postmortems with follow-up fixes.",
    ],
    "frontend": [
        "Rebuilt the checkout UI in {s0} and {s1}, raising conversion by 6%.",
        "Created 40+ reusable components with documentation and visual tests.",
        "Cut bundle size by 35% with code splitting and lazy loading.",
        "Fixed keyboard navigation and contrast issues found in an accessibility audit.",
        "Worked with designers in Figma to turn rough flows into production screens.",
        "Added {s3} tests for the most used screens and wired them into CI.",
    ],
    "fullstack": [
        "Shipped a self-serve onboarding flow: {s1} UI, {s2} API and {s3} schema.",
        "Built an admin console used daily by 30 support staff.",
        "Owned deployments and alerts for three services and their web clients.",
        "Replaced a cron-based sync with webhooks, removing a 15-minute data lag.",
        "Mentored two interns through their first production features.",
        "Wrote end-to-end tests for signup, billing and invoicing.",
    ],
    "data_ml": [
        "Built a {s1} model that improved forecast accuracy by 11% over the previous baseline.",
        "Prepared training data from 200M rows of transactions using {s2}.",
        "Set up experiment tracking and offline evaluation so results were reproducible.",
        "Presented findings to business stakeholders with clear charts and caveats.",
        "Deployed a model as an internal API and monitored drift every week.",
        "Cleaned and joined messy data from five source systems.",
    ],
    "devops": [
        "Managed {s0} clusters running 300 services across three environments.",
        "Wrote {s2} modules for networking, databases and IAM; reviewed all infra changes.",
        "Cut deploy time from 25 to 6 minutes by reworking the {s4} pipelines.",
        "Set up {s5} dashboards and paging alerts tied to SLOs.",
        "Ran incident response for P1 outages and led blameless reviews.",
        "Reduced monthly cloud spend by 18% with right-sizing and spot instances.",
    ],
    "mobile": [
        "Built new screens in {s2} and moved shared logic into a clean architecture layer.",
        "Reduced cold start time by 40% on low-end devices.",
        "Brought crash-free sessions from 97.1% to 99.6%.",
        "Implemented offline caching and background sync for unreliable networks.",
        "Released fortnightly builds to the store with staged rollouts.",
        "Wrote unit and UI tests for login, payments and profile flows.",
    ],
    "qa": [
        "Automated 450 regression cases with {s0}, cutting a 3-day manual cycle to 2 hours.",
        "Built an API test suite covering 120 endpoints, run on every pull request.",
        "Wrote test plans and acceptance criteria with product managers.",
        "Logged and triaged defects with clear steps, logs and screenshots.",
        "Reduced flaky tests from 9% to under 1% of runs.",
        "Ran smoke tests on every release candidate before rollout.",
    ],
}

PAST_EMPLOYERS = [
    "Brightline Software",
    "Corvid Technologies",
    "Lotus Infoways",
    "Northwind Digital",
    "Indigo Bay Systems",
    "Copperleaf IT",
    "Mango Grove Labs",
    "Silverline Apps",
]

COLLEGES = [
    "B.Tech in Computer Science, NIT Warangal",
    "B.E. in Information Science, RV College of Engineering, Bengaluru",
    "B.Tech in Information Technology, VIT Vellore",
    "B.E. in Computer Engineering, Pune Institute of Computer Technology",
    "B.Tech in Electronics and Communication, JNTU Hyderabad",
    "M.Tech in Computer Science, IIIT Hyderabad",
    "B.Sc Computer Science, Loyola College, Chennai",
    "MCA, College of Engineering Guindy, Chennai",
]

# (name, email local part, category, years, city, title, skills, explicit_years_in_summary)
PEOPLE = [
    (
        "Rahul Verma",
        "rahul",
        "backend",
        3,
        "Bengaluru",
        "Backend Engineer",
        ["Python", "Django", "PostgreSQL", "Redis", "Celery", "Docker", "AWS", "REST APIs"],
        True,
    ),
    (
        "Sneha Kulkarni",
        "sneha",
        "backend",
        6,
        "Pune",
        "Senior Software Engineer",
        ["Java", "Spring Boot", "PostgreSQL", "Kafka", "Microservices", "AWS", "Hibernate"],
        True,
    ),
    (
        "Imran Shaikh",
        "imran",
        "backend",
        4,
        "Hyderabad",
        "Software Engineer II",
        ["Go", "gRPC", "PostgreSQL", "Redis", "Kubernetes", "Docker"],
        False,
    ),
    (
        "Deepika Rao",
        "deepika",
        "backend",
        1,
        "Chennai",
        "Associate Backend Developer",
        ["Python", "FastAPI", "PostgreSQL", "SQLAlchemy", "Docker", "Git"],
        False,
    ),
    (
        "Aditya Joshi",
        "aditya",
        "frontend",
        3,
        "Bengaluru",
        "Frontend Engineer",
        ["React", "TypeScript", "Redux", "Jest", "CSS", "HTML"],
        True,
    ),
    (
        "Nandini Krishnan",
        "nandini",
        "frontend",
        6,
        "Hyderabad",
        "Senior Frontend Engineer",
        [
            "React",
            "Next.js",
            "TypeScript",
            "Tailwind CSS",
            "Storybook",
            "Web Accessibility",
            "Web Performance",
        ],
        True,
    ),
    (
        "Farhan Ali",
        "farhan",
        "frontend",
        2,
        "Pune",
        "UI Developer",
        ["Angular", "TypeScript", "Sass", "D3.js", "Jest", "HTML"],
        False,
    ),
    (
        "Pooja Reddy",
        "pooja",
        "fullstack",
        3,
        "Pune",
        "Full Stack Engineer",
        ["TypeScript", "React", "Node.js", "PostgreSQL", "Prisma", "Docker"],
        True,
    ),
    (
        "Karthik Subramanian",
        "karthik",
        "fullstack",
        7,
        "Chennai",
        "Senior Full Stack Engineer",
        ["React", "TypeScript", "Python", "Django", "PostgreSQL", "AWS"],
        True,
    ),
    (
        "Simran Kaur",
        "simran",
        "fullstack",
        1.5,
        "Bengaluru",
        "Full Stack Developer",
        ["MongoDB", "Express", "React", "Node.js", "JavaScript"],
        False,
    ),
    (
        "Vikram Iyer",
        "vikram",
        "data_ml",
        3,
        "Pune",
        "Data Scientist",
        ["Python", "Pandas", "scikit-learn", "SQL", "Statistics", "Tableau"],
        True,
    ),
    (
        "Ayesha Khan",
        "ayesha",
        "data_ml",
        5,
        "Hyderabad",
        "Machine Learning Engineer",
        ["Python", "PyTorch", "Apache Spark", "MLflow", "Kubernetes", "Recommender Systems"],
        True,
    ),
    (
        "Siddharth Menon",
        "siddharth",
        "data_ml",
        3,
        "Pune",
        "Data Engineer",
        ["Python", "Apache Spark", "Apache Airflow", "dbt", "SQL", "AWS"],
        False,
    ),
    (
        "Lakshmi Narayanan",
        "lakshmi",
        "data_ml",
        2,
        "Chennai",
        "NLP Engineer",
        ["Python", "NLP", "Hugging Face", "PyTorch", "FastAPI"],
        True,
    ),
    (
        "Manish Gupta",
        "manish",
        "devops",
        4,
        "Bengaluru",
        "DevOps Engineer",
        ["Kubernetes", "Docker", "Terraform", "AWS", "GitHub Actions", "Prometheus"],
        True,
    ),
    (
        "Revathi Srinivasan",
        "revathi",
        "devops",
        1,
        "Chennai",
        "Junior DevOps Engineer",
        ["Linux", "Docker", "Jenkins", "Bash", "AWS", "Git"],
        False,
    ),
    (
        "Aman Tiwari",
        "aman",
        "mobile",
        3,
        "Hyderabad",
        "Android Developer",
        ["Kotlin", "Android", "Jetpack Compose", "Kotlin Coroutines", "Retrofit", "MVVM"],
        True,
    ),
    (
        "Divya Pillai",
        "divya",
        "mobile",
        2.5,
        "Bengaluru",
        "iOS Developer",
        ["Swift", "iOS", "SwiftUI", "UIKit", "Xcode"],
        False,
    ),
    (
        "Harish Kumar",
        "harish",
        "qa",
        3,
        "Chennai",
        "QA Automation Engineer",
        ["Selenium", "Java", "TestNG", "API Testing", "Jenkins", "Postman"],
        True,
    ),
    (
        "Tanvi Deshpande",
        "tanvi",
        "qa",
        2,
        "Pune",
        "QA Engineer",
        ["Manual Testing", "Selenium", "Jira", "SQL", "Test Planning"],
        False,
    ),
]

DEMO_SEEKERS = {"rahul", "aditya", "pooja", "vikram", "aman"}
REF_YEAR, REF_MONTH = 2026, 10  # resumes are written as of October 2026

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _month_str(idx: int) -> str:
    return f"{MONTH_NAMES[idx % 12]} {idx // 12}"


def build_resume(p: tuple, rng: random.Random) -> dict:
    name, local, cat, years, city, title, skills, explicit = p
    now_idx = REF_YEAR * 12 + (REF_MONTH - 1)
    total_months = int(round(years * 12))
    fmt = {f"s{i}": skills[i] if i < len(skills) else skills[-1] for i in range(8)}
    bullets = [b.format(**fmt) for b in RESUME_BULLETS[cat]]
    rng.shuffle(bullets)
    experience = []
    if years >= 4:
        recent = total_months // 2 + 3
        start_recent = now_idx - recent + 1
        start_old = now_idx - total_months + 1
        experience.append(
            {
                "title": title,
                "company": rng.choice(PAST_EMPLOYERS[:4]),
                "dates": f"{_month_str(start_recent)} - Present",
                "bullets": bullets[:3],
            }
        )
        experience.append(
            {
                "title": title.replace("Senior ", "").replace(" II", ""),
                "company": rng.choice(PAST_EMPLOYERS[4:]),
                "dates": f"{_month_str(start_old)} - {_month_str(start_recent - 1)}",
                "bullets": bullets[3:5],
            }
        )
    else:
        start = now_idx - total_months + 1
        experience.append(
            {
                "title": title,
                "company": rng.choice(PAST_EMPLOYERS),
                "dates": f"{_month_str(start)} - Present",
                "bullets": bullets[:4],
            }
        )
    yrs = f"{years:g}"
    summary = (
        f"{title} with {yrs} years of experience in {', '.join(skills[:3])}."
        if explicit
        else f"{title} working with {', '.join(skills[:3])}."
    )
    summary += (
        " "
        + {
            "backend": "I like boring, reliable systems and clear APIs.",
            "frontend": "I care about accessible, fast interfaces.",
            "fullstack": "I enjoy owning features from the database to the UI.",
            "data_ml": "I focus on models that are measurable and useful to the business.",
            "devops": "I automate repetitive operations work and keep production calm.",
            "mobile": "I build apps that stay fast on budget phones.",
            "qa": "I make releases predictable with good test coverage.",
        }[cat]
    )
    grad_year = REF_YEAR - int(years) - 1
    edu = f"{rng.choice(COLLEGES)}, {grad_year - 4} - {grad_year}"
    phone = f"+91 9{rng.randint(100000000, 999999999)}"
    return {
        "name": name,
        "email": f"{local}@example.com",
        "phone": f"{phone[:8]} {phone[8:]}",
        "location": city,
        "category": cat,
        "years": years,
        "title": title,
        "skills": skills,
        "summary": summary,
        "experience": experience,
        "skills_text": ", ".join(skills),
        "education": [edu],
        "file": f"{local}_{name.split()[1].lower()}.pdf",
        "demo": local in DEMO_SEEKERS,
    }


def is_relevant(resume: dict, job: dict) -> bool:
    """Ground-truth rule for the eval set: same role family and plausible seniority.

    A candidate is a fit when the job's category matches theirs and their experience is
    no more than 1 year under the minimum or 2 years over the maximum.
    """
    return (
        resume["category"] == job["role_category"]
        and job["experience_min"] - 1 <= resume["years"] <= job["experience_max"] + 2
    )


def main() -> None:
    rng = random.Random(42)
    DATA.mkdir(exist_ok=True)
    PDF_DIR.mkdir(exist_ok=True)

    companies = [
        {"name": n, "industry": ind, "size_range": size, "hq_city": hq, "about": about}
        for n, ind, size, hq, about in COMPANIES
    ]
    jobs = []
    for i, j in enumerate(JOBS):
        ci, title, cat, loc, remote, lo, hi, skills, _ = j
        smin, smax = salary_band(cat, lo, hi, rng)
        jobs.append(
            {
                "key": i + 1,
                "company": COMPANIES[ci][0],
                "recruiter": ["meera", "rohan", "ananya"][ci // 7],
                "title": title,
                "role_category": cat,
                "location": loc,
                "remote_type": remote,
                "experience_min": lo,
                "experience_max": hi,
                "salary_min": smin,
                "salary_max": smax,
                "skills": skills,
                "description_md": describe(COMPANIES[ci], j, rng),
                # Spread posting dates over the last ~6 weeks.
                "posted_days_ago": round((i * 7) % 41 + rng.random(), 2),
            }
        )

    resumes = [build_resume(p, rng) for p in PEOPLE]
    for r in resumes:
        render_pdf(r, PDF_DIR / r["file"])

    pairs = []
    for r in resumes:
        rel = [j["key"] for j in jobs if is_relevant(r, j)]
        assert rel, f"{r['name']} has no relevant job"
        pairs.append({"resume": r["file"], "relevant_jobs": rel})

    (DATA / "companies.json").write_text(json.dumps(companies, indent=1), encoding="utf-8")
    (DATA / "jobs.json").write_text(json.dumps(jobs, indent=1), encoding="utf-8")
    (DATA / "resumes.json").write_text(json.dumps(resumes, indent=1), encoding="utf-8")
    (DATA / "eval_pairs.json").write_text(
        json.dumps(
            {
                "rule": is_relevant.__doc__.strip(),
                "pairs": pairs,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    n_rel = sum(len(p["relevant_jobs"]) for p in pairs)
    print(
        f"{len(companies)} companies, {len(jobs)} jobs, {len(resumes)} resumes, "
        f"{n_rel} relevant pairs out of {len(jobs) * len(resumes)}"
    )


if __name__ == "__main__":
    main()
