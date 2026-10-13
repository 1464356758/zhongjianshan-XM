#!/usr/bin/env python3
"""Offline illustrative first-order economics; no accounts, network or messaging."""
import argparse
import json
import math
from pathlib import Path


def number(value, field, fraction=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    if not math.isfinite(value) or value < 0 or (fraction and value > 1):
        raise ValueError(f"{field} must be finite and within the allowed range")
    return value


def calculate_case(case):
    n = number(case["submissions"], "submissions")
    if int(n) != n:
        raise ValueError("submissions must be an integer")
    q = number(case["qualified_rate"], "qualified_rate", True)
    p = number(case["payable_given_qualified_rate"], "payable_given_qualified_rate", True)
    c = number(case["collection_scenario_rate"], "collection_scenario_rate", True)
    pricing = case["pricing"]
    if pricing["type"] == "share":
        base = number(pricing["recognized_base_per_payable"], "recognized_base_per_payable")
        share = number(pricing["channel_share"], "channel_share", True)
        fee = base * share
    elif pricing["type"] == "fixed_per_payable":
        base = None
        fee = number(pricing["fee_per_payable"], "fee_per_payable")
    else:
        raise ValueError("Unknown pricing type")
    costs = case["cash_costs_excluding_owner_labor"]
    total_cost = n * number(costs["per_submission"], "per_submission")
    total_cost += sum(number(costs[k], k) for k in ("recruitment_allocated", "setup", "overhead_allocated"))
    labor = case["owner_labor"]
    hours = n * number(labor["minutes_per_submission"], "minutes_per_submission") / 60
    hours += number(labor["other_hours"], "other_hours")
    labor_value = hours * number(labor["value_per_hour"], "value_per_hour")
    payable = n * q * p
    earned = payable * fee
    collected = earned * c
    denom = payable * c
    min_fee = (total_cost + labor_value) / denom if denom > 0 else None
    return {
        "case_id": case["id"], "name": case["name"],
        "status": "ILLUSTRATIVE_NOT_MARKET_QUOTE_NOT_ACTUAL_REVENUE",
        "expected_payable_count": payable,
        "fee_per_payable": fee,
        "expected_earned_service_fee": earned,
        "collection_scenario_amount": collected,
        "scenario_uncollected_receivable": earned - collected,
        "cash_cost_excluding_owner_labor": total_cost,
        "expected_earned_contribution_before_owner_labor": earned - total_cost,
        "collection_scenario_cash_contribution": collected - total_cost,
        "owner_hours": hours,
        "owner_labor_value": labor_value,
        "collection_scenario_contribution_after_owner_labor": collected - total_cost - labor_value,
        "minimum_fee_per_payable_in_collection_scenario_including_owner_labor": min_fee,
        "minimum_share_of_recognized_base": min_fee / base if min_fee is not None and base else None,
        "conditions": ["Actual permission, pricing, attribution and payout are not verified by this calculation",
                       "Creator rewards and platform fees are excluded from our revenue and expenses here",
                       "Uncollected amounts remain receivables; this does not waive payer obligations",
                       "Unlisted taxes, bad debts and other costs remain outside this illustrative model"]
    }


def calculate(spec):
    if spec["input_kind"] != "ILLUSTRATIVE_ASSUMPTIONS":
        raise ValueError("This file only accepts clearly labelled illustrative assumptions")
    ids = [c["id"] for c in spec["cases"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate case IDs")
    return {"input_kind": spec["input_kind"], "cases": [calculate_case(c) for c in spec["cases"]]}


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=root / "data/首单测算假设.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = calculate(json.loads(args.input.read_text(encoding="utf-8")))
    body = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(body, encoding="utf-8")
    else:
        print(body, end="")


if __name__ == "__main__":
    main()
