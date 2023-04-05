from flows.start import flow
from dff.pipeline import Pipeline

start_label = ('start_flow', 'start_node')

pipeline = Pipeline.from_script(script={
    'start_flow': flow,
}, start_label=start_label)
