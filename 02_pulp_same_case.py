import time
from pathlib import Path

import pandas as pd
import pulp


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = BASE_DIR / "results" / "pulp_same_case_results.xlsx"

SHIFT_LENGTH = 8 * 60
MAX_DAYS = 5
HORIZON = SHIFT_LENGTH * MAX_DAYS
BIG_M = HORIZON
MAINTENANCE_USAGE_LIMIT = 180
MAINTENANCE_CONDITION_DURATION = 30

ORDERS = [
    {"order_id": "O1", "batch_id": "O1_B1", "product_id": "P1", "quantity": 10},
    {"order_id": "O2", "batch_id": "O2_B1", "product_id": "P2", "quantity": 8},
    {"order_id": "O3", "batch_id": "O3_B1", "product_id": "P1", "quantity": 6},
    {"order_id": "O4", "batch_id": "O4_B1", "product_id": "P3", "quantity": 12},
]

PRODUCT_MACHINE_TIMES = {
    "P1": {"Cutting": 5, "Drilling": 3, "Painting": 4},
    "P2": {"Cutting": 4, "Milling": 6, "Painting": 5},
    "P3": {"Drilling": 4, "Welding": 7, "Painting": 3},
}

MACHINES = ["Cutting", "Drilling", "Milling", "Welding", "Painting"]

DUE_DATES = {
    "O1": 480,
    "O2": 480,
    "O3": 960,
    "O4": 960,
}

MAINTENANCE_WINDOWS = {
    "Cutting": [(120, 60)],
    "Painting": [(300, 60)],
}


def build_operations():
    operations = []

    for order in ORDERS:
        for machine, cycle_time in PRODUCT_MACHINE_TIMES[order["product_id"]].items():
            operations.append(
                {
                    "operation_id": len(operations),
                    "order_id": order["order_id"],
                    "batch_id": order["batch_id"],
                    "product_id": order["product_id"],
                    "machine": machine,
                    "quantity": order["quantity"],
                    "duration": cycle_time * order["quantity"],
                }
            )

    return operations


def add_no_overlap(model, start_vars, operations, name, counter):
    for left_index in range(len(operations)):
        for right_index in range(left_index + 1, len(operations)):
            left = operations[left_index]
            right = operations[right_index]
            i = left["operation_id"]
            j = right["operation_id"]

            i_before_j = pulp.LpVariable(f"{name}_{i}_before_{j}", cat="Binary")
            counter["binary_variables"] += 1

            model += start_vars[i] + left["duration"] <= start_vars[j] + BIG_M * (1 - i_before_j)
            model += start_vars[j] + right["duration"] <= start_vars[i] + BIG_M * i_before_j


def add_maintenance_constraints(model, start_vars, operations, counter):
    for op in operations:
        machine = op["machine"]

        for window_index, (window_start, window_duration) in enumerate(MAINTENANCE_WINDOWS.get(machine, [])):
            i = op["operation_id"]
            window_end = window_start + window_duration
            before_window = pulp.LpVariable(f"op_{i}_before_maintenance_{window_index}", cat="Binary")
            counter["binary_variables"] += 1

            model += start_vars[i] + op["duration"] <= window_start + BIG_M * (1 - before_window)
            model += start_vars[i] >= window_end - BIG_M * before_window


def calculate_bottleneck(schedule, makespan):
    load = (
        schedule.groupby("machine", as_index=False)["duration"]
        .sum()
        .rename(columns={"duration": "machine_load_min"})
    )
    load["makespan_min"] = makespan
    load["utilization_percent"] = (100 * load["machine_load_min"] / makespan).round(2)
    load["bottleneck_rank"] = load["machine_load_min"].rank(ascending=False, method="dense").astype(int)
    return load.sort_values(["bottleneck_rank", "machine"])


