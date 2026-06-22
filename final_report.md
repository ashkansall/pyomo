# Open Shop Scheduling with OR-Tools, PuLP, and Pyomo

## 1. Project Objective

The objective of this project is to schedule manufacturing orders in an open shop production system.
Each order has a product type and quantity, and each product requires processing on selected machines such as Cutting, Drilling, Milling, Welding, Painting, and Inspection.

The processing time of each operation is calculated as:

```text
operation duration = cycle time per unit x order quantity
```

The goal is to minimize the makespan, which is the finish time of the last completed operation.
When due dates are active, the code uses a weighted objective:

```text
objective = makespan x 1000 + total tardiness
```

This makes makespan the dominant target while still discouraging late orders.

## 2. Why This Is an Open Shop Problem

This is an open shop scheduling problem because the operations of the same order do not have a fixed sequence.
For example, if one batch needs Cutting, Drilling, and Painting, the model does not force Cutting before Drilling or Painting.
The solver chooses the operation order that gives the best feasible schedule.

This is different from:

| Scheduling Type | Main Difference |
|---|---|
| Job shop | Each job has a fixed machine sequence |
| Flow shop | All jobs follow the same machine sequence |
| Open shop | Operations are flexible and can be sequenced by the optimizer |

## 3. Final Files

The final project compares three optimization approaches:

| File | Solver | Purpose |
|---|---|---|
| `01_ortools_stress_model.py` | OR-Tools CP-SAT | Main model, stress testing, bottleneck analysis |
| `02_pulp_same_case.py` | PuLP CBC | Same original case using a MILP formulation |
| `03_pyomo_same_case.py` | Pyomo HiGHS | Same original case using a MILP formulation |

The Excel result files used for this report are:

| Result File | Main Content |
|---|---|
| `ortools_stress_results.xlsx` | Five stress scenarios, schedules, bottlenecks, condition-based maintenance |
| `pulp_same_case_results.xlsx` | Same-case schedule, bottleneck, condition-based maintenance |
| `pyomo_same_case_results.xlsx` | Same-case schedule, bottleneck, condition-based maintenance |

## 4. Main Constraints

The models include the following constraints:

1. Each required operation is scheduled exactly once.
2. Each machine can process only one operation at a time.
3. The same batch cannot be processed on two machines at the same time.
4. Operations are non-interruptible.
5. Each operation must start and finish inside one work shift.
6. Due dates are included in the due-date and realistic stress scenarios.
7. Fixed maintenance windows block machines in maintenance scenarios.
8. Condition-based maintenance is triggered when daily machine usage is above 180 minutes.
9. Operator capacity is limited in the realistic and large OR-Tools stress scenarios.
10. The objective strongly prioritizes makespan and also penalizes tardiness when due dates exist.

## 5. Condition-Based Maintenance Rule

The added realistic maintenance rule is:

```text
If a machine is used for more than 180 minutes in one day,
reserve 30 minutes of that machine-day for maintenance.
```

This is dynamic because the maintenance requirement depends on the schedule produced by the solver.
Before solving, we do not know which machine-days will exceed 180 minutes.
The optimizer decides the schedule, calculates daily machine usage, and then triggers maintenance if the threshold is crossed.

This is also a nonlinear or piecewise industrial rule in real life:

```text
usage <= 180 minutes -> no extra maintenance
usage > 180 minutes  -> 30 minutes maintenance
```

Optimization solvers usually cannot handle this threshold directly in a simple linear scheduling model.
Therefore, the condition is linearized with Boolean or binary variables.
The model creates a maintenance trigger variable for each machine and day.

## 6. How the Maintenance Rule Changes the Schedule

The condition-based maintenance rule reduces available machine capacity on busy days.
For example, a normal shift has 480 available minutes.
If a machine-day triggers maintenance, then 30 minutes are reserved for maintenance, so production must fit into the remaining capacity:

```text
daily production usage + 30 maintenance minutes <= 480 shift minutes
```

This can increase makespan, increase tardiness, and make the solver work harder because the model has more decision variables and threshold constraints.

In the small same-case, the rule does not change the schedule because no machine exceeds the 180-minute daily threshold.
In the larger OR-Tools stress cases, the rule is triggered many times, so it has a real effect on available capacity.

## 7. OR-Tools Stress Test Results

The OR-Tools file stress-tests the model by adding more orders, more batches, due dates, maintenance, operator limits, and condition-based maintenance.

| Scenario | Status | Orders | Batches | Operations | Makespan min | Makespan days | Tardiness min | Bottleneck | Solver time sec |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| `01_same_case` | OPTIMAL | 4 | 4 | 12 | 168 | 0.350 | 0 | Painting | 0.049 |
| `02_more_products_batches` | OPTIMAL | 15 | 30 | 95 | 462 | 0.963 | 0 | Milling | 0.296 |
| `03_due_dates` | OPTIMAL | 25 | 54 | 176 | 1012 | 2.108 | 1005 | Milling | 0.832 |
| `04_realistic_constraints` | FEASIBLE | 35 | 90 | 285 | 1901 | 3.960 | 3555 | Milling | 15.091 |
| `05_large_stress` | FEASIBLE | 60 | 155 | 503 | 3658 | 7.621 | 19985 | Milling | 20.140 |

