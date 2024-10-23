from docs.source.utils.generate_tutorials import generate_tutorial_links_for_notebook_creation
from docs.source.utils.link_misc_files import link_misc_files
from docs.source.utils.regenerate_apiref import regenerate_apiref


def setup(configs: dict):
    link_misc_files(
        [
            "utils/db_benchmark/benchmark_schema.json",
            "utils/db_benchmark/benchmark_streamlit.py",
        ],
        configs=configs,
    )
    generate_tutorial_links_for_notebook_creation(
        [
            ("tutorials.context_storages", "Context Storages"),
            (
                "tutorials.messengers",
                "Interfaces",
                [
                    ("telegram", "Telegram"),
                    ("web_api_interface", "Web API"),
                ],
            ),
            ("tutorials.pipeline", "Pipeline"),
            (
                "tutorials.script",
                "Script",
                [
                    ("core", "Core"),
                    ("responses", "Responses"),
                ],
            ),
            ("tutorials.slots", "Slots"),
            ("tutorials.utils", "Utils"),
            ("tutorials.stats", "Stats"),
        ],
        configs=configs,
    )
    regenerate_apiref(
        [
            ("chatsky.context_storages", "Context Storages"),
            ("chatsky.messengers", "Messenger Interfaces"),
            ("chatsky.pipeline", "Pipeline"),
            ("chatsky.script", "Script"),
            ("chatsky.slots", "Slots"),
            ("chatsky.stats", "Stats"),
            ("chatsky.utils.testing", "Testing Utils"),
            ("chatsky.utils.turn_caching", "Caching"),
            ("chatsky.utils.db_benchmark", "DB Benchmark"),
            ("chatsky.utils.devel", "Development Utils"),
        ],
        configs=configs,
    )
