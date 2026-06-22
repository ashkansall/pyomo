import random
import time
from pathlib import Path
import plotly.graph_objects as go
import pandas as pd
from ortools.sat.python import cp_model


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = BASE_DIR / "results" / "ortools_stress_results.xlsx"

SHIFT_LENGTH = 8 * 60
MAINTENANCE_USAGE_LIMIT = 180
MAINTENANCE_CONDITION_DURATION = 30

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

# for gnatt chart 
PRODUCT_COLORS = {
    "P1": "#2563eb", "P2": "#16a34a", "P3": "#dc2626", "P4": "#9333ea",
    "P5": "#f97316", "P6": "#0891b2", "P7": "#be123c", "P8": "#65a30d",
}

MACHINE_PATTERNS = {
    "Cutting": "/", "Drilling": "\\", "Milling": "x",
    "Welding": ".", "Painting": "+", "Inspection": "-",
}


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
    op_day = {}
    condition_usage_vars = {}
    condition_maintenance_vars = {}

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
            op_day[(i, day)] = in_day
            day_choices.append(in_day)
            model.Add(start_vars[i] >= day * SHIFT_LENGTH).OnlyEnforceIf(in_day)
            model.Add(end_vars[i] <= (day + 1) * SHIFT_LENGTH).OnlyEnforceIf(in_day)

        model.AddExactlyOne(day_choices)

    if scenario["maintenance"]:
        for machine in MACHINES:
            machine_ops = [op for op in operations if op["machine"] == machine]

            for day in range(max_days):
                daily_usage = model.NewIntVar(0, SHIFT_LENGTH, f"usage_{machine}_day_{day + 1}")
                maintenance_required = model.NewBoolVar(f"condition_maintenance_{machine}_day_{day + 1}")

                condition_usage_vars[(machine, day)] = daily_usage
                condition_maintenance_vars[(machine, day)] = maintenance_required

                model.Add(
                    daily_usage
                    == sum(
                        op["duration"] * op_day[(op["operation_id"], day)]
                        for op in machine_ops
                    )
                )
                model.Add(daily_usage <= MAINTENANCE_USAGE_LIMIT).OnlyEnforceIf(maintenance_required.Not())
                model.Add(daily_usage >= MAINTENANCE_USAGE_LIMIT + 1).OnlyEnforceIf(maintenance_required)
                model.Add(
                    daily_usage
                    + MAINTENANCE_CONDITION_DURATION * maintenance_required
                    <= SHIFT_LENGTH
                )

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
        summary = {
            "scenario": scenario["name"],
            "status": solver.StatusName(status),
            "orders": len({order["order_id"] for order in orders}),
            "batches": len(orders),
            "operations": len(operations),
            "makespan_min": None,
            "solve_time_sec": round(solve_time, 3),
        }
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), summary

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

    condition_rows = []
    for machine in MACHINES:
        for day in range(max_days):
            key = (machine, day)
            if key in condition_usage_vars:
                required = solver.Value(condition_maintenance_vars[key])
                condition_rows.append(
                    {
                        "scenario": scenario["name"],
                        "machine": machine,
                        "day": day + 1,
                        "daily_usage_min": solver.Value(condition_usage_vars[key]),
                        "threshold_min": MAINTENANCE_USAGE_LIMIT,
                        "maintenance_required": required,
                        "maintenance_reserved_min": MAINTENANCE_CONDITION_DURATION if required == 1 else 0,
                    }
                )
    condition_maintenance = pd.DataFrame(condition_rows)

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

    return schedule, bottleneck, condition_maintenance, summary


def short_sheet_name(prefix, name):
    return f"{prefix}_{name}"[:31]





# gnatt demostration
def minute_label(minute):
    day = minute // SHIFT_LENGTH + 1
    shift_min = minute % SHIFT_LENGTH
    hour = 8 + shift_min // 60
    mins = shift_min % 60
    return f"Day {day} {hour:02d}:{mins:02d}"


