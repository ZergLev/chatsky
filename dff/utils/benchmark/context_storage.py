"""
Context storage benchmarking
----------------------------
This module contains functions for context storages benchmarking.

Basic usage::


    from dff.utils.benchmark.context_storage import report
    from dff.context_storages import context_storage_factory

    storage = context_storage_factory("postgresql+asyncpg://postgres:pass@localhost:5432/test", table_name="benchmark")

    report(storage)

"""
from uuid import uuid4
import pathlib
from time import perf_counter
import typing as tp
from copy import deepcopy
import json
import importlib
from statistics import mean

from pydantic import BaseModel, Field
from pympler import asizeof
from tqdm.auto import tqdm
from humanize import naturalsize

from dff.script import Context

try:
    import matplotlib
    from matplotlib.backends.backend_pdf import PdfPages
    import matplotlib.pyplot as plt
except ImportError:
    matplotlib = None

from dff.context_storages import DBContextStorage
from dff.script import Context, Message


def get_dict(dimensions: tp.Tuple[int, ...]):
    """
    Misc dictionary build in `dimensions` dimensions.

    :param dimensions:
        Dimensions of the dictionary.
        Each element of the dimensions tuple is the number of keys on the corresponding level of the dictionary.
        The last element of the dimensions tuple is the length of the str values of the dict.

        e.g. dimensions=(1, 2) produces a dictionary with 1 key that points to a string of len 2.
        whereas dimensions=(1, 2, 3) produces a dictionary with 1 key that points to a dictionary
        with 2 keys each of which points to a string of len 3.

        So, the len of dimensions is the depth of the dictionary, while its values are
        the width of the dictionary at each level.
    :return: Misc dictionary.
    """
    def _get_dict(dimensions: tp.Tuple[int, ...]):
        if len(dimensions) < 2:
            return "." * dimensions[0]
        return {i: _get_dict(dimensions[1:]) for i in range(dimensions[0])}

    if len(dimensions) > 1:
        return _get_dict(dimensions)
    elif len(dimensions) == 1:
        return _get_dict((dimensions[0], 0))
    else:
        return _get_dict((0, 0))


def get_message(message_dimensions: tp.Tuple[int, ...]):
    """
    Message with misc field of message_dimensions dimension.
    :param message_dimensions:
    :return:
    """
    return Message(misc=get_dict(message_dimensions))


def get_context(dialog_len: int, message_dimensions: tp.Tuple[int, ...], misc_dimensions: tp.Tuple[int, ...]) -> Context:
    """
    A context with a given number of dialog turns, a given message dimension
    and a given misc dimension.
    """

    return Context(
        labels={i: (f"flow_{i}", f"node_{i}") for i in range(dialog_len)},
        requests={i: get_message(message_dimensions) for i in range(dialog_len)},
        responses={i: get_message(message_dimensions) for i in range(dialog_len)},
        misc=get_dict(misc_dimensions),
    )


def time_context_read_write(
    context_storage: DBContextStorage,
    context: Context,
    context_num: int,
    context_updater=None,
) -> tp.Tuple[tp.List[float], tp.List[tp.Dict[int, float]], tp.List[tp.Dict[int, float]]]:
    """
    Generate `context_num` ids and for each write into `context_storage` value of `context` under generated id,
    after that read the value stored in `context_storage` under generated id and compare it to `context`.

    Keep track of the time it takes to write and read context to/from the context storage.

    This function clear context storage before and after execution.

    :param context_storage: Context storage to benchmark.
    :param context: An instance of context which will be repeatedly written into context storage.
    :param context_num: A number of times the context will be written and checked.
    :param context_updater:
    :return:
        Depends on `as_dataframe` parameter.
        1. By default, it is set to None in which case it returns:
            two lists: first one contains individual write times, second one contains individual read times.
        2. If set to "pandas":
            A pandas DataFrame with two columns: "write" and "read" which contain corresponding data series.
        3. If set to "polars":
            A polars DataFrame with the same columns as in a pandas DataFrame.
    :raises RuntimeError: If context written into context storage does not match read context.
    """
    context_storage.clear()

    write_times: tp.List[float] = []
    read_times: tp.List[tp.Dict[int, float]] = []
    update_times: tp.List[tp.Dict[int, float]] = []

    if context_updater is not None:
        updated_contexts = [context]

        while updated_contexts[-1] is not None:
            updated_contexts.append(context_updater(deepcopy(updated_contexts[-1])))

    for _ in tqdm(range(context_num), desc=f"Benchmarking context storage:{context_storage.full_path}"):
        ctx_id = uuid4()

        # write operation benchmark
        write_start = perf_counter()
        context_storage[ctx_id] = context
        write_times.append(perf_counter() - write_start)

        read_times.append({})

        # read operation benchmark
        read_start = perf_counter()
        actual_context = context_storage[ctx_id]
        read_time = perf_counter() - read_start
        read_times[-1][len(context.labels)] = read_time

        # check returned context
        # if actual_context != context:
        #     raise RuntimeError(f"True context:\n{context}\nActual context:\n{actual_context}")

        if context_updater is not None:
            update_times.append({})

            for updated_context in updated_contexts[1:-1]:
                update_start = perf_counter()
                context_storage[ctx_id] = updated_context
                update_time = perf_counter() - update_start
                update_times[-1][len(updated_context.labels)] = update_time

                read_start = perf_counter()
                actual_context = context_storage[ctx_id]
                read_time = perf_counter() - read_start
                read_times[-1][len(updated_context.labels)] = read_time

    context_storage.clear()
    return write_times, read_times, update_times


