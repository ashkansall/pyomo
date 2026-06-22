# Open Shop Scheduling with OR-Tools, PuLP, and Pyomo

## 1. Project Objective

The objective is to solve an open shop scheduling problem for a manufacturing company. Each customer order has a product type and quantity. Each product requires processing on a set of machines.

The operation duration is:

```text
operation duration = cycle time per unit x order quantity
```

The goal is to minimize the makespan, which is the finishing time of the last completed operation.

## 2. Why This Is Open Shop Scheduling

This is an open shop problem because the operations of the same order do not have a fixed sequence. The optimizer decides the order of operations while respecting capacity constraints.

For example, if one order needs Cutting, Drilling, and Painting, the model does not force Cutting to happen first unless that rule is added separately.

## 3. Final Code Structure

The final project has three main files:

| File | Solver | Purpose |
|---|---|---|
| `01_ortools_stress_model.py` | OR-Tools CP-SAT | Main model, stress tests, bottleneck analysis |
| `02_pulp_same_case.py` | PuLP CBC | Same original case for comparison |
| `03_pyomo_same_case.py` | Pyomo HiGHS | Same original case for comparison |

The OR-Tools file is the main scheduling system. The PuLP and Pyomo files solve the same original case to compare modeling style and solver behavior.

## 4. Constraints Included

The model includes:

1. Each operation is completed once.
2. Each machine can process only one operation at a time.
3. The same batch cannot be processed on two machines at the same time.
4. Each operation must start and finish inside one 08:00-16:00 shift.
5. Operations are non-interruptible.
6. Due dates are included in constrained scenarios.
7. Planned maintenance windows block selected machines.
8. Condition-based maintenance is triggered when daily machine usage exceeds 180 minutes.
9. Operator capacity is included in the larger OR-Tools stress scenarios.
10. The objective minimizes makespan first, then tardiness.

## 5. Solver Specification

The OR-Tools CP-SAT solver is specified as:

```python
solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = scenario["time_limit"]
solver.parameters.num_search_workers = 8
solver.parameters.relative_gap_limit = 0.02
```

The time limits are short demo limits:

| Scenario Type | Time Limit |
|---|---:|
| Original case | 5 seconds |
| Medium stress | 8-10 seconds |
| Realistic constrained case | 15 seconds |
| Large stress case | 20 seconds |

In real industry, the time limit depends on the planning process. A factory could run the solver for a few minutes, or even overnight for a large planning problem. For this project, short limits make the experiment practical and show how the model behaves under pressure.

## 6. Why OR-Tools CP-SAT Was Used

OR-Tools CP-SAT was used because it has native scheduling tools:

```python
NewIntervalVar
AddNoOverlap
AddCumulative
```

These directly represent scheduling ideas:

- an operation is an interval
- machine operations cannot overlap
- operator capacity can be limited

This makes OR-Tools more natural for open shop scheduling than PuLP or Pyomo.

## 7. Algorithm Behind OR-Tools CP-SAT

CP-SAT combines constraint programming and SAT/integer optimization. It uses:

- integer variables
- Boolean variables
- constraint propagation
- branching search
- conflict learning
- branch-and-bound optimization

The solver searches for feasible schedules, removes impossible choices, and improves the objective until it proves optimality or reaches the time limit.

## 8. OR-Tools Stress Test Results

| Scenario | Status | Orders | Batches | Operations | Makespan min | Makespan days | Bottleneck | Time sec |
|---|---|---:|---:|---:|---:|---:|---|---:|
| `01_same_case` | OPTIMAL | 4 | 4 | 12 | 168 | 0.350 | Painting | 0.093 |
| `02_more_products_batches` | OPTIMAL | 15 | 30 | 95 | 462 | 0.963 | Milling | 0.309 |
| `03_due_dates` | OPTIMAL | 25 | 54 | 176 | 1012 | 2.108 | Milling | 0.877 |
| `04_realistic_constraints` | FEASIBLE | 35 | 90 | 285 | 1899 | 3.956 | Milling | 15.116 |
| `05_large_stress` | UNKNOWN | 60 | 155 | 503 | Not found | Not found | Not found | 20.170 |

The first three scenarios are solved optimally. The fourth scenario is feasible but not proven optimal within the time limit. The largest stress case returns `UNKNOWN` within 20 seconds after adding condition-based maintenance. This is useful because it shows that the new maintenance rule makes the model harder and pushes the practical limit of the solver.

## 9. Condition-Based Maintenance Result

A condition-based maintenance rule was added:

