import json
import pathlib

from dff.utils.benchmark.context_storage import BenchmarkCase

benchmark_path = pathlib.Path("benchmarks")

for file in benchmark_path.iterdir():
    if file.suffix == ".json":
        with open(file, "r") as fd:
            benchmark_set = json.load(fd)

        non_benchmark_fields = ("name", "description", "uuid", "benchmarks")

        new_benchmark_set = {k: v for k, v in benchmark_set.items() if k in non_benchmark_fields}

        if "benchmarks" not in benchmark_set:
            new_benchmark_set["benchmarks"] = {k: v for k, v in benchmark_set.items() if k not in non_benchmark_fields}

        for key, benchmark in new_benchmark_set["benchmarks"].items():
            # update old factory specification
            if benchmark["db_factory"].get("base_factory") == "dev":
                postfix = "_old"
            elif benchmark["db_factory"].get("base_factory") == "partial":
                postfix = ""
            else:
                postfix = None

            if postfix is not None:
                benchmark["db_factory"].pop("base_factory", None)
                benchmark["db_factory"].update(
                    {
                        "factory_module": "dff.context_storages" + postfix,
                        "factory": "context_storage_factory",
                    }
                )

        # update average calculation
        for benchmark in new_benchmark_set["benchmarks"].values():
            BenchmarkCase.set_average_results(benchmark)

        # update lengths -> dimensions renaming
        for benchmark in new_benchmark_set["benchmarks"].values():
            for param in ("message", "misc"):
                dimensions = benchmark.pop(f"{param}_lengths", None)
                if dimensions is not None:
                    benchmark[f"{param}_dimensions"] = dimensions

        with open(file, "w") as fd:
            json.dump(new_benchmark_set, fd)