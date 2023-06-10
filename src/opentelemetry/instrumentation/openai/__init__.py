# Copyright your mom
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
OpenTelemetry instrumentation for OpenAI's client library.

Usage
-----
Instrument all OpenAI client calls:

.. code-block:: python

    import openai
    from opentelemetry.instrumentation.openai import OpenAIInstrumentation

    # Enable instrumentation
    OpenAIInstrumentation().instrument()

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "tell me a joke about opentelemetry"}],
    )
"""
import math
from typing import Collection

import wrapt
import openai

from opentelemetry import context as context_api
from opentelemetry.trace import get_tracer, Tracer

from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.utils import (
    _SUPPRESS_INSTRUMENTATION_KEY,
    unwrap,
)
from opentelemetry.instrumentation.openai.package import _instruments
from opentelemetry.instrumentation.openai.version import __version__


def _instrument_chat(tracer: Tracer):
    def _instrumented_create(wrapped, instance, args, kwargs):
        if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
            return

        name = "openai.chat"
        with tracer.start_as_current_span(name) as span:
            span.set_attribute(f"{name}.model", kwargs["model"])
            span.set_attribute(f"{name}.temperature", kwargs["temperature"] if "temperature" in kwargs else 1.0)
            span.set_attribute(f"{name}.top_p", kwargs["top_p"] if "top_p" in kwargs else 1.0)
            span.set_attribute(f"{name}.n", kwargs["n"] if "n" in kwargs else 1)
            span.set_attribute(f"{name}.stream", kwargs["stream"] if "stream" in kwargs else False)
            span.set_attribute(f"{name}.stop", kwargs["stop"] if "stop" in kwargs else "")
            span.set_attribute(f"{name}.max_tokens", kwargs["max_tokens"] if "max_tokens" in kwargs else math.inf)
            span.set_attribute(f"{name}.presence_penalty", kwargs["presence_penalty"] if "presence_penalty" in kwargs else 0.0)
            span.set_attribute(f"{name}.frequency_penalty", kwargs["frequency_penalty"] if "frequency_penalty" in kwargs else 0.0)
            span.set_attribute(f"{name}.logit_bias", kwargs["logit_bias"] if "logit_bias" in kwargs else "")
            span.set_attribute(f"{name}.name", kwargs["name"] if "name" in kwargs else "")

            # "messages": [{"role": "user", "content": "Hello!"}]
            # role can be user, system, or assistant
            # capture the messages as an attribute
            messages = kwargs["messages"]
            messages_str = ""
            for message in messages:
                messages_str += f"{message['role']}: {message['content']}\n"

            span.set_attribute(f"{name}.messages", messages_str)

            response = wrapped(*args, **kwargs)

            span.set_attribute(f"{name}.response.id", response["id"])
            span.set_attribute(f"{name}.response.object", response["object"])
            span.set_attribute(f"{name}.response.created", response["created"])
            for index, choice in enumerate(response["choices"]):
                span.set_attribute(f"{name}.response.choices.{index}.message.role", choice["message"]["role"])
                span.set_attribute(f"{name}.response.choices.{index}.message.content", choice["message"]["content"])
                span.set_attribute(f"{name}.response.choices.{index}.finish_reason", choice["finish_reason"])

            span.set_attribute(f"{name}.response.usage.prompt_tokens", response["usage"]["prompt_tokens"])
            span.set_attribute(f"{name}.response.usage.completion_tokens", response["usage"]["completion_tokens"])
            span.set_attribute(f"{name}.response.usage.total_tokens", response["usage"]["total_tokens"])


        return response

    wrapt.wrap_function_wrapper(openai.ChatCompletion, "create", _instrumented_create)


def _uninstrument():
    unwrap(openai.ChatCompletion, "create")


class OpenAIInstrumentor(BaseInstrumentor):
    """An instrumenter for OpenAI's client library."""

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs):
        tracer_provider = kwargs.get("tracer_provider")
        tracer = get_tracer(__name__, __version__, tracer_provider)
        _instrument_chat(tracer)

    def _uninstrument(self, **kwargs):
        _uninstrument()