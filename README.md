# Final Open Shop Scheduling Project

This is the clean final version of the project.

## Install Dependencies

```bash
python -m pip install -r outputs/final_open_shop/requirements.txt
```

## Run OR-Tools Stress Model

```bash
python outputs/final_open_shop/01_ortools_stress_model.py
```

Output:

```text
outputs/final_open_shop/results/ortools_stress_results.xlsx
```

## Run PuLP Same-Case Model

```bash
python outputs/final_open_shop/02_pulp_same_case.py
```

Output:

```text
outputs/final_open_shop/results/pulp_same_case_results.xlsx
```

## Run Pyomo Same-Case Model

```bash
python outputs/final_open_shop/03_pyomo_same_case.py
```

Output:

```text
outputs/final_open_shop/results/pyomo_same_case_results.xlsx
```

## Main Code Files

| File | Purpose |
|---|---|
| `01_ortools_stress_model.py` | Main OR-Tools model, stress tests, bottleneck analysis, Excel output |
| `02_pulp_same_case.py` | Same original case solved with PuLP |
| `03_pyomo_same_case.py` | Same original case solved with Pyomo |

## Solver Time Limits

The OR-Tools stress model uses short time limits between 5 and 20 seconds. These are classroom/demo limits so the script runs quickly. In a real factory, a company might allow a solver to run longer, for example several minutes or overnight, depending on the planning process.
