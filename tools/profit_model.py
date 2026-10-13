#!/usr/bin/env python3
"""Recalculate illustrative local scenarios. No network or messaging."""
import argparse
import json
import math
from pathlib import Path

def check_fraction(name, value):
    if not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise ValueError(f"{name} must be in [0, 1]")

def calculate(spec):
    music = []
    for m in spec["music"]:
        for field in ("active_rate", "qualified_rate", "payable_rate", "channel_share"):
            check_fraction(field, m[field])
        for field in ("creators", "submissions_per_active", "approved_gross_per_paid",
                      "cost_per_submission", "fixed_cost", "minutes_per_submission",
                      "other_month_hours"):
            if m[field] < 0:
                raise ValueError(f"{field} cannot be negative")
        submitted = m["creators"] * m["active_rate"] * m["submissions_per_active"]
        payable = submitted * m["qualified_rate"] * m["payable_rate"]
        revenue = payable * m["approved_gross_per_paid"] * m["channel_share"]
        variable = submitted * m["cost_per_submission"]
        music.append(dict(m, submissions=submitted, payable=payable,
                          channel_revenue=revenue, variable_cost=variable,
                          pre_tax_operating_profit=revenue-variable-m["fixed_cost"],
                          total_execution_hours=submitted*m["minutes_per_submission"]/60
                                                +m["other_month_hours"]))
    brand = []
    for m in spec["brand"]:
        for field in ("service_rate", "execution_cost_rate", "loss_reserve_rate"):
            check_fraction(field, m[field])
        if m["creator_budget"] < 0 or m["fixed_cost"] < 0:
            raise ValueError("Budget and fixed costs cannot be negative")
        brand.append(dict(m, service_revenue=m["creator_budget"]*m["service_rate"],
                          execution_cost=m["creator_budget"]*m["execution_cost_rate"],
                          loss_reserve=m["creator_budget"]*m["loss_reserve_rate"],
                          pre_tax_operating_profit=m["creator_budget"]*(
                              m["service_rate"]-m["execution_cost_rate"]-
                              m["loss_reserve_rate"])-m["fixed_cost"]))
    scale = spec["music"][2]
    per_creator = scale["active_rate"]*scale["submissions_per_active"]*(
        scale["qualified_rate"]*scale["payable_rate"]*
        scale["approved_gross_per_paid"]*scale["channel_share"] -
        scale["cost_per_submission"])
    target_music = []
    for target in spec["target"]:
        target_music.append({
            "monthly_profit_target": target,
            "creators_required_under_scale_assumptions":
                math.ceil((target+scale["fixed_cost"])/per_creator) if per_creator > 0 else None,
            **({"note": "No finite profitable scale under these assumptions"}
               if per_creator <= 0 else {})
        })
    targets = {"music": target_music, "brand": []}
    for target, fixed, case in ((50000,20000,spec["brand"][1]),
                               (100000,45000,spec["brand"][2])):
        contribution = case["service_rate"]-case["execution_cost_rate"]-case["loss_reserve_rate"]
        targets["brand"].append({
            "monthly_profit_target": target, "fixed_cost": fixed,
            "creator_budget_required":
                math.ceil((target+fixed)/contribution) if contribution > 0 else None
        })
    return {"music": music, "brand": brand, "targets": targets}

def main():
    default = Path(__file__).resolve().parents[1]/"data/profit_assumptions.json"
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, default=default)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    result = calculate(json.loads(a.input.read_text(encoding="utf-8")))
    body = json.dumps(result, ensure_ascii=False, indent=2)+"\n"
    if a.output:
        a.output.write_text(body, encoding="utf-8")
    else:
        print(body, end="")

if __name__ == "__main__":
    main()

