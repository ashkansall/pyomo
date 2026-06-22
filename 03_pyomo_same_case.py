
import time
from pathlib import Path

import pandas as pd
from pyomo.environ import (
    Binary,
    ConcreteModel,
    ConstraintList,
    NonNegativeIntegers,
    Objective,
    SolverFactory,
    Var,
    minimize,
    value,
)


SHIFT_LENGTH = 8 * 60
MAX_DAYS = 5
HORIZON = SHIFT_LENGTH * MAX_DAYS
BIG_M = HORIZON

# adding maintenance non-linear constraints 
maintenance_usage_limit = 180
maintenance_condition_duration = 30

OUTPUT_FILE = Path("outputs/final_open_shop/results/pyomo_same_case_results.xlsx")

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


def pairwise_keys(operations):
    """Create binary ordering keys for no-overlap constraints."""
    keys = []

    for machine in MACHINES:
        machine_ops = [op for op in operations if op["machine"] == machine]
        keys.extend(create_pairs(machine_ops, f"machine_{machine}"))

    for order in ORDERS:
        order_ops = [op for op in operations if op["order_id"] == order["order_id"]]
        keys.extend(create_pairs(order_ops, f"order_{order['order_id']}"))

    return keys


def create_pairs(operations, group_name):
    pairs = []

    for left_index in range(len(operations)):
        for right_index in range(left_index + 1, len(operations)):
            left = operations[left_index]
            right = operations[right_index]
            pairs.append(
                (
                    group_name,
                    left["operation_id"],
                    right["operation_id"],
                    left["duration"],
                    right["duration"],
                )
            )

    return pairs


def maintenance_keys(operations):
    keys = []

    for op in operations:
        for window_index, (window_start, window_duration) in enumerate(MAINTENANCE_WINDOWS.get(op["machine"], [])):
            keys.append(
                (
                    op["operation_id"],
                    window_index,
                    op["duration"],
                    window_start,
                    window_start + window_duration,
                )
            )

    return keys


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

    operation_ids = [op["operation_id"] for op in operations]
    order_ids = sorted({order["order_id"] for order in ORDERS})
    day_keys = [(op["operation_id"], day) for op in operations for day in range(MAX_DAYS)]
    ordering_keys = pairwise_keys(operations)
    maint_keys = maintenance_keys(operations)
    
    # for conditioned-based maintenance 
    
    condition_maintenance_keys = [
    (machine, day)
    for machine in MACHINES
    for day in range(MAX_DAYS)
    ]

    duration = {op["operation_id"]: op["duration"] for op in operations}

    model = ConcreteModel()
    model.start = Var(operation_ids, within=NonNegativeIntegers, bounds=(0, HORIZON))
    model.end = Var(operation_ids, within=NonNegativeIntegers, bounds=(0, HORIZON))
    model.makespan = Var(within=NonNegativeIntegers, bounds=(0, HORIZON))
    model.in_day = Var(day_keys, within=Binary)
    model.ordering = Var(range(len(ordering_keys)), within=Binary)
    model.before_maintenance = Var(range(len(maint_keys)), within=Binary)
    
    # for conditioned based maintenance 
    model.condition_maintenance = Var(condition_maintenance_keys, within=Binary)
    
    model.completion = Var(order_ids, within=NonNegativeIntegers, bounds=(0, HORIZON))
    model.tardiness = Var(order_ids, within=NonNegativeIntegers, bounds=(0, HORIZON))

    model.constraints = ConstraintList()

    for op in operations:
        i = op["operation_id"]
        model.constraints.add(model.end[i] == model.start[i] + duration[i])
        model.constraints.add(model.makespan >= model.end[i])

    for index, (_, i, j, duration_i, duration_j) in enumerate(ordering_keys):
        y = model.ordering[index]
        model.constraints.add(model.start[i] + duration_i <= model.start[j] + BIG_M * (1 - y))
        model.constraints.add(model.start[j] + duration_j <= model.start[i] + BIG_M * y)

    for op in operations:
        i = op["operation_id"]
        model.constraints.add(sum(model.in_day[i, day] for day in range(MAX_DAYS)) == 1)

        for day in range(MAX_DAYS):
            model.constraints.add(model.start[i] >= day * SHIFT_LENGTH - BIG_M * (1 - model.in_day[i, day]))
            model.constraints.add(model.end[i] <= (day + 1) * SHIFT_LENGTH + BIG_M * (1 - model.in_day[i, day]))
            
            
    # for conditioned based maintenance
    
    for machine in MACHINES:
        machine_ops = [op for op in operations if op["machine"] == machine]

    for day in range(MAX_DAYS):
        daily_usage = sum(
            duration[op["operation_id"]] * model.in_day[op["operation_id"], day]
            for op in machine_ops
        )

        maintenance_required = model.condition_maintenance[machine, day]

        model.constraints.add(
            daily_usage
            <= maintenance_usage_limit + BIG_M * maintenance_required
        )

        model.constraints.add(
            daily_usage
            >= maintenance_usage_limit + 1
            - BIG_M * (1 - maintenance_required)
        )

        model.constraints.add(
            daily_usage
            + maintenance_condition_duration * maintenance_required
            <= SHIFT_LENGTH
        )
        
    for index, (i, _, op_duration, window_start, window_end) in enumerate(maint_keys):
        before = model.before_maintenance[index]
        model.constraints.add(model.start[i] + op_duration <= window_start + BIG_M * (1 - before))
        model.constraints.add(model.start[i] >= window_end - BIG_M * before)

    for order_id in order_ids:
        for op in operations:
            if op["order_id"] == order_id:
                model.constraints.add(model.completion[order_id] >= model.end[op["operation_id"]])

        model.constraints.add(model.tardiness[order_id] >= model.completion[order_id] - DUE_DATES[order_id])

    model.objective = Objective(
        expr=model.makespan * 1000 + sum(model.tardiness[order_id] for order_id in order_ids),
        sense=minimize,
    )

    solver = SolverFactory("appsi_highs")
    solver.options["time_limit"] = 15

    start_time = time.perf_counter()
    result = solver.solve(model)
    solve_time = time.perf_counter() - start_time

    rows = []
    for op in operations:
        i = op["operation_id"]
        start = int(round(value(model.start[i])))
        end = int(round(value(model.end[i])))

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
    final_makespan = int(round(value(model.makespan)))
    bottleneck = calculate_bottleneck(schedule, final_makespan)
    total_tardiness = int(round(sum(value(model.tardiness[order_id]) for order_id in order_ids)))

    # binary_variables = len(day_keys) + len(ordering_keys) + len(maint_keys)
    # after adding conditioned based constraints :
    binary_variables = (
        len(day_keys)
        + len(ordering_keys)
        + len(maint_keys)
        + len(condition_maintenance_keys)
    )

    summary = pd.DataFrame(
        [
            {
                "solver": "Pyomo HiGHS",
                "status": str(result.solver.termination_condition),
                "operations": len(operations),
                "makespan_min": final_makespan,
                "total_tardiness_min": total_tardiness,
                "binary_variables": binary_variables,
                "solve_time_sec": round(solve_time, 3),
                "formulation": "MILP with big-M and binary ordering variables",
            }
        ]
    )

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)
        schedule.to_excel(writer, sheet_name="Schedule", index=False)
        bottleneck.to_excel(writer, sheet_name="Bottleneck", index=False)

    print(summary.to_string(index=False))
    print(f"\nExcel file created: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