Important interpretation:

- The first three scenarios are proven optimal.
- The fourth and fifth scenarios are feasible but not proven optimal within the time limit.
- `FEASIBLE` means the solver found a valid schedule, but it did not prove that this schedule is the absolute best possible.
- The large stress case is no longer `UNKNOWN`; the current Excel file shows it is `FEASIBLE`.
- As the model becomes larger and more constrained, solver time increases and proving optimality becomes harder.

## 8. Condition-Based Maintenance Results

The condition-based maintenance results are saved in separate Excel sheets.
The key current results are:

| Scenario | Maintenance Triggers | Reserved Maintenance Minutes | Maximum Daily Machine Usage |
|---|---:|---:|---:|
| `01_same_case` | 0 | 0 | 140 |
| `04_realistic_constraints` | 15 | 450 | 449 |
| `05_large_stress` | 31 | 930 | 407 |

In the same-case scenario, no machine crosses the 180-minute threshold.
Therefore, condition-based maintenance is not triggered.

In the realistic scenario, maintenance is triggered 15 times.
That reserves:

```text
15 triggers x 30 minutes = 450 maintenance minutes
```

In the large stress scenario, maintenance is triggered 31 times.
That reserves:

```text
31 triggers x 30 minutes = 930 maintenance minutes
```

This is the clearest result of adding the nonlinear maintenance logic:
the larger and more loaded the factory becomes, the more often machines enter maintenance, and the less production capacity remains available.

## 9. Maintenance Trigger Breakdown

For the realistic OR-Tools stress case:

| Machine | Total Usage min | Triggered Days | Reserved Maintenance min | Max Daily Usage |
|---|---:|---:|---:|---:|
| Cutting | 937 | 3 | 90 | 310 |
| Drilling | 625 | 1 | 30 | 200 |
| Inspection | 419 | 1 | 30 | 195 |
| Milling | 1341 | 3 | 90 | 449 |
| Painting | 1094 | 3 | 90 | 368 |
| Welding | 1272 | 4 | 120 | 401 |

For the large OR-Tools stress case:

| Machine | Total Usage min | Triggered Days | Reserved Maintenance min | Max Daily Usage |
|---|---:|---:|---:|---:|
| Cutting | 2254 | 7 | 210 | 407 |
| Drilling | 1462 | 4 | 120 | 309 |
| Inspection | 628 | 0 | 0 | 146 |
| Milling | 2637 | 8 | 240 | 405 |
| Painting | 1933 | 7 | 210 | 351 |
| Welding | 1768 | 5 | 150 | 399 |

Milling has the highest total usage in the large stress case.
This agrees with the bottleneck result, where Milling becomes the bottleneck machine.

## 10. Bottleneck Analysis

Bottleneck analysis is calculated from the total processing load on each machine:

```text
machine utilization = total machine processing time / makespan
```

The bottleneck is the machine with the highest utilization.

Current OR-Tools results:

| Scenario | Bottleneck Machine | Utilization |
|---|---|---:|
| `01_same_case` | Painting | 83.33% |
| `02_more_products_batches` | Milling | 100.00% |
| `03_due_dates` | Milling | 99.21% |
| `04_realistic_constraints` | Milling | 70.54% |
| `05_large_stress` | Milling | 72.09% |

The bottleneck changes from Painting in the small case to Milling in the scaled cases.
This means that after adding more products and batches, Milling becomes the machine that limits production flow.

## 11. OR-Tools vs PuLP vs Pyomo Same-Case Comparison

The same original case was solved with all three approaches.

| Solver | Status | Operations | Makespan min | Tardiness min | Binary Variables | Solver Time sec | Formulation |
|---|---|---:|---:|---:|---:|---:|---|
| OR-Tools CP-SAT | OPTIMAL | 12 | 168 | 0 | Uses Boolean scheduling logic | 0.049 | Interval variables and no-overlap |
| PuLP CBC | Optimal | 12 | 168 | 0 | 116 | 0.213 | Big-M MILP |
| Pyomo HiGHS | optimal | 12 | 168 | 0 | 116 | 0.228 | Big-M MILP |

All three solvers return the same makespan of 168 minutes for the same-case model.
This confirms that the three formulations are consistent on the small test case.

The condition-based maintenance rule does not trigger in the same-case model for any solver:

| Solver | Max Daily Usage | Threshold | Maintenance Triggers |
|---|---:|---:|---:|
| OR-Tools CP-SAT | 140 | 180 | 0 |
| PuLP CBC | 140 | 180 | 0 |
| Pyomo HiGHS | 140 | 180 | 0 |