def create_ortools_gantt(schedule, condition_df, scenario_name, max_days):
    if schedule.empty:
        print(f"No Gantt chart created for {scenario_name}: empty schedule")
        return

    chart_dir = BASE_DIR / "results" / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)

    machine_order = [m for m in MACHINES if m in schedule["machine"].unique()]
    y_pos = {machine: i for i, machine in enumerate(machine_order)}

    fig = go.Figure()

    # Alternating day background bands
    for day in range(max_days):
        x0 = day * SHIFT_LENGTH
        x1 = (day + 1) * SHIFT_LENGTH
        fig.add_shape(
            type="rect",
            x0=x0,
            x1=x1,
            y0=-0.7,
            y1=len(machine_order) - 0.3,
            fillcolor="rgba(240,240,240,0.35)" if day % 2 == 0 else "rgba(220,230,255,0.28)",
            line_width=0,
            layer="below",
        )
        fig.add_vline(
            x=x0,
            line_width=1,
            line_dash="dot",
            line_color="rgba(70,70,70,0.45)",
        )
        fig.add_annotation(
            x=x0 + SHIFT_LENGTH / 2,
            y=len(machine_order) - 0.15,
            text=f"Day {day + 1}",
            showarrow=False,
            font=dict(size=11, color="#374151"),
        )

    # Operation bars
    used_legend = set()
    for _, op in schedule.iterrows():
        product = op["product_id"]
        machine = op["machine"]
        show_legend = product not in used_legend
        used_legend.add(product)

        fig.add_trace(
            go.Bar(
                x=[op["duration"]],
                y=[y_pos[machine]],
                base=[op["start_min"]],
                orientation="h",
                width=0.58,
                name=product,
                legendgroup=product,
                showlegend=show_legend,
                marker=dict(
                    color=PRODUCT_COLORS.get(product, "#6b7280"),
                    line=dict(color="#111827", width=1.2),
                    pattern=dict(shape=MACHINE_PATTERNS.get(machine, "")),
                ),
                text=[f"{op['order_id']}<br>{product}"],
                textposition="inside",
                insidetextanchor="middle",
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Product: %{customdata[1]}<br>"
                    "Batch: %{customdata[2]}<br>"
                    "Machine: %{customdata[3]}<br>"
                    "Duration: %{customdata[4]} min<br>"
                    "Start: %{customdata[5]}<br>"
                    "End: %{customdata[6]}<extra></extra>"
                ),
                customdata=[[
                    op["order_id"],
                    product,
                    op["batch_id"],
                    machine,
                    op["duration"],
                    minute_label(int(op["start_min"])),
                    minute_label(int(op["end_min"])),
                ]],
            )
        )

    # Fixed planned maintenance windows
    planned = maintenance_windows(max_days)
    for machine, windows in planned.items():
        if machine not in y_pos:
            continue
        y = y_pos[machine]
        for start, duration in windows:
            fig.add_shape(
                type="rect",
                x0=start,
                x1=start + duration,
                y0=y - 0.42,
                y1=y + 0.42,
                fillcolor="rgba(75,85,99,0.55)",
                line=dict(color="#111827", width=2, dash="dash"),
            )
            fig.add_annotation(
                x=start + duration / 2,
                y=y,
                text="Planned<br>Maint.",
                showarrow=False,
                font=dict(size=9, color="white"),
            )

    # Condition-based maintenance: displayed at end of triggered shift
    if condition_df is not None and not condition_df.empty:
        triggered = condition_df[condition_df["maintenance_required"] == 1]

        for _, row in triggered.iterrows():
            machine = row["machine"]
            if machine not in y_pos:
                continue

            day = int(row["day"])
            reserved = int(row["maintenance_reserved_min"])
            x1 = day * SHIFT_LENGTH
            x0 = x1 - reserved
            y = y_pos[machine]

            fig.add_shape(
                type="rect",
                x0=x0,
                x1=x1,
                y0=y - 0.47,
                y1=y + 0.47,
                fillcolor="rgba(239,68,68,0.55)",
                line=dict(color="#991b1b", width=2),
            )

            fig.add_trace(
                go.Scatter(
                    x=[(x0 + x1) / 2],
                    y=[y],
                    mode="markers",
                    marker=dict(symbol="diamond", size=14, color="#ef4444", line=dict(color="white", width=1)),
                    name="Condition maintenance",
                    showlegend=False,
                    hovertemplate=(
                        f"<b>Condition-Based Maintenance</b><br>"
                        f"Machine: {machine}<br>"
                        f"Day: {day}<br>"
                        f"Daily usage: {row['daily_usage_min']} min<br>"
                        f"Reserved: {reserved} min<extra></extra>"
                    ),
                )
            )

    makespan = int(schedule["end_min"].max())
    fig.add_vline(x=makespan, line_width=3, line_dash="dash", line_color="black")
    fig.add_annotation(x=makespan, y=-0.55, text=f"Makespan: {makespan} min", showarrow=True)

    tick_step = 240
    x_ticks = list(range(0, max(makespan + tick_step, max_days * SHIFT_LENGTH + 1), tick_step))

    fig.update_layout(
        title=f"Detailed OR-Tools Gantt Chart - {scenario_name}",
        barmode="overlay",
        height=720,
        width=1450,
        plot_bgcolor="white",
        paper_bgcolor="white",
        xaxis=dict(
            title="Production time",
            tickvals=x_ticks,
            ticktext=[minute_label(x) for x in x_ticks],
            showgrid=True,
            gridcolor="rgba(180,180,180,0.35)",
        ),
        yaxis=dict(
            title="Machines",
            tickvals=list(y_pos.values()),
            ticktext=list(y_pos.keys()),
            autorange="reversed",
        ),
        legend=dict(title="Product ID", orientation="h", y=-0.18),
        margin=dict(l=110, r=40, t=80, b=120),
    )

    output_html = chart_dir / f"gantt_{scenario_name}.html"
    fig.write_html(output_html)
    print(f"Gantt chart created: {output_html}")

# gnatt demostration END


def main():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    summaries = []
    schedules = {}
    bottlenecks = {}
    condition_maintenance_results = {}

    print("Running OR-Tools open shop stress model")

    for scenario in SCENARIOS:
        schedule, bottleneck, condition_maintenance, summary = solve_scenario(scenario)
        summaries.append(summary)
        schedules[scenario["name"]] = schedule
        bottlenecks[scenario["name"]] = bottleneck
        condition_maintenance_results[scenario["name"]] = condition_maintenance

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

        for name, condition_df in condition_maintenance_results.items():
            if not condition_df.empty:
                condition_df.to_excel(writer, sheet_name=short_sheet_name("cbm", name), index=False)

        for name, schedule in schedules.items():
            schedule.to_excel(writer, sheet_name=short_sheet_name("sch", name), index=False)
            
        # gnatt demostration code
           
        chart_scenario_name = "04_realistic_constraints"
        chart_scenario = next(s for s in SCENARIOS if s["name"] == chart_scenario_name)

        create_ortools_gantt(
            schedules[chart_scenario_name],
            condition_maintenance_results[chart_scenario_name],
            chart_scenario_name,
            chart_scenario["max_days"],
        )
        # gnatt demostration code END

    print(f"\nExcel file created: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
