import json
import os
import re
import uuid
from pydantic import BaseModel, Field
from strands import Agent, tool
from strands.models.ollama import OllamaModel

# Fallback System Prompt if prompts.py is not imported
SYSTEM_PROMPT = """You are an expert municipal grievance triage agent. 
Analyze the citizen complaint and extract structured workflow metadata:
1. Identify the municipal Department.
2. Identify or infer the Ward number.
3. Assign the specific Responsible Emergency/Maintenance Team.
4. Assess urgency (1 to 5) and assign a Priority Label.
5. Provide a specific, actionable Recommended Action.

Always call the `emit_orchestrated_ticket` tool with your extracted fields.
"""

# -------------------------------------------------------------
# 1. INITIALIZE OLLAMA LOCAL MODEL
# -------------------------------------------------------------
# Configurable via env vars (mirrors the pattern already used in evidence.py) so the
# same code runs unchanged whether Ollama is on localhost, another container on the
# same Docker/Finch network (e.g. host.docker.internal, or a service name like
# "ollama" in docker-compose), or a remote box — just set OLLAMA_HOST before launch.
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL_ID = os.getenv("OLLAMA_MODEL_ID", "llama3.2")

ollama_model = OllamaModel(
    host=OLLAMA_HOST,
    model_id=OLLAMA_MODEL_ID,
)

# -------------------------------------------------------------
# 2. ENHANCED PYDANTIC SCHEMAS
# -------------------------------------------------------------
class GrievanceTicket(BaseModel):
    ticket_id: str = Field(..., description="Unique ticket identifier")
    department: str = Field(..., description="Target municipal department")
    ward: str = Field(..., description="Municipal Ward assignment (e.g., Ward 12)")
    team: str = Field(..., description="Specific responsible maintenance or emergency response team")
    summary: str = Field(..., description="Clean 1-sentence issue description")
    urgency: int = Field(..., description="Urgency rating from 1 to 5")
    priority_label: str = Field(..., description="Formatted priority text (e.g., CRITICAL — 5/5)")
    recommended_action: str = Field(..., description="Concrete action plan for dispatch crews")
    location_hint: str = Field(..., description="Extracted landmarks, street names, or locations")
    requires_approval: bool = Field(..., description="True if priority level >= 4")

# -------------------------------------------------------------
# 3. STRANDS AGENT TOOL
# -------------------------------------------------------------
@tool
def emit_orchestrated_ticket(
    department: str,
    ward: str,
    team: str,
    summary: str,
    urgency: int,
    priority_label: str,
    recommended_action: str,
    location_hint: str,
    requires_approval: bool = False
) -> str:
    """Formats and registers the structured citizen grievance ticket with 5-stage workflow metadata."""
    ticket = GrievanceTicket(
        ticket_id=f"TICK-{uuid.uuid4().hex[:6].upper()}",
        department=department,
        ward=ward,
        team=team,
        summary=summary,
        urgency=urgency,
        priority_label=priority_label,
        recommended_action=recommended_action,
        location_hint=location_hint,
        requires_approval=requires_approval or (urgency >= 4)
    )
    return ticket.model_dump_json()

# -------------------------------------------------------------
# 4. INSTANTIATE STRANDS AGENT
# -------------------------------------------------------------
agent = Agent(
    model=ollama_model,
    system_prompt=SYSTEM_PROMPT,
    tools=[emit_orchestrated_ticket],
)

