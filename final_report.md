# Open Shop Scheduling Project Report

## 1. Project Idea

This project solves an open shop scheduling problem for a manufacturing system.

The company has customer orders. Each order has:

- an order ID
- a batch ID
- a product ID
- a quantity

Each product needs processing on selected machines such as Cutting, Drilling, Milling, Welding, Painting, and Inspection.

The processing time is calculated as:

```text
operation duration = cycle time per unit x order quantity
```

The goal is to create a feasible production schedule and minimize the makespan.

```text
makespan = finish time of the last completed operation
```

This is an open shop problem because the operations of the same order do not have a fixed sequence. The optimizer can decide the best order of operations.

## 2. Project Files

The project has three main model files:

| File | Solver | Purpose |
|---|---|---|
| `01_ortools_stress_model.py` | OR-Tools CP-SAT | Main model, stress tests, Gantt chart, KPI dashboard, bottleneck chart |
| `02_pulp_same_case.py` | PuLP CBC | Same case and maintenance stress case using MILP |
| `03_pyomo_same_case.py` | Pyomo CBC | Same case and maintenance stress case using MILP |

The result files are:

| Result File | Content |
|---|---|
| `ortools_stress_results.xlsx` | OR-Tools stress results, schedules, bottlenecks, maintenance analysis |
| `pulp_same_case_results.xlsx` | PuLP same case and maintenance stress case |
| `pyomo_same_case_results.xlsx` | Pyomo same case and maintenance stress case |

The chart files are:

| Chart File | Meaning |
|---|---|
| `gantt_04_realistic_constraints.html` | Detailed OR-Tools Gantt chart |
| `kpi_summary_ortools.html` | KPI dashboard |
| `bottleneck_04_realistic_constraints.html` | Bottleneck bar chart |

## 3. Main Constraints

The model includes these constraints:

1. Each required operation is processed once.
2. Each machine can process only one operation at a time.
3. Operations of the same order or batch cannot overlap.
4. Operations are not interrupted once they start.
5. Each operation must fit inside a work shift.
6. Planned maintenance blocks selected machines.
7. Condition-based maintenance is triggered by daily machine usage.
8. Due dates are included in some scenarios.
9. Operator capacity is limited in the realistic and large OR-Tools scenarios.
10. The objective minimizes makespan and also penalizes tardiness.

The objective is:

```text
objective = makespan x 1000 + total tardiness
```

This means makespan is the main goal, while tardiness is still considered.

## 4. Nonlinear Maintenance Rule

The important nonlinear industrial rule is:

```text
If machine daily usage > 180 minutes,
reserve 30 minutes for maintenance.
```

This is nonlinear in the industrial meaning because the behavior changes after a threshold:

```text
usage <= 180 minutes -> no maintenance
usage > 180 minutes  -> 30 minutes maintenance
```

In the code, this is converted into a linear or Boolean optimization form.

The model uses:

```text
maintenance_required = 0 or 1
```

Then it applies constraints like:

```text
daily_usage <= 180 + M x maintenance_required
daily_usage >= 181 - M x (1 - maintenance_required)
daily_usage + 30 x maintenance_required <= 480
```

So the project has a nonlinear maintenance idea, but it is solved using binary variables.

## 5. What Happens in the OR-Tools Code

The OR-Tools file is the main model.

### Input Data

The code defines:

- machines
- products
- cycle times
- original orders
- generated stress-test orders
- shift length
- maintenance threshold
- maintenance duration

The shift is:

```text
480 minutes = 8 hours
```

The maintenance threshold is:

```text
180 minutes
```

The maintenance duration is:

```text
30 minutes
```

### Scenarios

The OR-Tools file runs five scenarios:

| Scenario | Meaning |
|---|---|
| `01_same_case` | Small original case |
| `02_more_products_batches` | More products and batches |
| `03_due_dates` | Adds due dates |
| `04_realistic_constraints` | Adds due dates, planned maintenance, condition maintenance, operator limit |
| `05_large_stress` | Largest stress test |

### Important Functions

| Function | What It Does |
|---|---|
| `generate_orders()` | Creates larger random order sets |
| `get_orders()` | Chooses original or generated orders |
| `build_operations()` | Converts orders into operations |
| `create_due_dates()` | Creates due dates |
| `maintenance_windows()` | Creates fixed planned maintenance windows |
| `calculate_bottleneck()` | Finds the machine with highest load |
| `solve_scenario()` | Builds and solves the optimization model |
| `create_ortools_gantt()` | Creates the Gantt chart |
| `create_kpi_dashboard()` | Creates KPI summary dashboard |
| `create_bottleneck_bar_chart()` | Creates bottleneck bar chart |
| `main()` | Runs everything and exports results |

### OR-Tools Modeling

OR-Tools uses interval variables:

```text
operation = start + duration + end
```

It uses `AddNoOverlap` so two operations cannot use the same machine at the same time.

It uses Boolean variables to decide:

- which day an operation belongs to
- whether maintenance is required
- whether operation sequencing is feasible

It uses `AddCumulative` for the operator capacity constraint.

## 6. What Happens in the PuLP Code

