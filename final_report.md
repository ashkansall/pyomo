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
7. Maintenance windows block selected machines.
8. Operator capacity is included in the larger OR-Tools stress scenarios.
9. The objective minimizes makespan first, then tardiness.

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
| `01_same_case` | OPTIMAL | 4 | 4 | 12 | 168 | 0.350 | Painting | 0.052 |
| `02_more_products_batches` | OPTIMAL | 15 | 30 | 95 | 462 | 0.963 | Milling | 0.298 |
| `03_due_dates` | OPTIMAL | 25 | 54 | 176 | 1012 | 2.108 | Milling | 0.826 |
| `04_realistic_constraints` | FEASIBLE | 35 | 90 | 285 | 1899 | 3.956 | Milling | 15.071 |
| `05_large_stress` | FEASIBLE | 60 | 155 | 503 | 3578 | 7.454 | Milling | 20.090 |

The first three scenarios are solved optimally. The last two scenarios are feasible but not proven optimal within the short time limit. This is useful because it shows the practical limit of the model as the number of operations and constraints increases.

## 9. Bottleneck Analysis

Bottleneck analysis is calculated using:

```text
machine load = total processing time on the machine
utilization = machine load / makespan
```

The bottleneck is the machine with the highest workload/utilization.

In the larger scenarios, Milling becomes the bottleneck. This means Milling limits the production flow more than the other machines.

## 10. OR-Tools vs PuLP vs Pyomo Same-Case Comparison

The original same case was solved with all three approaches.

| Solver | Status | Operations | Makespan min | Tardiness min | Binary Variables | Time sec | Formulation |
|---|---|---:|---:|---:|---:|---:|---|
| OR-Tools CP-SAT | OPTIMAL | 12 | 168 | 0 | 0 | 0.052 | Interval variables + no-overlap |
| PuLP CBC | Optimal | 12 | 168 | 0 | 91 | 0.470 | Big-M MILP |
| Pyomo HiGHS | optimal | 12 | 168 | 0 | 91 | 0.417 | Big-M MILP |

All three approaches found the same makespan. This confirms that the formulations are consistent for the small original case.

The difference is how the constraints are modeled.

## 11. Which Constraints Are Better?

For this project, OR-Tools constraints are better because scheduling is represented directly:

```python
interval = model.NewIntervalVar(start, duration, end, name)
model.AddNoOverlap(machine_intervals[machine])
```

PuLP and Pyomo do not have direct interval variables or no-overlap constraints. They need binary ordering variables:

```text
operation i before operation j OR operation j before operation i
```

This requires big-M constraints and many binary variables. In the same small case, PuLP and Pyomo already need 91 binary variables.

Therefore:

- OR-Tools is better for the main scheduling model.
- PuLP is useful for simpler MILP models and small comparisons.
- Pyomo is useful for general mathematical optimization, but scheduling still requires a manual MILP formulation.

## 12. Conclusion

OR-Tools CP-SAT is the best solver for this open shop scheduling project because it directly supports scheduling constraints. PuLP and Pyomo can solve the same small case, but they require big-M constraints and many binary variables.

The stress test shows that the scheduling problem becomes harder when more products, batches, due dates, maintenance, and operator limits are added. OR-Tools still finds feasible schedules for large cases, but proving optimality can require more time.
