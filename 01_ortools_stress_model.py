
import random
import time
from pathlib import Path

import pandas as pd
from ortools.sat.python import cp_model


SHIFT_LENGTH = 8 * 60
OUTPUT_FILE = Path("outputs/final_open_shop/results/ortools_stress_results.xlsx")

MACHINES = ["Cutting", "Drilling", "Milling", "Welding", "Painting", "Inspection"]

PRODUCT_MACHINE_TIMES = {
    "P1": {"Cutting": 5, "Drilling": 3, "Painting": 4},
    "P2": {"Cutting": 4, "Milling": 6, "Painting": 5},
    "P3": {"Drilling": 4, "Welding": 7, "Painting": 3},
    "P4": {"Cutting": 6, "Milling": 5, "Inspection": 2},
    "P5": {"Welding": 5, "Painting": 4, "Inspection": 3},
    "P6": {"Cutting": 3, "Drilling": 5, "Milling": 4, "Painting": 2},
    "P7": {"Milling": 7, "Welding": 4, "Inspection": 2},
    "P8": {"Cutting": 4, "Drilling": 4, "Welding": 6, "Painting": 3},
}

ORIGINAL_ORDERS = [
    {"order_id": "O1", "batch_id": "O1_B1", "product_id": "P1", "quantity": 10},
    {"order_id": "O2", "batch_id": "O2_B1", "product_id": "P2", "quantity": 8},
    {"order_id": "O3", "batch_id": "O3_B1", "product_id": "P1", "quantity": 6},
    {"order_id": "O4", "batch_id": "O4_B1", "product_id": "P3", "quantity": 12},
]

SCENARIOS = [
    {
        "name": "01_same_case",
        "orders": ORIGINAL_ORDERS,
        "max_days": 5,
        "due_dates": True,
        "maintenance": True,
        "operator_limit": False,
        "time_limit": 5,
    },
    {
        "name": "02_more_products_batches",
        "orders": None,
        "num_orders": 15,
        "max_batches": 3,
        "quantity_min": 4,
        "quantity_max": 14,
        "max_days": 10,
        "due_dates": False,
        "maintenance": False,
        "operator_limit": False,
        "time_limit": 8,
    },
    {
        "name": "03_due_dates",
        "orders": None,
        "num_orders": 25,
        "max_batches": 3,
        "quantity_min": 5,
        "quantity_max": 16,
        "max_days": 15,
        "due_dates": True,
        "maintenance": False,
        "operator_limit": False,
        "time_limit": 10,
    },
    {
        "name": "04_realistic_constraints",
        "orders": None,
        "num_orders": 35,
        "max_batches": 4,
        "quantity_min": 5,
        "quantity_max": 18,
        "max_days": 20,
        "due_dates": True,
        "maintenance": True,
        "operator_limit": True,
        "operator_capacity": 3,
        "time_limit": 15,
    },
    {
        "name": "05_large_stress",
        "orders": None,
        "num_orders": 60,
        "max_batches": 4,
        "quantity_min": 5,
        "quantity_max": 20,
        "max_days": 30,
        "due_dates": True,
        "maintenance": True,
        "operator_limit": True,
        "operator_capacity": 3,
        "time_limit": 20,
    },
]


def generate_orders(num_orders, max_batches, quantity_min, quantity_max, seed=7):
    random.seed(seed)
    product_ids = list(PRODUCT_MACHINE_TIMES)
    orders = []

    for order_number in range(1, num_orders + 1):
        product_id = random.choice(product_ids)
        batch_count = random.randint(1, max_batches)
        total_quantity = random.randint(quantity_min, quantity_max)
        remaining = total_quantity

        for batch_number in range(1, batch_count + 1):
            batches_left = batch_count - batch_number + 1
            if batches_left == 1:
                quantity = remaining
            else:
                quantity = random.randint(1, remaining - batches_left + 1)
            remaining -= quantity

            orders.append(
                {
                    "order_id": f"O{order_number:03d}",
                    "batch_id": f"O{order_number:03d}_B{batch_number}",
                    "product_id": product_id,
                    "quantity": quantity,
                }
            )

    return orders


def get_orders(scenario):
    if scenario["orders"] is not None:
        return scenario["orders"]

    return generate_orders(
        scenario["num_orders"],
        scenario["max_batches"],
        scenario["quantity_min"],
        scenario["quantity_max"],
    )


def build_operations(orders):
    operations = []

    for order in orders:
        product_id = order["product_id"]
        quantity = order["quantity"]

        for machine, cycle_time in PRODUCT_MACHINE_TIMES[product_id].items():
            operations.append(
                {
                    "operation_id": len(operations),
                    "order_id": order["order_id"],
                    "batch_id": order["batch_id"],
                    "product_id": product_id,
                    "machine": machine,
                    "quantity": quantity,
                    "duration": cycle_time * quantity,
                }
            )

    return operations


def create_due_dates(orders, max_days):
    due_dates = {}
    order_ids = sorted({order["order_id"] for order in orders})

    for index, order_id in enumerate(order_ids):
        due_day = 1 + index // 2
        due_dates[order_id] = min(due_day * SHIFT_LENGTH, max_days * SHIFT_LENGTH)

    return due_dates


def maintenance_windows(max_days):
    windows = {machine: [] for machine in MACHINES}

    windows["Cutting"].append((120, 60))
    windows["Painting"].append((300, 60))

    if max_days >= 4:
        windows["Painting"].append((2 * SHIFT_LENGTH + 180, 90))
        windows["Cutting"].append((3 * SHIFT_LENGTH + 120, 60))

    if max_days >= 8:
        windows["Milling"].append((6 * SHIFT_LENGTH + 240, 120))
        windows["Inspection"].append((7 * SHIFT_LENGTH + 60, 90))

    return windows


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


