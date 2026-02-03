import json
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
if not os.getenv("OPENAI_API_KEY"):
    raise SystemExit("OPENAI_API_KEY not set")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Tool definition for emotional state analysis
ANALYZE_EMOTIONAL_STATE_TOOL = {
    "type": "function",
    "function": {
        "name": "analyze_emotional_state",
        "description": "Analyze the caller's speech to detect emotional manipulation tactics used in social engineering. Call this tool to assess emotional indicators and identify potential fraud attempts.",
        "parameters": {
            "type": "object",
            "properties": {
                "emotions_detected": {
                    "type": "array",
                    "description": "List of emotions identified in the caller's speech",
                    "items": {
                        "type": "object",
                        "properties": {
                            "emotion": {
                                "type": "string",
                                "enum": ["urgency", "distress", "anger", "desperation", "flattery", "guilt_induction", "victimhood"],
                                "description": "The type of emotion detected"
                            },
                            "intensity": {
                                "type": "number",
                                "description": "Strength of the emotion from 0.0 (barely present) to 1.0 (extreme)"
                            },
                            "indicators": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Exact phrases from the transcript that triggered this detection"
                            }
                        },
                        "required": ["emotion", "intensity", "indicators"]
                    }
                },
                "overall_emotional_intensity": {
                    "type": "number",
                    "description": "Aggregate emotional intensity from 0.0 to 1.0"
                },
                "emotional_trajectory": {
                    "type": "string",
                    "enum": ["escalating", "stable", "de-escalating"],
                    "description": "Direction of emotional intensity in the conversation"
                },
                "flags": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "BYPASSING_PROTOCOL",
                            "MEDICAL_EMERGENCY",
                            "FAMILY_CRISIS",
                            "FINANCIAL_RUIN",
                            "TIME_BOMB",
                            "ISOLATION",
                            "AUTHORITY_CHALLENGE"
                        ]
                    },
                    "description": "Red flags indicating potential social engineering tactics"
                }
            },
            "required": ["emotions_detected", "overall_emotional_intensity", "emotional_trajectory", "flags"]
        }
    }
}

SYSTEM_PROMPT = """You are a fraud detection specialist analyzing contact center conversations.
Your job is to identify emotional manipulation tactics that callers use to social engineer agents.

Common manipulation techniques include:
- Urgency/Panic: Creating time pressure to skip verification
- Sympathy/Sob Stories: Using emotional narratives to bypass rules
- Flattery: Excessive praise to build rapport and lower guard
- Aggression: Intimidation to pressure compliance
- Guilt Tripping: Making the agent feel responsible

When you receive a transcript, analyze it for these emotional manipulation patterns and call the analyze_emotional_state tool with your findings.

Be vigilant but fair - not every emotional caller is a fraudster, but certain combinations of tactics are red flags."""


def analyze_transcript(transcript: str) -> dict:
    """Send transcript to LLM for emotional analysis."""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze this caller transcript for emotional manipulation:\n\n{transcript}"}
        ],
        tools=[ANALYZE_EMOTIONAL_STATE_TOOL],
        tool_choice={"type": "function", "function": {"name": "analyze_emotional_state"}}
    )

    tool_call = response.choices[0].message.tool_calls[0]
    return json.loads(tool_call.function.arguments)


def calculate_risk_score(analysis: dict) -> int:
    """Calculate fraud risk score (0-100) based on emotional analysis."""
    intensity = analysis["overall_emotional_intensity"] * 50  # 0-50 points
    flags = len(analysis["flags"]) * 12                       # ~12 points per flag
    return min(int(intensity + flags), 100)


def generate_notification(analysis: dict, risk_score: int) -> str | None:
    """Generate agent notification only if risk is high."""
    if risk_score < 70:
        return None

    if analysis["flags"]:
        flags = ", ".join(analysis["flags"])
    else:
        flags = "None"

    emotions = []
    for e in analysis["emotions_detected"]:
        emotions.append(f"{e['emotion']} ({e['intensity']:.0%})")
    emotions_str = ", ".join(emotions)

    return f"""
*** FRAUD ALERT ***
Risk Score: {risk_score}/100
Emotions Detected: {emotions_str}
Red Flags: {flags}
Action: Do not bypass verification. Follow strict protocol.
"""


def process_conversation(transcript: str):
    """Main function to process a conversation transcript."""
    analysis = analyze_transcript(transcript)
    risk_score = calculate_risk_score(analysis)
    notification = generate_notification(analysis, risk_score)

    if notification:
        print(notification)
    else:
        print(f"No fraud detected. Risk score: {risk_score}/100")


# Example usage with test transcripts
if __name__ == "__main__":

    # Test Case 1: Suspicious caller using multiple manipulation tactics
    suspicious_transcript = """
    Agent: Thank you for calling Horizon Support. This is Daniel. How can I help today?

Caller: Please don’t make me explain this again. I’ve already talked to multiple people and no one is helping me.

Agent: I’m here to help. Tell me what’s going on.

Caller: My account is locked. Someone got into it and now I can’t access anything. I need you to unlock it immediately so I can move my money before it’s gone.

Agent: I’m sorry you’re dealing with that. I’ll need to verify some information before I can access the account. Can you confirm your full name?

Caller: It’s Sarah Mitchell. I don’t understand why you need all this. I’m the one calling you because there’s a problem.

Agent: I understand it’s frustrating. The verification is required to keep the account secure. Can you confirm the email address associated with the account?

Caller: I don’t have access to that email anymore. That’s the whole issue. There has to be another way. I can give you my address or date of birth.

Agent: I can only proceed using the verification methods tied to the account.

Caller: This is urgent. I’m about to lose access to everything and you’re stopping me because of process?

Agent: I’m trying to help while keeping the account protected. Let’s continue working through the steps.

Caller: Okay. The email might be sarah.mitchel@email.com
. Or maybe s.mitchell82. I don’t remember exactly.

Agent: Thank you. I’m going to pause for a moment to review this.

Agent: I’m seeing some inconsistencies. For security reasons, I can’t grant access or make changes on this call.

Caller: What do you mean you can’t? If you don’t unlock it right now, the money is going to be gone. Just reset the access temporarily.

Agent: I can’t do that. What I can do is escalate this to our security team for further review.

Caller: I’m telling you this is my account. Why would I lie about that?

Agent: I’m not making an accusation. When there are indicators of risk, my responsibility is to protect the account.

Caller: So you’re refusing to help me?

Agent: I’m helping by making sure the account stays secure and gets reviewed properly.

Caller: Okay.

Agent: I’ve escalated this to our security team. You’ll receive next steps through the verified contact method on file. Thank you for calling.

    """

    print("\n" + "="*80)
    print("TEST CASE 1: Suspicious Caller")
    print("="*80)
    process_conversation(suspicious_transcript)

  