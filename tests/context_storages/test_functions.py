from dff.context_storages import DBContextStorage
from dff.context_storages.context_schema import SchemaFieldWritePolicy
from dff.pipeline import Pipeline
from dff.script import Context, Message
from dff.utils.testing import TOY_SCRIPT_ARGS, HAPPY_PATH, check_happy_path


def basic_test(db: DBContextStorage, testing_context: Context, context_id: str):
    assert len(db) == 0
    assert testing_context.storage_key == None

    # Test write operations
    db[context_id] = Context()
    assert context_id in db
    assert len(db) == 1
    db[context_id] = testing_context  # overwriting a key
    assert len(db) == 1

    # Test read operations
    new_ctx = db[context_id]
    assert isinstance(new_ctx, Context)
    assert new_ctx.dict() == testing_context.dict()

    if not isinstance(db, dict):
        assert testing_context.storage_key == new_ctx.storage_key == context_id

    # Test delete operations
    del db[context_id]
    assert context_id not in db

    # Test `get` method
    assert db.get(context_id) is None
    pipeline = Pipeline.from_script(*TOY_SCRIPT_ARGS, context_storage=db)
    check_happy_path(pipeline, happy_path=HAPPY_PATH)


def partial_storage_test(db: DBContextStorage, testing_context: Context, context_id: str):
    # Write and read initial context
    db[context_id] = testing_context
    read_context = db[context_id]
    assert testing_context.dict() == read_context.dict()

    # Remove key
    del db[context_id]

    # Add key to misc and request to requests
    read_context.misc.update(new_key="new_value")
    for i in range(1, 5):
        read_context.add_request(Message(text=f"new message: {i}"))
    write_context = read_context.dict()

    if not isinstance(db, dict):
        for i in sorted(write_context["requests"].keys())[:-3]:
            del write_context["requests"][i]

    # Write and read updated context
    db[context_id] = read_context
    read_context = db[context_id]
    assert write_context == read_context.dict()


def different_policies_test(db: DBContextStorage, testing_context: Context, context_id: str):
    # Setup append policy for misc
    db.context_schema.misc.on_write = SchemaFieldWritePolicy.APPEND
    
    # Setup some data in context misc
    testing_context.misc["OLD_KEY"] = "some old data"
    db[context_id] = testing_context

    # Alter context
    testing_context.misc["OLD_KEY"] = "some new data"
    testing_context.misc["NEW_KEY"] = "some new data"
    db[context_id] = testing_context

    # Check keys updated correctly
    new_context = db[context_id]
    assert new_context.misc["OLD_KEY"] == "some old data"
    assert new_context.misc["NEW_KEY"] == "some new data"

    # Setup append policy for misc
    db.context_schema.misc.on_write = SchemaFieldWritePolicy.HASH_UPDATE

    # Alter context
    testing_context.misc["NEW_KEY"] = "brand new data"
    db[context_id] = testing_context

    # Check keys updated correctly
    new_context = db[context_id]
    assert new_context.misc["NEW_KEY"] == "brand new data"

basic_test.no_dict = False
partial_storage_test.no_dict = False
different_policies_test.no_dict = True
_TEST_FUNCTIONS = [basic_test, partial_storage_test, different_policies_test]


def run_all_functions(db: DBContextStorage, testing_context: Context, context_id: str):
    frozen_ctx = testing_context.dict()
    for test in _TEST_FUNCTIONS:
        if not (bool(test.no_dict) and isinstance(db, dict)):
            db.clear()
            test(db, Context.cast(frozen_ctx), context_id)