The PuLP file solves two cases:

| Scenario | Meaning |
|---|---|
| `same_case` | Original small case |
| `maintenance_stress_case` | Larger quantity case where maintenance activates |

PuLP does not have interval variables like OR-Tools.

So the code uses a MILP formulation with:

- integer start variables
- integer end variables
- binary ordering variables
- big-M constraints

The main idea is:

```text
operation i before operation j
or
operation j before operation i
```

This is how PuLP prevents overlap.

The nonlinear maintenance rule is represented with binary variables and big-M constraints.

## 7. What Happens in the Pyomo Code

The Pyomo file solves the same two cases as PuLP:

| Scenario | Meaning |
|---|---|
| `same_case` | Original small case |
| `maintenance_stress_case` | Larger quantity case where maintenance activates |

Pyomo also uses a MILP model.

It uses:

- variables for start and end times
- binary variables for operation order
- binary variables for day assignment
- binary variables for maintenance triggers
- CBC as the solver backend

Pyomo is more mathematical in style than PuLP, but the model idea is very similar.

## 8. OR-Tools Results

The current OR-Tools Excel results are:

| Scenario | Status | Orders | Batches | Operations | Makespan min | Makespan days | Tardiness min | Bottleneck | Bottleneck % | Solver time sec |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| `01_same_case` | OPTIMAL | 4 | 4 | 12 | 168 | 0.350 | 0 | Painting | 83.33 | 0.079 |
| `02_more_products_batches` | OPTIMAL | 15 | 30 | 95 | 462 | 0.963 | 0 | Milling | 100.00 | 0.239 |
| `03_due_dates` | OPTIMAL | 25 | 54 | 176 | 1012 | 2.108 | 1005 | Milling | 99.21 | 0.736 |
| `04_realistic_constraints` | FEASIBLE | 35 | 90 | 285 | 1900 | 3.958 | 3665 | Milling | 70.58 | 15.075 |
| `05_large_stress` | FEASIBLE | 60 | 155 | 503 | 3586 | 7.471 | 16247 | Milling | 73.54 | 20.194 |

### Interpretation

The first three scenarios are `OPTIMAL`.

This means the solver proved that the solution is the best possible.

The fourth and fifth scenarios are `FEASIBLE`.

This means the solver found a valid schedule, but it did not prove it is the best possible within the time limit.

As the model becomes larger, the solver needs more time and proving optimality becomes harder.

## 9. OR-Tools Maintenance Results

Condition-based maintenance results:

| Scenario | Maintenance Triggers | Reserved Maintenance min | Max Daily Usage min |
|---|---:|---:|---:|
| `01_same_case` | 0 | 0 | 140 |
| `04_realistic_constraints` | 18 | 540 | 449 |
| `05_large_stress` | 31 | 930 | 450 |

### Interpretation

In `01_same_case`, maintenance does not activate because the maximum daily usage is only 140 minutes.

In `04_realistic_constraints`, maintenance activates 18 times:

```text
18 x 30 = 540 minutes reserved for maintenance
```

In `05_large_stress`, maintenance activates 31 times:

```text
31 x 30 = 930 minutes reserved for maintenance
```

This shows that the nonlinear maintenance rule becomes important when the production system is more loaded.

## 10. Bottleneck Results

The current bottleneck results are:

| Scenario | Bottleneck Machine | Machine Load min | Makespan min | Utilization % |
|---|---|---:|---:|---:|
| `01_same_case` | Painting | 140 | 168 | 83.33 |
| `02_more_products_batches` | Milling | 462 | 462 | 100.00 |
| `03_due_dates` | Milling | 1004 | 1012 | 99.21 |
| `04_realistic_constraints` | Milling | 1341 | 1900 | 70.58 |
| `05_large_stress` | Milling | 2637 | 3586 | 73.54 |

### Interpretation

Painting is the bottleneck only in the small original case.

After scaling up, Milling becomes the bottleneck.

This means Milling is the machine that most limits the production schedule in larger scenarios.

Industrial recommendation:

```text
If the company wants to reduce makespan, Milling should be improved first.
```

Possible actions:

- add overtime on Milling
- add another milling machine
- outsource some milling operations
- reduce setup or downtime on Milling

## 11. PuLP Results

PuLP solves two scenarios:

| Scenario | Status | Operations | Makespan min | Tardiness min | Maintenance Triggers | Reserved Maintenance min | Max Daily Usage | Binary Variables | Solver time sec |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `same_case` | Optimal | 12 | 168 | 0 | 0 | 0 | 140 | 116 | 0.288 |
| `maintenance_stress_case` | Optimal | 12 | 680 | 0 | 6 | 180 | 376 | 116 | 0.429 |

### Interpretation

The same case matches OR-Tools:

```text
makespan = 168 minutes
```

The maintenance stress case activates maintenance:

```text
6 triggers x 30 minutes = 180 reserved maintenance minutes
```

This proves the condition-based maintenance rule is active in PuLP.

## 12. Pyomo Results

Pyomo solves the same two scenarios:

