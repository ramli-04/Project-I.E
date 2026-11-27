"""Process-local clock and deterministic model IDs, restored on exit."""
from contextlib import ExitStack, contextmanager
from datetime import timedelta
import random
import uuid
from unittest.mock import patch
from django.apps import apps


class Clock:
    def __init__(self, now):
        self.current = now

    def __call__(self):
        return self.current

    def advance(self, now):
        if now < self.current:
            raise ValueError('The simulation clock cannot move backwards.')
        self.current = now


@contextmanager
def simulation_clock(clock, seed):
    rng = random.Random(seed)
    changed = []
    def identifier():
        return uuid.UUID(int=rng.getrandbits(128), version=4)
    with ExitStack() as stack:
        stack.enter_context(patch('django.utils.timezone.now', clock))
        for model in apps.get_models():
            if model._meta.app_label not in {'api', 'customers'}:
                continue
            for field in model._meta.local_fields:
                default = field.default
                if not callable(default):
                    continue
                captured_now = (getattr(default, '__module__', '') == 'django.utils.timezone'
                                and getattr(default, '__name__', '') == 'now')
                if captured_now or default is uuid.uuid4:
                    # Django caches the callable separately from field.default.
                    previous = field.__dict__.pop('_get_default', None)
                    changed.append((field, default, previous))
                    field.default = clock if captured_now else identifier
        try:
            yield
        finally:
            for field, default, previous in changed:
                field.default = default
                field.__dict__.pop('_get_default', None)
                if previous is not None:
                    field.__dict__['_get_default'] = previous