def report(
    *context_storages: DBContextStorage,
    context_num: int = 1000,
    dialog_len: int = 300,
    message_dimensions: tp.Tuple[int, ...] = (10, 10),
    misc_dimensions: tp.Tuple[int, ...] = (10, 10),
    pdf: tp.Optional[str] = None,
):
    """
    Benchmark context storage(s) and generate a report.

    :param context_storages: Context storages to benchmark.
    :param context_num: Number of times a single context should be written to/read from context storage.
    :param dialog_len:
        A number of turns inside a single context. The context will contain simple text requests/responses.
    :param message_dimensions:
    :param misc_dimensions:
    :param pdf:
        A pdf file name to save report to.
        Defaults to None.
        If set to None, prints the result to stdout instead of creating a pdf file.
    """
    context = get_context(dialog_len, message_dimensions, misc_dimensions)
    context_size = asizeof.asizeof(context)
    misc_size = asizeof.asizeof(get_dict(misc_dimensions))
    message_size = asizeof.asizeof(get_message(message_dimensions))

    benchmark_config = (
        f"Number of contexts: {context_num}\n"
        f"Dialog len: {dialog_len}\n"
        f"Message misc dimensions: {message_dimensions}\n"
        f"Misc dimensions: {misc_dimensions}\n"
        f"Size of misc field: {misc_size} ({naturalsize(misc_size, gnu=True)})\n"
        f"Size of one message: {message_size} ({naturalsize(message_size, gnu=True)})\n"
        f"Size of one context: {context_size} ({naturalsize(context_size, gnu=True)})"
    )

    print(f"Starting benchmarking with following parameters:\n{benchmark_config}")

    benchmarking_results: tp.Dict[str, tp.Union[tp.Tuple[tp.List[float], tp.List[float]], str]] = {}

    for context_storage in context_storages:
        try:
            # todo: update report method
            write, read = time_context_read_write(context_storage, context, context_num)

            benchmarking_results[context_storage.full_path] = write, read
        except Exception as e:
            benchmarking_results[context_storage.full_path] = getattr(e, "message", repr(e))

    # define functions for displaying results
    line_separator = "-" * 80

    pretty_config = f"{line_separator}\nDB benchmark\n{line_separator}\n{benchmark_config}\n{line_separator}"

    def pretty_benchmark_result(storage_name, benchmarking_result) -> str:
        result = f"{storage_name}\n{line_separator}\n"
        if not isinstance(benchmarking_result, str):
            write, read = benchmarking_result
            result += (
                f"Average write time: {sum(write) / len(write)} s\n"
                f"Average read time: {sum(read) / len(read)} s\n{line_separator}"
            )
        else:
            result += f"{benchmarking_result}\n{line_separator}"
        return result

    def get_scores_and_leaderboard(
        sort_by: tp.Literal["Write", "Read"]
    ) -> tp.Tuple[tp.List[tp.Tuple[str, tp.Optional[float]]], str]:
        benchmark_index = 0 if sort_by == "Write" else 1

        scores = sorted(
            [
                (storage_name, sum(result[benchmark_index]) / len(result[benchmark_index]))
                for storage_name, result in benchmarking_results.items()
                if not isinstance(result, str)
            ],
            key=lambda benchmark: benchmark[1],  # sort in ascending order
        )
        scores += [
            (storage_name, None) for storage_name, result in benchmarking_results.items() if isinstance(result, str)
        ]
        leaderboard = (
            f"{sort_by} time leaderboard\n{line_separator}\n"
            + "\n".join(
                [f"{result}{' s' if result is not None else ''}: {storage_name}" for storage_name, result in scores]
            )
            + "\n"
            + line_separator
        )

        return scores, leaderboard

    _, write_leaderboard = get_scores_and_leaderboard("Write")
    _, read_leaderboard = get_scores_and_leaderboard("Read")

    if pdf is None:
        result = pretty_config

        for storage_name, benchmarking_result in benchmarking_results.items():
            result += f"\n{pretty_benchmark_result(storage_name, benchmarking_result)}"

        if len(context_storages) > 1:
            result += f"\n{write_leaderboard}\n{read_leaderboard}"

        print(result)
    else:
        if matplotlib is None:
            raise RuntimeError("`matplotlib` is required to generate pdf reports.")

        figure_size = (11, 8)

        def text_page(text, *, x=0.5, y=0.5, size=18, ha="center", family="monospace", **kwargs):
            page = plt.figure(figsize=figure_size)
            page.clf()
            page.text(x, y, text, transform=page.transFigure, size=size, ha=ha, family=family, **kwargs)

        def scatter_page(storage_name, write, read):
            plt.figure(figsize=figure_size)
            plt.scatter(range(len(write)), write, label="write times")
            plt.scatter(range(len(read)), read, label="read times")
            plt.legend(loc="best")
            plt.grid(True)
            plt.title(storage_name)

        with PdfPages(pdf) as mpl_pdf:
            text_page(pretty_config, size=24)
            mpl_pdf.savefig()
            plt.close()

            if len(context_storages) > 1:
                text_page(write_leaderboard, x=0.05, size=14, ha="left")
                mpl_pdf.savefig()
                plt.close()
                text_page(read_leaderboard, x=0.05, size=14, ha="left")
                mpl_pdf.savefig()
                plt.close()

            for storage_name, benchmarking_result in benchmarking_results.items():
                txt = pretty_benchmark_result(storage_name, benchmarking_result)

                if not isinstance(benchmarking_result, str):
                    write, read = benchmarking_result

                    text_page(txt)
                    mpl_pdf.savefig()
                    plt.close()

                    scatter_page(storage_name, write, read)
                    mpl_pdf.savefig()
                    plt.close()
                else:
                    text_page(txt)
                    mpl_pdf.savefig()
                    plt.close()


