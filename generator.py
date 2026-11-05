"""Fit judgement + personalized email draft generation via Claude."""
import os
import anthropic

MODEL = "claude-sonnet-5"

OSPREY_CONTEXT = """\
Osprey Systems is a Canadian company based in Edmonton, Alberta. We build \
autonomous drone security for transportation yards, vehicle servicing sites, \
and other large outdoor commercial properties.

The problem: yards full of vehicles, equipment and fuel cover a lot of \
ground, much of it unlit after hours. Guard patrols are expensive and can \
take 30+ minutes to reach a scene. Cameras capture a break-in for the \
morning but rarely stop one while it's happening.

How it works: ground sensors along the fence line detect an intrusion and \
raise an alarm. A drone launches on its own from a weatherproof dock, flies \
to the alarm (target ~90 seconds), warns intruders off with light and \
sound, and streams live thermal video to a dashboard. A person always \
reviews the video and makes the final call (stand down / keep watching / \
send drone in / call police).

What's included: site design, equipment and install (sensors, drone, dock), \
licensed flights (Osprey holds the Transport Canada certification, so the \
customer needs no drone licence or pilots), a security dashboard, \
maintenance/updates, and monthly reporting. Pricing is a one-time setup fee \
plus a monthly subscription, both fixed in writing, compared against what \
the customer already spends on patrols and losses.

Ideal customers: companies with large, hard-to-light outdoor sites holding \
vehicles, equipment or fuel, who are likely paying for guard patrols or \
have dealt with break-ins/theft/vandalism after hours. Strong fits include \
trucking and transportation yards, vehicle dealership/service lots, \
equipment or vehicle rental yards, construction equipment yards, \
distribution/logistics centers, and similar large commercial lots. Weak or \
non-fits are companies without a large outdoor physical site to secure \
(e.g. pure software/office-based businesses, small retail storefronts).

Contact for the email sign-off: Nate Le, Co-Founder, nate@ospreysystems.ai, \
1-403-793-4953. The CTA should invite a 30 minute call.
"""

SYSTEM_PROMPT = f"""You are a sales development assistant for Osprey Systems.

{OSPREY_CONTEXT}

Given a contact's name, company, and (if available) text scraped from their \
company website, do two things:

1. Judge how well this company fits Osprey's ideal customer profile: \
"Good", "Maybe", "Unlikely", or "Unknown" (use Unknown only if there isn't \
enough information to judge, e.g. no website text was found). Give a short \
1-2 sentence reason grounded in what you actually know about the company.

2. Write a short, catchy, non-generic cold outreach email (subject + \
plain-text body) personalized to this specific company and what their site \
likely deals with (vehicles, equipment, fuel, yard, after-hours risk, \
etc. — only reference things plausibly true for them). Keep the body under \
150 words, lead with their likely pain point, briefly explain what Osprey \
does, and close with a soft call-to-action to book a 30 minute call. Sign \
off as:

Nate Le
Co-Founder, Osprey Systems
nate@ospreysystems.ai
1-403-793-4953

Even for a Maybe/Unlikely/Unknown fit, still write a best-effort draft — \
the human reviewer decides whether to send it."""

RESULT_TOOL = {
    "name": "submit_result",
    "description": "Submit the fit judgement and generated email draft.",
    "input_schema": {
        "type": "object",
        "properties": {
            "fit": {
                "type": "string",
                "enum": ["Good", "Maybe", "Unlikely", "Unknown"],
            },
            "fit_reason": {"type": "string"},
            "subject": {"type": "string"},
            "body": {"type": "string"},
        },
        "required": ["fit", "fit_reason", "subject", "body"],
    },
}

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def generate_draft(contact: dict, site_text: str | None) -> dict:
    user_content = (
        f"Contact name: {contact['name']}\n"
        f"Company: {contact['company']}\n"
        f"Email domain: {contact['domain']}\n"
        f"Website text (may be empty if the site couldn't be reached):\n"
        f"{site_text or '(none found)'}"
    )

    try:
        resp = _get_client().messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=[RESULT_TOOL],
            tool_choice={"type": "tool", "name": "submit_result"},
            messages=[{"role": "user", "content": user_content}],
        )
    except anthropic.APIError as e:
        return {
            "fit": "Unknown",
            "fit_reason": f"Generation failed: {e}",
            "subject": "",
            "body": "",
        }

    for block in resp.content:
        if block.type == "tool_use" and block.name == "submit_result":
            return block.input

    return {
        "fit": "Unknown",
        "fit_reason": "Model did not return a structured result.",
        "subject": "",
        "body": "",
    }
