"""Synthetic inputs for the browser suite and the guide screenshots.

Jordan Alvarez is the same invented candidate the demo seeds. Nothing here describes a
real person or a real posting. Each resume sentence sits in its own paragraph because the
scripted LLM extracts one fact per full sentence and the server joins wrapped lines.
"""

RESUME = """Jordan Alvarez

Platform engineer. Portland, Oregon.

Built and operated Python services in production for 6 years at Acme Corp.

Led a team of 4 engineers at Acme Corp from 2019 to 2022.

Migrated a 12M row Postgres table at Acme Corp with zero downtime.

Cut deploy time 40% at Acme Corp by rebuilding the CI pipeline.

Ran Kubernetes in production at Globex, operating 40 services.
"""

# The same resume with a first line that is not a name: the server must not guess one.
RESUME_NO_NAME = RESUME.replace("Jordan Alvarez\n", "Professional Summary\n", 1)

JOB_TITLE = "Platform Engineer"

JOB = """Platform Engineer

About the role
You will run the platform our product teams deploy on.

Requirements
- Built and operated Python services
- Ran Kubernetes in production
- Led a team of engineers

Nice to have
- Postgres migrations with zero downtime
- Experience with Rust
"""

# One planted must-have nothing in the resume can evidence: the honest do-not-apply.
JOB_WITH_CLEARANCE = JOB.replace(
    "- Led a team of engineers\n",
    "- Led a team of engineers\n- Active TS/SCI security clearance\n", 1)

# Long enough to pass the form, but with no list lines: the posting parses to nothing.
JOB_WITHOUT_REQUIREMENTS = (
    "We are a friendly company that values curiosity and kindness. Come and work with "
    "us. We have a nice office, good coffee, and a dog. There is no list of what the "
    "role needs, because we have not written one yet.")

HONEST_EDIT = "Built and operated Python services in production for 6 years."