def solve_scenario(scenario):
    orders = get_orders(scenario)
    operations = build_operations(orders)
    max_days = scenario["max_days"]
    horizon = max_days * SHIFT_LENGTH

    model = cp_model.CpModel()

    start_vars = {}
    end_vars = {}
    intervals = {}
    machine_intervals = {machine: [] for machine in MACHINES}
    batch_intervals = {}

    for op in operations:
        i = op["operation_id"]
        start = model.NewIntVar(0, horizon, f"start_{i}")
        end = model.NewIntVar(0, horizon, f"end_{i}")
        interval = model.NewIntervalVar(start, op["duration"], end, f"interval_{i}")

        start_vars[i] = start
        end_vars[i] = end
        intervals[i] = interval
        machine_intervals[op["machine"]].append(interval)
        batch_intervals.setdefault(op["batch_id"], []).append(interval)

    if scenario["maintenance"]:
        for machine, windows in maintenance_windows(max_days).items():
            for index, (start, duration) in enumerate(windows):
                blocked = model.NewFixedSizeIntervalVar(start, duration, f"maintenance_{machine}_{index}")
                machine_intervals[machine].append(blocked)

    for machine in MACHINES:
        model.AddNoOverlap(machine_intervals[machine])

    for batch_id in batch_intervals:
        model.AddNoOverlap(batch_intervals[batch_id])

    for op in operations:
        i = op["operation_id"]
        day_choices = []

        for day in range(max_days):
            in_day = model.NewBoolVar(f"op_{i}_day_{day + 1}")
            day_choices.append(in_day)
            model.Add(start_vars[i] >= day * SHIFT_LENGTH).OnlyEnforceIf(in_day)
            model.Add(end_vars[i] <= (day + 1) * SHIFT_LENGTH).OnlyEnforceIf(in_day)

        model.AddExactlyOne(day_choices)

    if scenario["operator_limit"]:
        model.AddCumulative(
            list(intervals.values()),
            [1] * len(intervals),
            scenario.get("operator_capacity", 3),
        )

    makespan = model.NewIntVar(0, horizon, "makespan")
    model.AddMaxEquality(makespan, list(end_vars.values()))

    tardiness_vars = []
    if scenario["due_dates"]:
        due_dates = create_due_dates(orders, max_days)

        for order_id, due_date in due_dates.items():
            order_ends = [end_vars[op["operation_id"]] for op in operations if op["order_id"] == order_id]
            completion = model.NewIntVar(0, horizon, f"completion_{order_id}")
            tardiness = model.NewIntVar(0, horizon, f"tardiness_{order_id}")
            model.AddMaxEquality(completion, order_ends)
            model.Add(tardiness >= completion - due_date)
            model.Add(tardiness >= 0)
            tardiness_vars.append(tardiness)

    model.Minimize(makespan * 1000 + sum(tardiness_vars))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = scenario["time_limit"]
    solver.parameters.num_search_workers = 8
    solver.parameters.relative_gap_limit = 0.02

    solve_start = time.perf_counter()
    status = solver.Solve(model)
    solve_time = time.perf_counter() - solve_start

    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        return pd.DataFrame(), pd.DataFrame(), {
            "scenario": scenario["name"],
            "status": solver.StatusName(status),
            "orders": len({order["order_id"] for order in orders}),
            "batches": len(orders),
            "operations": len(operations),
            "makespan_min": None,
            "solve_time_sec": round(solve_time, 3),
        }

    rows = []
    for op in operations:
        i = op["operation_id"]
        start = solver.Value(start_vars[i])
        end = solver.Value(end_vars[i])

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
    bottleneck = calculate_bottleneck(schedule, solver.Value(makespan))

    summary = {
        "scenario": scenario["name"],
        "status": solver.StatusName(status),
        "orders": len({order["order_id"] for order in orders}),
        "batches": len(orders),
        "operations": len(operations),
        "due_dates": scenario["due_dates"],
        "maintenance": scenario["maintenance"],
        "operator_limit": scenario["operator_limit"],
        "makespan_min": solver.Value(makespan),
        "makespan_days": round(solver.Value(makespan) / SHIFT_LENGTH, 3),
        "total_tardiness_min": sum(solver.Value(var) for var in tardiness_vars),
        "bottleneck_machine": bottleneck.iloc[0]["machine"],
        "bottleneck_utilization_percent": bottleneck.iloc[0]["utilization_percent"],
        "solve_time_sec": round(solve_time, 3),
        "best_bound": round(solver.BestObjectiveBound(), 3),
        "objective_value": round(solver.ObjectiveValue(), 3),
    }

    return schedule, bottleneck, summary


def short_sheet_name(prefix, name):
    return f"{prefix}_{name}"[:31]


def main():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    summaries = []
    schedules = {}
    bottlenecks = {}

    print("Running OR-Tools open shop stress model")

    for scenario in SCENARIOS:
        schedule, bottleneck, summary = solve_scenario(scenario)
        summaries.append(summary)
        schedules[scenario["name"]] = schedule
        bottlenecks[scenario["name"]] = bottleneck

        print(
            f"{scenario['name']}: {summary['status']}, "
            f"operations={summary['operations']}, "
            f"makespan={summary['makespan_min']}, "
            f"time={summary['solve_time_sec']} sec"
        )

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        pd.DataFrame(summaries).to_excel(writer, sheet_name="Stress Summary", index=False)

        for name, bottleneck in bottlenecks.items():
            bottleneck.to_excel(writer, sheet_name=short_sheet_name("bn", name), index=False)

        for name, schedule in schedules.items():
            schedule.to_excel(writer, sheet_name=short_sheet_name("sch", name), index=False)

    print(f"\nExcel file created: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