| Scenario | Status | Operations | Makespan min | Tardiness min | Maintenance Triggers | Reserved Maintenance min | Max Daily Usage | Binary Variables | Solver time sec |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `same_case` | optimal | 12 | 168 | 0 | 0 | 0 | 140 | 116 | 0.266 |
| `maintenance_stress_case` | optimal | 12 | 680 | 0 | 6 | 180 | 376 | 116 | 0.313 |

### Interpretation

Pyomo gives the same result as PuLP because both models solve the same MILP formulation.

This is a good result because it validates that the model was written consistently.

## 13. Solver Comparison

### Same Case

| Solver | Makespan min | Maintenance Triggers | Result |
|---|---:|---:|---|
| OR-Tools CP-SAT | 168 | 0 | Correct baseline |
| PuLP CBC | 168 | 0 | Matches OR-Tools |
| Pyomo CBC | 168 | 0 | Matches OR-Tools |

The same case proves the three models are consistent.

### Maintenance Stress Case

| Solver | Makespan min | Maintenance Triggers | Reserved Maintenance min |
|---|---:|---:|---:|
| PuLP CBC | 680 | 6 | 180 |
| Pyomo CBC | 680 | 6 | 180 |

This proves that the maintenance threshold rule works in both MILP libraries.

### Main Difference

| Solver | Strength |
|---|---|
| OR-Tools CP-SAT | Best for scheduling because it has interval variables and no-overlap constraints |
| PuLP CBC | Simple and readable MILP modeling |
| Pyomo CBC | More formal mathematical modeling |

OR-Tools is the best main solver for this project.

PuLP and Pyomo are useful for comparison and for explaining the MILP version of the same problem.

## 14. How PuLP and Pyomo Solve the Nonlinear Maintenance Constraint

The maintenance rule is nonlinear in real industrial logic because it is conditional:

```text
If daily machine usage > 180 minutes,
then maintenance is required.
```

The solver cannot use a normal Python `if` statement for this because `daily_usage` is not known before solving. It is a decision value created by the optimization model.

So PuLP and Pyomo solve this by introducing a binary variable:

```text
maintenance_required = 0 or 1
```

The meaning is:

```text
maintenance_required = 0 -> machine does not need maintenance that day
maintenance_required = 1 -> machine needs maintenance that day
```

Then the nonlinear condition is rewritten as linear big-M constraints:

```text
daily_usage <= 180 + M x maintenance_required
daily_usage >= 181 - M x (1 - maintenance_required)
daily_usage + 30 x maintenance_required <= 480
```

This works as follows:

| Case | What Happens |
|---|---|
| `maintenance_required = 0` | Daily usage must stay at or below 180 minutes |
| `maintenance_required = 1` | Daily usage must be at least 181 minutes |
| `maintenance_required = 1` | 30 minutes are reserved for maintenance |

In PuLP, the binary variable is created using:

```python
maintenance_required = pulp.LpVariable(
    f"condition_maintenance_{machine}_day_{day + 1}",
    cat="Binary",
)
```

In Pyomo, the same idea is created using:

```python
model.condition_maintenance = Var(condition_maintenance_keys, within=Binary)
```

So the important point is:

```text
The real maintenance rule is nonlinear/conditional,
but PuLP and Pyomo solve it by converting it into a MILP model
using binary variables and big-M constraints.
```

This is why the model can still be solved by linear MILP solvers such as CBC.

## 15. Visualization Results

The OR-Tools code now creates three HTML visual outputs.

### Gantt Chart

File:

```text
results/charts/gantt_04_realistic_constraints.html
```

This chart shows:

- machines on the y-axis
- production time on the x-axis
- colored bars for operations
- different colors for product IDs
- patterns for machine styles
- gray blocks for planned maintenance
- red markers for condition-based maintenance
- black dashed line for makespan

The red condition-based maintenance markers represent reserved capacity. They are not exact maintenance start times.

### KPI Dashboard

File:

```text
results/charts/kpi_summary_ortools.html
```

This dashboard summarizes:

- status
- orders
- batches
- operations
- makespan
- tardiness
- bottleneck machine
- bottleneck utilization
- maintenance triggers
- reserved maintenance time
- solver time

### Bottleneck Bar Chart

File:

```text
results/charts/bottleneck_04_realistic_constraints.html
```

This chart highlights the bottleneck machine.

The red bar is the bottleneck.

For the realistic scenario, the bottleneck is:

```text
Milling
```

## 16. Final Conclusion

The project successfully builds and compares an open shop scheduling model using OR-Tools, PuLP, and Pyomo.

The main findings are:

1. OR-Tools is the strongest solver for the main scheduling model.
2. PuLP and Pyomo validate the same-case result using MILP.
3. The nonlinear maintenance rule is included as a threshold-based rule.
4. The maintenance rule activates in the stress cases.
5. Milling becomes the main bottleneck after scaling the production system.
6. Larger scenarios become harder to prove optimal, so solver status changes from `OPTIMAL` to `FEASIBLE`.
7. The Gantt chart, KPI dashboard, and bottleneck chart make the results easier to explain.

Overall, the project is now not only an optimization model, but also a small production planning analysis system.
