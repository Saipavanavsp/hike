"""Regenerate the sample resumes used by the parser tests.

Run from backend/:  python -m tests.fixtures.make_fixtures
"""

from pathlib import Path

from seed.render import render_docx, render_pdf

HERE = Path(__file__).parent

PRIYA = {
    "name": "Priya Sharma",
    "location": "Hyderabad, Telangana",
    "email": "priya.sharma.dev@example.com",
    "phone": "+91 98765 43210",
    "summary": "Backend engineer who builds reliable Python services and data-heavy APIs.",
    "experience": [
        {
            "title": "Software Engineer",
            "company": "Nimbus Ledger",
            "dates": "Jul 2022 - Present",
            "bullets": [
                "Built REST APIs in FastAPI and Django serving 2M requests a day.",
                "Moved background jobs to Celery with Redis, cutting p95 latency by 40%.",
                "Containerised services with Docker and deployed them on AWS (ECS, RDS).",
            ],
        },
        {
            "title": "Backend Intern",
            "company": "Tidepool Labs",
            "dates": "Jan 2022 - Jun 2022",
            "bullets": ["Wrote PostgreSQL migrations and unit tests with pytest."],
        },
    ],
    "skills_text": "Python, Django, FastAPI, PostgreSQL, Redis, Celery, Docker, AWS, Git, CI/CD",
    "education": ["B.Tech in Computer Science, JNTU Hyderabad, 2018 - 2022, CGPA 8.4"],
}

ARJUN = {
    "name": "Arjun Menon",
    "location": "Bengaluru",
    "email": "arjun.menon@example.com",
    "phone": "9123456789",
    "summary": (
        "Frontend engineer with 4+ years of experience building React and TypeScript apps "
        "for fintech dashboards."
    ),
    "experience": [
        {
            "title": "Senior Frontend Engineer",
            "company": "Saffron Pay",
            "dates": "Mar 2023 - Present",
            "bullets": [
                "Led migration of a JS codebase to TypeScript and Next.js.",
                "Built a design system with Tailwind and Storybook used by 6 teams.",
            ],
        },
        {
            "title": "Frontend Developer",
            "company": "Quillstack",
            "dates": "Jun 2021 - Feb 2023",
            "bullets": ["Wrote Jest and React Testing Library tests; state in Redux."],
        },
    ],
    "skills_text": "ReactJS, TypeScript, Next.js, Redux, Tailwind, HTML5, CSS3, Jest, Webpack, Postgres",
    "education": ["Bachelor of Engineering (B.E.), Information Technology, PES University, 2021"],
}

KAVYA = {
    "name": "Kavya Iyer",
    "location": "Pune",
    "email": "kavya.iyer@example.com",
    "phone": "+91-90000-11122",
    "summary": (
        "Data scientist with 2 years of experience in NLP and forecasting. Ready to go deep "
        "on messy data; joined a research group in spring 2023."
    ),
    "experience": [
        {
            "title": "Data Scientist",
            "company": "Orchid Analytics",
            "dates": "Aug 2024 - Present",
            "bullets": [
                "Trained text classifiers with scikit-learn and PyTorch on 1M support tickets.",
                "Built PySpark feature pipelines and Tableau dashboards for the ops team.",
            ],
        }
    ],
    "projects": ["Sentiment model with Hugging Face transformers, served behind a Flask API."],
    "skills_text": "Python, Pandas, NumPy, sklearn, PyTorch, NLP, SQL, PySpark, Tableau, Statistics",
    "education": ["M.Tech in Data Science, COEP Pune, 2024", "B.Sc Mathematics, Fergusson College"],
}


def main() -> None:
    render_pdf(PRIYA, HERE / "priya_sharma_backend.pdf")
    render_docx(ARJUN, HERE / "arjun_menon_frontend.docx")
    render_pdf(KAVYA, HERE / "kavya_iyer_data.pdf")
    print("fixtures written to", HERE)


if __name__ == "__main__":
    main()
