"""Replay synthetic incidents; --live explicitly benchmarks low-reasoning budgets.

Run: python -m scripts.evaluate_descriptions --live --output /tmp/description-eval.json
No production incident data is sent. At most nine provider calls are made.
"""
import argparse
import json
import os
import sqlite3
import tempfile
from unittest.mock import patch

from backend import db, llm
from backend.incident_facts import incident_facts, compact_input, severity_for, template_description

CASES = [
    {'name': 'lane_reopened', 'Source': 'CHP', 'Type': 'Traffic Collision', 'Location': 'I-5 northbound at Test Road',
     'Details': ['Two vehicles involved; injuries unknown', 'BLOCKING #1 LN', 'ALL LANES OPEN']},
    {'name': 'fsp_only_closed', 'Source': 'CHP', 'Type': 'Traffic Collision', 'Location': 'I-8 eastbound at Example Avenue',
     'Details': ['BLOCKING #1 LN', 'Injuries unknown', '[3] [FSP] has closed their incident [260923BCFSP0123]']},
    {'name': 'uncertain_report', 'Source': 'CHP', 'Type': 'Traffic Hazard', 'Location': 'SR-163 northbound at Test Street',
     'Details': ['Possible debris reported', 'ROAD NOT CLOSED', 'No injuries reported']},
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.live and (not llm.LLM_API_CONFIGURED or llm.TESTMODE):
        raise SystemExit('Live evaluation requires a configured API key and TESTMODE=false.')
    results = []
    stop = False
    with tempfile.TemporaryDirectory() as temp:
        path = os.path.join(temp, 'evaluation.db')
        db.init_db(path)
        for case in CASES:
            if stop:
                break
            facts = incident_facts(case)
            if not args.live:
                results.append({'case': case['name'], 'input': compact_input(facts), 'severity': severity_for(facts), 'template': template_description(facts)})
                continue
            for cap in (512, 1024, 2048):
                context = {'db_file': path, 'trigger_reason': 'evaluation', 'incident_no': case['name']}
                row = {'case': case['name'], 'max_tokens': cap, 'reasoning': 'low'}
                try:
                    with patch.object(llm, 'LLM_MAX_TOKENS', cap), patch.object(llm, 'LLM_REASONING_EFFORT', 'low'):
                        summary, severity = llm.generate_description(case, raise_on_error=True, usage_context=context)
                    row.update(summary=summary, severity=severity)
                except Exception as exc:
                    row['error'] = type(exc).__name__
                    stop = getattr(exc, 'status_code', None) in (400, 401, 402, 403, 404, 422)
                with sqlite3.connect(path) as conn:
                    conn.row_factory = sqlite3.Row
                    usage = conn.execute('SELECT input_tokens, completion_tokens, reasoning_tokens, cost, duration_seconds, finish_reason FROM llm_attempts WHERE id=?', (context.get('attempt_id'),)).fetchone()
                row['usage'] = dict(usage) if usage else None
                results.append(row)
                if stop:
                    break
    output = json.dumps(results, indent=2)
    if args.output:
        with open(args.output, 'w') as handle:
            handle.write(output + '\n')
    print(output)


if __name__ == '__main__':
    main()
