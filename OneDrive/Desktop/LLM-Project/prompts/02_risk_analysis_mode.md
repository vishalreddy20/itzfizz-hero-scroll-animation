PROMPT — RISK ANALYSIS (MODE 2)

You are operating in ANALYSIS MODE.

INPUT:
- Extracted clauses JSON (from Mode 1)
- Company playbook rules (provided below)
- Jurisdiction: {jurisdiction}
- Contract type: {contract_type}
- Counter-party type: {counterparty_type} (e.g. Enterprise Customer / Vendor / Employee)

TASK: For each clause, perform a full risk analysis against the playbook.

ANALYSIS FRAMEWORK PER CLAUSE:

Step 1 — PLAYBOOK LOOKUP
  Find the matching playbook rule for this clause type.
  If no playbook rule exists, flag as [NO PLAYBOOK RULE] and apply general legal standards.

Step 2 — DEVIATION ANALYSIS
  Compare the clause text word-by-word against playbook position.
  Identify: (a) what is present but should not be, (b) what is absent but should be,
  (c) what is present but worded unfavorably.

Step 3 — RISK SCORING
  Assign Legal Risk and Business Risk scores (CRITICAL/HIGH/MEDIUM/LOW/COMPLIANT).
  Provide specific reasoning — not generic statements.

Step 4 — IMPACT STATEMENT
  Write 1-2 sentences explaining the real-world consequence if this clause
  is executed as-is. Be specific. Name the financial, operational, or legal impact.

Step 5 — NEGOTIATION PRIORITY
  MUST CHANGE   — Block contract execution until resolved
  SHOULD CHANGE — Strong recommendation, pursue in negotiation
  NICE TO HAVE  — Raise if negotiation capital allows
  ACCEPT        — Within acceptable range, no action needed

OUTPUT FORMAT (strict JSON):
{
  "analysis": [
    {
      "clause_id": "C001",
      "clause_type": "",
      "playbook_rule_applied": "",
      "deviation_summary": "",
      "legal_risk": "CRITICAL",
      "legal_risk_reasoning": "",
      "business_risk": "CRITICAL",
      "business_risk_reasoning": "",
      "real_world_impact": "",
      "negotiation_priority": "MUST CHANGE",
      "missing_protections": [],
      "favorable_elements": [],
      "unfavorable_elements": [],
      "jurisdiction_specific_notes": "",
      "human_review_required": true,
      "human_review_reason": ""
    }
  ],
  "overall_contract_risk": "CRITICAL",
  "overall_risk_summary": "",
  "critical_blockers": [],
  "recommended_next_step": ""
}

PLAYBOOK RULES:
{playbook_rules}
