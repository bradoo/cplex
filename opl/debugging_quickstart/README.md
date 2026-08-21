# OPL Debugging Quickstart

This folder contains small examples for practicing OPL debugging.

Use these commands from this folder:

```bash
oplrun good_model.mod good_data.dat
oplrun syntax_error_missing_semicolon.mod good_data.dat
oplrun good_model.mod data_error_bad_array.dat
oplrun infeasible_model.mod good_data.dat
```

What to learn:

- Syntax error: the model cannot be parsed.
- Data error: the data file does not match the model declaration.
- Infeasible model: the syntax is valid, but the constraints cannot all be satisfied.

Typical messages:

- Syntax error: `PARSE_001`, often caused by a missing semicolon.
- Data error: `DATA_012`, for example assigning a string to an `int`.
- Infeasible model: `<<< no solution` after solve.

In CPLEX Studio, these errors appear in the Problems tab and Console.
Read the file name, line number, and message first. Then check the nearby model or data statement.