class DBFactory(BaseModel):
    uri: str
    factory_module: str = "dff.context_storages"
    factory: str = "context_storage_factory"

    def db(self):
        module = importlib.import_module(self.factory_module)
        return getattr(module, self.factory)(self.uri)


class BenchmarkCase(BaseModel):
    name: str
    db_factory: DBFactory
    uuid: str = Field(default_factory=lambda: str(uuid4()))
    description: str = ""
    context_num: int = 100
    from_dialog_len: int = 300
    to_dialog_len: int = 311
    step_dialog_len: int = 1
    message_dimensions: tp.Tuple[int, ...] = (10, 10)
    misc_dimensions: tp.Tuple[int, ...] = (10, 10)

    def get_context_updater(self):
        def _context_updater(context: Context):
            start_len = len(context.requests)
            if start_len + self.step_dialog_len < self.to_dialog_len:
                for i in range(start_len, start_len + self.step_dialog_len):
                    context.add_label((f"flow_{i}", f"node_{i}"))
                    context.add_request(get_message(self.message_dimensions))
                    context.add_response(get_message(self.message_dimensions))
                return context
            else:
                return None

        return _context_updater

    def sizes(self):
        return {
            "starting_context_size": asizeof.asizeof(
                get_context(self.from_dialog_len, self.message_dimensions, self.misc_dimensions)
            ),
            "final_context_size": asizeof.asizeof(
                get_context(self.to_dialog_len, self.message_dimensions, self.misc_dimensions)
            ),
            "misc_size": asizeof.asizeof(get_dict(self.misc_dimensions)),
            "message_size": asizeof.asizeof(get_message(self.message_dimensions)),
        }

    @staticmethod
    def set_average_results(benchmark):
        if not benchmark["success"] or isinstance(benchmark["result"], str):
            return

        def get_complex_stats(results):
            average_grouped_by_context_num = [mean(times.values()) for times in results]
            average_grouped_by_dialog_len = {
                key: mean([times[key] for times in results]) for key in next(iter(results), {}).keys()
            }
            average = mean(average_grouped_by_context_num)
            return average_grouped_by_context_num, average_grouped_by_dialog_len, average

        read_stats = get_complex_stats(benchmark["result"]["read_times"])
        update_stats = get_complex_stats(benchmark["result"]["update_times"])

        result = {
            "average_write_time": mean(benchmark["result"]["write_times"]),
            "average_read_time": read_stats[2],
            "average_update_time": update_stats[2],
            "write_times": benchmark["result"]["write_times"],
            "read_times_grouped_by_context_num": read_stats[0],
            "read_times_grouped_by_dialog_len": read_stats[1],
            "update_times_grouped_by_context_num": update_stats[0],
            "update_times_grouped_by_dialog_len": update_stats[1],
        }
        result["pretty_write"] = float(f'{result["average_write_time"]:.3}')
        result["pretty_read"] = float(f'{result["average_read_time"]:.3}')
        result["pretty_update"] = float(f'{result["average_update_time"]:.3}')
        result["pretty_read+update"] = float(f'{result["average_read_time"] + result["average_update_time"]:.3}')

        benchmark["average_results"] = result

    def _run(self):
        try:
            write_times, read_times, update_times = time_context_read_write(
                self.db_factory.db(),
                get_context(self.from_dialog_len, self.message_dimensions, self.misc_dimensions),
                self.context_num,
                context_updater=self.get_context_updater()
            )
            return {
                "success": True,
                "result": {
                    "write_times": write_times,
                    "read_times": read_times,
                    "update_times": update_times,
                }
            }
        except Exception as e:
            exception_message = getattr(e, "message", repr(e))
            print(exception_message)
            return {
                "success": False,
                "result": exception_message,
            }

    def run(self):
        benchmark = self._run()
        BenchmarkCase.set_average_results(benchmark)
        return benchmark


