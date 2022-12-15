import re
from dff.core.engine.core.keywords import GLOBAL
from dff.core.engine.core.keywords import TRANSITIONS
from dff.core.engine.core.keywords import RESPONSE
import dff.core.engine.conditions as cnd
import dff.core.engine.labels as lbl
from dff.core.pipeline import Pipeline
toy_script = {
    GLOBAL: {
        TRANSITIONS: {
            ('greeting_flow', 'node1', 1.1): cnd.regexp('\\b(hi|hello)\\b', re.I),
            ('music_flow', 'node1', 1.1): cnd.regexp('talk about music'),
            lbl.to_fallback(0.1): cnd.true(),
            lbl.forward(): cnd.all([cnd.regexp('next\\b'), cnd.has_last_labels(labels=[('music_flow', i) for i in ['node2', 'node3']])]),
            lbl.repeat(0.2): cnd.all([cnd.regexp('repeat', re.I), cnd.negation(cnd.has_last_labels(flow_labels=['global_flow']))]),
        },
    },
    'global_flow': {
        'start_node': {
            RESPONSE: '',
        },
        'fallback_node': {
            RESPONSE: 'Ooops',
            TRANSITIONS: {
                lbl.previous(): cnd.regexp('previous', re.I),
            },
        },
    },
    'greeting_flow': {
        'node1': {
            RESPONSE: 'Hi, how are you?',
            TRANSITIONS: {
                'node2': cnd.regexp('how are you'),
            },
        },
        'node2': {
            RESPONSE: 'Good. What do you want to talk about?',
            TRANSITIONS: {
                lbl.forward(0.5): cnd.regexp('talk about'),
                lbl.previous(): cnd.regexp('previous', re.I),
            },
        },
        'node3': {
            RESPONSE: 'Sorry, I can not talk about that now.',
            TRANSITIONS: {
                lbl.forward(): cnd.regexp('bye'),
            },
        },
        'node4': {
            RESPONSE: 'bye',
        },
    },
    'music_flow': {
        'node1': {
            RESPONSE: 'I love `System of a Down` group, would you like to tell about it? ',
            TRANSITIONS: {
                lbl.forward(): cnd.regexp('yes|yep|ok', re.I),
            },
        },
        'node2': {
            RESPONSE: 'System of a Downis an Armenian-American heavy metal band formed in in 1994.',
        },
        'node3': {
            RESPONSE: 'The band achieved commercial success with the release of five studio albums.',
            TRANSITIONS: {
                lbl.backward(): cnd.regexp('back', re.I),
            },
        },
        'node4': {
            RESPONSE: "That's all what I know",
            TRANSITIONS: {
                ('greeting_flow', 'node4'): cnd.regexp('next time', re.I),
                ('greeting_flow', 'node2'): cnd.regexp('next', re.I),
            },
        },
    },
}
pipeline = Pipeline.from_script(toy_script, start_label=('global_flow', 'start_node'), fallback_label=('global_flow', 'fallback_node'))
