import json
import argparse
from datetime import datetime
from pathlib import Path

BANNED_PATTERN = "-–—_"


def sanitize_output(text: str) -> str:
    if not text:
        return text
    # Remove fenced code blocks (``` or ~~~)
    # Simple conservative removal
    import re
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"~~~[\s\S]*?~~~", " ", text)
    # Replace banned characters with space
    text = re.sub(r"[-–—_]", " ", text)
    # Collapse spaces
    text = re.sub(r" {2,}", " ", text).strip()
    return text


def load_prompt(prompt_path: Path) -> dict:
    with prompt_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_context_files(paths):
    context_entries = []
    for p in paths:
        fp = Path(p)
        if not fp.exists():
            context_entries.append({"path": str(fp), "error": "missing"})
            continue
        try:
            content = fp.read_text(encoding="utf-8")
        except Exception as e:
            content = f"<read_error: {e}>"
        context_entries.append({"path": str(fp), "content": content})
    return context_entries


def build_payload(prompt_json: dict, job_description: str, job_title: str, company_name: str, hiring_manager: str = "Hiring Team", company_address: str = ""):
    current_date = datetime.now().strftime("%B %d, %Y")
    query_template = prompt_json["promptTemplate"]["query"]
    query_filled = (query_template
                    .replace("{{job_title}}", job_title)
                    .replace("{{company_name}}", company_name)
                    .replace("{{current_date}}", current_date)
                    .replace("{{job_description}}", job_description))
    system = prompt_json["systemInstruction"]["text"]
    resume_ctx = prompt_json["promptTemplate"]["resumeContext"]
    required = {
        "hiringManager": hiring_manager,
        "companyAddress": company_address,
    }
    payload = {
        "system": system,
        "query": query_filled,
        "resumeContext": resume_ctx,
        "requiredInputs": required,
        "rules": prompt_json.get("rules", []),
        "persona": prompt_json.get("persona", {}),
        "memory": prompt_json.get("memory", {}),
        "dynamicContext": prompt_json.get("dynamicContext", {}),
    }
    return payload


def main():
    parser = argparse.ArgumentParser(description="Prepare cover letter generation payload")
    parser.add_argument("--prompt", default="prompt.json", help="Path to prompt JSON file")
    parser.add_argument("--job-desc", required=True, help="Path to file containing raw job description")
    parser.add_argument("--job-title", required=True)
    parser.add_argument("--company-name", required=True)
    parser.add_argument("--hiring-manager", default="Hiring Team")
    parser.add_argument("--company-address", default="")
    parser.add_argument("--extra-context", nargs="*", default=[], help="Additional context file paths")
    parser.add_argument("--out", default="cover_letter_payload.json")
    args = parser.parse_args()

    prompt_json = load_prompt(Path(args.prompt))
    job_description = Path(args.job_desc).read_text(encoding="utf-8")

    payload = build_payload(prompt_json, job_description, args.job_title, args.company_name,
                            hiring_manager=args.hiring_manager, company_address=args.company_address)

    if args.extra_context:
        payload["contextFiles"] = load_context_files(args.extra_context)

    # Write raw payload (pre-generation)
    Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Payload written to {args.out}")

    print("Next step: send 'system' + 'query' + other fields to your model API. After receiving model text, run sanitize_output(text) if needed.")

if __name__ == "__main__":
    main()