So, for the small case, the new maintenance rule adds modeling complexity but does not change the final makespan.

## 12. Solver Comparison

### OR-Tools CP-SAT

OR-Tools is the best fit for the full scheduling model.
It supports interval variables and no-overlap constraints directly:

```python
interval = model.NewIntervalVar(start, duration, end, name)
model.AddNoOverlap(machine_intervals[machine])
```

This makes the code closer to the real scheduling problem.
It is also easier to scale the model with shifts, machine capacity, maintenance windows, and operator capacity.

### PuLP CBC

PuLP can solve the same small open shop problem, but it uses a MILP formulation.
Because PuLP does not have interval variables, machine conflicts are modeled with binary ordering variables:

```text
operation i before operation j OR operation j before operation i
```

This requires big-M constraints.
The model is understandable, but the number of binary variables grows quickly when more operations are added.

### Pyomo HiGHS

Pyomo is more general than PuLP and is useful for mathematical optimization models.
It can represent MILP models clearly and can also support nonlinear optimization if a nonlinear solver is used.
However, for this scheduling problem, Pyomo still needs the same big-M logic as PuLP because the model is written as a MILP.

## 13. Which Solver Is Better for This Project?

For this project, OR-Tools is the best main solver.

Reasons:

1. It has native scheduling constraints.
2. It handles no-overlap constraints directly.
3. It is easier to model machine calendars, maintenance windows, and operator capacity.
4. It can still find feasible schedules for the large stress case within the time limit.

PuLP and Pyomo are useful for comparison because they show how the same problem can be expressed as a mathematical programming model.
However, they are less natural for open shop scheduling because they need many binary variables and big-M constraints.

## 14. Code Explanation by File

### `01_ortools_stress_model.py`

Main sections:

| Section / Function | Purpose |
|---|---|
| Input data and constants | Defines products, machines, shift length, maintenance threshold, and stress scenarios |
| `generate_orders()` | Creates larger random order sets for stress testing |
| `get_orders()` | Uses original orders or generated stress-test orders |
| `build_operations()` | Converts orders into machine operations and durations |
| `create_due_dates()` | Adds due dates for scenarios that use tardiness |
| `maintenance_windows()` | Creates fixed planned maintenance windows |
| `solve_scenario()` | Builds and solves the CP-SAT model for one scenario |
| `calculate_bottleneck()` | Calculates machine load and bottleneck utilization |
| `main()` | Runs all scenarios and writes the Excel workbook |

The most important OR-Tools modeling objects are:

| Object | Meaning |
|---|---|
| Start variable | When an operation begins |
| End variable | When an operation finishes |
| Interval variable | The full operation block: start, duration, end |
| `AddNoOverlap` | Prevents two operations from using the same machine at the same time |
| `AddCumulative` | Limits the number of operators used at one time |
| Boolean day variables | Choose which day an operation is assigned to |
| Maintenance trigger variables | Decide whether condition-based maintenance is required |

### `02_pulp_same_case.py`

Main sections:

| Section / Function | Purpose |
|---|---|
| Input data and constants | Defines the same original case and maintenance threshold |
| `build_operations()` | Builds operations from orders and product-machine times |
| `add_no_overlap()` | Adds pairwise big-M constraints for machine and batch conflicts |
| `add_maintenance_constraints()` | Adds fixed maintenance and condition-based maintenance logic |
| `calculate_bottleneck()` | Calculates machine utilization |
| `main()` | Solves the model and writes the Excel workbook |

PuLP solves the same problem as a MILP.
The main difference is that it must create binary ordering variables for operation pairs.

### `03_pyomo_same_case.py`

Main sections:

| Section / Function | Purpose |
|---|---|
| Input data and constants | Defines the same original case and maintenance threshold |
| `build_operations()` | Builds operations from orders and product-machine times |
| `pairwise_keys()` and `create_pairs()` | Create operation pairs that may conflict |
| `maintenance_keys()` | Creates machine-day keys for maintenance triggers |
| `calculate_bottleneck()` | Calculates machine utilization |
| `main()` | Builds the Pyomo model, solves it, and writes the Excel workbook |

Pyomo also uses a MILP formulation with big-M constraints.
Its syntax is more mathematical than PuLP, but the scheduling logic is similar.

## 15. Final Conclusion

The project successfully scales the original open shop scheduling model and compares three optimization libraries.

The most important result is that condition-based maintenance makes the model more realistic and more difficult.
In the small same-case, no machine crosses the maintenance threshold, so the makespan remains 168 minutes for OR-Tools, PuLP, and Pyomo.
In the larger OR-Tools stress tests, the maintenance rule has a strong effect:
15 triggers in the realistic case and 31 triggers in the large stress case.

The current results show that OR-Tools CP-SAT is the most suitable solver for this project because it directly supports scheduling constraints and can handle the larger stress scenarios.
PuLP and Pyomo are useful for explaining the equivalent MILP approach, but they are less convenient for full-scale open shop scheduling.
