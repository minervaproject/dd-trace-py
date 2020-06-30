import datetime
import os
import platform
import sys

import ddtrace
from ddtrace import api, compat, payload
from ddtrace.utils import formats


def ping_agent(api_=None, hostname=None, port=None, uds_path=None):
    # Attempt to query the agent, returns an api.Response
    # or one of the following exceptions: httplib.HTTPException, OSError, IOError

    if not api_:
        api_ = api.API(hostname=hostname, port=port, uds_path=uds_path,)

    # We can't use api.send_traces([]) since it'll shortcut
    # if traces is falsy.
    p = payload.Payload(encoder=api_._encoder)

    # We can't use payload.add_trace([]) for the same reason
    # as api.send_trace([]).
    encoded = p.encoder.encode_trace([])
    p.traces.append(encoded)
    p.size += len(encoded)

    resp = api_._flush(p)

    return resp


def tags_to_str(tags):
    # Turn a dict of tags to a string "k1:v1,k2:v2,..."
    return ",".join(["%s:%s" % (k, v) for k, v in tags.items()])


def flare(tracer):
    """Collect system and library information
    """

    # The tracer doesn't actually maintain a hostname/port, instead it stores
    # it on the possibly None writer which actually stores it on an API object.
    if tracer.writer:
        hostname = tracer.writer.api.hostname
        port = tracer.writer.api.port
        uds_path = tracer.writer.api.uds_path

        # If all specified, uds_path will take precedence
        if uds_path:
            agent_url = uds_path
        else:
            agent_url = "%s:%s" % (hostname, port)
    else:
        # Else if we can't infer anything from the tracer, rely on the defaults.
        hostname = Tracer.DEFAULT_HOSTNAME
        port = Tracer.DEFAULT_PORT
        agent_url = "%s:%s" % (hostname, port)

    resp = ping_agent(hostname=hostname, port=port, uds_path=uds_path)

    if isinstance(resp, api.Response):
        if resp.code == 200:
            agent_error = None
        else:
            agent_error = "HTTP code %s, reason %s, message %s" % (resp.status, resp.reason, resp.msg)
    else:
        # There was an exception
        agent_error = "Exception raised: %s" % str(resp)

    return dict(
        # Timestamp UTC ISO 8601
        date=datetime.datetime.utcnow().isoformat(),
        # eg. 'Linux', 'Darwin'
        os_name=platform.system(),
        # eg. 12.5.0
        os_version=platform.release(),
        is_64_bit=sys.maxsize > 2 ** 32,
        architecture=platform.architecture()[0],
        vm=platform.python_implementation(),
        version=ddtrace.__version__,
        lang="python",
        lang_version=platform.python_version(),
        env=ddtrace.config.env,
        enabled=os.getenv("DATADOG_TRACE_ENABLED"),
        service=ddtrace.config.service,
        debug=os.getenv("DATADOG_TRACE_DEBUG"),
        enabled_cli="ddtrace" in os.getenv("PYTHONPATH", ""),
        agent_url=agent_url,
        analytics_enabled=ddtrace.config.analytics_enabled,
        logs_correlation_enabled=ddtrace.config.logs_injection,
        health_metrics_enabled=ddtrace.config.health_metrics_enabled,
        agent_error=agent_error,
        global_tags=os.getenv("DD_TAGS", ""),
        tracer_tags=tags_to_str(tracer.tags),
        profiling_enabled=None,  # TODO
        integrations=None,  # TODO
        integrations_loaded=None,  # TODO
    )