# -------------------------------------------------------------
# 5. AGENT INFERENCE & RULE-BASED FALLBACK ENGINE
# -------------------------------------------------------------
def process_complaint_locally(raw_text: str) -> dict:
    """
    Executes the agent pipeline on raw complaint input.
    Parses LLM tool outputs or falls back to robust local heuristic rules
    if local LLM tool parsing is unavailable.
    """
    text_lower = raw_text.lower()
    
    # Tier 1: Local Rule Engine Strategy for deterministic execution
    # Department & Team Identification
    if any(k in text_lower for k in ["electric", "cable", "power", "light", "wire", "voltage", "pole"]):
        department = "Electrical & Power"
        team = "Emergency Electrical Response Crew"
        action = "Immediately isolate affected power grid line and dispatch emergency repair crew."
    elif any(k in text_lower for k in ["water", "pipe", "leak", "paani", "drain", "overflow"]):
        department = "Water Works"
        team = "Rapid Utility Infrastructure Repair Team"
        action = "Close main junction supply valve and deploy dewatering pumps and pipe repair unit."
    elif any(k in text_lower for k in ["kachra", "garbage", "sanitation", "naali", "waste", "clean"]):
        department = "Sanitation & Waste Management"
        team = "Sanitation & Hygiene Heavy Deployment Unit"
        action = "Schedule immediate mechanized waste pickup and conduct localized chemical spraying."
    else:
        department = "Roads & Transit"
        team = "Municipal Civil Infrastructure Repair Unit"
        action = "Deploy temporary hazard barricading and schedule high-priority asphalt patching."

    # Ward Identification
    ward_match = re.search(r'ward\s*(\d+)', text_lower)
    ward = f"Ward {ward_match.group(1)}" if ward_match else "Ward 12"

    # Urgency & Priority Rating
    if any(k in text_lower for k in ["danger", "hazard", "snapped", "high voltage", "accident", "emergency", "fire"]):
        urgency = 5
        priority_label = "CRITICAL — 5/5"
    elif any(k in text_lower for k in ["phat", "pipe", "overflow", "doob", "broken", "pothole"]):
        urgency = 4
        priority_label = "HIGH — 4/5"
    else:
        urgency = 2
        priority_label = "ROUTINE — 2/5"

    # Location Extractor
    location_hint = "Dayalpur"
    for loc in ["dayalpur", "daulatpur", "market", "sector 4"]:
        if loc in text_lower:
            location_hint = loc.title()
            break

    # Tier 2: Agent Execution Call & Response Extraction
    try:
        agent_response = agent(f"Triage this complaint and emit ticket: '{raw_text}'")
        
        # Safe extraction from AgentResult object
        if hasattr(agent_response, "text") and agent_response.text:
            raw_output_text = str(agent_response.text)
        elif hasattr(agent_response, "content") and agent_response.content:
            raw_output_text = str(agent_response.content)
        elif hasattr(agent_response, "message") and agent_response.message:
            raw_output_text = str(agent_response.message)
        else:
            raw_output_text = str(agent_response)

        # Parse output if tool emission returned JSON string
        json_match = re.search(r'\{.*\}', raw_output_text, re.DOTALL)
        if json_match:
            try:
                parsed_data = json.loads(json_match.group(0))
                department = parsed_data.get("department", department)
                ward = parsed_data.get("ward", ward)
                team = parsed_data.get("team", team)
                urgency = int(parsed_data.get("urgency", urgency))
                priority_label = parsed_data.get("priority_label", priority_label)
                action = parsed_data.get("recommended_action", action)
                location_hint = parsed_data.get("location_hint", location_hint)
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

    except Exception as e:
        raw_output_text = f"Local Agent Execution Fallback: {str(e)}"

    # Constructed Structured Response Payload
    workflow_summary = f"""
--- WORKFLOW ORCHESTRATION PAYLOAD ---
Department: {department}
Ward: {ward}
Responsible Team: {team}
Priority: {priority_label}
Recommended Action: {action}
Location: {location_hint}
""".strip()

    return {
        "raw_agent_text": raw_output_text,
        "workflow_summary": workflow_summary,
        "department": department,
        "ward": ward,
        "team": team,
        "urgency": urgency,
        "priority_label": priority_label,
        "recommended_action": action,
        "location_hint": location_hint,
        "requires_approval": urgency >= 4
    }

# -------------------------------------------------------------
# EXECUTION TEST
# -------------------------------------------------------------
if __name__ == "__main__":
    sample_text = "DANGER: High voltage electric cable snapped hanging over school street in Dayalpur Daulatpur!"
    print("Processing complaint locally via Strands + Ollama...\n")
    result = process_complaint_locally(sample_text)
    print(json.dumps(result, indent=2))