def main():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    operations = build_operations()
    counter = {"binary_variables": 0}
    op_day = {}
    condition_usage_vars = {}
    condition_maintenance_vars = {}

    model = pulp.LpProblem("open_shop_pulp_same_case", pulp.LpMinimize)

    start_vars = {
        op["operation_id"]: pulp.LpVariable(f"start_{op['operation_id']}", 0, HORIZON, cat="Integer")
        for op in operations
    }
    end_vars = {
        op["operation_id"]: pulp.LpVariable(f"end_{op['operation_id']}", 0, HORIZON, cat="Integer")
        for op in operations
    }
    makespan = pulp.LpVariable("makespan", 0, HORIZON, cat="Integer")

    for op in operations:
        i = op["operation_id"]
        model += end_vars[i] == start_vars[i] + op["duration"]
        model += makespan >= end_vars[i]

    for machine in MACHINES:
        machine_ops = [op for op in operations if op["machine"] == machine]
        add_no_overlap(model, start_vars, machine_ops, f"machine_{machine}", counter)

    for order in ORDERS:
        order_ops = [op for op in operations if op["order_id"] == order["order_id"]]
        add_no_overlap(model, start_vars, order_ops, f"order_{order['order_id']}", counter)

    for op in operations:
        i = op["operation_id"]
        day_choices = []

        for day in range(MAX_DAYS):
            in_day = pulp.LpVariable(f"op_{i}_day_{day + 1}", cat="Binary")
            op_day[(i, day)] = in_day
            counter["binary_variables"] += 1
            day_choices.append(in_day)

            model += start_vars[i] >= day * SHIFT_LENGTH - BIG_M * (1 - in_day)
            model += end_vars[i] <= (day + 1) * SHIFT_LENGTH + BIG_M * (1 - in_day)

        model += sum(day_choices) == 1

    for machine in MACHINES:
        machine_ops = [op for op in operations if op["machine"] == machine]

        for day in range(MAX_DAYS):
            daily_usage = pulp.LpVariable(
                f"usage_{machine}_day_{day + 1}",
                lowBound=0,
                upBound=SHIFT_LENGTH,
                cat="Integer",
            )
            maintenance_required = pulp.LpVariable(
                f"condition_maintenance_{machine}_day_{day + 1}",
                cat="Binary",
            )
            counter["binary_variables"] += 1
            condition_usage_vars[(machine, day)] = daily_usage
            condition_maintenance_vars[(machine, day)] = maintenance_required

            model += daily_usage == sum(
                op["duration"] * op_day[(op["operation_id"], day)]
                for op in machine_ops
            )
            model += daily_usage <= MAINTENANCE_USAGE_LIMIT + BIG_M * maintenance_required
            model += daily_usage >= MAINTENANCE_USAGE_LIMIT + 1 - BIG_M * (1 - maintenance_required)
            model += daily_usage + MAINTENANCE_CONDITION_DURATION * maintenance_required <= SHIFT_LENGTH

    add_maintenance_constraints(model, start_vars, operations, counter)

    tardiness_vars = {}
    for order in ORDERS:
        order_id = order["order_id"]
        completion = pulp.LpVariable(f"completion_{order_id}", 0, HORIZON, cat="Integer")
        tardiness = pulp.LpVariable(f"tardiness_{order_id}", 0, HORIZON, cat="Integer")
        tardiness_vars[order_id] = tardiness

        for op in operations:
            if op["order_id"] == order_id:
                model += completion >= end_vars[op["operation_id"]]

        model += tardiness >= completion - DUE_DATES[order_id]

    model += makespan * 1000 + sum(tardiness_vars.values())

    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=15)

    start_time = time.perf_counter()
    status = model.solve(solver)
    solve_time = time.perf_counter() - start_time

    rows = []
    for op in operations:
        i = op["operation_id"]
        start = int(round(pulp.value(start_vars[i])))
        end = int(round(pulp.value(end_vars[i])))

        rows.append(
            {
                **op,
                "start_min": start,
                "end_min": end,
                "start_day": start // SHIFT_LENGTH + 1,
                "end_day": (end - 1) // SHIFT_LENGTH + 1,
            }
        )

    schedule = pd.DataFrame(rows).sort_values(["start_min", "machine"])
    final_makespan = int(round(pulp.value(makespan)))
    bottleneck = calculate_bottleneck(schedule, final_makespan)

    condition_rows = []
    for machine in MACHINES:
        for day in range(MAX_DAYS):
            key = (machine, day)
            required = int(round(pulp.value(condition_maintenance_vars[key])))
            condition_rows.append(
                {
                    "solver": "PuLP CBC",
                    "machine": machine,
                    "day": day + 1,
                    "daily_usage_min": int(round(pulp.value(condition_usage_vars[key]))),
                    "threshold_min": MAINTENANCE_USAGE_LIMIT,
                    "maintenance_required": required,
                    "maintenance_reserved_min": MAINTENANCE_CONDITION_DURATION if required == 1 else 0,
                }
            )
    condition_maintenance = pd.DataFrame(condition_rows)

    summary = pd.DataFrame(
        [
            {
                "solver": "PuLP CBC",
                "status": pulp.LpStatus[status],
                "operations": len(operations),
                "makespan_min": final_makespan,
                "total_tardiness_min": int(round(sum(pulp.value(v) for v in tardiness_vars.values()))),
                "binary_variables": counter["binary_variables"],
                "solve_time_sec": round(solve_time, 3),
                "formulation": "MILP with big-M and binary ordering variables",
            }
        ]
    )

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)
        schedule.to_excel(writer, sheet_name="Schedule", index=False)
        bottleneck.to_excel(writer, sheet_name="Bottleneck", index=False)
        condition_maintenance.to_excel(writer, sheet_name="Condition Maintenance", index=False)

    print(summary.to_string(index=False))
    print(f"\nExcel file created: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