```text
If daily machine usage > 180 minutes, reserve 30 minutes for maintenance.
```

This represents maintenance triggered by machine workload. It is dynamic because the maintenance requirement depends on the optimized schedule. It is also nonlinear or piecewise in real industrial logic because the maintenance time changes after a threshold:

```text
usage <= 180 minutes  -> no extra maintenance
usage > 180 minutes   -> 30 minutes maintenance
```

In the optimization model, this threshold behavior is linearized using Boolean/binary variables.

The Excel outputs now include condition-based maintenance sheets:

| File | Sheet |
|---|---|
| `ortools_stress_results.xlsx` | `cbm_01_same_case`, `cbm_04_realistic_constraints` |
| `pulp_same_case_results.xlsx` | `Condition Maintenance` |
| `pyomo_same_case_results.xlsx` | `Condition Maintenance` |

In the small same case, no machine exceeds the 180-minute threshold. For example, Painting has 140 minutes of usage, Cutting has 112 minutes, and Drilling has 96 minutes. Therefore, condition-based maintenance is not triggered in the small case.

In the realistic OR-Tools stress case, the rule is triggered several times. For example:

| Scenario | Machine | Day | Daily Usage | Threshold | Maintenance Required | Reserved |
|---|---|---:|---:|---:|---:|---:|
| `04_realistic_constraints` | Cutting | 1 | 266 | 180 | 1 | 30 |
| `04_realistic_constraints` | Cutting | 2 | 247 | 180 | 1 | 30 |
| `04_realistic_constraints` | Cutting | 3 | 192 | 180 | 1 | 30 |
| `04_realistic_constraints` | Cutting | 4 | 232 | 180 | 1 | 30 |
| `04_realistic_constraints` | Drilling | 4 | 197 | 180 | 1 | 30 |

This shows the effect of the nonlinear threshold rule: when machine usage becomes high, the model reserves maintenance capacity and reduces the available production time for that machine/day.

## 10. Bottleneck Analysis

Bottleneck analysis is calculated using:

```text
machine load = total processing time on the machine
utilization = machine load / makespan
```

The bottleneck is the machine with the highest workload/utilization.

In the larger scenarios, Milling becomes the bottleneck. This means Milling limits the production flow more than the other machines.

## 11. OR-Tools vs PuLP vs Pyomo Same-Case Comparison

The original same case was solved with all three approaches.

| Solver | Status | Operations | Makespan min | Tardiness min | Binary Variables | Time sec | Formulation |
|---|---|---:|---:|---:|---:|---:|---|
| OR-Tools CP-SAT | OPTIMAL | 12 | 168 | 0 | Uses Boolean scheduling logic | 0.093 | Interval variables + no-overlap |
| PuLP CBC | Optimal | 12 | 168 | 0 | 116 | 0.282 | Big-M MILP |
| Pyomo HiGHS | optimal | 12 | 168 | 0 | 116 | 0.290 | Big-M MILP |

All three approaches found the same makespan. This confirms that the formulations are consistent for the small original case.

After adding condition-based maintenance, PuLP and Pyomo require 116 binary variables. Before this rule, they required fewer binary variables. The increase happens because the model adds one maintenance trigger variable for each machine/day combination.

The difference is how the constraints are modeled.

## 12. Which Constraints Are Better?

For this project, OR-Tools constraints are better because scheduling is represented directly:

```python
interval = model.NewIntervalVar(start, duration, end, name)
model.AddNoOverlap(machine_intervals[machine])
```

PuLP and Pyomo do not have direct interval variables or no-overlap constraints. They need binary ordering variables:

```text
operation i before operation j OR operation j before operation i
```

This requires big-M constraints and many binary variables. In the same small case, PuLP and Pyomo need 116 binary variables after adding the condition-based maintenance rule.

Therefore:

- OR-Tools is better for the main scheduling model.
- PuLP is useful for simpler MILP models and small comparisons.
- Pyomo is useful for general mathematical optimization, but scheduling still requires a manual MILP formulation.

## 13. Conclusion

OR-Tools CP-SAT is the best solver for this open shop scheduling project because it directly supports scheduling constraints. PuLP and Pyomo can solve the same small case, but they require big-M constraints and many binary variables.

The condition-based maintenance rule makes the model more realistic because maintenance is triggered by machine workload. It also makes the model harder because the solver must decide whether each machine/day crosses the usage threshold. The stress test shows that as more products, batches, due dates, maintenance, and operator limits are added, proving optimality becomes more difficult.
