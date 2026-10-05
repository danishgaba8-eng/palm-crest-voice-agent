"""Place an outbound call: the agent rings a lead and offers a consultation.

Usage:
    python -m voice_agent.outbound --to +971501234567 --name "Sara" --reason "enquired about 2-bed rentals in JVC"
"""

import argparse
import os

from dotenv import load_dotenv
from retell import Retell


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--to", required=True, help="Lead's number in E.164 format, e.g. +971501234567")
    parser.add_argument("--name", required=True, help="Lead's first name")
    parser.add_argument("--reason", required=True, help="Why we're calling, as the agent should say it")
    args = parser.parse_args()

    load_dotenv()
    retell = Retell(api_key=os.environ["RETELL_API_KEY"])
    call = retell.call.create_phone_call(
        from_number=os.environ["RETELL_FROM_NUMBER"],
        to_number=args.to,
        retell_llm_dynamic_variables={
            "call_type": "outbound",
            "lead_name": args.name,
            "call_reason": args.reason,
        },
    )
    print(f"Call started: {call.call_id}")


if __name__ == "__main__":
    main()