def save_results_to_file(
    benchmark_cases: tp.List[BenchmarkCase],
    file: tp.Union[str, pathlib.Path],
    name: str,
    description: str,
    exist_ok: bool = False,
):
    with open(file, "w" if exist_ok else "x", encoding="utf-8") as fd:
        uuid = str(uuid4())
        result: tp.Dict[str, tp.Any] = {
            "name": name,
            "description": description,
            "uuid": uuid,
            "benchmarks": {},
        }
        for case in benchmark_cases:
            result["benchmarks"][case.uuid] = {**case.dict(), **case.sizes(), **case.run()}

        json.dump(result, fd)


def get_cases(
    db_uris: tp.Dict[str, str],
    case_name_postfix: str = "",
    context_num: int = 100,
    from_dialog_len: int = 300,
    to_dialog_len: int = 311,
    step_dialog_len: int = 1,
    message_dimensions: tp.Tuple[int, ...] = (10, 10),
    misc_dimensions: tp.Tuple[int, ...] = (10, 10),
    description: str = "",
):
    benchmark_cases = []
    for db, uri in db_uris.items():
        benchmark_cases.append(
            BenchmarkCase(
                name=db + "-dev" + case_name_postfix,
                db_factory=DBFactory(uri=uri, factory_module="dff.context_storages_old"),
                context_num=context_num,
                from_dialog_len=from_dialog_len,
                to_dialog_len=to_dialog_len,
                step_dialog_len=step_dialog_len,
                message_dimensions=message_dimensions,
                misc_dimensions=misc_dimensions,
                description=description,
            )
        )
        benchmark_cases.append(
            BenchmarkCase(
                name=db + "-partial" + case_name_postfix,
                db_factory=DBFactory(uri=uri),
                context_num=context_num,
                from_dialog_len=from_dialog_len,
                to_dialog_len=to_dialog_len,
                step_dialog_len=step_dialog_len,
                message_dimensions=message_dimensions,
                misc_dimensions=misc_dimensions,
                description=description,
            )
        )
    return benchmark_cases


def benchmark_all(
    file: tp.Union[str, pathlib.Path],
    name: str,
    description: str,
    db_uris: tp.Dict[str, str],
    case_name_postfix: str = "",
    context_num: int = 100,
    from_dialog_len: int = 300,
    to_dialog_len: int = 311,
    step_dialog_len: int = 1,
    message_dimensions: tp.Tuple[int, ...] = (10, 10),
    misc_dimensions: tp.Tuple[int, ...] = (10, 10),
    exist_ok: bool = False,
):
    save_results_to_file(
        get_cases(
            db_uris,
            case_name_postfix,
            context_num,
            from_dialog_len,
            to_dialog_len,
            step_dialog_len,
            message_dimensions,
            misc_dimensions,
            description=description,
        ),
        file,
        name,
        description,
        exist_ok=exist_ok
    )