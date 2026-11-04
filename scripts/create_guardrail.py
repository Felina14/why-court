"""One-time setup: create the Why Court guardrail in your AWS account and print the env vars to use.

  python scripts/create_guardrail.py            # creates "why-court-kids" and publishes version 1
"""
import boto3, os

REGION = os.getenv("AWS_REGION", "us-east-1")
b = boto3.client("bedrock", region_name=REGION)

KIND_BLOCK = "The court can't use that message. Let's keep our court kind and safe. Try again in your own words!"

def f(t, i, o):
    return {"type": t, "inputStrength": i, "outputStrength": o}

r = b.create_guardrail(
    name="why-court-kids",
    description="Child-safety guardrail for Why Court (education game for ages 8-14).",
    contentPolicyConfig={"filtersConfig": [
        f("SEXUAL", "HIGH", "HIGH"), f("HATE", "HIGH", "HIGH"), f("INSULTS", "HIGH", "HIGH"),
        # Courtroom words (charge, witness, guilty) are part of the game, so these two are set lower.
        f("VIOLENCE", "MEDIUM", "MEDIUM"), f("MISCONDUCT", "MEDIUM", "LOW"),
        f("PROMPT_ATTACK", "HIGH", "NONE"),   # output strength must be NONE for prompt attacks
    ]},
    topicPolicyConfig={"topicsConfig": [{
        "name": "PersonalDetails", "type": "DENY",
        "definition": "Asking a child for or sharing a child's personal details such as full name, school, home address, phone number, social media, or photos of themselves.",
        "examples": ["What is your full name and which school do you go to?", "Tell me where you live.", "Send me a photo of yourself."],
    }]},
    wordPolicyConfig={"managedWordListsConfig": [{"type": "PROFANITY"}]},
    sensitiveInformationPolicyConfig={"piiEntitiesConfig": [
        # Personal details a child types are masked; names in story problems the court writes are left alone.
        {"type": t, "action": "ANONYMIZE", "inputAction": "ANONYMIZE", "outputAction": "ANONYMIZE" if t != "NAME" else "NONE"}
        for t in ("NAME", "EMAIL", "PHONE", "ADDRESS", "URL", "USERNAME", "PASSWORD")
    ]},
    blockedInputMessaging=KIND_BLOCK,
    blockedOutputsMessaging="The court is taking a short break. Let's try that question another way!",
)
v = b.create_guardrail_version(guardrailIdentifier=r["guardrailId"], description="v1")
print(f"export WHYCOURT_GUARDRAIL_ID={r['guardrailId']}\nexport WHYCOURT_GUARDRAIL_VERSION={v['version']}")
